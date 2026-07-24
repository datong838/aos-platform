"""185m — media metadata deepen (dimensions / light EXIF / text; no GPU OCR)."""
from __future__ import annotations

import hashlib
import re
import struct
from datetime import datetime, timezone
from typing import Any


def extract_media_meta(
    data: bytes | None,
    content_type: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Legacy-shaped extractor used by enrich paths."""
    ct = (content_type or "").lower()
    nm = (name or "").lower()
    out: dict[str, Any] = {
        "ok": False,
        "format": None,
        "width": None,
        "height": None,
        "durationSec": None,
        "exif": {},
        "extractedAt": datetime.now(timezone.utc).isoformat(),
        "detail": "",
    }
    if not data:
        out["detail"] = "empty"
        return out

    if data[:8] == b"\x89PNG\r\n\x1a\n" or "png" in ct or nm.endswith(".png"):
        meta = _png_size(data)
        if meta:
            out.update(meta)
            out["ok"] = True
            out["format"] = "png"
            return out
        out["format"] = "png"
        out["detail"] = "png_header_incomplete"
        return out

    if data[:2] == b"\xff\xd8" or "jpeg" in ct or "jpg" in ct or nm.endswith((".jpg", ".jpeg")):
        wh = _jpeg_size(data)
        exif = _jpeg_exif_lite(data)
        if wh:
            out["width"], out["height"] = wh
            out["ok"] = True
            out["format"] = "jpeg"
            out["exif"] = exif
            return out
        out["format"] = "jpeg"
        out["exif"] = exif
        out["detail"] = "jpeg_sof_missing"
        return out

    if data[:6] in (b"GIF87a", b"GIF89a") or "gif" in ct or nm.endswith(".gif"):
        if len(data) >= 10:
            w, h = struct.unpack_from("<HH", data, 6)
            out.update({"ok": True, "format": "gif", "width": w, "height": h})
            return out
        out["format"] = "gif"
        out["detail"] = "gif_incomplete"
        return out

    if ct.startswith("video/") or ct.startswith("audio/") or nm.endswith(
        (".mp4", ".mov", ".webm", ".mkv", ".mp3", ".wav")
    ):
        dur = _ffprobe_duration(data, name or "clip.bin")
        if dur is not None:
            out["ok"] = True
            out["format"] = "av"
            out["durationSec"] = dur
            return out
        out["format"] = "av"
        out["detail"] = "ffprobe_unavailable"
        return out

    out["detail"] = "unsupported_or_non_media"
    return out


def extract_metadata(
    data: bytes | None,
    *,
    content_type: str = "application/octet-stream",
    name: str = "",
) -> dict[str, Any]:
    """185m HTTP contract: sha256 / kind / dims / lineCount; ocr always false."""
    raw = data or b""
    base = extract_media_meta(raw, content_type=content_type, name=name)
    kind = _sniff_kind(raw, content_type)
    meta: dict[str, Any] = {
        "sha256": hashlib.sha256(raw).hexdigest() if raw else None,
        "byteSize": len(raw),
        "kind": kind,
        "contentTypeDeclared": content_type,
        "name": name or None,
        "extractor": "185m-stdlib",
        "ocr": False,
        "ok": bool(base.get("ok")),
        "format": base.get("format"),
        "durationSec": base.get("durationSec"),
        "exif": base.get("exif") or {},
        "extractedAt": base.get("extractedAt"),
        "detail": base.get("detail") or "",
    }
    if base.get("width") is not None:
        meta["width"] = base["width"]
    if base.get("height") is not None:
        meta["height"] = base["height"]
    if kind == "text" and raw:
        try:
            text = raw.decode("utf-8", errors="replace")
            meta["lineCount"] = len(text.splitlines()) if text else 0
            meta["ok"] = True
            meta["format"] = meta.get("format") or "text"
        except Exception:
            meta["lineCount"] = None
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        meta["contentTypeSniff"] = "image/png"
    elif raw[:2] == b"\xff\xd8":
        meta["contentTypeSniff"] = "image/jpeg"
    elif kind == "text":
        meta["contentTypeSniff"] = (
            content_type if str(content_type).startswith("text/") else "text/plain"
        )
    else:
        meta["contentTypeSniff"] = "application/octet-stream"
    return meta


def _sniff_kind(data: bytes, content_type: str) -> str:
    ct = (content_type or "").lower()
    if not data:
        return "empty"
    if data[:8] == b"\x89PNG\r\n\x1a\n" or data[:2] == b"\xff\xd8" or data[:6] in (
        b"GIF87a",
        b"GIF89a",
    ):
        return "image"
    if ct.startswith("text/") or ct in {"application/json", "application/csv", "text/csv"}:
        return "text"
    try:
        data[:4096].decode("utf-8")
        if b"\x00" not in data[:4096]:
            return "text"
    except Exception:
        pass
    if ct.startswith("video/") or ct.startswith("audio/"):
        return "av"
    return "binary"


def _png_size(data: bytes) -> dict[str, int] | None:
    if len(data) < 24:
        return None
    if data[12:16] != b"IHDR":
        return None
    w, h = struct.unpack_from(">II", data, 16)
    return {"width": int(w), "height": int(h)}


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9):
            i += 2
            continue
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if i + 3 >= n:
            break
        seglen = struct.unpack_from(">H", data, i + 2)[0]
        if seglen < 2:
            break
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            if i + 8 < n:
                h, w = struct.unpack_from(">HH", data, i + 5)
                return int(w), int(h)
            return None
        i += 2 + seglen
    return None


def _jpeg_exif_lite(data: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    idx = data.find(b"Exif\x00\x00")
    if idx < 0:
        return out
    blob = data[idx : idx + 2048]
    m = re.search(rb"(\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2})", blob)
    if m:
        out["DateTime"] = m.group(1).decode("ascii", errors="ignore")
    if b"Apple" in blob:
        out["Make"] = "Apple"
    elif b"Canon" in blob:
        out["Make"] = "Canon"
    elif b"Nikon" in blob:
        out["Make"] = "Nikon"
    return out


def _ffprobe_duration(data: bytes, name: str) -> float | None:
    import os
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("ffprobe"):
        return None
    suffix = os.path.splitext(name)[1] or ".bin"
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as fh:
            fh.write(data)
            fh.flush()
            proc = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    fh.name,
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        if proc.returncode != 0:
            return None
        return float(proc.stdout.strip())
    except Exception:
        return None
