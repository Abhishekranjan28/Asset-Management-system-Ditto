from __future__ import annotations
import os
import pathlib


CONFIG = {
    "GEMINI_MODEL": "gemini-2.5-flash",  # or gemini-1.5-pro
    "GEMINI_MAX_IMAGE_BYTES": 6_000_000,
    "PROXIMITY_METERS": 10.0,  # compare to images within this radius (meters)
    "IOU_THRESHOLD": 0.5,      # kept for compatibility
    "SEND_ALERT_MESSAGE": True,
    "EMBED_THUMBNAIL": True,
    "THUMBNAIL_MAX_SIZE": 256,
    "DITTO_HISTORY_MAX": 20,
}


DITTO_BASE_URL = os.getenv("DITTO_BASE_URL", "http://localhost:8080")
DITTO_USER = os.getenv("DITTO_USER", "ditto")
DITTO_PASS = os.getenv("DITTO_PASS", "ditto")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

APP_DATA_DIR = os.getenv("APP_DATA_DIR", str(pathlib.Path(__file__).parent.resolve()))
UPLOAD_DIR = pathlib.Path(APP_DATA_DIR) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DB_DEFAULT = os.getenv("DB_PATH", str(pathlib.Path(APP_DATA_DIR) / "images.db"))
STATIC_MOUNT = "/static"  # public URL prefix served by Flask
