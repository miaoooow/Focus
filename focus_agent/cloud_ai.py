"""Focus Cloud plus optional user-owned AI connections.

End users can sign in to a Focus Cloud deployment and use its managed free
quota without obtaining a provider API key. Optional OpenRouter/Gemini keys
remain available for advanced self-hosted use and are protected with DPAPI.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from ctypes import wintypes
from pathlib import Path

from .paths import resource_root, user_data_root


OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_OPENROUTER_MODEL = "openrouter/free"
DEFAULT_GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"


def _packaged_focus_cloud_url() -> str:
    configured = os.environ.get("FOCUS_CLOUD_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    try:
        payload = json.loads(
            (resource_root() / "data" / "focus_cloud.json").read_text(encoding="utf-8")
        )
        return str(payload.get("base_url", "")).strip().rstrip("/")
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return ""


DEFAULT_SETTINGS = {
    "schema_version": 2,
    "text_provider": "local",
    "focus_cloud_url": _packaged_focus_cloud_url(),
    "focus_account_token": "",
    "focus_account_name": "",
    "focus_account_expires": 0,
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
    description = "Focus local API key" if protect else None
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
            if payload.get("schema_version") not in {1, 2}:
                raise ValueError
            migrated = {**DEFAULT_SETTINGS, **payload, "schema_version": 2}
            if not migrated.get("focus_cloud_url"):
                migrated["focus_cloud_url"] = _packaged_focus_cloud_url()
            return migrated
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
        account_token = _unseal(str(self.data.get("focus_account_token", "")))
        return {
            "text_provider": self.data["text_provider"],
            "focus_cloud_url": self.data.get("focus_cloud_url", ""),
            "focus_cloud_available": bool(self.data.get("focus_cloud_url")),
            "focus_account": {
                "signed_in": bool(account_token),
                "username": str(self.data.get("focus_account_name", "")),
                "expires_at": int(self.data.get("focus_account_expires", 0) or 0),
            },
            "openrouter_model": self.data["openrouter_model"],
            "openrouter_configured": bool(self.data.get("openrouter_key")),
            "pet_renderer": self.data["pet_renderer"],
            "gemini_image_model": self.data["gemini_image_model"],
            "gemini_configured": bool(self.data.get("gemini_key")),
            "key_storage": "Windows DPAPI" if os.name == "nt" else "本机配置文件",
        }

    def update(self, payload: dict) -> dict:
        text_provider = str(payload.get("text_provider", self.data["text_provider"])).strip()
        if text_provider not in {"local", "focus_cloud", "openrouter", "ollama"}:
            raise ValueError("不支持这种任务解析方式")
        pet_renderer = str(payload.get("pet_renderer", self.data["pet_renderer"])).strip()
        if pet_renderer not in {"local", "focus_cloud", "gemini"}:
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
        if "focus_cloud_url" in payload:
            self.data["focus_cloud_url"] = self._cloud_url(payload.get("focus_cloud_url"))
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

    @staticmethod
    def _cloud_url(value: object) -> str:
        url = str(value or "").strip().rstrip("/")
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url)
        local = parsed.hostname in {"127.0.0.1", "localhost"}
        if parsed.scheme not in ({"http", "https"} if local else {"https"}) or not parsed.netloc:
            raise ValueError("Focus Cloud 地址必须是 HTTPS；本机调试可使用 localhost")
        return url

    def focus_cloud_url(self) -> str:
        return str(self.data.get("focus_cloud_url", "")).strip().rstrip("/")

    def focus_account_token(self) -> str:
        return _unseal(str(self.data.get("focus_account_token", "")))

    def save_focus_account(self, payload: dict) -> dict:
        token = str(payload.get("token", "")).strip()
        username = str(payload.get("username", "")).strip()[:24]
        if not token or not username:
            raise ValueError("Focus账户返回不完整")
        self.data["focus_account_token"] = _seal(token)
        self.data["focus_account_name"] = username
        self.data["focus_account_expires"] = int(payload.get("expires_at", 0) or 0)
        self.data["text_provider"] = "focus_cloud"
        self._save()
        return self.snapshot()

    def clear_focus_account(self) -> dict:
        self.data["focus_account_token"] = ""
        self.data["focus_account_name"] = ""
        self.data["focus_account_expires"] = 0
        if self.data.get("text_provider") == "focus_cloud":
            self.data["text_provider"] = "local"
        if self.data.get("pet_renderer") == "focus_cloud":
            self.data["pet_renderer"] = "local"
        self._save()
        return self.snapshot()


def _provider_error(exc: urllib.error.HTTPError, label: str) -> ValueError:
    detail = ""
    try:
        payload = json.loads(exc.read().decode("utf-8", errors="replace"))
        detail = str(payload.get("error", {}).get("message", ""))[:140]
    except (OSError, ValueError, TypeError):
        pass
    message = detail or f"HTTP {exc.code}"
    return ValueError(f"{label}调用失败：{message}")


class FocusCloudClient:
    """Account-backed AI client; no provider key is exposed to end users."""

    def __init__(self, settings: CloudAISettingsStore):
        self.settings = settings

    def _request(
        self,
        path: str,
        payload: dict | None = None,
        *,
        authenticated: bool = False,
        timeout_seconds: float = 60,
    ) -> dict:
        base_url = self.settings.focus_cloud_url()
        if not base_url:
            raise ValueError("Focus Cloud尚未由项目维护者部署；本地场景库仍可正常使用")
        headers = {"Content-Type": "application/json"}
        if authenticated:
            token = self.settings.focus_account_token()
            if not token:
                raise ValueError("请先登录Focus账户")
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            f"{base_url}{path}",
            data=None if payload is None else json.dumps(
                payload, ensure_ascii=False
            ).encode("utf-8"),
            headers=headers,
            method="GET" if payload is None else "POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = str(json.loads(exc.read().decode("utf-8")).get("error", ""))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
            raise ValueError(detail[:160] or f"Focus Cloud调用失败：HTTP {exc.code}") from None
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Focus Cloud暂时不可用：{str(exc)[:120]}") from None
        if not isinstance(result, dict) or not result.get("ok"):
            raise ValueError(str(result.get("error", "Focus Cloud返回异常"))[:160])
        data = result.get("data")
        if not isinstance(data, dict):
            raise ValueError("Focus Cloud返回内容不完整")
        return data

    def register(self, username: str, password: str) -> dict:
        data = self._request(
            "/v1/auth/register",
            {"username": username, "password": password},
            timeout_seconds=30,
        )
        return self.settings.save_focus_account(data)

    def login(self, username: str, password: str) -> dict:
        data = self._request(
            "/v1/auth/login",
            {"username": username, "password": password},
            timeout_seconds=30,
        )
        return self.settings.save_focus_account(data)

    def logout(self) -> dict:
        try:
            if self.settings.focus_account_token():
                self._request(
                    "/v1/auth/logout",
                    {},
                    authenticated=True,
                    timeout_seconds=15,
                )
        except ValueError:
            # Local logout must remain available while the gateway is offline.
            pass
        return self.settings.clear_focus_account()

    def chat(
        self,
        *,
        messages: list[dict],
        timeout_seconds: float = 60,
        **_kwargs,
    ) -> str:
        data = self._request(
            "/v1/chat",
            {"messages": messages},
            authenticated=True,
            timeout_seconds=timeout_seconds,
        )
        text = str(data.get("text", "")).strip()
        if not text:
            raise ValueError("Focus Cloud没有返回可用文本")
        return text

    def cartoonize(self, image_data: str, *, timeout_seconds: float = 120) -> str:
        data = self._request(
            "/v1/pet",
            {"image": image_data},
            authenticated=True,
            timeout_seconds=timeout_seconds,
        )
        image = str(data.get("image", "")).strip()
        if not image.startswith("data:image/"):
            raise ValueError("Focus Cloud没有返回可用图片")
        return image


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
                "HTTP-Referer": "https://github.com/miaoooow/Focus",
                "X-Title": "Focus",
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
    """Turn a pet photo into a consistent four-action animation sheet."""

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
            "把照片里的真实宠物设计成 Focus 的原创二维动画角色，并输出严格的2x2四格动作设定图。"
            "四格必须是同一只宠物、同一画风、同一比例，并准确保留毛色、斑纹、耳朵轮廓、眼睛和"
            "物种特征。左上：安静站立；右上：开心害羞并带腮红；左下：走神后摇头扭身；右下："
            "生气抬爪准备推杯子。每格只出现完整的一只宠物，主体居中且留足边距，使用完全相同的"
            "纯绿色背景和奶油色细描边。简洁高级、可爱但不幼稚。不要格线、文字、水印、道具、"
            "阴影或其他动物。"
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
