from __future__ import annotations
import io
import json
import pathlib
from typing import Any, Dict, Optional, Tuple, List
from PIL import Image

from .config import CONFIG, STATIC_MOUNT, DB_DEFAULT
from .utils import haversine_m, sha256_hex, load_image_bytes, make_thumbnail_b64, pixel_hash
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
    Batch-mode processing.

    For consistency with the HTTP /upload flow, we:
      - Look at all other images within `proximity_m` meters of this record.
      - If any baseline shows "major change" via compare_change, we treat this
        image as changed vs. that baseline.
      - Otherwise we treat this as not changed (but still push to Ditto).

    NOTE: In batch mode we do NOT mutate other DB rows; mutation is handled
    by the ingestion flow. This function only decides changed/reason and
    pushes to Ditto for the current `rec`.
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

    # Look for *all* candidate baselines within `proximity_m`
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, lat, lon, detections_json, path FROM images WHERE id <> ?",
        (rec.id,),
    )
    rows = cur.fetchall()
    conn.close()

    candidates: List[Dict[str, Any]] = []
    for r in rows:
        try:
            d = haversine_m(rec.lat, rec.lon, r["lat"], r["lon"])
        except Exception:
            continue
        if d <= proximity_m:
            candidates.append(
                {
                    "id": int(r["id"]),
                    "lat": r["lat"],
                    "lon": r["lon"],
                    "detections_json": r["detections_json"],
                    "path": r["path"],
                    "distance": float(d),
                }
            )

    baseline_change = None
    baseline_prev_objs: List[Dict[str, Any]] = []

    for c in candidates:
        prev_path = c["path"]
        if not prev_path:
            continue
        try:
            prev_raw = load_image_bytes(prev_path)
        except Exception:
            continue

        # Parse previous objects from detections_json
        prev_objs_local: List[Dict[str, Any]] = []
        try:
            pj = json.loads(c["detections_json"]) if c["detections_json"] else {}
            prev_objs_local = (
                pj.get("objects", [])
                if isinstance(pj, dict)
                else (pj or [])
            )
        except Exception:
            prev_objs_local = []

        # Fast equality checks
        try:
            if sha256_hex(prev_raw) == sha256_hex(raw):
                continue
            if pixel_hash(prev_raw) == pixel_hash(raw):
                continue
        except Exception:
            pass

        # Call VLM compare_change
        try:
            cmp = vlm.compare_change(prev_raw, raw)
            is_changed = bool(cmp.get("changed", False))
            reason_local = str(cmp.get("reason", "")).strip()
        except Exception:
            is_changed = False
            reason_local = ""

        if is_changed:
            if baseline_change is None or c["distance"] < baseline_change["distance"]:
                baseline_change = {**c, "reason": reason_local}
                baseline_prev_objs = prev_objs_local

    if baseline_change is not None:
        changed, reason = (True, baseline_change.get("reason") or "changed")
        prev_objs = baseline_prev_objs
    else:
        changed, reason = (False, "")
        prev_objs = []

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

    # For per-image things in batch mode, history is trivial
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
