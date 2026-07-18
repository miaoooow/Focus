import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicEditionTests(unittest.TestCase):
    def test_browser_extension_contains_only_runtime_files(self):
        folder = ROOT / "browser_extension_standalone"
        self.assertEqual(
            {item.name for item in folder.iterdir() if item.is_file()},
            {"manifest.json", "background.js", "bridge.js", "popup.html", "popup.css", "popup.js"},
        )
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["version"], "4.1.0")
        self.assertEqual(
            set(manifest["permissions"]),
            {"storage", "tabs", "alarms", "notifications"},
        )
        self.assertEqual(manifest["host_permissions"], ["http://127.0.0.1/*"])
        self.assertIn("https://miaoooow.github.io/Focus/*", manifest["content_scripts"][0]["matches"])
        self.assertNotIn("http://127.0.0.1/*", manifest["content_scripts"][0]["matches"])
        popup = (folder / "popup.js").read_text(encoding="utf-8")
        background = (folder / "background.js").read_text(encoding="utf-8")
        self.assertIn('chrome.runtime.getURL("focus.html")', popup)
        self.assertIn('page.searchParams.set("domain", domain)', popup)
        self.assertIn("activeTabSummary", background)
        self.assertIn("lastEvent", background)
        self.assertIn("publishActiveTabToDesktop", background)
        self.assertIn("focus-page-v1", (folder / "bridge.js").read_text(encoding="utf-8"))

    def test_web_edition_contains_only_runtime_files(self):
        folder = ROOT / "web_standalone"
        self.assertEqual(
            {item.name for item in folder.iterdir() if item.is_file()},
            {"index.html", "styles.css", "app.js", "manifest.webmanifest", "sw.js"},
        )
        manifest = json.loads((folder / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "./")
        self.assertIn("Focus 扩展是完整监督的必选组件", (folder / "index.html").read_text(encoding="utf-8"))
        page = (folder / "index.html").read_text(encoding="utf-8")
        script = (folder / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="pet-photo"', page)
        self.assertIn('id="pet-name"', page)
        self.assertIn("createPetActionSet", script)
        self.assertIn("petActions", script)
        self.assertIn('id="pet-renderer-web"', page)
        self.assertIn('cloudApi("/v1/pet"', script)
        self.assertIn("prepareCloudPetImage", script)
        self.assertIn(
            "releases/latest/download/Focus-Browser-Extension.zip",
            page,
        )
        self.assertNotIn("createNoiseBuffer", script)
        self.assertIn("assets/soundscapes", (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8"))
        self.assertIn("extensionConnected", script)
        self.assertIn("focus-page-v1", script)
        self.assertIn('extensionSend("start"', script)
        self.assertIn('id="allowed-domains"', page)
        for sound in (ROOT / "assets" / "soundscapes").glob("*.ogg"):
            self.assertIn(sound.name, page)
            self.assertIn(sound.name, (folder / "sw.js").read_text(encoding="utf-8"))

    def test_readme_explains_three_editions_and_attribution(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in ("Windows EXE", "Focus 浏览器扩展", "网页版", "项目结构"):
            self.assertIn(phrase, readme)
        self.assertIn("YouTube 博主 **mocha.**", readme)
        self.assertIn("声音花园", readme)
        self.assertNotIn("Focus Buddy", readme)
        self.assertIn("github.com/miaoooow/Focus/", readme)
        self.assertIn("Focus Cloud", readme)
        self.assertIn("都使用同一个 Focus 浏览器扩展", readme)
        for asset in (
            "releases/latest/download/Focus-Windows-Setup.exe",
            "releases/latest/download/Focus-Browser-Extension.zip",
            "releases/latest/download/Focus-Web.zip",
        ):
            self.assertIn(asset, readme)
        self.assertNotIn(r"D:\Agent", readme)
        self.assertNotIn("设计说明书.docx", readme)

    def test_pages_workflow_deploys_only_web_edition(self):
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertIn("path: site", workflow)
        self.assertIn("cp pictures/*.png site/media/", workflow)
        self.assertIn("cp assets/soundscapes/*.ogg site/media/sounds/", workflow)
        self.assertIn("actions/upload-pages-artifact@v4", workflow)
        self.assertIn("test -f web_standalone/index.html", workflow)
        self.assertNotIn("path: .", workflow)

    def test_windows_installer_is_per_user_and_one_click(self):
        installer = (ROOT / "installer" / "Focus.iss").read_text(encoding="utf-8")
        for setting in (
            "PrivilegesRequired=lowest",
            "DisableWelcomePage=yes",
            "DisableDirPage=no",
            "DisableReadyPage=yes",
            "DisableFinishedPage=yes",
            "OutputBaseFilename=Focus-Windows-Setup",
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
        self.assertIn("AI 增强（可选）", page)
        self.assertIn('id="ai-settings-dialog"', page)
        self.assertIn("Windows DPAPI", page)
        self.assertIn('<input id="ai-plan-toggle" type="checkbox">', page)
        self.assertNotIn('<input id="ai-plan-toggle" type="checkbox" checked>', page)

    def test_windows_brand_assets_and_curated_audio_are_packaged(self):
        spec = (ROOT / "Focus.spec").read_text(encoding="utf-8")
        installer = (ROOT / "installer" / "Focus.iss").read_text(encoding="utf-8")
        self.assertIn('"assets"', spec)
        self.assertIn("focus.ico", spec)
        self.assertIn("SetupIconFile=", installer)
        self.assertTrue((ROOT / "assets" / "branding" / "focus-icon.png").is_file())
        self.assertTrue((ROOT / "assets" / "branding" / "focus.ico").is_file())
        soundscapes = list((ROOT / "assets" / "soundscapes").glob("*.ogg"))
        self.assertEqual(len(soundscapes), 4)
        self.assertLess(sum(path.stat().st_size for path in soundscapes), 9 * 1024 * 1024)

    def test_public_artifact_names_are_stable_for_direct_links(self):
        script = (ROOT / "scripts" / "build_public_editions.ps1").read_text(encoding="utf-8")
        for name in (
            "Focus-Windows-Setup.exe",
            "Focus-Browser-Extension.zip",
            "Focus-Web.zip",
            "SHA256.txt",
        ):
            self.assertIn(name, script)
        self.assertIn("[bool]$IncludeLocalMusic = $false", script)
        self.assertIn("web_standalone\\index.html", script)
        self.assertIn("BrowserStage 'focus.html'", script)
        self.assertIn("$BrowserMedia", script)
        self.assertIn("$BrowserSounds", script)
        self.assertIn("$WebSounds", script)
        self.assertIn("data\\focus_cloud.json", script)

    def test_focus_cloud_gateway_uses_accounts_and_real_image_to_image(self):
        worker = (ROOT / "focus_cloud" / "src" / "index.js").read_text(encoding="utf-8")
        config = (ROOT / "focus_cloud" / "wrangler.toml").read_text(encoding="utf-8")
        schema = (ROOT / "focus_cloud" / "schema.sql").read_text(encoding="utf-8")
        self.assertIn("PBKDF2", worker)
        self.assertIn("token_hash", worker)
        self.assertIn("/v1/auth/register", worker)
        self.assertIn("/v1/auth/login", worker)
        self.assertIn("@cf/runwayml/stable-diffusion-v1-5-img2img", worker)
        self.assertIn("image_b64", worker)
        self.assertIn("@cf/runwayml/stable-diffusion-v1-5-img2img", config)
        self.assertIn("CREATE TABLE IF NOT EXISTS users", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS sessions", schema)


if __name__ == "__main__":
    unittest.main()
