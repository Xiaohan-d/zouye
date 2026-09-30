"""AnythingLLM MCP Server (MVP) - access the first workspace and answer questions.

MCP protocol version: 2026-07-28 (modern, stateless).
Transport: HTTP (streamable HTTP). stdio is not used.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Annotated

from pydantic import Field

from mcp.server.mcpserver import MCPServer


def _load_dotenv(path: str = ".env") -> None:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("\"'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass


_load_dotenv()

BASE_URL = os.environ.get("ANYTHINGLLM_BASE_URL", "http://localhost:3001").rstrip("/")
API_KEY = os.environ.get("ANYTHINGLLM_API_KEY", "").strip()


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers


def _request(method: str, path: str, body: dict | None = None, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers=_headers(),
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"AnythingLLM API error {e.code}: {e.read().decode('utf-8', 'ignore')}") from e


def first_workspace() -> dict:
    return _request("GET", "/workspaces")["workspaces"][0]


def workspace_documents(slug: str) -> tuple[str, list]:
    ws = _request("GET", f"/workspace/{slug}")["workspace"][0]
    docs = []
    for d in ws.get("documents", []):
        try:
            meta = json.loads(d.get("metadata") or "{}")
        except json.JSONDecodeError:
            meta = {}
        docs.append(
            {
                "title": meta.get("title", d.get("filename")),
                "wordCount": meta.get("wordCount"),
                "tokenEstimate": meta.get("token_count_estimate"),
            }
        )
    return ws.get("name", slug), docs


def file_count(ws_name: str, docs: list) -> str:
    return f"工作区「{ws_name}」共有 {len(docs)} 个文件。"


def chat_workspace(slug: str, message: str) -> tuple[str, list]:
    resp = _request(
        "POST",
        f"/workspace/{slug}/chat",
        {"message": message, "mode": "query"},
        timeout=300,
    )
    sources = [{"title": s.get("title"), "chunk": s.get("text")} for s in resp.get("sources", [])]
    return resp.get("textResponse", ""), sources


mcp = MCPServer(
    "anythingllm-mcp",
    version="1.0.0",
    description="Reads documents of the first AnythingLLM workspace and answers questions about them.",
)


@mcp.tool()
def ask_first_workspace(
    question: Annotated[
        str,
        Field(
            description="The question to answer using documents in the first AnythingLLM workspace. Defaults to asking how many files the workspace contains.",
        ),
    ] = "我的工作区有多少个文件",
) -> dict:
    """Find the first AnythingLLM workspace, extract its document info, and answer the question based on its documents."""
    try:
        ws = first_workspace()
        slug = ws["slug"]
        ws_name, docs = workspace_documents(slug)
        answer, sources = chat_workspace(slug, question)
        return {
            "workspace": ws_name,
            "fileCount": len(docs),
            "fileCountAnswer": file_count(ws_name, docs),
            "documents": docs,
            "answer": answer,
            "sources": sources,
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=os.environ.get("SERVER_HOST", "127.0.0.1"),
        port=int(os.environ.get("SERVER_PORT", "8000")),
        streamable_http_path=os.environ.get("MCP_PATH", "/mcp"),
        stateless_http=True,
    )