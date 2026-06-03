"""Tests for Ollama client (mocked HTTP)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ollama_client import OllamaConfig, generate, health_check, list_models  # noqa: E402


def test_health_check_ok() -> None:
    payload = json.dumps({"models": []}).encode()

    def fake_urlopen(req, timeout=0):
        class Resp:
            status = 200

            def read(self):
                return payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        return Resp()

    with mock.patch("urllib.request.urlopen", fake_urlopen):
        assert health_check(OllamaConfig()) is True


def test_generate_parses_response() -> None:
    body = json.dumps({"response": '{"id": "x"}'}).encode()

    def fake_urlopen(req, timeout=0):
        class Resp:
            def read(self):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        return Resp()

    with mock.patch("urllib.request.urlopen", fake_urlopen):
        text = generate("test-model", "prompt", config=OllamaConfig())
    assert "id" in text


def test_list_models() -> None:
    payload = json.dumps({"models": [{"name": "llama3:8b"}]}).encode()

    def fake_urlopen(req, timeout=0):
        class Resp:
            def read(self):
                return payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        return Resp()

    with mock.patch("urllib.request.urlopen", fake_urlopen):
        names = list_models(OllamaConfig())
    assert names == ["llama3:8b"]
