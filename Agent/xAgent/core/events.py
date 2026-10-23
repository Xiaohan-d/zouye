from __future__ import annotations

from dataclasses import dataclass


class AgentEvent:
    """Base class for events emitted by ChatAgent."""


@dataclass(frozen=True, slots=True)
class AssistantDelta(AgentEvent):
    text: str


@dataclass(frozen=True, slots=True)
class ToolCallStarted(AgentEvent):
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class ToolCallFinished(AgentEvent):
    name: str
    result: str


@dataclass(frozen=True, slots=True)
class TurnFinished(AgentEvent):
    content: str


@dataclass(frozen=True, slots=True)
class AgentError(AgentEvent):
    message: str
