"""Read-only catalog for small bundled and user-owned focus ambience files."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import quote

from .paths import resource_root, user_data_root


PLAYABLE_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a"}

CATEGORIES = (
    {"id": "rain", "label": "雨幕", "icon": "☂", "description": "雨声、雷声与屋檐水滴"},
    {"id": "water", "label": "溪流", "icon": "≈", "description": "泉水与缓慢流动的水声"},
    {"id": "ocean", "label": "海岸", "icon": "◒", "description": "浪花、卵石与海边空气"},
    {"id": "birds", "label": "鸟鸣", "icon": "⌁", "description": "林间鸟声与自然清晨"},
    {"id": "sunny", "label": "晴日", "icon": "✦", "description": "轻盈、明亮的日间环境声"},
    {"id": "ambient", "label": "漫游", "icon": "∞", "description": "不打断思路的自然氛围"},
)

SYNTHETIC_TRACKS = (
    {
        "id": "synth-rain",
        "title": "窗边雨幕",
        "artist": "Focus Buddy 合成声景",
        "category": "rain",
        "url": "",
        "source": "synth",
        "size_mb": 0,
    },
    {
        "id": "synth-stream",
        "title": "缓慢溪流",
        "artist": "Focus Buddy 合成声景",
        "category": "water",
        "url": "",
        "source": "synth",
        "size_mb": 0,
    },
    {
        "id": "synth-ocean",
        "title": "深夜海岸",
        "artist": "Focus Buddy 合成声景",
        "category": "ocean",
        "url": "",
        "source": "synth",
        "size_mb": 0,
    },
    {
        "id": "synth-forest",
        "title": "林间微风",
        "artist": "Focus Buddy 合成声景",
        "category": "birds",
        "url": "",
        "source": "synth",
        "size_mb": 0,
    },
)


def _category(filename: str) -> str:
    name = filename.casefold()
    if any(word in name for word in ("rain", "thunder", "hail", "raindrop", "storm", "雨", "비", "빗소리")):
        return "rain"
    if any(word in name for word in ("surf", "beach", "ocean", "wave", "海")):
        return "ocean"
    if any(word in name for word in ("bird", "鸟", "鳥")):
        return "birds"
    if any(word in name for word in ("stream", "spring", "water", "溪", "泉")):
        return "water"
    if any(word in name for word in ("fresh air", "sun", "晴", "春")):
        return "sunny"
    return "ambient"


def _media_url(relative_path: Path, source: str = "bundled") -> str:
    encoded = "/".join(quote(part, safe="") for part in relative_path.parts)
    return f"/media/music/{source}/{encoded}"


def build_media_library(project_root: Path | None = None, data_root: Path | None = None) -> dict:
    root = project_root or resource_root()
    writable_root = data_root or user_data_root()
    user_music_root = writable_root / "Musics"
    user_music_root.mkdir(parents=True, exist_ok=True)
    # The curated pack is intentionally short Opus audio and is always bundled.
    # A user's full-size collection stays outside the executable in AppData.
    music_roots = (
        ("bundled", root / "assets" / "soundscapes"),
        ("user", user_music_root),
        # Source checkouts may still expose the gitignored Musics directory.
        # Packaged builds do not include it unless explicitly requested.
        ("local", root / "Musics"),
    )
    tracks: list[dict] = []
    unavailable = 0
    seen_files: set[tuple[str, str]] = set()
    for source, music_root in music_roots:
        if not music_root.exists():
            continue
        for path in sorted(music_root.rglob("*"), key=lambda item: item.name.casefold()):
            if not path.is_file():
                continue
            if path.suffix.casefold() == ".ncm":
                unavailable += 1
                continue
            if path.suffix.casefold() not in PLAYABLE_EXTENSIONS:
                continue
            relative = path.relative_to(music_root)
            identity = (source, relative.as_posix().casefold())
            if identity in seen_files:
                continue
            seen_files.add(identity)
            stem = path.stem
            if " - " in stem:
                artist, title = stem.split(" - ", 1)
            else:
                artist, title = "自然采样", stem
            tracks.append(
                {
                    "id": hashlib.sha1(f"{source}:{relative.as_posix()}".encode("utf-8")).hexdigest()[:12],
                    "title": title.strip(),
                    "artist": artist.strip(),
                    "category": _category(stem),
                    "url": _media_url(relative, source),
                    "source": source,
                    "size_mb": round(path.stat().st_size / 1024 / 1024, 1),
                }
            )
    # Keep a zero-byte Web Audio fallback only for installs with no playable
    # files. Real recordings should never be mixed with the old synthetic set.
    if not tracks:
        tracks = [dict(item) for item in SYNTHETIC_TRACKS]
    synth_count = sum(1 for track in tracks if track["source"] == "synth")
    counts = {item["id"]: 0 for item in CATEGORIES}
    for track in tracks:
        counts[track["category"]] += 1
    categories = [{**item, "count": counts[item["id"]]} for item in CATEGORIES if counts[item["id"]]]
    return {
        "tracks": tracks,
        "categories": categories,
        "playable_count": len(tracks),
        "synth_count": synth_count,
        "file_count": len(tracks) - synth_count,
        "unavailable_count": unavailable,
    }
