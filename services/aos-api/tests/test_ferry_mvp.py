"""T5.6 Ferry MVP — scheme 53."""

import base64
import io
import tarfile


def test_ferry_status_not_deferred(client, auth_headers):
    st = client.get("/v1/apollo/ferry/status", headers=auth_headers)
    assert st.status_code == 200
    body = st.json()
    assert body["deferred"] is False
    assert body["mode"] == "mvp-hmac+images"
    assert "skopeo" in body and "cosign" in body


def test_ferry_export_import_roundtrip(client, auth_headers):
    ex = client.post(
        "/v1/apollo/ferry/export",
        headers=auth_headers,
        json={"env": "dev", "channel": "lite", "contents": ["WorkOrder"]},
    )
    assert ex.status_code == 200
    data = ex.json()
    assert data["contentBase64"]
    assert data["manifest"]["bundleId"] == data["bundleId"]

    im = client.post(
        "/v1/apollo/ferry/import",
        headers=auth_headers,
        json={"contentBase64": data["contentBase64"]},
    )
    assert im.status_code == 200
    assert im.json()["ok"] is True
    assert im.json()["verified"] is True
    assert im.json()["bundleId"] == data["bundleId"]


def test_ferry_import_rejects_missing_signature(client, auth_headers):
    ex = client.post("/v1/apollo/ferry/export", headers=auth_headers, json={})
    assert ex.status_code == 200
    im = client.post(
        "/v1/apollo/ferry/import",
        headers=auth_headers,
        json={"contentBase64": ex.json()["contentBase64"], "stripSignature": True},
    )
    assert im.status_code == 403
    assert im.json()["code"] == "FERRY_SIGNATURE_MISSING"


def test_ferry_import_rejects_tampered_manifest(client, auth_headers):
    ex = client.post("/v1/apollo/ferry/export", headers=auth_headers, json={})
    raw = base64.b64decode(ex.json()["contentBase64"])
    out = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as src, tarfile.open(
        fileobj=out, mode="w:gz"
    ) as dst:
        for m in src.getmembers():
            f = src.extractfile(m)
            data = f.read() if f else b""
            if m.name == "manifest.json":
                data = data.replace(b'"lite"', b'"evil"')
            info = tarfile.TarInfo(name=m.name)
            info.size = len(data)
            dst.addfile(info, io.BytesIO(data))
    bad = base64.b64encode(out.getvalue()).decode("ascii")
    im = client.post(
        "/v1/apollo/ferry/import",
        headers=auth_headers,
        json={"contentBase64": bad},
    )
    # tamper breaks signature and/or checksum
    assert im.status_code in {400, 403}
    assert im.json()["code"] in {
        "FERRY_SIGNATURE_INVALID",
        "FERRY_CHECKSUM_MISMATCH",
    }
