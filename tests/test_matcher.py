import json
import os
import time
import unittest

from focus_agent.controller import FocusController
from focus_agent.contracts import parse_session_response
from focus_agent.matcher import (
    browser_domain_is_unknown,
    matching_rules,
    rule_matches,
    unsupported_rules,
)
from focus_agent.window_monitor import ForegroundSnapshot
from focus_agent.runtime import FocusSessionEngine


def config_with(target, mode="whitelist"):
    payload = {
        "schema_version": 1,
        "duration_minutes": 25,
        "mode": mode,
        "allowed_targets": [target] if mode == "whitelist" else [],
        "blocked_targets": [target] if mode == "blacklist" else [],
        "grace_seconds": 8,
        "check_interval_seconds": 2,
        "popup_cooldown_seconds": 30,
        "max_alerts": 10,
        "roast_intensity": "mild",
        "needs_clarification": False,
        "clarification_question": "",
    }
    return parse_session_response(json.dumps(payload, ensure_ascii=False))


class MatcherTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = ForegroundSnapshot(
            hwnd=100,
            pid=200,
            process_name="Code.exe",
            window_title="论文 - Visual Studio Code",
            input_idle_seconds=0.2,
        )

    def test_process_and_app_alias_match(self):
        process = config_with({"kind": "process", "value": "Code.exe", "match": "exact"})
        app = config_with({"kind": "app", "value": "VS Code", "match": "exact"})
        self.assertTrue(rule_matches(process.allowed_targets[0], self.snapshot))
        self.assertTrue(rule_matches(app.allowed_targets[0], self.snapshot))

    def test_window_title_match(self):
        config = config_with(
            {"kind": "window_title", "value": "Visual Studio Code", "match": "contains"}
        )
        self.assertEqual(len(matching_rules(config.allowed_targets, self.snapshot)), 1)

    def test_domain_suffix_rule_uses_the_browser_bridge_domain(self):
        config = config_with(
            {"kind": "domain", "value": "example.com", "match": "domain_suffix"}
        )
        browser = ForegroundSnapshot(
            hwnd=101,
            pid=201,
            process_name="msedge.exe",
            window_title="Example docs",
            input_idle_seconds=0.2,
            browser_domain="docs.example.com",
        )
        self.assertEqual(unsupported_rules(config), ())
        self.assertTrue(rule_matches(config.allowed_targets[0], browser))
        self.assertFalse(rule_matches(config.allowed_targets[0], self.snapshot))

    def test_missing_browser_domain_is_uncertain_not_a_confirmed_violation(self):
        config = config_with(
            {"kind": "domain", "value": "example.com", "match": "domain_suffix"}
        )
        browser_without_bridge = ForegroundSnapshot(
            hwnd=102,
            pid=202,
            process_name="msedge.exe",
            window_title="Browser page",
            input_idle_seconds=0.2,
        )
        self.assertTrue(browser_domain_is_unknown(config, browser_without_bridge))
        self.assertFalse(browser_domain_is_unknown(config, self.snapshot))

    def test_wrong_known_domain_is_not_uncertain(self):
        config = config_with(
            {"kind": "domain", "value": "example.com", "match": "domain_suffix"}
        )
        known_other_domain = ForegroundSnapshot(
            hwnd=103,
            pid=203,
            process_name="chrome.exe",
            window_title="Other page",
            input_idle_seconds=0.2,
            browser_domain="other.example",
        )
        self.assertFalse(browser_domain_is_unknown(config, known_other_domain))

    def test_controller_never_penalizes_a_temporarily_unknown_domain(self):
        config = config_with(
            {"kind": "domain", "value": "example.com", "match": "domain_suffix"}
        )
        snapshot = ForegroundSnapshot(
            hwnd=104,
            pid=204,
            process_name="msedge.exe",
            window_title="Browser page",
            input_idle_seconds=0.2,
        )
        controller = FocusController.__new__(FocusController)
        effective, status, suggestion = controller._related_snapshot(
            config, snapshot, time.monotonic()
        )
        engine = FocusSessionEngine(config, own_pid=os.getpid(), now=10.0)
        update = engine.tick(effective, now=20.0)
        self.assertFalse(update.violating)
        self.assertIn("不扣分", status)
        self.assertIsNone(suggestion)

    def test_focus_local_control_page_is_always_safe_in_whitelist_mode(self):
        config = config_with(
            {"kind": "domain", "value": "example.com", "match": "domain_suffix"}
        )
        control_page = ForegroundSnapshot(
            hwnd=105,
            pid=205,
            process_name="msedge.exe",
            window_title="Focus · 本地专注伙伴",
            input_idle_seconds=0.2,
            browser_domain="127.0.0.1",
        )
        controller = FocusController.__new__(FocusController)
        effective, status, _ = controller._related_snapshot(
            config, control_page, time.monotonic()
        )
        engine = FocusSessionEngine(config, own_pid=os.getpid(), now=10.0)
        update = engine.tick(effective, now=20.0)
        self.assertFalse(update.violating)
        self.assertIn("自动放行", status)


if __name__ == "__main__":
    unittest.main()
