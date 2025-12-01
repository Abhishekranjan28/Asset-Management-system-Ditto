from __future__ import annotations
import os
import io
import json
import time
import sqlite3
import pathlib
import logging
from typing import Any, Dict, List

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image

from .config import (
    CONFIG,
    DITTO_BASE_URL,
    DITTO_USER,
    DITTO_PASS,
    GOOGLE_API_KEY,
    UPLOAD_DIR,
    DB_DEFAULT,
    STATIC_MOUNT,
)
from .db import ensure_schema
from .ditto_client import DittoClient
from .vlm import VisionClient
from .utils import sha256_hex, make_thumbnail_b64, haversine_m, load_image_bytes, pixel_hash

log = logging.getLogger("camera-vlm-ditto")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
)
log.addHandler(handler)


def _thing_id_for_image(camera_id: str, image_id: int) -> str:
    """
    Per-image Ditto thingId.

    Ditto expects a single ':' as <namespace>:<name>.
    We encode camera + image into the <name> with a '-' separator, e.g.:

      site01:camera-02-40
    """
    return f"site01:{camera_id}-{image_id}"


def _append_unique_capture(history: List[Dict[str, Any]], capture: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Append a capture dict to history if its image_hash is not already present.
    Strips thumbnail_b64 to keep history compact.
    """
    if not isinstance(capture, dict):
        return history

    h = str(capture.get("image_hash", "")).strip()
    if h and any(str(x.get("image_hash", "")).strip() == h for x in history):
        return history

    slim = {k: v for k, v in capture.items() if k != "thumbnail_b64"}
    history.append(slim)
    return history


def create_app() -> Flask:
    flask_app = Flask(
        __name__, static_url_path=STATIC_MOUNT, static_folder=str(UPLOAD_DIR)
    )
    CORS(flask_app)
    ensure_schema(DB_DEFAULT)

    @flask_app.route("/")
    def root_ok():
        return jsonify({"ok": True, "service": "Camera → VLM (Gemini) → Ditto"})

    @flask_app.route("/upload", methods=["POST"])
    def upload_image_flask():
        """
        Upload one image and apply the three rules:

          1. If there IS at least one existing image within PROXIMITY_METERS (<=10 m)
             AND a MAJOR change is detected against ANY of them:
               - Reuse the corresponding DB row and Ditto thing for that baseline.
               - Overwrite that row with the *new* image metadata.
               - Append Ditto history, keep previous captures.

          2. If there IS at least one existing image within PROXIMITY_METERS (<=10 m)
             AND NO major change is detected against any of them:
               - Reuse the NEAREST DB row + Ditto thing.
               - Overwrite that row with the new image metadata
                 (caption, objects, etc.).
               - Append Ditto history and lastCapture (changed_since_previous=False).

          3. If there is NO existing image within PROXIMITY_METERS:
               - Insert a NEW DB row.
               - Create a NEW Ditto thing for this row.
               - Start history for this thing.
        """
        try:
            file = request.files.get("file")
            camera_id = request.form.get("camera_id") or "camera-01"
            if not file:
                return jsonify({"detail": "Missing file"}), 400

            # Save the file to disk
            safe_name = f"{int(time.time() * 1000)}_{os.path.basename(file.filename)}"
            save_path = UPLOAD_DIR / safe_name
            raw = file.read()
            with open(save_path, "wb") as f:
                f.write(raw)

            # Clients
            ditto = DittoClient(DITTO_BASE_URL, DITTO_USER, DITTO_PASS)
            vlm = VisionClient(GOOGLE_API_KEY, CONFIG["GEMINI_MODEL"])

            # Extract metadata (lat/lon/time) from the image via VLM
            meta = vlm.extract_metadata(raw)
            lat = float(meta["lat"])
            lon = float(meta["lon"])
            captured_at = meta.get("captured_at") or time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            )

            conn = sqlite3.connect(DB_DEFAULT)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Fetch all existing images
            cur.execute("SELECT id,lat,lon,detections_json,path,camera_id FROM images")
            rows = cur.fetchall()

            # Step 1: collect candidates within PROXIMITY_METERS
            proximity = CONFIG["PROXIMITY_METERS"]
            candidates: List[Dict[str, Any]] = []
            for r in rows:
                try:
                    d = haversine_m(lat, lon, r["lat"], r["lon"])
                except Exception:
                    continue
                if d <= proximity:
                    candidates.append(
                        {
                            "id": int(r["id"]),
                            "lat": r["lat"],
                            "lon": r["lon"],
                            "detections_json": r["detections_json"],
                            "path": r["path"],
                            "camera_id": r["camera_id"],
                            "distance": float(d),
                        }
                    )

            # For reporting/debugging
            nearest_any_id = None
            nearest_any_dist = None
            if candidates:
                nearest_any = min(candidates, key=lambda c: c["distance"])
                nearest_any_id = nearest_any["id"]
                nearest_any_dist = nearest_any["distance"]

            # Step 2: run comparisons against ALL candidates
            # to see if ANY major change is detected.
            baseline_change = None          # candidate where major change detected
            baseline_change_prev_objs: List[Dict[str, Any]] = []
            baseline_nonchange = None       # nearest candidate even if no major change
            baseline_nonchange_prev_objs: List[Dict[str, Any]] = []

            for c in candidates:
                prev_path = c["path"]
                if not prev_path:
                    continue
                try:
                    prev_raw = load_image_bytes(prev_path)
                except Exception:
                    continue

                # Parse prev objects from DB
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

                # Fast equality checks: file bytes & content hash
                try:
                    if sha256_hex(prev_raw) == sha256_hex(raw):
                        # Completely identical – treat as no major change
                        if baseline_nonchange is None or c["distance"] < baseline_nonchange["distance"]:
                            baseline_nonchange = c
                            baseline_nonchange_prev_objs = prev_objs_local
                        continue
                    if pixel_hash(prev_raw) == pixel_hash(raw):
                        # Visually identical – treat as no major change
                        if baseline_nonchange is None or c["distance"] < baseline_nonchange["distance"]:
                            baseline_nonchange = c
                            baseline_nonchange_prev_objs = prev_objs_local
                        continue
                except Exception:
                    # If hashing fails, fall through to VLM compare
                    pass

                # Call VLM compare_change only if content differs
                try:
                    cmp = vlm.compare_change(prev_raw, raw)
                    is_changed = bool(cmp.get("changed", False))
                    reason_local = str(cmp.get("reason", "")).strip()
                except Exception:
                    is_changed = False
                    reason_local = ""

                if is_changed:
                    # Prefer the closest "changed" candidate
                    if baseline_change is None or c["distance"] < baseline_change["distance"]:
                        baseline_change = {**c, "reason": reason_local}
                        baseline_change_prev_objs = prev_objs_local
                else:
                    # Track nearest non-change candidate as fallback
                    if baseline_nonchange is None or c["distance"] < baseline_nonchange["distance"]:
                        baseline_nonchange = c
                        baseline_nonchange_prev_objs = prev_objs_local

            # Step 3: decide which rule to apply
            if baseline_change is not None:
                # RULE 1: nearby + major change
                baseline = baseline_change
                changed = True
                reason = baseline.get("reason") or "changed"
                prev_objs = baseline_change_prev_objs
            elif baseline_nonchange is not None:
                # RULE 2: nearby + no major change
                baseline = baseline_nonchange
                changed = False
                reason = ""
                prev_objs = baseline_nonchange_prev_objs
            else:
                # RULE 3: no nearby image at all
                baseline = None
                changed = False
                reason = ""
                prev_objs = []

            # Analyze new image (objects + caption)
            analysis = vlm.analyze(raw)
            new_objs = analysis.get("objects", [])
            caption = analysis.get("caption", "")

            # === DB WRITE LOGIC ACCORDING TO RULES 1–3 ===

            if baseline is not None:
                # Reuse existing DB row for this "location cluster"
                baseline_id = int(baseline["id"])
                baseline_camera = baseline["camera_id"] or camera_id

                cur.execute(
                    """
                    UPDATE images
                    SET camera_id = ?,
                        path = ?,
                        lat = ?,
                        lon = ?,
                        captured_at = ?,
                        processed = 1,
                        changed = ?,
                        reason = ?,
                        caption = ?,
                        detections_json = ?
                    WHERE id = ?
                    """,
                    (
                        baseline_camera,
                        str(save_path),
                        float(lat),
                        float(lon),
                        captured_at,
                        int(bool(changed)),
                        reason or "",
                        caption,
                        json.dumps({"objects": new_objs}),
                        baseline_id,
                    ),
                )
                image_id = baseline_id
                thing_id = _thing_id_for_image(baseline_camera, baseline_id)
            else:
                # No nearby image within radius → NEW row + NEW thing
                cur.execute(
                    """
                    INSERT INTO images(
                        camera_id,path,lat,lon,captured_at,processed,
                        changed,reason,caption,detections_json
                    ) VALUES (?,?,?,?,?,1,?,?,?,?)
                    """,
                    (
                        camera_id,
                        str(save_path),
                        float(lat),
                        float(lon),
                        captured_at,
                        int(bool(changed)),
                        reason or "",
                        caption,
                        json.dumps({"objects": new_objs}),
                    ),
                )
                image_id = cur.lastrowid
                thing_id = _thing_id_for_image(camera_id, image_id)

            conn.commit()

            # Ensure Ditto thing exists for whichever row we're using
            ditto.ensure_thing(thing_id)

            try:
                # Build lastCapture for *this* upload
                try:
                    img = Image.open(io.BytesIO(raw)).convert("RGB")
                    width, height = img.width, img.height
                except Exception:
                    width = height = None

                last_capture = {
                    "image_url": f"{STATIC_MOUNT}/{safe_name}",
                    "image_hash": f"sha256:{sha256_hex(raw)}",
                    "captured_at": captured_at,
                    "size_bytes": len(raw),
                    "lat": float(lat),
                    "lon": float(lon),
                }
                if width and height:
                    last_capture.update({"width": width, "height": height})
                if CONFIG["EMBED_THUMBNAIL"] and width and height:
                    try:
                        last_capture["thumbnail_b64"] = make_thumbnail_b64(
                            Image.open(save_path), CONFIG["THUMBNAIL_MAX_SIZE"]
                        )
                    except Exception:
                        pass

                detections_payload = {
                    "objects": new_objs,
                    "caption": caption,
                    "changed_since_previous": bool(changed),
                    "change_reason": reason or "",
                    "prev": {"objects": prev_objs},
                }

                # === DITTO HISTORY APPEND LOGIC ===
                # We want to keep previous captures in history, and treat only the
                # newest as baseline for the *next* comparison (which is done via DB).

                history: List[Dict[str, Any]] = []
                try:
                    if baseline is not None:
                        # Start from existing history for this thing
                        history = ditto.get_history(thing_id) or []
                        if not isinstance(history, list):
                            history = []

                        # Append previous lastCapture snapshot if present
                        prev_last = ditto.get_last_capture(thing_id)
                        if prev_last:
                            history = _append_unique_capture(history, prev_last)

                    # In all cases, append this new capture snapshot
                    history = _append_unique_capture(history, last_capture)

                    # Enforce max length
                    max_len = CONFIG.get("DITTO_HISTORY_MAX", 20)
                    if len(history) > max_len:
                        history = history[-max_len:]
                except Exception:
                    # Fallback – at least store current capture
                    history = [{k: v for k, v in last_capture.items() if k != "thumbnail_b64"}]

                ditto.patch_updates(
                    thing_id,
                    last_capture=last_capture,
                    history=history,
                    detections=detections_payload,
                    max_len=CONFIG.get("DITTO_HISTORY_MAX", 20),
                )

                # Optional alert only when there is major change
                if changed and CONFIG["SEND_ALERT_MESSAGE"] and baseline is not None:
                    ditto.send_alert(
                        thing_id,
                        "alert",
                        {
                            "reason": reason or "major change detected",
                            "thingId": thing_id,
                            "image_url": f"{STATIC_MOUNT}/{safe_name}",
                            "objects": new_objs,
                            "compared_to_image_id": baseline["id"],
                            "compared_to_camera_id": baseline["camera_id"],
                            "distance_m": baseline["distance"],
                        },
                    )

            except Exception as e:
                # Don't fail request after DB update/insert; just record the error
                log.exception("Ditto update failed")
                try:
                    cur.execute(
                        "UPDATE images SET reason=? WHERE id=?",
                        (f"ditto update error: {e}", image_id),
                    )
                    conn.commit()
                except Exception:
                    pass

            conn.close()

            return jsonify(
                {
                    "accepted": True,
                    "stored": True,
                    "id": image_id,
                    "camera_id": camera_id,
                    "thing_id": thing_id,
                    "url": f"{STATIC_MOUNT}/{safe_name}",
                    "lat": lat,
                    "lon": lon,
                    "captured_at": captured_at,
                    "changed": bool(changed),
                    "reason": reason or "",
                    "has_nearby": bool(candidates),
                    "nearest_any_id": nearest_any_id,
                    "nearest_any_dist": nearest_any_dist,
                    "baseline_id": baseline["id"] if baseline is not None else None,
                    "baseline_distance": baseline["distance"] if baseline is not None else None,
                }
            )
        except Exception as e:
            log.exception("Upload failed")
            return jsonify({"detail": f"processing error: {e}"}), 500

    @flask_app.route("/images", methods=["GET"])
    def list_images_flask():
        conn = sqlite3.connect(DB_DEFAULT)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,camera_id,path,lat,lon,captured_at,processed,changed,reason,caption
            FROM images
            ORDER BY id ASC
            LIMIT ?
            """,
            (100,),
        )
        out: List[Dict[str, Any]] = []
        for r in cur.fetchall():
            p = pathlib.Path(r["path"]) if r["path"] else None
            out.append(
                {
                    "id": r["id"],
                    "camera_id": r["camera_id"],
                    "image_url": f"{STATIC_MOUNT}/{p.name}" if (p and p.exists()) else None,
                    "lat": r["lat"],
                    "lon": r["lon"],
                    "captured_at": r["captured_at"],
                    "processed": bool(r["processed"]),
                    "changed": bool(r["changed"]),
                    "reason": r["reason"] or "",
                    "caption": r["caption"] or "",
                }
            )
        conn.close()
        return jsonify(out)

    @flask_app.route("/ditto/image/<camera_id>/<int:image_id>", methods=["GET"])
    def get_ditto_state_for_image(camera_id: str, image_id: int):
        """
        Get Ditto state (lastCapture + detections) for a specific image Thing.
        """
        thing_id = _thing_id_for_image(camera_id, image_id)
        ditto = DittoClient(DITTO_BASE_URL, DITTO_USER, DITTO_PASS)
        det = ditto.get_detections(thing_id)
        url = (
            f"{DITTO_BASE_URL.rstrip('/')}"
            f"/api/2/things/{thing_id}/features/camera/properties/lastCapture"
        )
        r = requests.get(url, auth=(DITTO_USER, DITTO_PASS))
        last_capture = r.json() if r.status_code == 200 else {}
        return jsonify(
            {"thingId": thing_id, "detections": det, "lastCapture": last_capture}
        )

    @flask_app.route(f"{STATIC_MOUNT}/<path:filename>")
    def serve_upload(filename: str):
        return send_from_directory(str(UPLOAD_DIR), filename)

    @flask_app.route("/ditto/image/<camera_id>/<int:image_id>/captures", methods=["GET"])
    def get_captures_for_image(camera_id: str, image_id: int):
        """
        For per-image Things, captures are history + lastCapture from Ditto.
        """
        try:
            include_last = request.args.get("include_last", "1") not in (
                "0",
                "false",
                "False",
            )
            limit = request.args.get("limit")
            limit = int(limit) if (limit is not None and str(limit).isdigit()) else None
            offset = int(request.args.get("offset", "0") or 0)
            order = (request.args.get("order") or "desc").lower()
            if order not in ("asc", "desc"):
                order = "desc"

            thing_id = _thing_id_for_image(camera_id, image_id)
            ditto = DittoClient(DITTO_BASE_URL, DITTO_USER, DITTO_PASS)

            items = ditto.get_all_captures(thing_id, include_last=include_last)

            # Optional sort by captured_at when present
            def _ts(x):
                return str(x.get("captured_at", "")) if isinstance(x, dict) else ""

            items = sorted(items, key=_ts, reverse=(order == "desc"))

            total = len(items)
            if offset:
                items = items[offset:]
            if limit is not None:
                items = items[: max(0, limit)]

            return jsonify(
                {
                    "thingId": thing_id,
                    "total": total,
                    "offset": offset,
                    "returned": len(items),
                    "order": order,
                    "captures": items,
                }
            )
        except Exception as e:
            log.exception("Get captures failed")
            return jsonify({"detail": f"captures fetch error: {e}"}), 500

    @flask_app.route(
        "/ditto/image/<camera_id>/<int:image_id>/revisions", methods=["GET"]
    )
    def get_ditto_revisions_for_image(camera_id: str, image_id: int):
        thing_id = _thing_id_for_image(camera_id, image_id)
        ditto = DittoClient(DITTO_BASE_URL, DITTO_USER, DITTO_PASS)

        try:
            short_history = ditto.get_history(thing_id)
            revisions = ditto.get_revisions(thing_id)
            return jsonify(
                {
                    "thingId": thing_id,
                    "short_history": short_history,
                    "revisions_count": len(revisions),
                    "revisions": revisions,
                }
            )
        except Exception as e:
            log.exception("Failed getting revisions")
            return jsonify({"detail": f"failed to fetch revisions: {e}"}), 500

    return flask_app
