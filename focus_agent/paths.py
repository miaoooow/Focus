"""Stable resource and writable-data paths for source and packaged builds."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


APP_DIR_NAME = "Focus"
LEGACY_APP_DIR_NAME = "Focus" + "BuddyAI"


def resource_root() -> Path:
    """Return the read-only application resource root.

    PyInstaller exposes bundled files through ``sys._MEIPASS``. Source runs
    continue to use the project root so the existing development workflow is
    unchanged.
    """
    override = os.environ.get("FOCUS_AGENT_RESOURCE_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        bundled_root = getattr(sys, "_MEIPASS", "")
        if bundled_root:
            return Path(bundled_root).resolve()
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_root() -> Path:
    """Return a writable location for profiles and learned local data."""
    override = os.environ.get("FOCUS_AGENT_DATA_DIR", "").strip()
    if override:
        root = Path(override).expanduser().resolve()
    elif getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        root = base / APP_DIR_NAME
        legacy_root = base / LEGACY_APP_DIR_NAME
        if not root.exists() and legacy_root.is_dir():
            try:
                shutil.copytree(legacy_root, root)
            except OSError:
                # A locked legacy cache must never prevent Focus from starting.
                pass
    else:
        root = resource_root() / ".runtime"
    root.mkdir(parents=True, exist_ok=True)
    return root


def browser_extension_root() -> Path:
    """Return the user-loadable browser extension folder."""
    if getattr(sys, "frozen", False):
        beside_executable = Path(sys.executable).resolve().parent / "browser_extension"
        if beside_executable.exists():
            return beside_executable
    return resource_root() / "browser_extension"
