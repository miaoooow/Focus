# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path


project_root = Path(SPECPATH)
datas = [
    (str(project_root / "web"), "web"),
    (str(project_root / "data"), "data"),
    (str(project_root / "pictures"), "pictures"),
    (str(project_root / "assets"), "assets"),
]

# Local tracks are optional because public redistribution requires the owner to
# verify audio licences. The personal/demo build can include playable formats
# while encrypted NCM and lyric sidecars are always excluded.
if os.environ.get("FOCUS_BUNDLE_MUSIC", "0") == "1":
    music_root = project_root / "Musics"
    for track in music_root.rglob("*"):
        if track.is_file() and track.suffix.casefold() in {".mp3", ".wav", ".ogg", ".m4a"}:
            destination = Path("Musics") / track.relative_to(music_root).parent
            datas.append((str(track), str(destination)))


a = Analysis(
    [str(project_root / "app.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Focus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=os.environ.get("FOCUS_CONSOLE_BUILD", "0") == "1",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=str(project_root / "assets" / "branding" / "focus.ico"),
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Focus",
)
