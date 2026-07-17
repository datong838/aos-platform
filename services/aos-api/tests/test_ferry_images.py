"""T5.6 Ferry image layer — scheme 56."""

import base64
import io
import tarfile


def test_export_includes_images_layer(client, auth_headers):
    ex = client.post("/v1/apollo/ferry/export", headers=auth_headers, json={})
    assert ex.status_code == 200
    data = ex.json()
    assert data["mode"] == "mvp-hmac+images"
    assert data.get("images")
    assert data["images"]["images"]

    raw = base64.b64decode(data["contentBase64"])
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        names = {m.name for m in tar.getmembers() if m.isfile()}
    assert "artifacts/images.json" in names
    assert "artifacts/images.sig" in names


def test_images_roundtrip(client, auth_headers):
    ex = client.post("/v1/apollo/ferry/export", headers=auth_headers, json={})
    im = client.post(
        "/v1/apollo/ferry/import",
        headers=auth_headers,
        json={"contentBase64": ex.json()["contentBase64"]},
    )
    assert im.status_code == 200
    body = im.json()
    assert body["ok"] is True
    assert body["mode"] == "mvp-hmac+images"
    assert body["images"]["cosignMode"] in {"cosign-dev-hmac", "cosign"}


def test_missing_images_sig_rejected(client, auth_headers):
    ex = client.post("/v1/apollo/ferry/export", headers=auth_headers, json={})
    raw = base64.b64decode(ex.json()["contentBase64"])
    out = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as src, tarfile.open(
        fileobj=out, mode="w:gz"
    ) as dst:
        for m in src.getmembers():
            if m.name == "artifacts/images.sig":
                continue
            f = src.extractfile(m)
            data = f.read() if f else b""
            info = tarfile.TarInfo(name=m.name)
            info.size = len(data)
            dst.addfile(info, io.BytesIO(data))
    bad = base64.b64encode(out.getvalue()).decode("ascii")
    im = client.post(
        "/v1/apollo/ferry/import",
        headers=auth_headers,
        json={"contentBase64": bad},
    )
    # may fail checksum first if checksums still list images.sig — either is ok
    assert im.status_code in {400, 403}
    assert im.json()["code"] in {
        "FERRY_IMAGE_SIGNATURE_MISSING",
        "FERRY_CHECKSUM_MISMATCH",
        "FERRY_SIGNATURE_INVALID",
    }


def test_include_images_false_compat(client, auth_headers):
    ex = client.post(
        "/v1/apollo/ferry/export",
        headers=auth_headers,
        json={"includeImages": False},
    )
    assert ex.status_code == 200
    assert ex.json()["mode"] == "mvp-hmac"
    raw = base64.b64decode(ex.json()["contentBase64"])
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        names = {m.name for m in tar.getmembers() if m.isfile()}
    assert "artifacts/images.json" not in names

    im = client.post(
        "/v1/apollo/ferry/import",
        headers=auth_headers,
        json={"contentBase64": ex.json()["contentBase64"]},
    )
    assert im.status_code == 200
    assert im.json()["mode"] == "mvp-hmac"


def test_strip_images_sig_via_repack_clear_checksum(client, auth_headers):
    """Drop images.sig and rewrite checksums so only image-sig gate fires."""
    from aos_api.ferry import IMAGES_JSON, IMAGES_SIG, CHECKSUMS_NAME, _sha256_bytes

    ex = client.post("/v1/apollo/ferry/export", headers=auth_headers, json={})
    raw = base64.b64decode(ex.json()["contentBase64"])
    members: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile() or m.name == IMAGES_SIG:
                continue
            f = tar.extractfile(m)
            members[m.name] = f.read() if f else b""

    # rebuild checksums without images.sig
    lines = []
    for path, data in sorted(members.items()):
        if path == CHECKSUMS_NAME:
            continue
        lines.append(f"{_sha256_bytes(data)}  {path}")
    members[CHECKSUMS_NAME] = ("\n".join(lines) + "\n").encode("utf-8")

    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    bad = base64.b64encode(out.getvalue()).decode("ascii")
    assert IMAGES_JSON in members
    im = client.post(
        "/v1/apollo/ferry/import",
        headers=auth_headers,
        json={"contentBase64": bad},
    )
    assert im.status_code == 403
    assert im.json()["code"] == "FERRY_IMAGE_SIGNATURE_MISSING"
