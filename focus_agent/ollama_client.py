"""Small dependency-free client for the local Ollama service."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class OllamaStatus:
    online: bool
    models: tuple[str, ...] = ()
    error: str = ""


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: int = 180):
        configured_url = base_url or os.environ.get(
            "FOCUS_BUDDY_OLLAMA_URL",
            "http://127.0.0.1:11434",
        )
        self.base_url = configured_url.rstrip("/")
        self.timeout = timeout

    def status(self) -> OllamaStatus:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            models = tuple(
                item.get("name", "") for item in payload.get("models", [])
                if item.get("name")
            )
            return OllamaStatus(True, models=models)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return OllamaStatus(False, error=str(exc))

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_context: int = 6144,
        timeout_seconds: float | None = None,
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": float(temperature),
                "top_p": 0.85,
                "repeat_penalty": 1.06,
                "num_ctx": int(max_context),
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            timeout = self.timeout if timeout_seconds is None else max(1.0, float(timeout_seconds))
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            if result.get("error"):
                raise RuntimeError(result["error"])
            return result.get("message", {}).get("content", "").strip()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 404:
                raise RuntimeError(f"模型 {model} 尚未下载。") from exc
            raise RuntimeError(f"Ollama返回HTTP {exc.code}：{body}") from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            raise RuntimeError("无法连接本地Ollama。") from exc
