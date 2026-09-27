"""Read-only exact-source preflight; fakes expose no publish/write method."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from aos_api.aip_solution_pack_publisher import AipSolutionPackPublisher
from aos_api.aip_solution_pack_signed_preflight import (
    CURRENT_SOURCE_REF, CurrentDefinitionSourceBlocked, inspect_current_signed_source,
)
from aos_api.asset_registry.contracts import BundleEvidenceStatus, BundleEvidenceType


HASH = "sha256:" + "a" * 64
FINGERPRINT = "sha256:" + "b" * 64


def _case(tmp_path: Path, monkeypatch):
    bundle_dir = tmp_path / "solution.ecommerce.growth" / "1.11.0"
    bundle_dir.mkdir(parents=True)
    candidate = SimpleNamespace(publisher="aos", id="solution.ecommerce.growth", version="1.11.0",
        content_hash=HASH, signature_fingerprint=FINGERPRINT)
    snapshot = SimpleNamespace(candidates=[candidate], snapshot_hash="sha256:" + "c" * 64)
    loaded = SimpleNamespace(source_ref=CURRENT_SOURCE_REF, content_hash=HASH,
        manifest=SimpleNamespace(metadata=SimpleNamespace(id=candidate.id, version=candidate.version, publisher="aos")),
        evidence=[SimpleNamespace(type=BundleEvidenceType.SIGNATURE_VERIFICATION,
            status=BundleEvidenceStatus.VALID, artifact_hash=FINGERPRINT)])

    class Reader:
        def read(self):
            return snapshot

    class Loader:
        def __init__(self):
            self.calls = []

        def load(self, source_ref):
            self.calls.append(source_ref)
            return loaded

    monkeypatch.setattr(AipSolutionPackPublisher, "inspect_current_candidate", classmethod(
        lambda _cls, path: SimpleNamespace(agent_count=6, skill_count=37, capability_count=10)
        if path == bundle_dir else (_ for _ in ()).throw(AssertionError("wrong directory"))))
    return Reader(), Loader(), snapshot, candidate, loaded


def test_exact_current_source_requires_two_identical_signed_loads(tmp_path, monkeypatch):
    reader, loader, _, _, _ = _case(tmp_path, monkeypatch)
    proof = inspect_current_signed_source(reader=reader, loader=loader, signed_root=tmp_path)
    assert (proof.agent_count, proof.skill_count, proof.capability_count) == (6, 37, 10)
    assert proof.content_hash == HASH and proof.signature_fingerprint == FINGERPRINT
    assert loader.calls == [CURRENT_SOURCE_REF, CURRENT_SOURCE_REF]


@pytest.mark.parametrize("drift", ("missing", "hash", "signature", "missing_signature", "status", "source", "version", "second_load"))
def test_current_source_fails_closed_on_exact_drift(tmp_path, monkeypatch, drift):
    reader, loader, snapshot, candidate, loaded = _case(tmp_path, monkeypatch)
    if drift == "missing":
        snapshot.candidates = []
    elif drift == "hash":
        candidate.content_hash = "sha256:" + "d" * 64
    elif drift == "signature":
        loaded.evidence[0].artifact_hash = "sha256:" + "d" * 64
    elif drift == "missing_signature":
        loaded.evidence = []
    elif drift == "status":
        loaded.evidence[0].status = BundleEvidenceStatus.INVALID
    elif drift == "source":
        loaded.source_ref = "bundle://catalog/solution.ecommerce.growth/1.11.0"
    elif drift == "version":
        loaded.manifest.metadata.version = "1.3.0"
    elif drift == "second_load":
        original_load = loader.load
        def changed_on_second(source_ref):
            result = original_load(source_ref)
            if len(loader.calls) == 2:
                result.content_hash = "sha256:" + "d" * 64
            return result
        loader.load = changed_on_second
    with pytest.raises(CurrentDefinitionSourceBlocked):
        inspect_current_signed_source(reader=reader, loader=loader, signed_root=tmp_path)
    assert len(loader.calls) <= 2
