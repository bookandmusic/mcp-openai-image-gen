# openai-image-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python >=3.11](https://img.shields.io/badge/python-≥3.11-blue.svg)](https://www.python.org/)

MCP server exposing multi-backend image generation as separate tools, built on [FastMCP](https://github.com/jlowin/fastmcp). Each configured backend (e.g. `sensenova`, `modelscope`) is exposed as its own MCP tool with its own model aliases, supported sizes, and descriptions. Works with opencode, Claude Code, Cursor, and other MCP clients.

---

## Quick start

```bash
uvx --from git+https://github.com/bookandmusic/openai-image-mcp.git openai-image-mcp
```

The first run downloads dependencies and creates an isolated virtual environment. The server auto-creates `~/.config/openai-image-mcp/` and writes an example `config.yaml`, then exits. Edit the config and restart.

---

## Tools

| Tool | Description |
|---|---|
| `list_models` | List all configured backends, tool names, and available models |
| `sensenova_generate_image` | Sensenova u1-fast 2K synchronous image generation (11 aspect ratios) |
| `modelscope_generate_image` | ModelScope async image generation / editing (Qwen-Image series) |

Tools are dynamically registered from `config.yaml` — each backend corresponds to one MCP tool, with configurable tool names, model lists, and supported sizes.

---

## Configuration

openai-image-mcp uses a YAML configuration file. The server resolves its config directory in this order:

1. `--config-dir <path>` (or `--config-dir=<path>`) on the command line
2. `$OPENAI_IMAGE_MCP_CONFIG_DIR` environment variable
3. `$XDG_CONFIG_HOME/openai-image-mcp` (falls back to `~/.config/openai-image-mcp`)

The directory is auto-created on startup if missing — no manual `mkdir` needed.

On first run, if the config is missing, the server writes an example `config.yaml` and exits. Edit it and restart.

### Config example

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
        Sensenova u1-fast image generation (2K, sync mode).
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
        ModelScope async image generation.
    models:
      qwen-image-2512: Qwen/Qwen-Image-2512
      qwen-image-edit-2511: Qwen/Qwen-Image-Edit-2511
```

Each backend's parameters (`prompt`, `size`, `n`, `image`, `save_path`) are defined in the `parameters` block. The `size` field supports an `enum` constraint with `value` (WxH) and `ratio` annotations.

API keys use `env:VAR_NAME` to reference environment variables. For local development, put them in a `.env` file:

```env
SENSENOVA_API_KEY=sk-...
MODELSCOPE_API_KEY=ms-...
```

---

## Client configuration

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

Add to `~/.claude/settings.json`:

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

Or in a project-level `.claude/settings.local.json`.

---

## Local development

```bash
git clone https://github.com/bookandmusic/openai-image-mcp.git
cd openai-image-mcp
uv sync
uv run python -m openai_image_mcp.server
```

Or install as a local command:

```bash
uv tool install .
openai-image-mcp
```

---

## License

MIT — see [LICENSE](./LICENSE).