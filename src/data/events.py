"""
events.py
Event tagging system — correlate LR operations with performance data.
Tags are stored in the session SQLite database.
"""

import time
import sqlite3
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class LROperation(Enum):
    IMPORT          = "Import"
    EXPORT          = "Export"
    RENDER_PREVIEWS = "Render Previews"
    CATALOG_SAVE    = "Catalog Save"
    DEVELOP_MODULE  = "Develop Module"
    LIBRARY_MODULE  = "Library Module"
    SLIDESHOW       = "Slideshow / Print / Web"
    SYNC            = "Sync / Publish"
    CUSTOM          = "Custom"


OPERATION_ICONS = {
    LROperation.IMPORT:          "⬇",
    LROperation.EXPORT:          "⬆",
    LROperation.RENDER_PREVIEWS: "🖼",
    LROperation.CATALOG_SAVE:    "💾",
    LROperation.DEVELOP_MODULE:  "🎨",
    LROperation.LIBRARY_MODULE:  "📚",
    LROperation.SLIDESHOW:       "▶",
    LROperation.SYNC:            "🔄",
    LROperation.CUSTOM:          "📌",
}

OPERATION_COLORS = {
    LROperation.IMPORT:          "#89b4fa",  # blue
    LROperation.EXPORT:          "#a6e3a1",  # green
    LROperation.RENDER_PREVIEWS: "#f9e2af",  # yellow
    LROperation.CATALOG_SAVE:    "#94e2d5",  # teal
    LROperation.DEVELOP_MODULE:  "#cba6f7",  # purple
    LROperation.LIBRARY_MODULE:  "#89dceb",  # sky
    LROperation.SLIDESHOW:       "#fab387",  # peach
    LROperation.SYNC:            "#f38ba8",  # red
    LROperation.CUSTOM:          "#a6adc8",  # grey
}


@dataclass
class EventTag:
    id: Optional[int]
    timestamp: float
    operation: LROperation
    note: str = ""
    snapshot_index: Optional[int] = None  # index into session history at tag time

    @property
    def label(self) -> str:
        icon = OPERATION_ICONS.get(self.operation, "📌")
        base = f"{icon} {self.operation.value}"
        if self.note:
            base += f" — {self.note}"
        return base

    @property
    def color(self) -> str:
        return OPERATION_COLORS.get(self.operation, "#a6adc8")

    @property
    def time_str(self) -> str:
        import datetime
        return datetime.datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")


class EventStore:
    """Manages event tags within a session SQLite database."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._create_table()

    def _create_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS event_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                operation TEXT NOT NULL,
                note TEXT DEFAULT '',
                snapshot_index INTEGER
            )
        """)
        self._conn.commit()

    def add_tag(self, operation: LROperation, note: str = "",
                snapshot_index: int = None) -> EventTag:
        now = time.time()
        cursor = self._conn.execute(
            "INSERT INTO event_tags (timestamp, operation, note, snapshot_index) VALUES (?, ?, ?, ?)",
            (now, operation.value, note, snapshot_index)
        )
        self._conn.commit()
        return EventTag(
            id=cursor.lastrowid,
            timestamp=now,
            operation=operation,
            note=note,
            snapshot_index=snapshot_index,
        )

    def get_all(self) -> List[EventTag]:
        rows = self._conn.execute(
            "SELECT id, timestamp, operation, note, snapshot_index FROM event_tags ORDER BY timestamp"
        ).fetchall()
        tags = []
        for row in rows:
            try:
                op = LROperation(row[2])
            except ValueError:
                op = LROperation.CUSTOM
            tags.append(EventTag(
                id=row[0],
                timestamp=row[1],
                operation=op,
                note=row[3] or "",
                snapshot_index=row[4],
            ))
        return tags

    def delete_tag(self, tag_id: int):
        self._conn.execute("DELETE FROM event_tags WHERE id = ?", (tag_id,))
        self._conn.commit()
