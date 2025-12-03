# camera_vlm_ditto/README.md
# ==============================================
# Camera → VLM (Gemini) → Ditto pipeline (Flask)

## What this does
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
python -m camera_vlm_ditto.cli --flask 1 --port 8089
```

## Optional batch processing
```bash
python -m camera_vlm_ditto.cli --db ./images.db --limit 50
