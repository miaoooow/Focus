import json
import shutil
import time
import unittest
from pathlib import Path

from focus_agent.controller import FocusController
from focus_agent.custom_pets import CustomPetStore
from focus_agent.goal_scenarios import GoalScenarioStore
from focus_agent.profile_store import FocusProfileStore
from tests.test_custom_pets import sample_action_sheet_data_url, sample_pet_data_url


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "test_controller_v2"


class ControllerV2Tests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)
        RUNTIME_ROOT.mkdir(parents=True)
        self.controller = FocusController()
        self.controller.profile = FocusProfileStore(
            RUNTIME_ROOT / "focus_profile.json",
            CustomPetStore(RUNTIME_ROOT / "custom_pets"),
        )
        self.controller.parser.scenarios = GoalScenarioStore(
            PROJECT_ROOT / "data" / "goal_scenarios.json",
            RUNTIME_ROOT / "goal_scenario_memory.json",
        )

    def tearDown(self):
        self.controller.close()
        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)

    def test_repeated_local_planning_is_fast_and_explainable(self):
        started = time.perf_counter()
        plans = [
            self.controller.plan_goal(goal, use_ai=False)
            for goal in (
                "45分钟完成高数作业第三章",
                "50分钟写Python接口并测试",
                "30分钟制作汇报PPT",
                "25分钟整理Excel报表",
            )
        ]
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.2)
        self.assertTrue(all(plan["scenes"] for plan in plans))
        self.assertTrue(all(plan["source"] == "本地场景库 · 即时规划" for plan in plans))

    def test_starting_session_learns_the_final_confirmed_whitelist(self):
        plan = self.controller.plan_goal("45分钟完成Python课程作业", use_ai=False)
        config = plan["config"]
        config["allowed_targets"] = [
            {"kind": "process", "value": "PyCharm64.exe", "match": "exact"},
            {"kind": "process", "value": "explorer.exe", "match": "exact"},
        ]
        self.controller.start_session({"goal": plan["goal"], "config": config})
        self.controller.stop_session()
        memory = json.loads(
            (RUNTIME_ROOT / "goal_scenario_memory.json").read_text(encoding="utf-8")
        )
        self.assertEqual(memory["mappings"][0]["targets"][0]["value"], "PyCharm64.exe")

    def test_custom_pet_controller_flow(self):
        profile = self.controller.create_custom_pet("豆包", sample_pet_data_url())
        self.assertTrue(profile["pet"]["skin"].startswith("custom:"))
        custom_id = profile["pet"]["skin"].removeprefix("custom:")
        deleted = self.controller.delete_custom_pet(custom_id)
        self.assertEqual(deleted["pet"]["skin"], "tuxedo")

    def test_ai_pet_flow_requires_consent_and_creates_four_actions(self):
        class FakePetClient:
            @staticmethod
            def cartoonize(_image_data):
                return sample_action_sheet_data_url()

        self.controller.cloud_pet_client = FakePetClient()
        with self.assertRaises(ValueError):
            self.controller.create_custom_pet(
                "云朵",
                sample_pet_data_url(),
                renderer="gemini",
                consent=False,
            )
        profile = self.controller.create_custom_pet(
            "云朵",
            sample_pet_data_url(),
            renderer="gemini",
            consent=True,
        )
        selected = next(
            item for item in profile["cat_skins"]
            if item["id"] == profile["pet"]["skin"]
        )
        self.assertEqual(set(selected["action_assets"]), {"idle", "happy", "wiggle", "angry"})
        self.assertEqual(selected["renderer"], "gemini-action-sheet+local-growth-v2")


if __name__ == "__main__":
    unittest.main()
