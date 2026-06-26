import base64
import json
import os
import time
from dataclasses import dataclass
from logging import getLogger
from typing import Any

import requests

from .config import BackendConfig

logger = getLogger(__name__)


@dataclass
class ImageResult:
    url: str | None = None
    b64_json: str | None = None

    def to_bytes(self, timeout: int = 60) -> bytes:
        if self.b64_json:
            return base64.b64decode(self.b64_json)
        if self.url:
            return download_image(self.url, timeout)
        raise ValueError("ImageResult has neither url nor b64_json")


def _parse_item(item: dict) -> ImageResult:
    return ImageResult(url=item.get("url"), b64_json=item.get("b64_json"))


def _build_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _resolve_image(image: str) -> str:
    if image.startswith(("http://", "https://", "data:")):
        return image
    if os.path.isfile(image):
        ext = os.path.splitext(image)[1].lower().lstrip(".")
        mime_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
        mime = mime_map.get(ext, "image/png")
        with open(image, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:{mime};base64,{b64}"
    raise FileNotFoundError(f"Image not found: {image}")


def _build_payload(model_id: str, prompt: str, size: str | None, n: int, image: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": model_id, "prompt": prompt, "n": n}
    if size:
        payload["size"] = size
    if image:
        payload["image_url"] = _resolve_image(image)
    return payload


def _sync_generate(backend: BackendConfig, model_id: str, prompt: str, size: str | None, n: int, image: str | None) -> list[ImageResult]:
    payload = _build_payload(model_id, prompt, size, n, image)
    resp = requests.post(
        f"{backend.base_url}/images/generations",
        headers=_build_headers(backend.api_key),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=backend.timeout.sync_generate,
    )
    resp.raise_for_status()
    data = resp.json()
    return [_parse_item(item) for item in data.get("data", [])]


def _async_generate(backend: BackendConfig, model_id: str, prompt: str, size: str | None, n: int, image: str | None) -> list[ImageResult]:
    payload = _build_payload(model_id, prompt, size, n, image)
    headers = {**_build_headers(backend.api_key), "X-ModelScope-Async-Mode": "true"}
    resp = requests.post(
        f"{backend.base_url}/images/generations",
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=backend.timeout.request,
    )
    resp.raise_for_status()
    task_id = resp.json()["task_id"]
    logger.info("Async task created: %s", task_id)

    deadline = time.time() + backend.timeout.max_wait
    poll_headers = {**_build_headers(backend.api_key), "X-ModelScope-Task-Type": "image_generation"}

    while time.time() < deadline:
        result = requests.get(f"{backend.base_url}/tasks/{task_id}", headers=poll_headers, timeout=backend.timeout.request)
        result.raise_for_status()
        data = result.json()

        if data["task_status"] == "SUCCEED":
            return [ImageResult(url=url) for url in data.get("output_images", [])]
        if data["task_status"] == "FAILED":
            raise RuntimeError(f"Image generation failed: {data}")

        logger.info("Polling task %s status=%s", task_id, data["task_status"])
        time.sleep(backend.timeout.poll_interval)

    raise TimeoutError(f"Task {task_id} timed out after {backend.timeout.max_wait}s")


def generate(
    backend: BackendConfig,
    model_id: str,
    prompt: str,
    size: str | None = None,
    n: int = 1,
    image: str | None = None,
) -> list[ImageResult]:
    fn = _async_generate if backend.async_mode else _sync_generate
    return fn(backend, model_id, prompt, size, n, image)


def download_image(url: str, timeout: int = 60) -> bytes:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content
