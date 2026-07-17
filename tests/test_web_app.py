import json
import threading
import unittest
import urllib.error
import urllib.request
from urllib.parse import quote

from focus_agent.web_app import (
    DESKTOP_WINDOW_ARG,
    FocusHTTPServer,
    FocusRequestHandler,
    _desktop_window_command,
    _find_server,
)


class FakeController:
    def __init__(self):
        self.last_plan_request = None

    def status(self):
        return {"state": "idle", "profile": {}, "suggestions": []}

    def plan_goal(self, goal, use_ai=True):
        self.last_plan_request = {"goal": goal, "use_ai": use_ai}
        return {
            "source": "本机AI · fake" if use_ai else "本地场景库",
            "ai_used": use_ai,
            "fallback_reason": "",
            "config": {"mode": "whitelist", "allowed_targets": []},
            "scenes": [],
        }

    def preview_alert(self):
        return {"queued": True, "mood": "patient"}

    def preview_reaction(self, kind):
        return {"queued": True, "kind": kind, "cat_name": "饭团"}

    def report_browser_tab(self, payload):
        return {"connected": True, "current_domain": payload.get("domain", "")}

    def rename_pet(self, name):
        if not name:
            raise ValueError("名字不能为空")
        return {"cat_name": name, "pet": {"name": name}}

    def select_pet_skin(self, skin):
        if skin not in {"orange", "tuxedo", "ragdoll"}:
            raise ValueError("不存在的小猫")
        return {"cat_skin": skin, "pet": {"name": "饭团", "skin": skin}}

    def create_custom_pet(self, name, image_data):
        return {"cat_name": name, "pet": {"name": name, "skin": "custom:0123456789abcdef"}}

    def delete_custom_pet(self, custom_id):
        return {"cat_name": "饭团", "pet": {"name": "饭团", "skin": "orange"}}


class WebAppTests(unittest.TestCase):
    def test_source_desktop_window_command_reuses_the_project_entrypoint(self):
        command = _desktop_window_command("http://127.0.0.1:8765/")
        self.assertEqual(command[-2], DESKTOP_WINDOW_ARG)
        self.assertEqual(command[-1], "http://127.0.0.1:8765/")
        self.assertTrue(command[-3].casefold().endswith("app.py"))

    def test_server_skips_an_occupied_port(self):
        occupied = FocusHTTPServer(
            ("127.0.0.1", 0), FocusRequestHandler, FakeController(), threading.Event()
        )
        selected = None
        try:
            selected = _find_server(
                FakeController(),
                threading.Event(),
                ports=(occupied.server_port, 0),
            )
            self.assertNotEqual(selected.server_port, occupied.server_port)
        finally:
            if selected:
                selected.server_close()
            occupied.server_close()

    def test_health_state_and_static_page_are_served_locally(self):
        controller = FakeController()
        server = FocusHTTPServer(
            ("127.0.0.1", 0), FocusRequestHandler, controller, threading.Event()
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urllib.request.urlopen(f"{base}/api/health", timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["version"], 8)
            self.assertEqual(payload["data"]["service"], "focus-buddy-ai")
            with urllib.request.urlopen(f"{base}/", timeout=3) as response:
                html = response.read().decode("utf-8")
                csp = response.headers.get("Content-Security-Policy", "")
            self.assertIn("Focus Buddy", html)
            self.assertIn("default-src 'self'", csp)
            self.assertIn("media-src 'self'", csp)
            self.assertIn("/styles.css?v=8", html)
            self.assertIn("/app.js?v=8", html)
            self.assertIn("本机 AI 增强", html)
            self.assertIn("选择雨幕、溪流、海岸或鸟鸣，让小猫替你守住这一段节奏。", html)
            self.assertNotIn('class="sound-facts"', html)
            self.assertNotIn('id="sound-library-note"', html)
            self.assertIn("失败 · 推翻茶杯", html)
            self.assertIn("story-cup", html)
            self.assertIn("nurture-head", html)
            self.assertIn("把自家宠物带进来", html)
            self.assertIn("生成并领养", html)

            with urllib.request.urlopen(f"{base}/api/media/library", timeout=3) as response:
                media = json.loads(response.read().decode("utf-8"))["data"]
            self.assertGreaterEqual(media["playable_count"], 15)
            self.assertEqual(media["synth_count"], 4)
            self.assertTrue(media["tracks"])
            self.assertTrue(all(not track["url"].casefold().endswith(".ncm") for track in media["tracks"]))

            file_track = next(track for track in media["tracks"] if track["source"] != "synth")
            range_request = urllib.request.Request(
                f"{base}{file_track['url']}",
                headers={"Range": "bytes=0-31"},
            )
            with urllib.request.urlopen(range_request, timeout=3) as response:
                audio_prefix = response.read()
                content_range = response.headers.get("Content-Range", "")
                accept_ranges = response.headers.get("Accept-Ranges", "")
                response_status = response.status
            self.assertEqual(response_status, 206)
            self.assertEqual(len(audio_prefix), 32)
            self.assertTrue(content_range.startswith("bytes 0-31/"))
            self.assertEqual(accept_ranges, "bytes")

            with urllib.request.urlopen(f"{base}/media/picture/{quote('happy.png')}", timeout=3) as response:
                picture_prefix = response.read(8)
                picture_type = response.headers.get("Content-Type", "")
            self.assertEqual(picture_prefix, b"\x89PNG\r\n\x1a\n")
            self.assertEqual(picture_type, "image/png")
            request = urllib.request.Request(
                f"{base}/api/preview/alert",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                preview = json.loads(response.read().decode("utf-8"))
            self.assertTrue(preview["data"]["queued"])
            rename_request = urllib.request.Request(
                f"{base}/api/pet/name",
                data=json.dumps({"name": "饭团"}, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(rename_request, timeout=3) as response:
                renamed = json.loads(response.read().decode("utf-8"))
            self.assertEqual(renamed["data"]["pet"]["name"], "饭团")
            skin_request = urllib.request.Request(
                f"{base}/api/pet/skin",
                data=json.dumps({"skin": "tuxedo"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(skin_request, timeout=3) as response:
                selected = json.loads(response.read().decode("utf-8"))
            self.assertEqual(selected["data"]["pet"]["skin"], "tuxedo")
            bridge_request = urllib.request.Request(
                f"{base}/api/browser/active",
                data=json.dumps({
                    "process_name": "msedge.exe", "domain": "example.com", "title": "Example"
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(bridge_request, timeout=3) as response:
                bridge = json.loads(response.read().decode("utf-8"))
            self.assertTrue(bridge["data"]["connected"])
            reaction_request = urllib.request.Request(
                f"{base}/api/preview/reaction",
                data=b'{"kind":"shy"}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(reaction_request, timeout=3) as response:
                reaction = json.loads(response.read().decode("utf-8"))
            self.assertEqual(reaction["data"]["kind"], "shy")

            plan_request = urllib.request.Request(
                f"{base}/api/plan",
                data=json.dumps(
                    {"goal": "40分钟完成课程报告", "use_ai": False},
                    ensure_ascii=False,
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(plan_request, timeout=3) as response:
                planned = json.loads(response.read().decode("utf-8"))
            self.assertFalse(planned["data"]["ai_used"])
            self.assertEqual(
                controller.last_plan_request,
                {"goal": "40分钟完成课程报告", "use_ai": False},
            )

            invalid_plan_request = urllib.request.Request(
                f"{base}/api/plan",
                data=b'{"goal":"test","use_ai":"false"}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(invalid_plan_request, timeout=3)
            self.assertEqual(caught.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
