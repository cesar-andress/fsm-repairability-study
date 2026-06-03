#!/usr/bin/env python3
"""Minimal Ollama HTTP client (stdlib only, local inference)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 300.0


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def health_check(config: OllamaConfig | None = None) -> bool:
    """Return True if Ollama responds at the configured base URL."""
    config = config or OllamaConfig()
    url = f"{config.base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def generate(
    model: str,
    prompt: str,
    *,
    config: OllamaConfig | None = None,
    options: dict[str, Any] | None = None,
    stream: bool = False,
) -> str:
    """
    Call Ollama /api/generate and return the full response text.

    Raises RuntimeError on connection or API errors.
    """
    if stream:
        raise NotImplementedError("streaming is not used in this artifact")
    config = config or OllamaConfig()
    url = f"{config.base_url.rstrip('/')}/api/generate"
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if options:
        payload["options"] = options
    try:
        result = _post_json(url, payload, config.timeout_seconds)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc
    response = result.get("response")
    if not isinstance(response, str):
        raise RuntimeError(f"unexpected Ollama response shape: {result!r}")
    return response


def list_models(config: OllamaConfig | None = None) -> list[str]:
    """Return model names reported by Ollama /api/tags."""
    config = config or OllamaConfig()
    url = f"{config.base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"cannot list Ollama models: {exc}") from exc
    models = []
    for entry in body.get("models", []):
        name = entry.get("name")
        if name:
            models.append(name)
    return models
