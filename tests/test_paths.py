import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from focus_agent.paths import browser_extension_root, resource_root, user_data_root


ROOT = Path(__file__).resolve().parent.parent


class ApplicationPathTests(unittest.TestCase):
    def test_path_overrides_keep_resources_and_user_data_separate(self):
        base = ROOT / ".runtime" / "path-test"
        resources = base / "resources"
        user_data = base / "user-data"
        extension = resources / "browser_extension_standalone"
        shutil.rmtree(base, ignore_errors=True)
        try:
            with patch.dict(
                os.environ,
                {
                    "FOCUS_AGENT_RESOURCE_ROOT": str(resources),
                    "FOCUS_AGENT_DATA_DIR": str(user_data),
                },
                clear=False,
            ):
                self.assertEqual(resource_root(), resources.resolve())
                self.assertEqual(user_data_root(), user_data.resolve())
                self.assertTrue(user_data.exists())
                self.assertEqual(browser_extension_root(), extension.resolve())
        finally:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
