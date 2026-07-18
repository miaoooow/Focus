"""Optional user-owned cloud AI connections.

No shared API key is embedded in Focus Buddy. On Windows, keys saved from the
local UI are encrypted with DPAPI and can only be decrypted by the same user.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import urllib.error
import urllib.request
from ctypes import wintypes
from pathlib import Path

from .paths import user_data_root


OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_OPENROUTER_MODEL = "openrouter/free"
DEFAULT_GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"

DEFAULT_SETTINGS = {
    "schema_version": 1,
    "text_provider": "local",
    "openrouter_model": DEFAULT_OPENROUTER_MODEL,
    "openrouter_key": "",
    "pet_renderer": "local",
    "gemini_image_model": DEFAULT_GEMINI_IMAGE_MODEL,
    "gemini_key": "",
}


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _dpapi_transform(raw: bytes, *, protect: bool) -> bytes:
    if os.name != "nt":
        return raw
    buffer = ctypes.create_string_buffer(raw, len(raw))
    source = _DataBlob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    output = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    description = "Focus Buddy local API key" if protect else None
    arguments = (
        ctypes.byref(source),
        description,
        None,
        None,
        None,
        0x1,  # CRYPTPROTECT_UI_FORBIDDEN
        ctypes.byref(output),
    )
    if not function(*arguments):
        raise OSError("Windows凭据加密失败")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def _seal(value: str) -> str:
    if not value:
        return ""
    protected = _dpapi_transform(value.encode("utf-8"), protect=True)
    prefix = "dpapi:" if os.name == "nt" else "portable:"
    return prefix + base64.b64encode(protected).decode("ascii")


def _unseal(value: str) -> str:
    if not value:
        return ""
    prefix, separator, encoded = value.partition(":")
    if not separator or prefix not in {"dpapi", "portable"}:
        return ""
    try:
        protected = base64.b64decode(encoded, validate=True)
        if prefix == "dpapi":
            protected = _dpapi_transform(protected, protect=False)
        return protected.decode("utf-8")
    except (OSError, ValueError, UnicodeDecodeError):
        return ""


class CloudAISettingsStore:
    """Persist provider choices while never returning API keys to the browser."""

    def __init__(self, path: Path | None = None):
        self.path = path or user_data_root() / "cloud_ai.json"
        self.data = self._load()

    def _load(self) -> dict:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != 1:
                raise ValueError
            return {**DEFAULT_SETTINGS, **payload}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return dict(DEFAULT_SETTINGS)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    @staticmethod
    def _model(value: object, fallback: str) -> str:
        model = str(value or "").strip()
        if not model:
            return fallback
        if len(model) > 100 or not re.fullmatch(r"[A-Za-z0-9._:/-]+", model):
            raise ValueError("模型名称格式不正确")
        return model

    def snapshot(self) -> dict:
        return {
            "text_provider": self.data["text_provider"],
            "openrouter_model": self.data["openrouter_model"],
            "openrouter_configured": bool(self.data.get("openrouter_key")),
            "pet_renderer": self.data["pet_renderer"],
            "gemini_image_model": self.data["gemini_image_model"],
            "gemini_configured": bool(self.data.get("gemini_key")),
            "key_storage": "Windows DPAPI" if os.name == "nt" else "本机配置文件",
        }

    def update(self, payload: dict) -> dict:
        text_provider = str(payload.get("text_provider", self.data["text_provider"])).strip()
        if text_provider not in {"local", "openrouter", "ollama"}:
            raise ValueError("不支持这种任务解析方式")
        pet_renderer = str(payload.get("pet_renderer", self.data["pet_renderer"])).strip()
        if pet_renderer not in {"local", "gemini"}:
            raise ValueError("不支持这种宠物生成方式")
        self.data["text_provider"] = text_provider
        self.data["pet_renderer"] = pet_renderer
        self.data["openrouter_model"] = self._model(
            payload.get("openrouter_model", self.data["openrouter_model"]),
            DEFAULT_OPENROUTER_MODEL,
        )
        self.data["gemini_image_model"] = self._model(
            payload.get("gemini_image_model", self.data["gemini_image_model"]),
            DEFAULT_GEMINI_IMAGE_MODEL,
        )
        if payload.get("clear_openrouter_key"):
            self.data["openrouter_key"] = ""
        elif str(payload.get("openrouter_api_key", "")).strip():
            self.data["openrouter_key"] = _seal(str(payload["openrouter_api_key"]).strip())
        if payload.get("clear_gemini_key"):
            self.data["gemini_key"] = ""
        elif str(payload.get("gemini_api_key", "")).strip():
            self.data["gemini_key"] = _seal(str(payload["gemini_api_key"]).strip())
        self._save()
        return self.snapshot()

    def openrouter_key(self) -> str:
        return _unseal(str(self.data.get("openrouter_key", "")))

    def gemini_key(self) -> str:
        return _unseal(str(self.data.get("gemini_key", "")))


def _provider_error(exc: urllib.error.HTTPError, label: str) -> ValueError:
    detail = ""
    try:
        payload = json.loads(exc.read().decode("utf-8", errors="replace"))
        detail = str(payload.get("error", {}).get("message", ""))[:140]
    except (OSError, ValueError, TypeError):
        pass
    message = detail or f"HTTP {exc.code}"
    return ValueError(f"{label}调用失败：{message}")


class OpenRouterClient:
    """Small OpenAI-compatible text client for the optional free router."""

    def __init__(self, settings: CloudAISettingsStore):
        self.settings = settings

    def chat(
        self,
        *,
        messages: list[dict],
        model: str = "",
        temperature: float = 0.1,
        timeout_seconds: float = 60,
        **_kwargs,
    ) -> str:
        key = self.settings.openrouter_key()
        if not key:
            raise ValueError("请先在 AI 连接里保存 OpenRouter API Key")
        selected_model = model or self.settings.snapshot()["openrouter_model"]
        request = urllib.request.Request(
            OPENROUTER_ENDPOINT,
            data=json.dumps(
                {
                    "model": selected_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 900,
                },
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/miaoooow/Focus-Buddy",
                "X-Title": "Focus Buddy",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise _provider_error(exc, "OpenRouter") from None
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"OpenRouter暂时不可用：{str(exc)[:120]}") from None
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ValueError("OpenRouter没有返回可用文本") from None
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict)
            )
        text = str(content).strip()
        if not text:
            raise ValueError("OpenRouter没有返回可用文本")
        return text


class GeminiPetClient:
    """Turn a user photo into one illustration, then let local code grow it."""

    def __init__(self, settings: CloudAISettingsStore):
        self.settings = settings

    @staticmethod
    def _image_part(payload: object) -> tuple[str, str] | None:
        if isinstance(payload, dict):
            candidate = payload.get("inlineData") or payload.get("inline_data")
            if isinstance(candidate, dict) and candidate.get("data"):
                return (
                    str(candidate.get("mimeType") or candidate.get("mime_type") or "image/png"),
                    str(candidate["data"]),
                )
            for value in payload.values():
                found = GeminiPetClient._image_part(value)
                if found:
                    return found
        elif isinstance(payload, list):
            for value in payload:
                found = GeminiPetClient._image_part(value)
                if found:
                    return found
        return None

    def cartoonize(self, image_data: str, *, timeout_seconds: float = 90) -> str:
        key = self.settings.gemini_key()
        if not key:
            raise ValueError("请先在 AI 连接里保存 Gemini API Key")
        match = re.fullmatch(
            r"data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\r\n]+)",
            str(image_data or ""),
            re.IGNORECASE,
        )
        if not match:
            raise ValueError("请选择 PNG、JPG 或 WebP 宠物照片")
        mime = "image/jpeg" if match.group(1).casefold() in {"jpg", "jpeg"} else f"image/{match.group(1).casefold()}"
        model = self.settings.snapshot()["gemini_image_model"]
        endpoint = GEMINI_ENDPOINT.format(model=model)
        prompt = (
            "把这只真实宠物设计成 Focus Buddy 的原创二维动画角色。严格保留毛色、斑纹、"
            "耳朵轮廓和眼睛特征；正面或四分之三视角，完整头部和上半身，深绿色纯色背景，"
            "奶油色细描边，简洁高级、可爱但不幼稚。不要文字、不要水印、不要添加其他动物。"
        )
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(
                {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"text": prompt},
                                {"inline_data": {"mime_type": mime, "data": match.group(2)}},
                            ],
                        }
                    ],
                    "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
                },
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "x-goog-api-key": key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise _provider_error(exc, "Gemini图片模型") from None
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Gemini图片模型暂时不可用：{str(exc)[:120]}") from None
        generated = self._image_part(payload)
        if not generated:
            raise ValueError("Gemini没有返回图片，请稍后重试或切换本机生成")
        output_mime, encoded = generated
        return f"data:{output_mime};base64,{encoded}"
