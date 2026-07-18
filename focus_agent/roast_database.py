"""Small local SQLite library for context-aware humorous focus reminders."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .paths import resource_root, user_data_root


class RoastDatabase:
    """Seed, select and learn short lines without putting SQLite in the hot loop."""

    def __init__(self, path: Path | None = None, seed_path: Path | None = None):
        root = user_data_root()
        default_path = root / "focus.sqlite3"
        legacy_path = root / ("focus" + "_buddy.sqlite3")
        if path is None and not default_path.exists() and legacy_path.is_file():
            try:
                default_path.write_bytes(legacy_path.read_bytes())
            except OSError:
                pass
        self.path = Path(path or default_path)
        self.seed_path = Path(seed_path or resource_root() / "data" / "roast_lines.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seed = self._read_seed()
        self._keywords = {
            category: tuple(str(word).casefold() for word in payload.get("keywords", []))
            for category, payload in self._seed.get("categories", {}).items()
            if category != "general"
        }
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=3)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _read_seed(self) -> dict:
        try:
            payload = json.loads(self.seed_path.read_text(encoding="utf-8"))
            if not isinstance(payload.get("categories"), dict):
                raise ValueError
            return payload
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise RuntimeError("提示语种子库无法读取") from error

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS roast_lines (
                    id INTEGER PRIMARY KEY,
                    category TEXT NOT NULL,
                    intensity TEXT NOT NULL,
                    line TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL DEFAULT 'curated',
                    use_count INTEGER NOT NULL DEFAULT 0,
                    last_used_at TEXT
                )
                """
            )
            rows = []
            for category, payload in self._seed["categories"].items():
                for intensity in ("mild", "spicy"):
                    rows.extend(
                        (category, intensity, str(line), "curated")
                        for line in payload.get("lines", {}).get(intensity, [])
                    )
            connection.executemany(
                """
                INSERT OR IGNORE INTO roast_lines(category, intensity, line, source)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )

    def classify_target(self, target: str) -> str:
        normalized = str(target or "").casefold()
        for category, keywords in self._keywords.items():
            if any(keyword in normalized for keyword in keywords):
                return category
        return "general"

    def pick(self, target: str, intensity: str = "mild") -> str | None:
        intensity = intensity if intensity in {"mild", "spicy"} else "mild"
        category = self.classify_target(target)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id, line FROM roast_lines
                WHERE category = ? AND intensity = ?
                ORDER BY use_count ASC, COALESCE(last_used_at, '') ASC, RANDOM()
                LIMIT 1
                """,
                (category, intensity),
            ).fetchone()
            if row is None and category != "general":
                row = connection.execute(
                    """
                    SELECT id, line FROM roast_lines
                    WHERE category = 'general' AND intensity = ?
                    ORDER BY use_count ASC, COALESCE(last_used_at, '') ASC, RANDOM()
                    LIMIT 1
                    """,
                    (intensity,),
                ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE roast_lines SET use_count = use_count + 1, last_used_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), row["id"]),
            )
            return str(row["line"])

    def add_generated(self, line: str, target: str, intensity: str) -> None:
        intensity = intensity if intensity in {"mild", "spicy"} else "mild"
        with self._connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO roast_lines(category, intensity, line, source)
                VALUES (?, ?, ?, 'ollama')
                """,
                (self.classify_target(target), intensity, str(line)),
            )

    def stats(self) -> dict:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS line_count,
                       COUNT(DISTINCT category) AS category_count,
                       SUM(CASE WHEN source = 'ollama' THEN 1 ELSE 0 END) AS generated_count,
                       COALESCE(SUM(use_count), 0) AS used_count
                FROM roast_lines
                """
            ).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}
