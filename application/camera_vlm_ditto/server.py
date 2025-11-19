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
        Upload one image:
          - Extract lat/lon/time via VLM
          - Find nearest existing image (ANY camera) within PROXIMITY_METERS
          - Compare content: sha, pixel_hash, then VLM compare_change
          - Insert row in DB
          - Create/update a Ditto Thing for THIS image (thingId = site01:<camera_id>-<image_id>)
        """
        try:
            file = request.files.get("file")
            camera_id = request.form.get("camera_id") or "camera-01"
            if not file:
                return jsonify({"detail": "Missing file"}), 400

            # Save the file
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

            # Find nearest stored image (ANY camera) based on geo distance
            cur.execute("SELECT id,lat,lon,detections_json,path,camera_id FROM images")
            rows = cur.fetchall()

            nearest_id = None
            nearest_dist = float("inf")
            nearest_path = None
            nearest_camera_id = None
            prev_objs: List[Dict[str, Any]] = []
            for r in rows:
                try:
                    d = haversine_m(lat, lon, r["lat"], r["lon"])
                except Exception:
                    continue
                if d < nearest_dist:
                    nearest_dist = d
                    nearest_id = r["id"]
                    nearest_path = r["path"]
                    nearest_camera_id = r["camera_id"]
                    try:
                        pj = (
                            json.loads(r["detections_json"])
                            if r["detections_json"]
                            else {}
                        )
                        prev_objs = (
                            pj.get("objects", [])
                            if isinstance(pj, dict)
                            else (pj or [])
                        )
                    except Exception:
                        prev_objs = []

            # Analyze new image
            analysis = vlm.analyze(raw)
            new_objs = analysis.get("objects", [])
            caption = analysis.get("caption", "")

            # Compare vs nearest within proximity, but NEVER flag if bytes OR pixels identical
            changed, reason = (False, "")
            if nearest_id is not None and nearest_dist <= CONFIG["PROXIMITY_METERS"]:
                try:
                    if nearest_path:
                        prev_raw = load_image_bytes(nearest_path)
                        # First: raw file equality (fast)
                        if sha256_hex(prev_raw) == sha256_hex(raw):
                            changed, reason = (False, "")
                        else:
                            # Second: content equality (EXIF/metadata agnostic)
                            if pixel_hash(prev_raw) == pixel_hash(raw):
                                changed, reason = (False, "")
                            else:
                                # Only if content differs, invoke the VLM
                                cmp = vlm.compare_change(prev_raw, raw)
                                changed, reason = (
                                    bool(cmp.get("changed", False)),
                                    str(cmp.get("reason", "")).strip(),
                                )
                except Exception:
                    changed, reason = (False, "")

            # ALWAYS insert the new row
            cur.execute(
                "INSERT INTO images(camera_id,path,lat,lon,captured_at,processed,changed,reason,caption,detections_json) "
                "VALUES (?,?,?,?,?,1,?,?,?,?)",
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
            conn.commit()

            # One Ditto thing per image
            thing_id = _thing_id_for_image(camera_id, image_id)
            ditto.ensure_thing(thing_id)

            try:
                # lastCapture
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

                # For an image-thing, history is just this capture (kept as list)
                history = [
                    {k: v for k, v in last_capture.items() if k != "thumbnail_b64"}
                ]

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
                            "image_url": f"{STATIC_MOUNT}/{safe_name}",
                            "objects": new_objs,
                            "compared_to_image_id": nearest_id,
                            "compared_to_camera_id": nearest_camera_id,
                            "distance_m": nearest_dist,
                        },
                    )

            except Exception as e:
                # Don't fail request after DB insert; just record the error
                log.exception("Ditto update failed")
                cur.execute(
                    "UPDATE images SET reason=? WHERE id=?",
                    (f"ditto update error: {e}", image_id),
                )
                conn.commit()

            conn.close()

            print(f"compared_to_id: {nearest_id}, distance_m: {nearest_dist}")

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
                    "compared_to_id": nearest_id,
                    "distance_m": (
                        None if nearest_id is None else float(nearest_dist)
                    ),
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
        For per-image Things, captures are trivial: history + lastCapture
        from Ditto for that image Thing.
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
