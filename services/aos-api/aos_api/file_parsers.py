"""T4.4b file parsers — T05 plugin IDs; stdlib-first (docx/xlsx via OOXML)."""
from __future__ import annotations

import csv
import io
import re
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def list_plugins() -> list[dict[str, str]]:
    """98 · 清单来自 plugins/parsers 注册表；实现仍 inproc。"""
    from aos_api.parser_registry import list_plugins_compat

    return list_plugins_compat()


def detect_format(name: str | None, content_type: str | None, data: bytes) -> str:
    n = (name or "").lower()
    ct = (content_type or "").lower()
    if n.endswith(".docx") or "wordprocessingml" in ct:
        return "docx"
    if n.endswith(".xlsx") or "spreadsheetml" in ct:
        return "xlsx"
    if n.endswith(".pdf") or "application/pdf" in ct:
        return "pdf"
    if n.endswith(".csv") or "text/csv" in ct:
        return "csv"
    if n.endswith(".md") or "text/markdown" in ct:
        return "md"
    if n.endswith((".txt", ".text")) or ct.startswith("text/"):
        return "txt"
    if data[:4] == b"%PDF":
        return "pdf"
    if data[:2] == b"PK":
        # zip — sniff
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = set(zf.namelist())
                if "word/document.xml" in names:
                    return "docx"
                if "xl/workbook.xml" in names:
                    return "xlsx"
        except zipfile.BadZipFile:
            pass
    if data[:8] in (b"\x89PNG\r\n\x1a\n",) or data[:2] == b"\xff\xd8":
        return "image"
    return "bin"


def _decode_text(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_text(data: bytes, fmt: str) -> dict[str, Any]:
    text = _decode_text(data)
    sheets = None
    if fmt == "csv":
        reader = csv.reader(io.StringIO(text))
        rows = [row for row in reader]
        sheets = [{"name": "Sheet1", "rows": rows[:200]}]
        # keep raw text too
    return {
        "ok": True,
        "parser": "parser-text",
        "format": fmt,
        "text": text,
        "charCount": len(text),
        "sheets": sheets,
        "hint": None,
    }


def _parse_docx(data: bytes) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return {
            "ok": False,
            "parser": "parser-office-word",
            "format": "docx",
            "text": "",
            "charCount": 0,
            "sheets": None,
            "hint": f"invalid docx: {exc}",
        }
    root = ET.fromstring(xml)
    parts: list[str] = []
    for node in root.iter(f"{W_NS}t"):
        if node.text:
            parts.append(node.text)
        if node.tail:
            parts.append(node.tail)
    # paragraph breaks
    text = "\n".join(
        "".join(t.text or "" for t in p.iter(f"{W_NS}t"))
        for p in root.iter(f"{W_NS}p")
    ).strip()
    if not text:
        text = "".join(parts).strip()
    return {
        "ok": bool(text),
        "parser": "parser-office-word",
        "format": "docx",
        "text": text,
        "charCount": len(text),
        "sheets": None,
        "hint": None if text else "empty document",
    }


def _col_to_idx(col: str) -> int:
    n = 0
    for ch in col:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
    return max(n - 1, 0)


def _parse_xlsx(data: bytes) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                sroot = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for si in sroot.findall(f"{A_NS}si"):
                    texts = [t.text or "" for t in si.iter(f"{A_NS}t")]
                    shared.append("".join(texts))
            sheet_names = [
                n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
            ]
            sheets_out: list[dict[str, Any]] = []
            lines: list[str] = []
            for sn in sorted(sheet_names)[:5]:
                root = ET.fromstring(zf.read(sn))
                grid: dict[tuple[int, int], str] = {}
                max_r, max_c = 0, 0
                for c in root.iter(f"{A_NS}c"):
                    ref = c.get("r") or "A1"
                    m = re.match(r"([A-Z]+)(\d+)", ref)
                    if not m:
                        continue
                    col_i, row_i = _col_to_idx(m.group(1)), int(m.group(2)) - 1
                    max_r, max_c = max(max_r, row_i), max(max_c, col_i)
                    v = c.find(f"{A_NS}v")
                    raw = v.text if v is not None else ""
                    if c.get("t") == "s" and raw.isdigit():
                        idx = int(raw)
                        val = shared[idx] if idx < len(shared) else raw
                    else:
                        val = raw or ""
                    grid[(row_i, col_i)] = val
                rows = []
                for r in range(max_r + 1):
                    row = [grid.get((r, c), "") for c in range(max_c + 1)]
                    rows.append(row)
                    if any(row):
                        lines.append("\t".join(row))
                sheets_out.append({"name": sn.split("/")[-1], "rows": rows[:200]})
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        return {
            "ok": False,
            "parser": "parser-office-sheet",
            "format": "xlsx",
            "text": "",
            "charCount": 0,
            "sheets": None,
            "hint": f"invalid xlsx: {exc}",
        }
    text = "\n".join(lines)
    return {
        "ok": bool(text),
        "parser": "parser-office-sheet",
        "format": "xlsx",
        "text": text,
        "charCount": len(text),
        "sheets": sheets_out,
        "hint": None if text else "empty workbook",
    }


def _parse_pdf(data: bytes) -> dict[str, Any]:
    # Prefer pypdf when available
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n".join(pages).strip()
        if text:
            return {
                "ok": True,
                "parser": "parser-pdf-text",
                "format": "pdf",
                "text": text,
                "charCount": len(text),
                "sheets": None,
                "hint": None,
                "engine": "pypdf",
                "pageCount": len(pages),
            }
        return {
            "ok": False,
            "parser": "parser-pdf-ocr",
            "format": "pdf",
            "text": "",
            "charCount": 0,
            "sheets": None,
            "hint": "no text layer — use OCR sidecar (/v1/docintel/ocr)",
            "engine": "pypdf",
            "pageCount": len(pages),
        }
    except Exception:
        pass

    # Heuristic: extract printable Latin/CJK-ish runs from PDF streams
    raw = data.decode("latin-1", errors="ignore")
    chunks = re.findall(r"\((?:\\.|[^\\)]){2,}\)", raw)
    cleaned: list[str] = []
    for ch in chunks:
        s = ch[1:-1]
        s = s.replace("\\n", "\n").replace("\\r", "").replace("\\t", "\t")
        s = re.sub(r"\\[0-7]{1,3}", "", s)
        s = re.sub(r"\\.", "", s)
        if sum(c.isprintable() for c in s) >= max(2, len(s) // 2):
            cleaned.append(s)
    text = " ".join(cleaned).strip()
    # also Tj / TJ operators with UTF-16BE hex strings are skipped in MVP
    if len(text) >= 4:
        return {
            "ok": True,
            "parser": "parser-pdf-text",
            "format": "pdf",
            "text": text[:20000],
            "charCount": len(text),
            "sheets": None,
            "hint": None,
            "engine": "pdf-heuristic",
        }
    return {
        "ok": False,
        "parser": "parser-pdf-ocr",
        "format": "pdf",
        "text": "",
        "charCount": 0,
        "sheets": None,
        "hint": "pdf text layer unavailable — install pypdf or use OCR",
        "engine": "none",
    }


def extract(
    *,
    data: bytes,
    name: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    fmt = detect_format(name, content_type, data)
    if fmt in {"txt", "md", "csv"}:
        out = _parse_text(data, fmt)
    elif fmt == "docx":
        out = _parse_docx(data)
    elif fmt == "xlsx":
        out = _parse_xlsx(data)
    elif fmt == "pdf":
        out = _parse_pdf(data)
    elif fmt == "image":
        out = {
            "ok": False,
            "parser": "parser-pdf-ocr",
            "format": "image",
            "text": "",
            "charCount": 0,
            "sheets": None,
            "hint": "image — use OCR sidecar (/v1/docintel/ocr)",
        }
    else:
        # try utf-8 text fallback
        try:
            text = _decode_text(data)
            if text.strip() and all(c.isprintable() or c in "\n\r\t" for c in text[:2000]):
                out = {
                    "ok": True,
                    "parser": "parser-text",
                    "format": "txt",
                    "text": text,
                    "charCount": len(text),
                    "sheets": None,
                    "hint": "binary sniffed as text",
                }
            else:
                out = {
                    "ok": False,
                    "parser": "parser-text",
                    "format": fmt,
                    "text": "",
                    "charCount": 0,
                    "sheets": None,
                    "hint": f"unsupported format: {fmt}",
                }
        except Exception as exc:  # noqa: BLE001
            out = {
                "ok": False,
                "parser": "parser-text",
                "format": fmt,
                "text": "",
                "charCount": 0,
                "sheets": None,
                "hint": str(exc),
            }
    out.setdefault("format", fmt)
    out["preview"] = (out.get("text") or "")[:240]
    return out


# —— test helpers: minimal OOXML builders ——


def build_minimal_docx(text: str) -> bytes:
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>
</w:document>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        zf.writestr("word/document.xml", document)
    return buf.getvalue()


def build_minimal_xlsx(rows: list[list[str]]) -> bytes:
    shared: list[str] = []
    sheet_rows = []
    for r_i, row in enumerate(rows, start=1):
        cs = []
        for c_i, val in enumerate(row):
            col = chr(ord("A") + c_i)
            if val not in shared:
                shared.append(val)
            idx = shared.index(val)
            cs.append(f'<c r="{col}{r_i}" t="s"><v>{idx}</v></c>')
        sheet_rows.append(f'<row r="{r_i}">{"".join(cs)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )
    sst = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared)}" uniqueCount="{len(shared)}">'
        + "".join(f"<si><t>{s}</t></si>" for s in shared)
        + "</sst>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>""",
        )
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        zf.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>""",
        )
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
        zf.writestr("xl/sharedStrings.xml", sst)
    return buf.getvalue()


def build_minimal_pdf(text: str) -> bytes:
    """Tiny PDF with a text string operator (heuristic-friendly)."""
    # Escape for PDF literal string
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 100 700 Td ({safe}) Tj ET"
    stream_bytes = stream.encode("latin-1", errors="replace")
    objects = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream_bytes)} >>stream\n".encode("ascii")
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )
    objects.append(
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)
