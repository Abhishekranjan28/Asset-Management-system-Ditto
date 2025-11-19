from __future__ import annotations
import argparse

from .config import CONFIG, DITTO_BASE_URL, DITTO_PASS, DITTO_USER, GOOGLE_API_KEY
from .db import fetch_new_images, mark_processed
from .vlm import VisionClient
from .ditto_client import DittoClient
from .pipeline import process_record
from .server import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="Path to SQLite DB (batch process unprocessed rows)")
    parser.add_argument("--limit", type=int, default=20, help="Batch size for --db mode")
    parser.add_argument("--flask", type=int, default=0, help="Run Flask API if 1")
    parser.add_argument("--port", type=int, default=8089, help="Flask port")
    args, _ = parser.parse_known_args()

    if args.db:
        rows = fetch_new_images(args.db, args.limit)
        if rows:
            vlm = VisionClient(GOOGLE_API_KEY, CONFIG["GEMINI_MODEL"])
            ditto = DittoClient(DITTO_BASE_URL, DITTO_USER, DITTO_PASS)
            processed_ids = []
            for rec in rows:
                try:
                    changed, reason = process_record(
                        rec,
                        vlm,
                        ditto,
                        proximity_m=CONFIG["PROXIMITY_METERS"],
                        iou_thr=CONFIG["IOU_THRESHOLD"],
                        embed_thumbnail=CONFIG["EMBED_THUMBNAIL"],
                        thumbnail_max=CONFIG["THUMBNAIL_MAX_SIZE"],
                        db_path=args.db,
                    )
                    print(
                        f"[{'CHANGED' if changed else 'OK'}] "
                        f"camera={rec.camera_id} image_id={rec.id} reason={reason or '-'}"
                    )
                    processed_ids.append(rec.id)
                except Exception as e:
                    print("Error processing record", rec.id, e)
            mark_processed(args.db, processed_ids)
        else:
            print("No new images to process.")

    if args.flask:
        app = create_app()
        app.run(host="0.0.0.0", port=args.port, debug=True)


if __name__ == "__main__":
    main()
