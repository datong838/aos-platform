"""T4.8 OCR sidecar — process-isolated; optional paddleocr, else shaped Dev engine."""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="aos-dev-ocr-sidecar", version="0.1.0")

_PADDLE = None
_PADDLE_ERR: str | None = None


def _try_paddle() -> Any | None:
    global _PADDLE, _PADDLE_ERR
    if _PADDLE is not None:
        return _PADDLE
    if _PADDLE_ERR is not None:
        return None
    try:
        from paddleocr import PaddleOCR  # type: ignore

        _PADDLE = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        return _PADDLE
    except Exception as exc:  # noqa: BLE001
        _PADDLE_ERR = str(exc)
        return None


class OcrPageIn(BaseModel):
    page: int = 1
    textHint: str | None = None
    imageBase64: str | None = None
    mediaRid: str | None = None


def _strip_data_url(raw: str) -> bytes:
    s = raw.strip()
    if "," in s and s.lower().startswith("data:"):
        s = s.split(",", 1)[1]
    try:
        return base64.b64decode(s, validate=False)
    except binascii.Error as exc:
        raise ValueError(f"invalid imageBase64: {exc}") from exc


def _shaped_from_bytes(data: bytes, hint: str | None) -> tuple[str, float, list[dict[str, Any]]]:
    """Dev OCR without paddle: prefer hint; else decode UTF-8-ish payload; else fingerprint."""
    if hint and hint.strip():
        return hint.strip(), 0.55, []
    # Tiny text payloads masquerading as "images" in Dev tests
    try:
        text = data.decode("utf-8")
        if text.strip() and all(c.isprintable() or c in "\n\r\t" for c in text):
            return text.strip(), 0.7, []
    except UnicodeDecodeError:
        pass
    digest = hashlib.sha256(data).hexdigest()[:12]
    # Strip non-ascii noise from filename-like bytes in header
    ascii_bits = re.sub(rb"[^\x20-\x7e]+", b" ", data[:256]).decode("ascii", errors="ignore").strip()
    if len(ascii_bits) >= 4:
        return f"[shaped] {ascii_bits[:120]}", 0.4, []
    return f"[shaped] page-image#{digest}", 0.35, []


def _run_paddle(data: bytes) -> tuple[str, float, list[dict[str, Any]]] | None:
    ocr = _try_paddle()
    if ocr is None:
        return None
    try:
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
        import io

        img = Image.open(io.BytesIO(data)).convert("RGB")
        arr = np.array(img)
        result = ocr.ocr(arr, cls=True)
        lines: list[str] = []
        boxes: list[dict[str, Any]] = []
        confs: list[float] = []
        for block in result or []:
            for item in block or []:
                box, (txt, conf) = item[0], item[1]
                lines.append(str(txt))
                confs.append(float(conf))
                boxes.append({"box": box, "text": txt, "confidence": conf})
        text = "\n".join(lines).strip()
        avg = sum(confs) / len(confs) if confs else 0.0
        return text or "[paddleocr] (empty)", avg, boxes
    except Exception:  # noqa: BLE001
        return None


@app.get("/health")
def health() -> dict[str, Any]:
    paddle = _try_paddle()
    return {
        "ok": True,
        "sidecar": "ocr",
        "engineReady": "paddleocr" if paddle else "paddleocr-shaped",
        "paddleError": _PADDLE_ERR,
    }


@app.post("/v1/ocr/page")
def ocr_page(body: OcrPageIn) -> dict[str, Any]:
    text = ""
    engine = "paddleocr-shaped"
    confidence = 0.0
    boxes: list[dict[str, Any]] = []

    if body.imageBase64:
        data = _strip_data_url(body.imageBase64)
        paddle_out = _run_paddle(data)
        if paddle_out is not None:
            text, confidence, boxes = paddle_out
            engine = "paddleocr"
        else:
            text, confidence, boxes = _shaped_from_bytes(data, body.textHint)
            engine = "paddleocr-shaped"
    elif body.textHint and body.textHint.strip():
        text = body.textHint.strip()
        confidence = 0.5
        engine = "paddleocr-shaped"
    else:
        text = f"[shaped] empty-page-{body.page}"
        confidence = 0.1
        engine = "paddleocr-shaped"

    return {
        "engine": engine,
        "page": body.page,
        "text": text,
        "sidecar": "ocr",
        "confidence": confidence,
        "boxes": boxes,
        "mediaRid": body.mediaRid,
    }
