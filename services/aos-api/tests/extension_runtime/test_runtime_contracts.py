import pytest
from pydantic import ValidationError

from aos_api.asset_registry.runtime_contracts import RuntimeSpec


def backend():
    return dict(entrypoint="backend/example/__init__.py:register", pythonPackage="example",
                schemaNamespace="example", profileId="internal-python-v1",
                imageIndex="artifacts/backend-image.json")


def runtime(**kwargs):
    return {"apiVersion": "aos.dev/bundle-runtime/v1alpha1", **kwargs}


def test_backend_and_frontend_are_independently_optional():
    assert "frontend" not in RuntimeSpec.model_validate(runtime(backend=backend())).model_dump(by_alias=True)
    RuntimeSpec.model_validate(runtime(frontend={"manifest": "frontend/manifest.json", "artifactHash": "sha256:" + "a" * 64}))


@pytest.mark.parametrize("patch", [{}, {"backend": None}, {"backend": {}}, {"tenant": "org-org"}, {"apiVersion": "other"}])
def test_invalid_runtime(patch):
    with pytest.raises(ValidationError):
        RuntimeSpec.model_validate(runtime(**patch))


@pytest.mark.parametrize("field,value", [
    ("entrypoint", "/backend/a.py:register"), ("entrypoint", "backend/../a.py:register"),
    ("entrypoint", "backend//a.py:register"), ("entrypoint", "backend/%2e/a.py:register"),
    ("entrypoint", "backend/a.py:other"), ("entrypoint", "backend/a.py:register;ls"),
    ("entrypoint", "backend\\a.py:register"), ("entrypoint", "backend/a.py\n:register"),
    ("pythonPackage", "a;ls"), ("pythonPackage", "a..b"), ("pythonPackage", "a" * 161),
    ("schemaNamespace", "A"), ("schemaNamespace", "a" * 64),
    ("profileId", "privileged"), ("imageIndex", "frontend/a.json"),
    ("imageIndex", "artifacts/a.json?x"), ("imageIndex", 123),
    ("imageIndex", "artifacts/" + "a" * 1024 + ".json"),
])
def test_invalid_backend(field, value):
    data = backend()
    data[field] = value
    with pytest.raises(ValidationError):
        RuntimeSpec.model_validate(runtime(backend=data))


def test_unknown_backend_field_rejected():
    with pytest.raises(ValidationError):
        RuntimeSpec.model_validate(runtime(backend={**backend(), "command": "sh"}))
