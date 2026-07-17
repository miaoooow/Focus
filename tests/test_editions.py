import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicEditionTests(unittest.TestCase):
    def test_browser_extension_contains_only_runtime_files(self):
        folder = ROOT / "browser_extension_standalone"
        self.assertEqual(
            {item.name for item in folder.iterdir() if item.is_file()},
            {"manifest.json", "background.js", "popup.html", "popup.css", "popup.js"},
        )
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["version"], "3.3.0")
        self.assertEqual(
            set(manifest["permissions"]),
            {"storage", "tabs", "alarms", "notifications"},
        )
        self.assertNotIn("host_permissions", manifest)

    def test_web_edition_contains_only_runtime_files(self):
        folder = ROOT / "web_standalone"
        self.assertEqual(
            {item.name for item in folder.iterdir() if item.is_file()},
            {"index.html", "styles.css", "app.js", "manifest.webmanifest", "sw.js"},
        )
        manifest = json.loads((folder / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "./")
        self.assertIn("只判断你是否离开当前页面", (folder / "index.html").read_text(encoding="utf-8"))
        page = (folder / "index.html").read_text(encoding="utf-8")
        script = (folder / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="pet-photo"', page)
        self.assertIn('id="pet-name"', page)
        self.assertIn("compressPetPhoto", script)
        self.assertIn("createNoiseBuffer", script)

    def test_readme_explains_three_editions_and_attribution(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in ("Windows 安装版", "浏览器扩展版", "网页版", "项目文件结构"):
            self.assertIn(phrase, readme)
        self.assertIn("YouTube 博主 **mocha.**", readme)
        self.assertIn("声音花园", readme)
        for asset in (
            "releases/latest/download/FocusBuddy-Windows-Setup.exe",
            "releases/latest/download/FocusBuddy-Browser-Extension.zip",
            "releases/latest/download/FocusBuddy-Web.zip",
        ):
            self.assertIn(asset, readme)
        self.assertNotIn(r"D:\Agent", readme)
        self.assertNotIn("设计说明书.docx", readme)

    def test_pages_workflow_deploys_only_web_edition(self):
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertIn("path: site", workflow)
        self.assertIn("cp pictures/*.png site/media/", workflow)
        self.assertIn("actions/upload-pages-artifact@v4", workflow)
        self.assertIn("test -f web_standalone/index.html", workflow)
        self.assertNotIn("path: .", workflow)

    def test_windows_installer_is_per_user_and_one_click(self):
        installer = (ROOT / "installer" / "FocusBuddy.iss").read_text(encoding="utf-8")
        for setting in (
            "PrivilegesRequired=lowest",
            "DisableWelcomePage=yes",
            "DisableDirPage=no",
            "DisableReadyPage=yes",
            "DisableFinishedPage=yes",
            "OutputBaseFilename=FocusBuddy-Windows-Setup",
        ):
            self.assertIn(setting, installer)
        self.assertIn('Name: "{autodesktop}\\{#MyAppName}"', installer)
        self.assertNotIn("postinstall", installer)

    def test_windows_app_uses_a_native_webview_window(self):
        runtime = (ROOT / "focus_agent" / "web_app.py").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
        self.assertIn('webview.create_window(', runtime)
        self.assertIn('gui="edgechromium"', runtime)
        self.assertIn("DESKTOP_WINDOW_ARG", runtime)
        self.assertIn("pywebview", requirements.casefold())

    def test_windows_ui_defaults_to_no_model_required(self):
        page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("本机 AI 增强（可选）", page)
        self.assertIn('<input id="ai-plan-toggle" type="checkbox">', page)
        self.assertNotIn('<input id="ai-plan-toggle" type="checkbox" checked>', page)

    def test_public_artifact_names_are_stable_for_direct_links(self):
        script = (ROOT / "scripts" / "build_public_editions.ps1").read_text(encoding="utf-8")
        for name in (
            "FocusBuddy-Windows-Setup.exe",
            "FocusBuddy-Browser-Extension.zip",
            "FocusBuddy-Web.zip",
            "SHA256.txt",
        ):
            self.assertIn(name, script)
        self.assertIn("[bool]$IncludeLocalMusic = $false", script)


if __name__ == "__main__":
    unittest.main()
