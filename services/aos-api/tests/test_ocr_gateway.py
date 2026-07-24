from aos_api.ocr_gateway import ocr_page, probe_sidecar


def test_fallback_mock_when_url_unset(monkeypatch):
    monkeypatch.delenv("AOS_OCR_URL", raising=False)
    monkeypatch.setenv("AOS_OCR_FALLBACK", "mock")
    out = ocr_page(page=2, text_hint="hello-ocr")
    assert out["engine"] == "fallback-mock"
    assert out["sidecar"] == "fallback-mock"
    assert out["page"] == 2
    assert out["text"] == "hello-ocr"
    assert out["confidence"] > 0
    assert len(out["boxes"]) >= 1
    assert out["boxes"][0]["text"] == "hello-ocr"


def test_215m_fallback_mock_boxes_multi_token(monkeypatch):
    monkeypatch.delenv("AOS_OCR_URL", raising=False)
    monkeypatch.setenv("AOS_OCR_FALLBACK", "mock")
    out = ocr_page(page=1, text_hint="alpha beta gamma")
    assert len(out["boxes"]) == 3
    assert out["confidence"] > 0.5
    assert {b["text"] for b in out["boxes"]} == {"alpha", "beta", "gamma"}


def test_probe_unset(monkeypatch):
    monkeypatch.delenv("AOS_OCR_URL", raising=False)
    p = probe_sidecar()
    assert p["ok"] is False
    assert p["sidecar"] == "unset"


def test_ocr_via_api_fallback(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_OCR_URL", raising=False)
    monkeypatch.setenv("AOS_OCR_FALLBACK", "mock")
    r = client.post(
        "/v1/docintel/ocr",
        headers=auth_headers,
        json={"page": 1, "textHint": "unit-page"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "unit-page"
    assert body["sidecar"] in {"fallback-mock", "ocr"}
    assert "engine" in body


def test_pipeline_includes_ocr(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_OCR_URL", raising=False)
    monkeypatch.setenv("AOS_OCR_FALLBACK", "mock")
    r = client.post(
        "/v1/docintel/pipeline",
        headers=auth_headers,
        json={"page": 1, "textHint": "pipeline-ocr"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["batchOk"] is True
    assert body["ocr"]["text"] == "pipeline-ocr"
    assert body["ocr"]["sidecar"] in {"fallback-mock", "ocr"}
