import base64
import io
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from focus_agent.cat_skins import cat_growth_asset_path
from focus_agent.custom_pets import CustomPetStore
from focus_agent.profile_store import FocusProfileStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "test_custom_pet_feature"


def sample_pet_data_url() -> str:
    image = Image.new("RGB", (420, 360), "#dbeed5")
    draw = ImageDraw.Draw(image)
    draw.ellipse((90, 68, 330, 308), fill="#c87945", outline="#3b2a21", width=8)
    draw.polygon(((125, 105), (155, 32), (195, 112)), fill="#c87945", outline="#3b2a21")
    draw.polygon(((225, 112), (270, 32), (302, 112)), fill="#c87945", outline="#3b2a21")
    draw.ellipse((160, 155, 185, 180), fill="#20251e")
    draw.ellipse((235, 155, 260, 180), fill="#20251e")
    draw.ellipse((201, 198, 221, 215), fill="#8e4e4e")
    output = io.BytesIO()
    image.save(output, "PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


class CustomPetTests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)
        self.pet_store = CustomPetStore(RUNTIME_ROOT / "custom_pets")

    def tearDown(self):
        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)

    def test_photo_generates_four_local_growth_assets(self):
        item = self.pet_store.create("豆包", sample_pet_data_url())
        self.assertTrue(item["id"].startswith("custom:"))
        self.assertEqual(item["renderer"], "local-cartoon-v1")
        self.assertEqual(len(item["stage_assets"]), 4)
        for filename in ("baby.png", "young.png", "adult.png", "guardian.png"):
            path = self.pet_store.root / item["custom_id"] / filename
            self.assertTrue(path.is_file())
            with Image.open(path) as image:
                self.assertEqual(image.size, (560, 340))

    def test_new_profile_starts_with_milk_cow_sheriff(self):
        profile = FocusProfileStore(
            RUNTIME_ROOT / "new_profile.json",
            custom_pets=self.pet_store,
        ).snapshot()
        self.assertEqual(profile["pet"]["skin"], "tuxedo")
        selected = next(item for item in profile["cat_skins"] if item["id"] == "tuxedo")
        self.assertEqual(selected["name"], "奶牛警长")

    def test_custom_pet_can_be_adopted_and_deleted(self):
        profile = FocusProfileStore(
            RUNTIME_ROOT / "focus_profile.json",
            custom_pets=self.pet_store,
        )
        created = profile.create_custom_pet("豆包", sample_pet_data_url())
        selected = created["pet"]["skin"]
        self.assertTrue(selected.startswith("custom:"))
        self.assertEqual(created["pet"]["name"], "豆包")
        self.assertEqual(len([item for item in created["cat_skins"] if item.get("custom")]), 1)
        custom_id = selected.removeprefix("custom:")
        after_delete = profile.delete_custom_pet(custom_id)
        self.assertEqual(after_delete["pet"]["skin"], "tuxedo")
        self.assertFalse(self.pet_store.exists(custom_id))

    def test_native_alert_resolves_the_selected_custom_growth_stage(self):
        native_root = RUNTIME_ROOT / "native"
        with patch.dict(os.environ, {"FOCUS_AGENT_DATA_DIR": str(native_root)}):
            store = CustomPetStore()
            item = store.create("豆包", sample_pet_data_url())
            adult = cat_growth_asset_path(item["skin"], 2)
            guardian = cat_growth_asset_path(item["skin"], 4)
            self.assertEqual(adult.name, "adult.png")
            self.assertEqual(guardian.name, "guardian.png")
            self.assertTrue(adult.is_file())
            self.assertTrue(guardian.is_file())

    def test_invalid_or_oversized_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            self.pet_store.create("豆包", "data:text/plain;base64,SGVsbG8=")
        too_large = "data:image/png;base64," + base64.b64encode(b"x" * (6 * 1024 * 1024 + 1)).decode()
        with self.assertRaises(ValueError):
            self.pet_store.create("豆包", too_large)


if __name__ == "__main__":
    unittest.main()
