from __future__ import annotations
import io
import json
import pathlib
from typing import Any, Dict, Optional, Tuple, List
import sqlite3
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


def _thing_id_for_image(camera_id: str, image_id: int) -> str:
    """
    One Ditto Thing per baseline DB row.

    Same convention as server:
      site01:<camera_id>-<image_id>
    """
    return f"site01:{camera_id}-{image_id}"


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
    Batch-mode processing with the SAME semantics as the live /upload flow:

    Given an unprocessed DB row `rec`:
      - Load its image from disk.
      - Compare to ALL existing images in DB (excluding rec.id).

      Rules:

      1. If ANY existing image is within <= proximity_m AND a major change is detected:
           * Use that existing row as the baseline.
           * Update that baseline row with the new capture (path, lat, lon, captured_at, caption, detections, changed=1, reason).
           * Append to Ditto history for that Thing.
           * Rec row is just marked processed=1 (it’s a “raw ingestion” row).

      2. If there is an existing image within <= proximity_m AND no major change is detected:
           * Use the nearest existing row as baseline.
           * Update that baseline row with the new capture (changed=0, reason="").
           * Append to Ditto history.
           * Rec row is marked processed=1.

      3. If NO existing image is within <= proximity_m:
           * Treat `rec` itself as the baseline.
           * Update its row with caption, detections, changed=0.
           * Create a new Ditto Thing and set history=[this capture].
           * Mark rec row processed=1.
    """
    # Load new image bytes (rec.path already exists)
    raw = load_image_bytes(rec.path)

    # Analyze new image once
    analysis = vlm.analyze(raw)
    new_objs = analysis.get("objects", [])
    caption = analysis.get("caption", "")

    # DB connection
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Existing rows EXCEPT rec.id
    cur.execute(
        "SELECT id,camera_id,path,lat,lon,detections_json FROM images WHERE id <> ?",
        (rec.id,),
    )
    rows = cur.fetchall()

    # --- Same baseline logic as server ---

    candidates: List[Tuple[float, sqlite3.Row]] = []
    for r in rows:
        try:
            d = haversine_m(rec.lat, rec.lon, r["lat"], r["lon"])
        except Exception:
            continue
        if d <= proximity_m:
            candidates.append((d, r))

    candidates.sort(key=lambda x: x[0])

    raw_hash = sha256_hex(raw)
    pixel_hash_new: Optional[str] = None

    baseline_row: Optional[sqlite3.Row] = None
    baseline_dist: Optional[float] = None
    prev_objs_for_baseline: List[Dict[str, Any]] = []
    major_changed = False
    change_reason = ""

    minor_candidate_row: Optional[sqlite3.Row] = None
    minor_candidate_dist: Optional[float] = None
    minor_prev_objs: List[Dict[str, Any]] = []

    for dist, r in candidates:
        if minor_candidate_row is None:
            minor_candidate_row = r
            minor_candidate_dist = dist
            try:
                pj = (
                    json.loads(r["detections_json"]) if r["detections_json"] else {}
                )
                minor_prev_objs = (
                    pj.get("objects", [])
                    if isinstance(pj, dict)
                    else (pj or [])
                )
            except Exception:
                minor_prev_objs = []

        prev_path = r["path"]
        if not prev_path:
            continue
        try:
            prev_raw = load_image_bytes(prev_path)
        except Exception:
            continue

        # Fast equality
        if sha256_hex(prev_raw) == raw_hash:
            continue
        if pixel_hash_new is None:
            pixel_hash_new = pixel_hash(raw)
        try:
            if pixel_hash(prev_raw) == pixel_hash_new:
                continue
        except Exception:
            pass

        cmp = vlm.compare_change(prev_raw, raw)
        changed = bool(cmp.get("changed", False))
        reason = str(cmp.get("reason", "")).strip()

        if changed:
            major_changed = True
            change_reason = reason or "changed"
            baseline_row = r
            baseline_dist = dist
            try:
                pj = (
                    json.loads(r["detections_json"])
                    if r["detections_json"]
                    else {}
                )
                prev_objs_for_baseline = (
                    pj.get("objects", [])
                    if isinstance(pj, dict)
                    else (pj or [])
                )
            except Exception:
                prev_objs_for_baseline = []
            break

    if major_changed:
        mode = "baseline_major"
    elif minor_candidate_row is not None:
        mode = "baseline_minor"
        baseline_row = minor_candidate_row
        baseline_dist = minor_candidate_dist
        prev_objs_for_baseline = minor_prev_objs
        change_reason = ""
    else:
        mode = "new_thing"
        baseline_row = None
        baseline_dist = None
        prev_objs_for_baseline = []

    # --- DB updates ---

    if mode == "new_thing":
        # Rule #3: rec itself becomes baseline; update its row
        changed_flag = 0
        reason_db = ""
        image_id = rec.id
        baseline_camera_id = rec.camera_id
        nearest_id = None
        nearest_dist = None

        cur.execute(
            "UPDATE images SET processed=1, changed=?, reason=?, caption=?, detections_json=? "
            "WHERE id=?",
            (
                changed_flag,
                reason_db,
                caption,
                json.dumps({"objects": new_objs}),
                rec.id,
            ),
        )
    else:
        # Rule #1 or #2: use existing baseline row, update it, mark rec processed
        assert baseline_row is not None
        image_id = int(baseline_row["id"])
        baseline_camera_id = str(baseline_row["camera_id"])

        nearest_id = image_id
        nearest_dist = baseline_dist

        changed_flag = 1 if mode == "baseline_major" else 0
        reason_db = change_reason if mode == "baseline_major" else ""

        # Update baseline row to latest capture
        cur.execute(
            "UPDATE images SET camera_id=?, path=?, lat=?, lon=?, captured_at=?, "
            "processed=1, changed=?, reason=?, caption=?, detections_json=? "
            "WHERE id=?",
            (
                rec.camera_id,
                str(rec.path),
                float(rec.lat),
                float(rec.lon),
                rec.captured_at,
                changed_flag,
                reason_db,
                caption,
                json.dumps({"objects": new_objs}),
                image_id,
            ),
        )

        # Mark the “incoming” rec row as processed too (it’s now just a source)
        cur.execute(
            "UPDATE images SET processed=1 WHERE id=?",
            (rec.id,),
        )

    conn.commit()
    conn.close()

    # --- Ditto updates ---

    thing_id = _thing_id_for_image(baseline_camera_id, image_id)
    ditto.ensure_thing(thing_id)

    # Build last_capture based on rec (the new capture)
    try:
        pil = Image.open(io.BytesIO(raw)).convert("RGB")
        width, height = pil.width, pil.height
    except Exception:
        pil = None
        width = height = None

    image_url = _public_url_for_path(rec.path)

    last_capture: Dict[str, Any] = {
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

    # Append to history (keep existing, if any)
    try:
        existing_history = ditto.get_history(thing_id)
    except Exception:
        existing_history = []
    if not isinstance(existing_history, list):
        existing_history = []

    history_entry = {
        k: v for k, v in last_capture.items() if k != "thumbnail_b64"
    }
    full_history = existing_history + [history_entry]
    max_len = CONFIG.get("DITTO_HISTORY_MAX", 20)
    if len(full_history) > max_len:
        full_history = full_history[-max_len:]

    detections_payload = {
        "objects": new_objs,
        "caption": caption,
        "changed_since_previous": bool(changed_flag),
        "change_reason": reason_db or "",
        "prev": {"objects": prev_objs_for_baseline},
    }

    ditto.patch_updates(
        thing_id,
        last_capture=last_capture,
        history=full_history,
        detections=detections_payload,
        max_len=max_len,
    )

    if changed_flag and CONFIG["SEND_ALERT_MESSAGE"]:
        ditto.send_alert(
            thing_id,
            "alert",
            {
                "reason": reason_db or "major change detected",
                "thingId": thing_id,
                "image_url": image_url,
                "objects": new_objs,
            },
        )

    return bool(changed_flag), reason_db or ""
