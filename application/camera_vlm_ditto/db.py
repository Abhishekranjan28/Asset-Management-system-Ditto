from __future__ import annotations
from dataclasses import dataclass
from typing import List
import sqlite3

from .config import DB_DEFAULT


@dataclass
class ImageRecord:
    id: int
    camera_id: str
    path: str
    lat: float
    lon: float
    captured_at: str


def ensure_schema(db_path: str = DB_DEFAULT):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY,
            camera_id TEXT NOT NULL,
            path TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            captured_at TEXT NOT NULL,
            processed INTEGER DEFAULT 0,
            detections_json TEXT,
            caption TEXT,
            changed INTEGER DEFAULT 0,
            reason TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def fetch_new_images(db_path: str, limit: int = 20) -> List[ImageRecord]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, camera_id, path, lat, lon, captured_at
        FROM images
        WHERE processed = 0
        ORDER BY captured_at ASC
        LIMIT ?
        """,
        (limit,),
    )
    rows = [ImageRecord(**dict(r)) for r in cur.fetchall()]
    conn.close()
    return rows


def mark_processed(db_path: str, row_ids: List[int]):
    if not row_ids:
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        f"UPDATE images SET processed = 1 WHERE id IN ({','.join('?' * len(row_ids))})",
        row_ids,
    )
    conn.commit()
    conn.close()
