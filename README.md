# openai-image-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python >=3.11](https://img.shields.io/badge/python-≥3.11-blue.svg)](https://www.python.org/)

基于 [FastMCP](https://github.com/jlowin/fastmcp) 的 MCP 服务器，将多个图像生成后端（`sensenova`、`modelscope` 等）分别暴露为独立的 MCP 工具。每个后端的模型别名、支持尺寸、参数描述均在 `config.yaml` 中独立配置。适用于 opencode、Claude Code、Cursor 等 MCP 客户端。

---

## 快速启动

```bash
uvx --from git+https://github.com/bookandmusic/openai-image-mcp.git openai-image-mcp
```

首次运行自动下载依赖并创建隔离虚拟环境。自动创建 `~/.config/openai-image-mcp/` 目录并写入示例 `config.yaml`，编辑后重启使用。

---

## 工具列表

| 工具名 | 说明 |
|---|---|
| `list_models` | 列出所有配置的后端、工具名和可用模型 |
| `sensenova_generate_image` | Sensenova u1-fast 2K 同步文生图（11 种宽高比） |
| `modelscope_generate_image` | ModelScope 异步文生图 / 图编辑（Qwen-Image 系列） |

工具为动态注册：`config.yaml` 中每个 backend 对应一个 MCP 工具，工具名、模型列表、支持尺寸均可自定义。

---

## 配置

openai-image-mcp 使用 YAML 配置文件。服务器按以下顺序查找配置目录：

1. 命令行 `--config-dir <path>`（或 `--config-dir=<path>`）
2. 环境变量 `$OPENAI_IMAGE_MCP_CONFIG_DIR`
3. `$XDG_CONFIG_HOME/openai-image-mcp`（回退到 `~/.config/openai-image-mcp`）

配置目录不存在时自动创建，无需手动 `mkdir`。

首次启动时，若配置文件不存在，服务器写入示例 `config.yaml` 并退出，编辑后重启使用。

### 配置示例

```yaml
backends:
  sensenova:
    base_url: https://token.sensenova.cn/v1
    api_key: env:SENSENOVA_API_KEY
    async: false
    timeout:
      sync_generate: 600
    tool:
      name: sensenova_generate_image
      description: |
        Sensenova u1-fast 图像生成（2K 分辨率，同步模式）。
    models:
      u1-fast: sensenova-u1-fast

  modelscope:
    base_url: https://api-inference.modelscope.cn/v1
    api_key: env:MODELSCOPE_API_KEY
    async: true
    timeout:
      request: 30
      poll_interval: 5
      max_wait: 600
    tool:
      name: modelscope_generate_image
      description: |
        ModelScope 异步图像生成。
    models:
      qwen-image-2512: Qwen/Qwen-Image-2512
      qwen-image-edit-2511: Qwen/Qwen-Image-Edit-2511
```

每个后端支持的参数（`prompt`、`size`、`n`、`image`、`save_path`）在 `parameters` 块中按需定义，`size` 支持 `enum` 约束（WxH + 比例标注）。

API 密钥用 `env:VAR_NAME` 引用环境变量，本地开发可放到 `.env` 文件中：

```env
SENSENOVA_API_KEY=sk-...
MODELSCOPE_API_KEY=ms-...
```

---

## 客户端配置

### opencode

```json
{
  "mcp": {
    "openai-image-mcp": {
      "type": "local",
      "command": [
        "uvx", "--from", "git+https://github.com/bookandmusic/openai-image-mcp.git",
        "openai-image-mcp",
        "--config-dir", "~/.config/openai-image-mcp"
      ],
      "enabled": true,
      "timeout": 600000
    }
  }
}
```

### Claude Code

添加到 `~/.claude/settings.json`：

```json
{
  "mcpServers": {
    "openai-image-mcp": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/bookandmusic/openai-image-mcp.git",
        "openai-image-mcp",
        "--config-dir", "~/.config/openai-image-mcp"
      ]
    }
  }
}
```

也可放在项目级 `.claude/settings.local.json` 中。

---

## 本地开发

```bash
git clone https://github.com/bookandmusic/openai-image-mcp.git
cd openai-image-mcp
uv sync
uv run python -m openai_image_mcp.server
```

或安装为本地命令：

```bash
uv tool install .
openai-image-mcp
```

---

## License

MIT — 详见 [LICENSE](./LICENSE)。