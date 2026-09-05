import hashlib
import json
import pytest

from aos_api.extension_runtime.artifact_cache import resolve_image_index


def data():
    return {"schemaVersion": 1, "images": [{"platform": "linux/arm64", "imageDigest": "sha256:" + "a"*64,
           "configDigest": "sha256:" + "b"*64, "dependencyLockHash": "sha256:" + "c"*64,
           "sbomPath": "evidence/sbom.json"}]}


def resolve(value, **kw):
    raw = json.dumps(value).encode()
    return resolve_image_index(raw, expected_hash="sha256:"+hashlib.sha256(raw).hexdigest(), platform="linux/arm64", **kw)


def test_exact_index():
    assert resolve(data()).config_digest == "sha256:"+"b"*64


@pytest.mark.parametrize("field,value", [("platform","linux/unknown"),("sbomPath","evidence/../x.json"),
    ("imageDigest","python:latest"),("configDigest","sha256:"+"A"*64),("secret","x")])
def test_bad_index(field,value):
    d=data(); d["images"][0][field]=value
    with pytest.raises(ValueError): resolve(d)


def test_digest_and_duplicate_rejected():
    with pytest.raises(ValueError):
        resolve_image_index(b'{}',expected_hash="sha256:"+"0"*64,platform="linux/arm64")
    d=data(); d["images"] *= 2
    with pytest.raises(ValueError): resolve(d)
