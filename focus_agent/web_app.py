"""Modern local web control surface with a native cat-alert companion."""

from __future__ import annotations

import json
import mimetypes
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from .cat_alert import CatAlertWindow
from .controller import FocusController, NativeAlert, NativeReaction, NativeSuggestion
from .media_library import build_media_library
from .paths import resource_root, user_data_root


PROJECT_ROOT = resource_root()
WEB_ROOT = PROJECT_ROOT / "web"
DESKTOP_WINDOW_ARG = "--focus-buddy-desktop-window"


def _startup_trace(message: str) -> None:
    """Expose opt-in milestones for diagnosing packaged startup failures."""
    if os.environ.get("FOCUS_BUDDY_STARTUP_TRACE", "").strip() == "1":
        print(f"[FocusBuddyAI] {message}", flush=True)


def _desktop_window_command(url: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, DESKTOP_WINDOW_ARG, url]
    return [sys.executable, str(PROJECT_ROOT / "app.py"), DESKTOP_WINDOW_ARG, url]


def _run_desktop_window(url: str) -> None:
    """Host the local control surface in a native WebView2 window."""
    try:
        import webview

        storage = user_data_root() / "WebView2"
        storage.mkdir(parents=True, exist_ok=True)
        webview.create_window(
            "Focus Buddy",
            url,
            width=1440,
            height=900,
            min_size=(1040, 700),
            background_color="#0b2119",
            text_select=True,
        )
        webview.start(
            gui="edgechromium",
            private_mode=False,
            storage_path=str(storage),
        )
    except Exception as exc:
        _startup_trace(f"desktop window unavailable: {exc}")
        webbrowser.open(url, new=1)
        raise SystemExit(42) from exc


class FocusHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    # HTTPServer enables SO_REUSEADDR by default. On Windows this can let two
    # Focus Buddy editions bind the same port, while traffic keeps reaching the
    # older process. Every running edition must own a distinct port.
    allow_reuse_address = False

    def __init__(self, address, handler, controller: FocusController, shutdown_event: threading.Event):
        super().__init__(address, handler)
        self.controller = controller
        self.shutdown_event = shutdown_event
        self.ui_heartbeat = 0.0
        self.popup_count = 0
        self.popup_visible = False
        self.last_ui_error = ""

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class FocusRequestHandler(BaseHTTPRequestHandler):
    server: FocusHTTPServer

    def log_message(self, _format: str, *_args) -> None:
        return

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self, max_size: int = 100_000) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > max_size:
            raise ValueError("请求内容为空或过大")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("请求必须是JSON对象")
        return payload

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/state":
            self._json({"ok": True, "data": self.server.controller.status()})
            return
        if path == "/api/health":
            self._json({"ok": True, "data": {"service": "focus-buddy-ai", "version": 8}})
            return
        if path == "/api/ui/status":
            self._json(
                {
                    "ok": True,
                    "data": {
                        "loop_alive": time.monotonic() - self.server.ui_heartbeat < 1.5,
                        "popup_count": self.server.popup_count,
                        "popup_visible": self.server.popup_visible,
                        "last_error": self.server.last_ui_error,
                    },
                }
            )
            return
        if path == "/api/media/library":
            self._json({"ok": True, "data": build_media_library(PROJECT_ROOT)})
            return
        self._serve_static(path)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._read_json(
                8 * 1024 * 1024 if path == "/api/pet/custom/create" else 100_000
            )
            if path == "/api/plan":
                use_ai = payload.get("use_ai", True)
                if not isinstance(use_ai, bool):
                    raise ValueError("use_ai必须是布尔值")
                data = self.server.controller.plan_goal(
                    str(payload.get("goal", "")),
                    use_ai=use_ai,
                )
            elif path == "/api/preview/alert":
                data = self.server.controller.preview_alert()
            elif path == "/api/preview/reaction":
                data = self.server.controller.preview_reaction(str(payload.get("kind", "")))
            elif path == "/api/browser/active":
                data = self.server.controller.report_browser_tab(payload)
            elif path == "/api/pet/name":
                data = self.server.controller.rename_pet(str(payload.get("name", "")))
            elif path == "/api/pet/skin":
                data = self.server.controller.select_pet_skin(str(payload.get("skin", "")))
            elif path == "/api/pet/custom/create":
                data = self.server.controller.create_custom_pet(
                    str(payload.get("name", "")),
                    str(payload.get("image", "")),
                )
            elif path == "/api/pet/custom/delete":
                data = self.server.controller.delete_custom_pet(str(payload.get("id", "")))
            elif path == "/api/session/start":
                data = self.server.controller.start_session(payload)
            elif path == "/api/session/pause":
                data = self.server.controller.pause()
            elif path == "/api/session/resume":
                data = self.server.controller.resume()
            elif path == "/api/session/stop":
                data = self.server.controller.stop_session()
            elif path == "/api/suggestion/approve":
                data = self.server.controller.approve_suggestion(
                    str(payload.get("id", "")), bool(payload.get("remember", False))
                )
            elif path == "/api/suggestion/dismiss":
                data = self.server.controller.dismiss_suggestion(str(payload.get("id", "")))
            elif path == "/api/shutdown":
                self.server.shutdown_event.set()
                data = {"closing": True}
            else:
                self._json({"ok": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
                return
            self._json({"ok": True, "data": data})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._json({"ok": False, "error": f"本地服务暂时出错：{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            file_path = WEB_ROOT / "index.html"
        elif path.startswith("/media/music/"):
            relative = unquote(path.removeprefix("/media/music/"))
            source, separator, media_relative = relative.partition("/")
            if not separator:
                source, media_relative = "bundled", relative
            roots = {
                "bundled": PROJECT_ROOT / "Musics",
                "user": user_data_root() / "Musics",
            }
            media_root = roots.get(source)
            if media_root is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._serve_media(media_root / media_relative, media_root)
            return
        elif path.startswith("/media/picture/"):
            relative = unquote(path.removeprefix("/media/picture/"))
            file_path = PROJECT_ROOT / "pictures" / relative
        elif path.startswith("/media/custom-pet/"):
            relative = unquote(path.removeprefix("/media/custom-pet/"))
            media_root = user_data_root() / "custom_pets"
            self._serve_media(media_root / relative, media_root)
            return
        elif path.startswith("/assets/"):
            file_path = PROJECT_ROOT / unquote(path.lstrip("/"))
        else:
            file_path = WEB_ROOT / unquote(path.lstrip("/"))
        try:
            resolved = file_path.resolve()
            allowed_roots = (
                WEB_ROOT.resolve(),
                (PROJECT_ROOT / "assets").resolve(),
                (PROJECT_ROOT / "pictures").resolve(),
            )
            if not any(resolved == root or root in resolved.parents for root in allowed_roots):
                raise FileNotFoundError
            body = resolved.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if resolved.suffix in {".html", ".css", ".js"}:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        else:
            self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _serve_media(self, file_path: Path, allowed_root: Path) -> None:
        try:
            resolved = file_path.resolve()
            root = allowed_root.resolve()
            if root not in resolved.parents or not resolved.is_file():
                raise FileNotFoundError
            size = resolved.stat().st_size
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        start, end = 0, max(0, size - 1)
        status = HTTPStatus.OK
        range_header = self.headers.get("Range", "")
        if range_header.startswith("bytes=") and "," not in range_header:
            try:
                first, last = range_header[6:].split("-", 1)
                if first:
                    start = int(first)
                    end = min(end, int(last)) if last else end
                elif last:
                    length = min(size, int(last))
                    start = size - length
                if start < 0 or start > end or start >= size:
                    raise ValueError
                status = HTTPStatus.PARTIAL_CONTENT
            except ValueError:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return

        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", mimetypes.guess_type(str(resolved))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()

        with resolved.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining:
                chunk = handle.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)


def _port_is_occupied(port: int) -> bool:
    if port == 0:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.08):
            return True
    except OSError:
        return False


def _find_server(
    controller: FocusController,
    shutdown_event: threading.Event,
    ports=range(8765, 8776),
) -> FocusHTTPServer:
    for port in ports:
        if _port_is_occupied(port):
            continue
        try:
            return FocusHTTPServer(("127.0.0.1", port), FocusRequestHandler, controller, shutdown_event)
        except OSError:
            continue
    raise OSError("8765-8775端口均被占用")


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == DESKTOP_WINDOW_ARG:
        _run_desktop_window(sys.argv[2])
        return

    _startup_trace("creating Tk root")
    root = tk.Tk()
    root.withdraw()
    _startup_trace("creating controller")
    alert_queue: queue.Queue[NativeAlert] = queue.Queue()
    suggestion_queue: queue.Queue[NativeSuggestion] = queue.Queue()
    reaction_queue: queue.Queue[NativeReaction] = queue.Queue()
    controller = FocusController(
        on_alert=alert_queue.put,
        on_suggestion=suggestion_queue.put,
        on_reaction=reaction_queue.put,
    )
    _startup_trace("creating cat alert")
    cat_alert = CatAlertWindow(root, on_return=controller.return_to_focus)
    shutdown_event = threading.Event()
    _startup_trace("binding local server")
    server = _find_server(controller, shutdown_event)
    server_thread = threading.Thread(target=server.serve_forever, name="focus-web", daemon=True)
    server_thread.start()
    _startup_trace(f"server ready on {server.server_port}")
    url = f"http://127.0.0.1:{server.server_port}/"
    desktop_process: subprocess.Popen | None = None
    if os.environ.get("FOCUS_BUDDY_NO_BROWSER", "").strip() != "1":
        try:
            desktop_process = subprocess.Popen(
                _desktop_window_command(url),
                close_fds=True,
            )
        except OSError as exc:
            _startup_trace(f"desktop process unavailable: {exc}")
            threading.Thread(
                target=webbrowser.open,
                args=(url,),
                kwargs={"new": 1},
                name="focus-open-browser",
                daemon=True,
            ).start()

    def pump() -> None:
        nonlocal desktop_process
        server.ui_heartbeat = time.monotonic()
        if desktop_process is not None and desktop_process.poll() is not None:
            exit_code = desktop_process.returncode
            desktop_process = None
            if exit_code != 42:
                shutdown_event.set()
        try:
            suggestion = suggestion_queue.get_nowait()
            cat_alert.show_suggestion(
                suggestion,
                on_once=lambda item=suggestion: controller.approve_suggestion(
                    item.suggestion_id, remember=False
                ),
                on_remember=lambda item=suggestion: controller.approve_suggestion(
                    item.suggestion_id, remember=True
                ),
                on_dismiss=lambda item=suggestion: controller.dismiss_suggestion(
                    item.suggestion_id
                ),
            )
        except queue.Empty:
            pass
        except ValueError:
            pass
        except Exception as exc:
            server.last_ui_error = f"suggestion: {exc}"
        try:
            while True:
                cat_alert.show(alert_queue.get_nowait())
                root.update_idletasks()
                server.popup_count += 1
                server.popup_visible = bool(
                    cat_alert.window and cat_alert.window.winfo_viewable()
                )
        except queue.Empty:
            pass
        except Exception as exc:
            server.last_ui_error = f"alert: {exc}"
        try:
            while True:
                cat_alert.show_reaction(reaction_queue.get_nowait())
                root.update_idletasks()
                server.popup_count += 1
                server.popup_visible = bool(
                    cat_alert.window and cat_alert.window.winfo_viewable()
                )
        except queue.Empty:
            pass
        except Exception as exc:
            server.last_ui_error = f"reaction: {exc}"
        if shutdown_event.is_set():
            root.destroy()
            return
        root.after(100, pump)

    root.after(100, pump)
    try:
        root.mainloop()
    finally:
        cat_alert.close()
        controller.close()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
