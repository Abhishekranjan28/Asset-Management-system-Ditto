"""Thin Ditto REST client used by pipeline and server."""
from __future__ import annotations

import json
import requests
from typing import Dict, Any, List
import re
import logging

from .config import DITTO_BASE_URL, DITTO_USER, DITTO_PASS, CONFIG

log = logging.getLogger("camera-vlm-ditto")


class DittoClient:
    def __init__(
        self,
        base_url: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self.base = (base_url or DITTO_BASE_URL).rstrip("/")
        self.session = requests.Session()
        self.session.auth = (user or DITTO_USER, password or DITTO_PASS)
        self.session.headers.update({"Content-Type": "application/json"})

    def ensure_thing(self, thing_id: str) -> None:
        url = f"{self.base}/api/2/things/{thing_id}"

        # Check if exists
        r = self.session.get(url)
        if r.status_code == 200:
            return

        # If error but not 404 → real error
        if r.status_code != 404:
            log.error("Ditto GET error for %s → %s %s", thing_id, r.status_code, r.text)
            r.raise_for_status()

        # Create new thing
        payload = {
            "thingId": thing_id,
            "features": {
                "camera": {"properties": {"lastCapture": {}, "history": []}},
                "detections": {"properties": {}},
            },
        }

        r2 = self.session.put(url, data=json.dumps(payload))

        if r2.status_code >= 400:
            log.error(
                "Ditto ensure_thing failed for %s → %s %s",
                thing_id,
                r2.status_code,
                r2.text,
            )
            r2.raise_for_status()

        r2.raise_for_status()


    def update_last_capture(self, thing_id: str, payload: Dict[str, Any]) -> None:
        url = f"{self.base}/api/2/things/{thing_id}/features/camera/properties/lastCapture"
        r = self.session.put(url, data=json.dumps(payload))
        r.raise_for_status()

    def append_history_capture(
        self, thing_id: str, capture: Dict[str, Any], max_len: int = 20
    ) -> None:
        def _slim(c: Dict[str, Any]) -> Dict[str, Any]:
            keys = [
                "image_url",
                "image_hash",
                "captured_at",
                "size_bytes",
                "lat",
                "lon",
                "width",
                "height",
            ]
            return {k: c[k] for k in keys if k in c}

        url_hist = f"{self.base}/api/2/things/{thing_id}/features/camera/properties/history"
        r = self.session.get(url_hist)
        history: List[Dict[str, Any]] = []
        if r.status_code == 200:
            try:
                j = r.json()
                if isinstance(j, list):
                    history = [{**_slim(x)} for x in j]
            except Exception:
                history = []
        history.append(_slim(capture))
        if len(history) > max_len:
            history = history[-max_len:]
        payload = json.dumps(history)
        r2 = self.session.put(url_hist, data=payload)
        if r2.status_code < 400:
            r2.raise_for_status()
            return
        if r2.status_code == 413:
            for keep in (min(10, max_len), 5, 3, 1):
                small = json.dumps(history[-keep:])
                rr = self.session.put(url_hist, data=small)
                if rr.status_code < 400:
                    rr.raise_for_status()
                    return
                if rr.status_code != 413:
                    rr.raise_for_status()
            last_only = json.dumps([_slim(capture)])
            rr = self.session.put(url_hist, data=last_only)
            rr.raise_for_status()
            return
        r2.raise_for_status()

    def update_detections(self, thing_id: str, payload: Dict[str, Any]) -> None:
        url = f"{self.base}/api/2/things/{thing_id}/features/detections/properties"
        r = self.session.put(url, data=json.dumps(payload))
        r.raise_for_status()

    def get_detections(self, thing_id: str) -> Dict[str, Any]:
        url = f"{self.base}/api/2/things/{thing_id}/features/detections/properties"
        r = self.session.get(url)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {}

    def send_alert(
        self,
        thing_id: str,
        subject: str,
        value: Dict[str, Any],
        path: str = "/application",
    ) -> None:
        url = f"{self.base}/api/2/things/{thing_id}/inbox/messages/{subject}"
        body = {"path": path, "value": value}
        r = self.session.post(url, params={"timeout": "0"}, json=body)
        if r.status_code not in (200, 201, 202):
            r.raise_for_status()

    def get_last_capture(self, thing_id: str) -> Dict[str, Any]:
        url = f"{self.base}/api/2/things/{thing_id}/features/camera/properties/lastCapture"
        r = self.session.get(url)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        try:
            return r.json() or {}
        except Exception:
            return {}

    def get_history(self, thing_id: str) -> List[Dict[str, Any]]:
        url_hist = f"{self.base}/api/2/things/{thing_id}/features/camera/properties/history"
        r = self.session.get(url_hist)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        try:
            j = r.json()
            return j if isinstance(j, list) else []
        except Exception:
            return []

    def get_all_captures(
        self, thing_id: str, include_last: bool = True
    ) -> List[Dict[str, Any]]:
        history = self.get_history(thing_id)
        if not include_last:
            return history
        last = self.get_last_capture(thing_id)
        if not last:
            return history
        try:
            last_hash = str(last.get("image_hash", "")).strip()
            if last_hash and any(
                str(x.get("image_hash", "")).strip() == last_hash for x in history
            ):
                return history
        except Exception:
            pass
        return history + [last]

    def _parse_revision_from_etag(self, etag: str) -> int:
        if not etag:
            return 0
        et = etag.strip().strip('"').lower()
        m = re.search(r"rev[:\-]?(\d+)", et)
        return int(m.group(1)) if m else 0

    def get_revisions(self, thing_id: str) -> List[Dict[str, Any]]:
        url = f"{self.base}/api/2/things/{thing_id}"
        r = self.session.get(url)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        etag = r.headers.get("ETag") or r.headers.get("etag") or ""
        current_rev = self._parse_revision_from_etag(etag)
        if current_rev <= 1:
            try:
                j = r.json()
                md = j.get("metadata", {}) if isinstance(j, dict) else {}
                current_rev = int(md.get("revision", current_rev or 0) or current_rev or 0)
            except Exception:
                pass
        revisions: List[Dict[str, Any]] = []
        if current_rev <= 1:
            try:
                revisions.append(r.json())
            except Exception:
                pass
            return revisions
        for rev in range(1, current_rev + 1):
            headers = {"at-historical-revision": str(rev)}
            rr = self.session.get(url, headers=headers)
            if rr.status_code == 404:
                continue
            try:
                rr.raise_for_status()
            except Exception:
                continue
            try:
                revisions.append(rr.json())
            except Exception:
                continue
        return revisions

    def patch_updates(
        self,
        thing_id: str,
        last_capture: Dict[str, Any] | None = None,
        history: List[Dict[str, Any]] | None = None,
        detections: Dict[str, Any] | None = None,
        max_len: int | None = None,
    ) -> None:
        patch_doc: Dict[str, Any] = {"features": {}}

        if last_capture is not None or history is not None:
            cam_props: Dict[str, Any] = {}
            if last_capture is not None:
                cam_props["lastCapture"] = last_capture
            if history is not None:
                if max_len is not None and len(history) > max_len:
                    history = history[-max_len:]
                cam_props["history"] = history
            patch_doc["features"]["camera"] = {"properties": cam_props}

        if detections is not None:
            patch_doc["features"]["detections"] = {"properties": detections}

        headers = {
            **self.session.headers,
            "Content-Type": "application/merge-patch+json",
        }
        url = f"{self.base}/api/2/things/{thing_id}"
        r = self.session.patch(url, data=json.dumps(patch_doc), headers=headers)

        if r.status_code == 413 and history is not None:
            for keep in (min(10, (max_len or 10)), 5, 3, 1):
                small_doc = {
                    "features": {
                        "camera": {
                            "properties": {
                                **(
                                    {"lastCapture": last_capture}
                                    if last_capture is not None
                                    else {}
                                ),
                                "history": history[-keep:],
                            }
                        },
                        **(
                            {"detections": {"properties": detections}}
                            if detections is not None
                            else {}
                        ),
                    }
                }
                rr = self.session.patch(
                    url, data=json.dumps(small_doc), headers=headers
                )
                if rr.status_code < 400:
                    rr.raise_for_status()
                    return
                if rr.status_code != 413:
                    rr.raise_for_status()

            fallback_doc = {
                "features": {
                    "camera": {"properties": {"lastCapture": last_capture or {}}}
                }
            }
            rr = self.session.patch(
                url, data=json.dumps(fallback_doc), headers=headers
            )
            rr.raise_for_status()
            return

        r.raise_for_status()
