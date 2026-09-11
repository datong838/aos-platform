from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from aos_api.asset_registry.composition_contracts import ResolvedBundle
from aos_api.asset_registry.errors import (
    ManifestInvalidError,
    RegistryIntegrityCorruptError,
    RegistrySnapshotStaleError,
)
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.extension_runtime.runtime_release_artifacts import CurrentRuntimeReleaseArtifacts
import aos_api.extension_runtime.runtime_release_artifacts as module
from aos_api.tenant_scope import TenantScope


def selected():
    return ResolvedBundle.model_validate({
        "publisher": "aos", "id": "runtime", "version": "1.0.0",
        "kind": "SolutionPack",
        "contentHash": "sha256:" + "1" * 64,
        "signatureFingerprint": "sha256:" + "2" * 64,
        "releaseEvidenceRevision": "sha256:" + "3" * 64,
        "dependencies": [], "capabilities": {"provides": [], "requires": []},
        "optionalDependencies": [], "conflicts": [],
        "permissions": {"roles": [], "markings": [], "dataScopes": [], "actionTypes": []},
        "migration": {"planRef": None, "downgradePolicy": "retain-canonical"},
        "contributions": [], "selectionReason": "requested",
    })


def reader(tmp_path):
    root = tmp_path / "catalog"
    bundle = root / "runtime"
    bundle.mkdir(parents=True)
    loader = ManifestLoader({"catalog": root})
    value = object.__new__(CurrentRuntimeReleaseArtifacts)
    value.scope = TenantScope("org-org", "dev-project")
    value.loader = loader
    return value, bundle


def artifact_row(path, raw, *, source="bundle://catalog/runtime", size=None, digest=None):
    return {
        "relative_path": path,
        "artifact_ref": source + "/" + path,
        "digest": digest or "sha256:" + hashlib.sha256(raw).hexdigest(),
        "size": len(raw) if size is None else size,
    }


def test_reads_allowlisted_bytes_bound_to_persisted_source_digest_and_size(tmp_path):
    value, bundle = reader(tmp_path)
    raw = b'{"schemaVersion":1}'
    path = "artifacts/runtime.json"
    target = bundle / path
    target.parent.mkdir()
    target.write_bytes(raw)
    value._load_artifacts = lambda _: (artifact_row(path, raw),)
    assert value.read_artifact(selected(), path, 1024) == raw


@pytest.mark.parametrize("case", ["mixed-source", "bad-ref", "duplicate", "missing", "size", "digest"])
def test_rejects_persisted_artifact_drift(tmp_path, case):
    value, bundle = reader(tmp_path)
    raw = b"trusted"
    path = "artifacts/runtime.json"
    target = bundle / path
    target.parent.mkdir()
    target.write_bytes(raw)
    rows = [artifact_row(path, raw)]
    if case == "mixed-source":
        rows.append(artifact_row("other.json", raw, source="bundle://catalog/other"))
    elif case == "bad-ref":
        rows[0]["artifact_ref"] = "bundle://catalog/runtime/wrong.json"
    elif case == "duplicate":
        rows.append(dict(rows[0]))
    elif case == "missing":
        path = "missing.json"
    elif case == "size":
        rows[0]["size"] = len(raw) + 1
    elif case == "digest":
        rows[0]["digest"] = "sha256:" + "0" * 64
    value._load_artifacts = lambda _: tuple(rows)
    with pytest.raises((ManifestInvalidError, RegistryIntegrityCorruptError, ValueError)):
        value.read_artifact(selected(), path, 1024)


@pytest.mark.parametrize("path,limit", [("", 1), (" x", 1), ("../x", 1), ("x", 0), ("x", True)])
def test_invalid_request_fails_before_database_read(tmp_path, path, limit):
    value, _ = reader(tmp_path)
    value._load_artifacts = lambda _: pytest.fail("database should not be read")
    with pytest.raises(ValueError):
        value.read_artifact(selected(), path, limit)


def test_record_requires_one_exact_published_row(tmp_path, monkeypatch):
    value, _ = reader(tmp_path)
    value._load_rows = lambda _: ()
    with pytest.raises(RegistrySnapshotStaleError):
        value.load_record(selected())


def test_record_rechecks_canonical_identity_after_row_conversion(tmp_path, monkeypatch):
    value, _ = reader(tmp_path)
    exact = selected()
    value._load_rows = lambda _: ({"row": "trusted"},)
    record = SimpleNamespace(
        publisher=exact.publisher,
        manifest=SimpleNamespace(metadata=SimpleNamespace(
            id=exact.id, version=exact.version,
        )),
        content_hash=exact.content_hash,
    )
    monkeypatch.setattr(module, "_record_from_row", lambda _: record)
    assert value.load_record(exact) is record
    record.content_hash = "sha256:" + "9" * 64
    with pytest.raises(RegistryIntegrityCorruptError):
        value.load_record(exact)
    value._load_rows = lambda _: ({}, {})
    with pytest.raises(RegistrySnapshotStaleError):
        value.load_record(selected())


def test_requires_exact_dependencies_and_resolved_type(tmp_path):
    with pytest.raises(TypeError, match="exact runtime"):
        CurrentRuntimeReleaseArtifacts(
            connect=lambda: None,
            scope=TenantScope("org", "project"),
            loader=object(),
        )
    value, _ = reader(tmp_path)
    with pytest.raises(TypeError, match="exact resolved"):
        value.read_artifact({}, "x", 1)
