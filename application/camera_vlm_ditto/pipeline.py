from __future__ import annotations
import io
import json
import pathlib
from typing import Any, Dict, Optional, Tuple, List
from PIL import Image

from .config import CONFIG, STATIC_MOUNT, DB_DEFAULT
from .utils import haversine_m, sha256_hex, load_image_bytes, make_thumbnail_b64
from .vlm import VisionClient
from .ditto_client import DittoClient
from .db import ImageRecord


def _public_url_for_path(path: str) -> str:
    p = pathlib.Path(path)
    try:
        if p.exists() and p.parent.name == "uploads":
            return f"{STATIC_MOUNT}/{p.name}"
    except Exception:
        pass
    return f"file://{p.resolve()}"


def _thing_id_for_image(rec: ImageRecord) -> str:
    """
    One Ditto Thing per image.

    Same convention as server:
      site01:<camera_id>-<image_id>
    """
    return f"site01:{rec.camera_id}-{rec.id}"


def process_record(
    rec: ImageRecord,
    vlm: VisionClient,
    ditto: DittoClient,
    proximity_m: float,
    iou_thr: float,  # unused (kept for compatibility)
    embed_thumbnail: bool,
    thumbnail_max: int,
    db_path: str = DB_DEFAULT,
) -> Tuple[bool, Optional[str]]:
    """
    Batch-mode processing: each image is its own Ditto thing.
    Compare to nearest image (any camera) within `proximity_m` meters.
    """
    thing_id = _thing_id_for_image(rec)
    ditto.ensure_thing(thing_id)

    raw = load_image_bytes(rec.path)
    try:
        pil = Image.open(io.BytesIO(raw)).convert("RGB")
        width, height = pil.width, pil.height
    except Exception:
        pil = None
        width = height = None

    analysis = vlm.analyze(raw)
    objects = analysis.get("objects", [])
    caption = analysis.get("caption", "")

    # Find nearest prior image (ANY camera), based on geo distance
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, lat, lon, detections_json, path FROM images WHERE id <> ? "
        "ORDER BY captured_at DESC",
        (rec.id,),
    )
    rows = cur.fetchall()
    conn.close()

    nearest_dist = float("inf")
    prev_objs: List[Dict[str, Any]] = []
    nearest_path = None
    for r in rows:
        try:
            d = haversine_m(rec.lat, rec.lon, r["lat"], r["lon"])
        except Exception:
            continue
        if d < nearest_dist:
            nearest_dist = d
            nearest_path = r["path"]
            try:
                pj = json.loads(r["detections_json"]) if r["detections_json"] else {}
                prev_objs = (
                    pj.get("objects", []) if isinstance(pj, dict) else (pj or [])
                )
            except Exception:
                prev_objs = []

    changed, reason = (False, "")
    if nearest_dist <= proximity_m and nearest_path:
        try:
            prev_bytes = load_image_bytes(nearest_path)
            # If file hash is identical, no change
            if sha256_hex(prev_bytes) != sha256_hex(raw):
                cmp = vlm.compare_change(prev_bytes, raw)
                changed, reason = (
                    bool(cmp.get("changed", False)),
                    str(cmp.get("reason", "")).strip(),
                )
                # Optional safeguard: if scene mismatch / low similarity, treat as changed
                scene_match = bool(cmp.get("scene_match", False))
                scene_similarity = float(cmp.get("scene_similarity", 0.0))
                if not scene_match or scene_similarity < 0.65:
                    changed = True
                    if not reason:
                        reason = "changed"
        except Exception:
            changed, reason = (False, "")

    image_url = _public_url_for_path(rec.path)
    last_capture = {
        "image_url": image_url,
        "image_hash": f"sha256:{sha256_hex(raw)}",
        "captured_at": rec.captured_at,
        "size_bytes": len(raw),
        "lat": float(rec.lat),
        "lon": float(rec.lon),
    }
    if width and height:
        last_capture.update({"width": width, "height": height})
    if embed_thumbnail and pil is not None:
        last_capture["thumbnail_b64"] = make_thumbnail_b64(pil, thumbnail_max)

    detections_payload = {
        "objects": objects,
        "caption": caption,
        "changed_since_previous": bool(changed),
        "change_reason": reason or "",
        "prev": {"objects": prev_objs},
    }

    # For per-image things, history is trivial (just this capture)
    history = [{k: v for k, v in last_capture.items() if k != "thumbnail_b64"}]

    ditto.patch_updates(
        thing_id,
        last_capture=last_capture,
        history=history,
        detections=detections_payload,
        max_len=1,
    )

    if changed and CONFIG["SEND_ALERT_MESSAGE"]:
        ditto.send_alert(
            thing_id,
            "alert",
            {
                "reason": reason or "major change detected",
                "thingId": thing_id,
                "image_url": image_url,
                "objects": objects,
            },
        )

    return bool(changed), reason
