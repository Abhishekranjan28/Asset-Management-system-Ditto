from __future__ import annotations
import io
import json
from typing import Any, Dict, List
from PIL import Image
from .config import CONFIG

try:
    import google.generativeai as genai
except Exception:
    genai = None


class VisionClient:
    def __init__(self, api_key: str, model_name: str):
        if genai is None:
            raise RuntimeError(
                "google-generativeai not installed. pip install google-generativeai"
            )
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is empty.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def _maybe_resize(self, image_bytes: bytes) -> bytes:
        if len(image_bytes) <= CONFIG["GEMINI_MAX_IMAGE_BYTES"]:
            return image_bytes
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((1920, 1080))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    def analyze(self, image_bytes: bytes) -> Dict[str, Any]:
        image_bytes = self._maybe_resize(image_bytes)
        img_part = {"mime_type": "image/jpeg", "data": image_bytes}
        prompt_text = (
            "Return ONLY strict JSON with keys: "
            '"objects" (array of {"label","confidence","bbox","state"}), "caption" (string).\n'
            "- bbox: [x,y,w,h] normalized to [0,1].\n"
            "- label: concise noun; confidence in [0,1].\n"
            '- state: one of ["intact","damaged"] when you can tell; otherwise "intact".'
        )
        resp = self.model.generate_content(
            [img_part, {"text": prompt_text}],
            generation_config={"response_mime_type": "application/json"},
        )
        text = getattr(resp, "text", None) or "{}"
        try:
            data = json.loads(text)
        except Exception:
            s, e = text.find("{"), text.rfind("}")
            data = json.loads(text[s : e + 1]) if s != -1 and e != -1 else {
                "objects": [],
                "caption": "",
            }

        objs_out: List[Dict[str, Any]] = []
        for o in data.get("objects") or []:
            try:
                bbox = [float(v) for v in (o.get("bbox") or [0, 0, 0, 0])]
                state = str(o.get("state", "intact")).strip().lower() or "intact"
                objs_out.append(
                    {
                        "label": str(o.get("label", "object"))[:64],
                        "confidence": float(o.get("confidence", 0.0)),
                        "bbox": [
                            max(0.0, min(1.0, bbox[0])),
                            max(0.0, min(1.0, bbox[1])),
                            max(0.0, min(1.0, bbox[2])),
                            max(0.0, min(1.0, bbox[3])),
                        ],
                        "state": "damaged" if state == "damaged" else "intact",
                    }
                )
            except Exception:
                continue
        return {"objects": objs_out, "caption": str(data.get("caption", "")).strip()}

    def extract_metadata(self, image_bytes: bytes) -> Dict[str, Any]:
        image_bytes = self._maybe_resize(image_bytes)
        img_part = {"mime_type": "image/jpeg", "data": image_bytes}
        prompt_text = (
            "Read any text printed ON the image and extract GPS and time.\n"
            "Return ONLY strict JSON with keys: lat (number), lon (number), captured_at (string or null).\n"
            "If a timestamp is not visible, set captured_at to null.\n"
            "lat/lon may appear as 'lat:', 'latitude', 'Lat', etc., with optional symbols."
        )
        resp = self.model.generate_content(
            [img_part, {"text": prompt_text}],
            generation_config={"response_mime_type": "application/json"},
        )
        text = getattr(resp, "text", None) or "{}"
        try:
            data = json.loads(text)
        except Exception:
            s, e = text.find("{"), text.rfind("}")
            data = json.loads(text[s : e + 1]) if s != -1 and e != -1 else {}
        lat = data.get("lat")
        lon = data.get("lon")
        cap = data.get("captured_at")
        try:
            lat = float(lat)
            lon = float(lon)
        except Exception:
            raise ValueError("Could not parse lat/lon from image text via VLM")
        cap = str(cap).strip() if cap not in (None, "") else None
        return {"lat": lat, "lon": lon, "captured_at": cap}

    def compare_change(
        self, prev_image_bytes: bytes, new_image_bytes: bytes
    ) -> Dict[str, Any]:
        prev_image_bytes = self._maybe_resize(prev_image_bytes)
        new_image_bytes = self._maybe_resize(new_image_bytes)
        prev_part = {"mime_type": "image/jpeg", "data": prev_image_bytes}
        new_part = {"mime_type": "image/jpeg", "data": new_image_bytes}
        prompt_text = (
            "You will compare TWO images from nearly the same location. Decide if there is a MAJOR CHANGE.\n"
            "CRITICAL: If the images are visually identical or differ only by metadata, compression artifacts, tiny crops, "
            "or insignificant lighting/white-balance shifts, set changed=false.\n"
            "Be STRICT about real changes: damaged items ('damaged'), previously present items missing ('missing'), "
            "or an obviously different scene ('changed').\n"
            "Return ONLY strict JSON with keys: changed (boolean), reason (string), details (string), "
            "scene_match (boolean), scene_similarity (number 0..1).\n"
            "Allowed reason values: 'damaged', 'missing', 'changed', or '' (empty if no change).\n"
            "If uncertain, prefer changed=false."
        )
        resp = self.model.generate_content(
            [
                {"text": prompt_text + "\nThe next image is BEFORE (baseline)."},
                prev_part,
                {"text": "The next image is AFTER (current)."},
                new_part,
            ],
            generation_config={"response_mime_type": "application/json"},
        )
        text = getattr(resp, "text", None) or "{}"
        try:
            data = json.loads(text)
        except Exception:
            s, e = text.find("{"), text.rfind("}")
            data = (
                json.loads(text[s : e + 1])
                if s != -1 and e != -1
                else {
                    "changed": False,
                    "reason": "",
                    "details": "parse_error",
                    "scene_match": False,
                    "scene_similarity": 0.0,
                }
            )
        changed = bool(data.get("changed", False))
        reason = str(data.get("reason", "")).strip().lower()
        if reason not in ("damaged", "missing", "changed"):
            reason = "" if not changed else "changed"
        details = str(data.get("details", "")).strip()
        scene_match = bool(data.get("scene_match", False))
        try:
            scene_similarity = float(data.get("scene_similarity", 0.0))
        except Exception:
            scene_similarity = 0.0
        return {
            "changed": changed,
            "reason": reason,
            "details": details,
            "scene_match": scene_match,
            "scene_similarity": scene_similarity,
        }
