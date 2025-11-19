# camera_vlm_ditto/README.md
# ==============================================
# Camera → VLM (Gemini) → Ditto pipeline (Flask)

## What this does
- Upload an image via API
- Extract `lat/lon/captured_at` from the image using Gemini (OCR-style)
- Always insert a row in SQLite
- Find nearest prior image for the same camera (≤ 10 m). If different bytes, let Gemini decide if a major change happened (damaged/missing/changed)
- Update Ditto (lastCapture + history + detections) and optionally emit an alert

## Install
```bash
pip install -r camera_vlm_ditto/requirements.txt
```

Set env vars:
```
GOOGLE_API_KEY=...
DITTO_BASE_URL=http://localhost:8080
DITTO_USER=ditto
DITTO_PASS=ditto
# optional
APP_DATA_DIR=...
DB_PATH=...
```

## Run Flask API
```bash
python -m camera_vlm_ditto --flask 1 --port 8089
```

## Optional batch processing
```bash
python -m camera_vlm_ditto --db ./images.db --limit 50
