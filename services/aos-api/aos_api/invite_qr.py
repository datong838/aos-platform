"""193m — invite QR SVG (qrcode → SVG, no PIL)."""
from __future__ import annotations

from urllib.parse import urlparse
from xml.sax.saxutils import escape

import qrcode
from qrcode.image.svg import SvgPathImage


def build_invite_url(*, origin: str, invite_path: str) -> str:
    origin = (origin or "").strip().rstrip("/")
    if not origin:
        raise ValueError("origin is required")
    parsed = urlparse(origin)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("origin must be http(s) URL with host")
    path = invite_path if invite_path.startswith("/") else f"/{invite_path}"
    return f"{origin}{path}"


def invite_qr_svg(invite_url: str, *, box_size: int = 4, border: int = 2) -> str:
    """Return SVG markup for the invite absolute URL."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
        image_factory=SvgPathImage,
    )
    qr.add_data(invite_url)
    qr.make(fit=True)
    img = qr.make_image()
    raw = img.to_string()
    if isinstance(raw, bytes):
        text = raw.decode("utf-8")
    else:
        text = str(raw)
    # Ensure scannable payload is also in a data attr for tests / a11y
    if "data-invite-url=" not in text:
        safe = escape(invite_url).replace('"', "&quot;")
        text = text.replace(
            "<svg",
            f'<svg data-invite-url="{safe}"',
            1,
        )
    return text
