import unittest
import json
import os
from unittest.mock import patch

from focus_agent.contracts import sanitize_roast_response, sanitize_summary_response
from focus_agent.ollama_client import OllamaClient
from focus_agent.services import CopyProvider, SessionParserService


class OfflineClient:
    def chat(self, **kwargs):
        raise RuntimeError("offline")


class UncertainClient:
    def chat(self, **kwargs):
        return json.dumps(
            {
                "schema_version": 1,
                "duration_minutes": 45,
                "mode": "whitelist",
                "allowed_targets": [
                    {"kind": "process", "value": "Code.exe", "match": "exact"}
                ],
                "blocked_targets": [],
                "grace_seconds": 8,
                "check_interval_seconds": 2,
                "popup_cooldown_seconds": 30,
                "max_alerts": 10,
                "roast_intensity": "mild",
                "needs_clarification": True,
                "clarification_question": "需要什么软件？",
            },
            ensure_ascii=False,
        )


class CountingClient:
    def __init__(self):
        self.calls = 0

    def chat(self, **kwargs):
        self.calls += 1
        raise AssertionError("fast planner must not wait for Ollama")


class ServiceTests(unittest.TestCase):
    def test_ollama_endpoint_can_be_overridden_for_offline_validation(self):
        with patch.dict(os.environ, {"FOCUS_BUDDY_OLLAMA_URL": "http://127.0.0.1:65534"}):
            client = OllamaClient()
        self.assertEqual(client.base_url, "http://127.0.0.1:65534")

    def test_goal_planner_falls_back_locally_when_ollama_is_offline(self):
        plan = SessionParserService(OfflineClient()).plan_goal(
            "45分钟完成高数作业第三章", use_ai=False
        )
        self.assertEqual(plan.config.duration_minutes, 45)
        self.assertTrue(plan.config.allowed_targets)
        self.assertFalse(plan.config.needs_clarification)
        self.assertEqual("本地场景库 · 即时规划", plan.source)

    def test_goal_planner_does_not_wait_for_model_guess(self):
        plan = SessionParserService(UncertainClient()).plan_goal(
            "完成高数作业第三章", use_ai=False
        )
        values = {target.value for target in plan.config.allowed_targets}
        self.assertIn("高数", values)
        self.assertNotIn("Code.exe", values)
        self.assertFalse(plan.config.needs_clarification)

    def test_fast_planner_never_calls_ollama(self):
        client = CountingClient()
        plan = SessionParserService(client).plan_goal("完成周报", use_ai=False)
        self.assertEqual(client.calls, 0)
        self.assertEqual(plan.source, "本地场景库 · 即时规划")

    def test_copy_provider_is_instant_without_model(self):
        provider = CopyProvider(OfflineClient(), model_probability=0)
        try:
            line = provider.alert_line(
                duration_minutes=25,
                rule_description="只允许VS Code",
                current_target="浏览器",
                elapsed_seconds=8,
                roast_intensity="mild",
            )
            self.assertIsNotNone(sanitize_roast_response(line))
            summary = provider.local_summary(alert_count=2, max_alerts=10)
            self.assertIsNotNone(sanitize_summary_response(summary))
        finally:
            provider.close()


if __name__ == "__main__":
    unittest.main()
