import base64

from aos_api.file_parsers import (
    build_minimal_docx,
    build_minimal_pdf,
    build_minimal_xlsx,
    extract,
    list_plugins,
)


def test_list_plugins():
    ids = {p["id"] for p in list_plugins()}
    assert "parser-text" in ids
    assert "parser-office-word" in ids
    assert "parser-office-sheet" in ids
    assert "parser-pdf-text" in ids


def test_parse_txt_md_csv():
    assert extract(data=b"hello aos", name="a.txt")["text"] == "hello aos"
    assert "title" in extract(data=b"# title\nbody", name="a.md")["text"]
    csv_out = extract(data=b"id,title\n1,wo", name="a.csv")
    assert csv_out["ok"]
    assert csv_out["sheets"]


def test_parse_docx():
    blob = build_minimal_docx("Hello Docx AOS")
    out = extract(data=blob, name="note.docx")
    assert out["ok"]
    assert out["parser"] == "parser-office-word"
    assert "Hello Docx AOS" in out["text"]


def test_parse_xlsx():
    blob = build_minimal_xlsx([["id", "title"], ["1", "WorkOrder"]])
    out = extract(data=blob, name="sheet.xlsx")
    assert out["ok"]
    assert out["parser"] == "parser-office-sheet"
    assert "WorkOrder" in out["text"]


def test_parse_pdf_heuristic():
    blob = build_minimal_pdf("HelloPDFText")
    out = extract(data=blob, name="page.pdf")
    assert out["format"] == "pdf"
    # pypdf or heuristic should recover the literal
    assert out["ok"] is True
    assert "HelloPDFText" in out["text"]


def test_extract_api(client, auth_headers):
    payload = {
        "name": "unit.txt",
        "bytesBase64": base64.b64encode(b"unit-parse-text").decode(),
    }
    r = client.post("/v1/parsers/extract", headers=auth_headers, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["text"] == "unit-parse-text"


def test_media_parse_and_pipeline(client, auth_headers):
    doc = build_minimal_docx("Pipeline Docx")
    media = client.post(
        "/v1/media-sets",
        headers=auth_headers,
        json={
            "name": "p.docx",
            "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "bytesBase64": base64.b64encode(doc).decode(),
        },
    )
    assert media.status_code == 200
    rid = media.json()["rid"]
    parsed = client.post(f"/v1/media-sets/{rid}/parse", headers=auth_headers)
    assert parsed.status_code == 200
    assert "Pipeline Docx" in parsed.json()["text"]

    pipe = client.post(
        "/v1/docintel/pipeline",
        headers=auth_headers,
        json={"mediaRid": rid, "name": "p.docx"},
    )
    assert pipe.status_code == 200
    body = pipe.json()
    assert body["batchOk"] is True
    assert body["parse"]["ok"] is True
    assert "Pipeline Docx" in body["parse"]["text"]
    assert "ocr" in body
