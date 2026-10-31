"""Content-only descriptor API; never release or execution authority."""
from copy import deepcopy
from inspect import Parameter, signature
from types import SimpleNamespace

import pytest

from aos_api.asset_registry.canonical_json import CanonicalJsonError, canonical_sha256
from aos_api.asset_registry.contracts import BundleManifest
from aos_api.asset_registry.errors import ManifestInvalidError
from aos_api.asset_registry.release_policy import (
    _verified_content_descriptor,
    verify_content_descriptor,
)


def manifest():
    return BundleManifest.model_validate({
        "apiVersion": "aos.dev/v1alpha1", "kind": "SolutionPack",
        "metadata": {"id": "solution.descriptor", "version": "1.0.0",
                     "displayName": "Descriptor", "publisher": "aos", "license": "internal"},
        "spec": {"platformApi": ">=1.7.0 <2.0.0", "dependencies": [],
                 "optionalDependencies": [], "conflicts": [], "exports": {},
                 "capabilities": {"provides": [], "requires": []},
                 "permissions": {"roles": [], "markings": [], "dataScopes": [], "actionTypes": []},
                 "migrations": {"plan": None, "downgradePolicy": "retain-canonical"},
                 "preflight": None, "regression": None, "rollback": None},
    })


def inputs():
    model = manifest()
    artifacts = [{"relativePath": "content.json", "digest": "sha256:" + "a" * 64,
                  "size": 17, "mediaType": "application/json"}]
    descriptor = {"manifest": model.model_dump(mode="json", by_alias=True, exclude_none=False),
                  "artifacts": artifacts}
    return model, artifacts, descriptor


def test_modern_descriptor_matches_original_and_preserves_inputs():
    model, artifacts, expected = inputs()
    before = deepcopy(expected)
    digest = canonical_sha256(expected)
    result = verify_content_descriptor(manifest=model, artifacts=artifacts, content_hash=digest)
    old = _verified_content_descriptor(SimpleNamespace(
        manifest=model, artifacts=artifacts, content_hash=digest))
    assert result == old == expected == before
    assert model.model_dump(mode="json", by_alias=True, exclude_none=False) == before["manifest"]
    assert artifacts == before["artifacts"]
    assert set(result) == {"manifest", "artifacts"}


def test_legacy_default_omission_keeps_original_signed_bytes():
    model, artifacts, current = inputs()
    persisted = deepcopy(current["manifest"])
    persisted["spec"]["exports"].pop("knowledge")
    expected = {"manifest": persisted, "artifacts": artifacts}
    before = deepcopy(expected)
    digest = canonical_sha256(expected)
    result = verify_content_descriptor(manifest=model, artifacts=artifacts,
        content_hash=digest, persisted_manifest=persisted)
    old = _verified_content_descriptor(SimpleNamespace(manifest=model,
        artifacts=artifacts, content_hash=digest, persisted_manifest=persisted))
    assert result == old == before
    assert canonical_sha256(result) == digest
    assert canonical_sha256(current) != digest


@pytest.mark.parametrize("damage", ["manifest", "artifact", "hash", "persisted", "missing-persisted"])
def test_damage_keeps_original_manifest_error(damage):
    model, artifacts, descriptor = inputs()
    persisted = deepcopy(descriptor["manifest"])
    persisted["spec"]["exports"].pop("knowledge")
    digest = canonical_sha256({"manifest": persisted, "artifacts": artifacts})
    if damage == "manifest":
        body = model.model_dump(mode="json", by_alias=True)
        body["metadata"]["displayName"] = "Different"
        model = BundleManifest.model_validate(body)
    elif damage == "artifact":
        artifacts = [{**artifacts[0], "size": 18}]
    elif damage == "hash":
        digest = "sha256:" + "f" * 64
    elif damage == "persisted":
        persisted["kind"] = "DomainPack"
    else:
        persisted = None
    kwargs = dict(manifest=model, artifacts=artifacts, content_hash=digest,
                  persisted_manifest=persisted)
    with pytest.raises(ManifestInvalidError) as new:
        verify_content_descriptor(**kwargs)
    with pytest.raises(ManifestInvalidError) as old:
        _verified_content_descriptor(SimpleNamespace(**kwargs))
    assert str(new.value) == str(old.value)


@pytest.mark.parametrize("artifact_value", [float("nan"), object()])
def test_original_canonical_value_rejection(artifact_value):
    model, _, descriptor = inputs()
    artifacts = [{"value": artifact_value}]
    with pytest.raises(CanonicalJsonError):
        verify_content_descriptor(manifest=model, artifacts=artifacts,
                                  content_hash=canonical_sha256(descriptor))


@pytest.mark.parametrize("field,value", [
    ("manifest", {}), ("artifacts", ()), ("content_hash", 1), ("persisted_manifest", []),
])
def test_new_api_rejects_wrong_exact_field_types(field, value):
    model, artifacts, descriptor = inputs()
    kwargs = dict(manifest=model, artifacts=artifacts,
                  content_hash=canonical_sha256(descriptor), persisted_manifest=None)
    kwargs[field] = value
    with pytest.raises(TypeError, match="exact content descriptor fields required"):
        verify_content_descriptor(**kwargs)


def test_public_signature_cannot_accept_release_grants():
    params = signature(verify_content_descriptor).parameters
    assert set(params) == {"manifest", "artifacts", "content_hash", "persisted_manifest"}
    assert all(p.kind is Parameter.KEYWORD_ONLY for p in params.values())
    model, artifacts, descriptor = inputs()
    kwargs = dict(manifest=model, artifacts=artifacts, content_hash=canonical_sha256(descriptor))
    for extra in ("signature", "approved", "evidence", "status", "release_policy"):
        with pytest.raises(TypeError):
            verify_content_descriptor(**kwargs, **{extra: True})


def test_old_current_path_does_not_read_legacy_property():
    model, artifacts, descriptor = inputs()

    class CurrentRecord:
        @property
        def persisted_manifest(self):
            raise AssertionError("current match must not inspect legacy storage")

    record = CurrentRecord()
    record.manifest, record.artifacts = model, artifacts
    record.content_hash = canonical_sha256(descriptor)
    assert _verified_content_descriptor(record) == descriptor
