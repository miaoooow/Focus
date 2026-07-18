import base64
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from focus_agent.cloud_ai import (
    CloudAISettingsStore,
    FocusCloudClient,
    GeminiPetClient,
    OpenRouterClient,
)


ROOT = Path(__file__).resolve().parents[1] / ".runtime" / "test_cloud_ai"


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class CloudAITests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(ROOT, ignore_errors=True)
        ROOT.mkdir(parents=True)
        self.store = CloudAISettingsStore(ROOT / "cloud_ai.json")

    def tearDown(self):
        shutil.rmtree(ROOT, ignore_errors=True)

    def test_keys_are_encrypted_and_never_returned_to_browser(self):
        snapshot = self.store.update(
            {
                "text_provider": "openrouter",
                "openrouter_api_key": "sk-or-secret-for-test",
                "pet_renderer": "gemini",
                "gemini_api_key": "gemini-secret-for-test",
            }
        )
        persisted = self.store.path.read_text(encoding="utf-8")
        self.assertNotIn("sk-or-secret-for-test", persisted)
        self.assertNotIn("gemini-secret-for-test", persisted)
        self.assertNotIn("api_key", snapshot)
        self.assertTrue(snapshot["openrouter_configured"])
        self.assertTrue(snapshot["gemini_configured"])
        reloaded = CloudAISettingsStore(self.store.path)
        self.assertEqual(reloaded.openrouter_key(), "sk-or-secret-for-test")
        self.assertEqual(reloaded.gemini_key(), "gemini-secret-for-test")

    def test_openrouter_uses_compatible_chat_endpoint(self):
        self.store.update({"openrouter_api_key": "key"})
        response = {
            "choices": [{"message": {"content": '{"duration_minutes":45}'}}],
        }
        with patch("focus_agent.cloud_ai.urllib.request.urlopen", return_value=FakeResponse(response)) as call:
            result = OpenRouterClient(self.store).chat(
                model="openrouter/free",
                messages=[{"role": "user", "content": "test"}],
            )
        self.assertEqual(result, '{"duration_minutes":45}')
        request = call.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer key")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "openrouter/free")

    def test_focus_account_hides_token_and_needs_no_provider_key(self):
        self.store.update({"focus_cloud_url": "https://focus.example"})
        response = {
            "ok": True,
            "data": {
                "token": "focus-session-secret",
                "username": "luna",
                "expires_at": 2_000_000_000,
            },
        }
        with patch(
            "focus_agent.cloud_ai.urllib.request.urlopen",
            return_value=FakeResponse(response),
        ) as call:
            snapshot = FocusCloudClient(self.store).register("luna", "password123")
        self.assertTrue(snapshot["focus_account"]["signed_in"])
        self.assertEqual(snapshot["text_provider"], "focus_cloud")
        self.assertNotIn("focus-session-secret", json.dumps(snapshot))
        self.assertNotIn(
            "focus-session-secret",
            self.store.path.read_text(encoding="utf-8"),
        )
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, "https://focus.example/v1/auth/register")
        self.assertNotIn("Authorization", dict(request.header_items()))

    def test_gemini_image_response_becomes_a_local_data_url(self):
        self.store.update({"gemini_api_key": "key"})
        generated = base64.b64encode(b"generated-png").decode("ascii")
        response = {
            "candidates": [
                {"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": generated}}]}}
            ]
        }
        source = "data:image/png;base64," + base64.b64encode(b"source").decode("ascii")
        with patch("focus_agent.cloud_ai.urllib.request.urlopen", return_value=FakeResponse(response)):
            result = GeminiPetClient(self.store).cartoonize(source)
        self.assertEqual(result, f"data:image/png;base64,{generated}")


if __name__ == "__main__":
    unittest.main()
