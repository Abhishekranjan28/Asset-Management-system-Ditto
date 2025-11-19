from __future__ import annotations

import math
import hashlib
import io
import base64
from pathlib import Path
from typing import List, Dict, Any
from PIL import Image, ImageOps  # ImageOps for EXIF orientation

from .config import DB_DEFAULT, UPLOAD_DIR, STATIC_MOUNT


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between two WGS84 points."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_image_bytes(path: str) -> bytes:
    """Read image bytes from a path (raises same exceptions as open())."""
    with open(path, "rb") as f:
        return f.read()


def make_thumbnail_b64(img: Image.Image, max_side: int = 256) -> str:
    """Return base64-encoded JPEG thumbnail (longest side max_side)."""
    img = img.copy()
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def pixel_hash(image_bytes: bytes) -> str:
    """
    Hash image *content* not file bytes:
      - apply EXIF orientation
      - strip metadata
      - convert to RGB
      - resize to a fixed, deterministic size
      - hash raw pixel buffer
    """
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((512, 512), Image.LANCZOS)
        return sha256_hex(im.tobytes())
