import os
import sys
from logging import INFO, basicConfig, getLogger
from pathlib import Path

# Must run before importing .config or .client: extracts --config-dir from argv
# and propagates it via the OPENAI_IMAGE_MCP_CONFIG_DIR env var so load_config()
# at module level resolves the correct path. Also strips the flag from sys.argv
# so FastMCP's own argparse does not see it.
def _absorb_config_dir_argv() -> None:
    argv = sys.argv
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--config-dir" and i + 1 < len(argv):
            os.environ["OPENAI_IMAGE_MCP_CONFIG_DIR"] = argv[i + 1]
            del argv[i :i + 2]
            return
        if a.startswith("--config-dir="):
            os.environ["OPENAI_IMAGE_MCP_CONFIG_DIR"] = a.split("=", 1)[1]
            del argv[i]
            return
        i += 1


_absorb_config_dir_argv()

from dotenv import load_dotenv  # noqa: E402
from fastmcp import FastMCP  # noqa: E402
from pydantic import Field  # noqa: E402

from .client import download_image, generate  # noqa: E402
from .config import BackendConfig, load_config, resolve_config_path  # noqa: E402

basicConfig(level=INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = getLogger(__name__)

load_dotenv(resolve_config_path().parent / ".env")
backends = load_config()
mcp = FastMCP(name="OpenAI Image Gen MCP")


@mcp.tool
def list_models() -> str:
    """List all configured image generation tools (one per backend) and their supported models."""
    lines = []
    for backend_name, cfg in backends.items():
        tool_name = cfg.tool.name or f"{backend_name}_generate_image"
        lines.append(f"## {tool_name}")
        for alias, model_id in cfg.models.items():
            async_label = " [async]" if cfg.async_mode else ""
            lines.append(f"  - `{alias}` → {model_id}{async_label}")
    return "\n".join(lines)


def _make_tool(backend_name: str, cfg: BackendConfig):
    """Build an MCP tool function bound to a single backend's config and tool metadata."""
    tool_params = cfg.tool.parameters
    model_aliases = list(cfg.models.keys())

    size_cfg = tool_params.get("size", {})
    size_enum = size_cfg.get("enum", [])
    size_default = size_cfg.get("default")
    size_desc = size_cfg.get("description", f"Image size WxH. Default: {size_default}")
    if size_enum:
        sizes_str = ", ".join(
            f"{e['value']} ({e.get('ratio', '?')})" for e in size_enum
        )
        size_desc = f"{size_desc} Valid: {sizes_str}."

    n_cfg = tool_params.get("n", {})
    n_default = n_cfg.get("default", 1)
    n_min = n_cfg.get("minimum", 1)
    n_max = n_cfg.get("maximum", 4)
    n_desc = n_cfg.get(
        "description", f"Number of images to generate ({n_min}-{n_max})"
    )

    prompt_desc = tool_params.get("prompt", {}).get(
        "description", "Image description text"
    )

    image_desc = tool_params.get("image", {}).get(
        "description", "Reference image URL / data URI / local file path"
    )

    save_path_cfg = tool_params.get("save_path", {})
    save_path_desc = save_path_cfg.get(
        "description",
        "Optional local file path. If provided, the first generated image is "
        "downloaded and saved here. Returns 'Saved: <path>' plus the URL.",
    )

    def generate_image(
        model: str = Field(
            description=(
                f"Model alias. Available for this backend: {', '.join(model_aliases)}"
            ),
        ),
        prompt: str = Field(description=prompt_desc),
        size: str | None = Field(default=size_default, description=size_desc),
        n: int = Field(default=n_default, ge=n_min, le=n_max, description=n_desc),
        image: str | None = Field(
            default=None,
            description=image_desc,
        ),
        save_path: str | None = Field(default=None, description=save_path_desc),
    ) -> str:
        if model not in cfg.models:
            return f"Error: model '{model}' not found. Available: {model_aliases}"

        model_id = cfg.models[model]

        if size is not None and size_enum:
            valid = {e["value"] for e in size_enum}
            if size not in valid:
                return f"Error: invalid size '{size}'. Valid: {sorted(valid)}"

        logger.info(
            "generate_image: backend=%s model=%s size=%s n=%d image=%s save_path=%s",
            backend_name, model, size, n, image is not None, save_path,
        )
        try:
            results = generate(cfg, model_id, prompt, size, n, image)
        except Exception as exc:
            logger.exception("generate_image failed")
            return f"Error: {type(exc).__name__}: {exc}"

        urls = [r.url for r in results if r.url]

        if save_path and results:
            first = results[0]
            try:
                content = first.to_bytes()
                path = Path(save_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                source = "b64_json" if first.b64_json else "url"
                msg = f"Saved: {path.resolve()}\nSource: {source}"
                if first.url:
                    msg += f"\nURL: {first.url}"
                return msg
            except Exception as exc:
                logger.exception("save_path failed")
                source = "b64_json" if first.b64_json else "url"
                url_line = f"\nURL: {first.url}" if first.url else ""
                return (
                    f"Error: failed to save to '{save_path}': "
                    f"{type(exc).__name__}: {exc}\n"
                    f"Source: {source}{url_line}"
                )

        return "\n".join(urls)

    return generate_image


for backend_name, cfg in backends.items():
    fn = _make_tool(backend_name, cfg)
    tool_name = cfg.tool.name or f"{backend_name}_generate_image"
    description = cfg.tool.description or f"Generate images via {backend_name} backend"
    mcp.tool(name=tool_name, description=description)(fn)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
