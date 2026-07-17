import unittest
import shutil
from pathlib import Path

from focus_agent.media_library import _category, _media_url, build_media_library


class MediaLibraryTests(unittest.TestCase):
    def test_category_rules_and_url_encoding_are_deterministic(self):
        self.assertEqual(_category("Rain Artist - Summer Rain"), "rain")
        self.assertEqual(_category("Forest - Stream and Bird"), "birds")
        self.assertEqual(_category("Coast - Rolling Surf on Beach"), "ocean")
        self.assertEqual(_category("Fresh Air"), "sunny")
        encoded = _media_url(Path("子目录") / "Rain Artist - Summer Rain.mp3")
        self.assertTrue(encoded.startswith("/media/music/"))
        self.assertIn("%20", encoded)
        self.assertIn("%E5%AD%90%E7%9B%AE%E5%BD%95", encoded)

    def test_project_music_library_has_playable_tracks(self):
        library = build_media_library()
        self.assertGreaterEqual(library["playable_count"], 15)
        self.assertGreaterEqual(library["unavailable_count"], 1)
        self.assertGreaterEqual(len(library["categories"]), 4)
        self.assertEqual(sum(category["count"] for category in library["categories"]), library["playable_count"])
        self.assertTrue(all(not track["url"].casefold().endswith(".ncm") for track in library["tracks"]))

    def test_empty_install_still_has_four_synthesized_soundscapes(self):
        root = Path(__file__).resolve().parents[1] / ".runtime" / "media-empty-test"
        project = root / "project"
        data = root / "data"
        shutil.rmtree(root, ignore_errors=True)
        project.mkdir(parents=True)
        try:
            library = build_media_library(project, data)
            self.assertEqual(library["synth_count"], 4)
            self.assertEqual(library["file_count"], 0)
            self.assertEqual(library["playable_count"], 4)
            self.assertTrue(all(track["source"] == "synth" for track in library["tracks"]))
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
