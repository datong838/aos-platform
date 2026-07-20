"""T4.8 DocIntel OCR → process-isolated OCR sidecar."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from aos_api.env_load import load_dotenv
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.ocr")

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def ocr_url() -> str:
    return _env("AOS_OCR_URL").rstrip("/")


def fallback_mode() -> str:
    return _env("AOS_OCR_FALLBACK", "mock").lower()


def timeout_s() -> float:
    try:
        return float(_env("AOS_OCR_TIMEOUT", "30") or "30")
    except ValueError:
        return 30.0


def probe_sidecar(timeout: float = 1.5) -> dict[str, Any]:
    base = ocr_url()
    if not base:
        return {"ok": False, "sidecar": "unset", "detail": "AOS_OCR_URL empty"}
    last = ""
    for path in ("/health", "/"):
        try:
            req = urllib.request.Request(f"{base}{path}", method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {"raw": body[:200]}
            return {"ok": True, "sidecar": "ocr", "probe": path, "health": payload}
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
    return {"ok": False, "sidecar": "ocr-down", "detail": last}


def _fallback(page: int, text_hint: str | None) -> dict[str, Any]:
    """215m — mock boxes + non-zero confidence from textHint (≠ GPU OCR)."""
    text = (text_hint or "OCR fallback mock text").strip() or "OCR fallback mock text"
    tokens = [t for t in text.replace("\n", " ").split(" ") if t] or [text]
    boxes: list[dict[str, Any]] = []
    x = 8.0
    y = 12.0 + max(0, int(page) - 1) * 24.0
    for i, tok in enumerate(tokens[:32]):
        w = max(12.0, min(180.0, 7.0 * len(tok)))
        boxes.append(
            {
                "text": tok,
                "x": round(x, 1),
                "y": round(y, 1),
                "w": round(w, 1),
                "h": 14.0,
                "confidence": round(0.72 + (i % 5) * 0.04, 2),
            }
        )
        x += w + 6.0
        if x > 520:
            x = 8.0
            y += 18.0
    avg = sum(float(b["confidence"]) for b in boxes) / len(boxes)
    return {
        "engine": "fallback-mock",
        "page": page,
        "text": text,
        "sidecar": "fallback-mock",
        "confidence": round(avg, 3),
        "boxes": boxes,
    }


def ocr_page(
    *,
    page: int = 1,
    text_hint: str | None = None,
    image_base64: str | None = None,
    media_rid: str | None = None,
) -> dict[str, Any]:
    """Prefer OCR sidecar → fallback-mock (unless FALLBACK=off)."""
    load_dotenv()
    base = ocr_url()
    payload = {
        "page": page,
        "textHint": text_hint,
        "imageBase64": image_base64,
        "mediaRid": media_rid,
    }
    if base:
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{base}/v1/ocr/page",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout_s()) as resp:
                out = json.loads(resp.read().decode("utf-8"))
            out.setdefault("sidecar", "ocr")
            out.setdefault("page", page)
            return out
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            log.warning("ocr_sidecar_fail err=%s", exc)
            if fallback_mode() in {"off", "false", "0", "no"}:
                raise
    elif fallback_mode() in {"off", "false", "0", "no"}:
        raise RuntimeError("AOS_OCR_URL empty and AOS_OCR_FALLBACK=off")

    return _fallback(page, text_hint)
