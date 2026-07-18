"""Build the small redistributable Focus ambience pack from local tracks.

The original files stay in ``Musics`` (gitignored). Only the short, compressed
Opus derivatives under ``assets/soundscapes`` are included in public builds.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Musics"
OUTPUT_ROOT = ROOT / "assets" / "soundscapes"

TRACKS = (
    (
        "The Nature Sounds SocietyJapan - Rain, Totoro Forest.mp3",
        "The Nature Sounds SocietyJapan - 雨落森林.ogg",
    ),
    (
        "The Nature Sounds SocietyJapan - Small Stream.mp3",
        "The Nature Sounds SocietyJapan - 林间溪流.ogg",
    ),
    (
        "Echoes of Nature - Pebble Beach.mp3",
        "Echoes of Nature - 卵石海岸.ogg",
    ),
    (
        "The Nature Sounds SocietyJapan - Stream and Bird.mp3",
        "The Nature Sounds SocietyJapan - 溪流与鸟鸣.ogg",
    ),
)


def find_ffmpeg(explicit: str) -> str:
    candidates = [explicit, shutil.which("ffmpeg") or ""]
    try:
        import imageio_ffmpeg

        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError:
        pass
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit(
        "找不到 FFmpeg。可安装 imageio-ffmpeg，或传入 --ffmpeg <ffmpeg.exe>。"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg", default="")
    parser.add_argument("--duration", type=int, default=360)
    args = parser.parse_args()
    ffmpeg = find_ffmpeg(args.ffmpeg)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    for source_name, output_name in TRACKS:
        source = SOURCE_ROOT / source_name
        if not source.is_file():
            raise SystemExit(f"缺少本地源音频：{source}")
        output = OUTPUT_ROOT / output_name
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-t",
            str(max(60, args.duration)),
            "-vn",
            "-map_metadata",
            "-1",
            "-ac",
            "1",
            "-ar",
            "24000",
            "-c:a",
            "libopus",
            "-b:a",
            "48k",
            "-vbr",
            "on",
            "-application",
            "audio",
            str(output),
        ]
        subprocess.run(command, check=True)
        print(f"{output.name}: {output.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
