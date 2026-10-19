# pythonchat

一次性大模型对话程序。读取 `config.ini` 中的 LLM 配置，接收用户提示词，先输出 `---` 分隔线，再以**流式**逐字打印模型回答，输出完毕程序结束。

## 文件清单

| 文件 | 说明 |
| --- | --- |
| `pythonchat.py` | 主程序 |
| `config.ini` | LLM 配置：`base_url`、`model_name`、`api_key` |

## 安装依赖

```bash
pip install openai
```

## 运行步骤

1. 打开 `config.ini`，把 `api_key` 换成你自己的密钥（`base_url`、`model_name` 按需修改）
2. 在本目录执行：

```bash
python pythonchat.py
```

3. 按提示输入问题并回车，即可看到模型回答
