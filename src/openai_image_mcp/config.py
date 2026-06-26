import json
import os
import sys
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

EXAMPLE_CONFIG_NAME = "config.example.yaml"
PACKAGE_NAME = "openai_image_mcp"

def default_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "openai-image-mcp"


def resolve_config_path(
    config_dir: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve the config file path.

    Order:
      1. Explicit ``config_dir`` argument (from --config-dir / OPENAI_IMAGE_MCP_CONFIG_DIR)
      2. ``$OPENAI_IMAGE_MCP_CONFIG_DIR`` env var
      3. ``$XDG_CONFIG_HOME/openai-image-mcp`` (or ``~/.config/openai-image-mcp``)
    """
    if config_dir is None:
        config_dir = os.environ.get("OPENAI_IMAGE_MCP_CONFIG_DIR")
    if config_dir is not None:
        return Path(config_dir).expanduser() / "config.yaml"
    return default_config_dir() / "config.yaml"


def write_example_config(target: Path) -> None:
    """Copy the bundled example config to ``target``, creating parent dirs."""
    target.parent.mkdir(parents=True, exist_ok=True)
    example = resources.files(PACKAGE_NAME).joinpath(EXAMPLE_CONFIG_NAME)
    target.write_bytes(example.read_bytes())


@dataclass
class TimeoutConfig:
    request: int = 30
    sync_generate: int = 120
    poll_interval: int = 5
    max_wait: int = 600


@dataclass
class ToolConfig:
    name: str | None = None
    description: str = ""
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class BackendConfig:
    base_url: str
    api_key: str
    async_mode: bool
    models: dict[str, str] = field(default_factory=dict)
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    tool: ToolConfig = field(default_factory=ToolConfig)


def _resolve_env(value: Any) -> Any:
    if not isinstance(value, str) or not value.startswith("env:"):
        return value
    var = value[4:]
    resolved = os.getenv(var)
    if resolved is None:
        raise ValueError(f"Environment variable '{var}' not set (required by config.yaml)")
    return resolved


def load_config(config_path: Path | None = None) -> dict[str, BackendConfig]:
    path = config_path or resolve_config_path()
    config_dir = path.parent
    config_dir.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        write_example_config(path)
        print(
            f"[openai-image-gen] No config found at {path}.",
            file=sys.stderr,
        )
        print(
            f"[openai-image-gen] Wrote example config. Edit it (and set "
            f"SENSENOVA_API_KEY / MODELSCOPE_API_KEY env vars), then restart.",
            file=sys.stderr,
        )
        sys.exit(0)

    with open(path) as f:
        raw = yaml.safe_load(f)

    backends: dict[str, BackendConfig] = {}
    for name, cfg in raw["backends"].items():
        raw_timeout = cfg.get("timeout", {})
        timeout = TimeoutConfig(
            request=raw_timeout.get("request", 30),
            sync_generate=raw_timeout.get("sync_generate", 120),
            poll_interval=raw_timeout.get("poll_interval", 5),
            max_wait=raw_timeout.get("max_wait", 600),
        )
        raw_tool = cfg.get("tool", {})
        tool = ToolConfig(
            name=raw_tool.get("name"),
            description=raw_tool.get("description", ""),
            parameters=raw_tool.get("parameters", {}),
        )
        backends[name] = BackendConfig(
            base_url=cfg["base_url"],
            api_key=_resolve_env(cfg["api_key"]),
            async_mode=cfg.get("async", False),
            models=cfg["models"],
            timeout=timeout,
            tool=tool,
        )
    return backends
