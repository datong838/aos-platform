import hashlib
import os
from pathlib import Path

import pytest

from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_research_artifact_storage import (
    ResearchArtifactStorage,
    ResearchArtifactStorageBlocked,
    configured_artifact_hash_resolver,
    configured_memo_resolver,
)
from aos_api.ecommerce_internal_research_step_owner import configured_content_hash_resolver
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
OTHER = TenantScope("dev-org", "dev-project")
SAMPLE = "样例备忘，不是真实经营。\n"


def _plant(root: Path, org: str, project: str, name: str, payload: bytes) -> None:
    directory = root / org / project
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(payload)


def _ref(name: str, scope: TenantScope = SCOPE) -> str:
    return f"aos://research/{scope.org_id}/{scope.project_id}/{name}"


def test_unconfigured_root_keeps_resolvers_closed(monkeypatch):
    monkeypatch.delenv("AOS_RESEARCH_ARTIFACT_ROOT", raising=False)
    assert configured_artifact_hash_resolver() is None
    assert configured_memo_resolver() is None
    assert configured_content_hash_resolver() is None


def test_sample_memo_hash_matches_utf8_bytes(tmp_path, monkeypatch):
    _plant(tmp_path, "org-org", "dev-project", "memo.txt", SAMPLE.encode())
    monkeypatch.setenv("AOS_RESEARCH_ARTIFACT_ROOT", str(tmp_path))
    digest = hashlib.sha256(SAMPLE.encode()).hexdigest()
    resolver = configured_artifact_hash_resolver()
    assert resolver(SCOPE, _ref("memo.txt")) == digest
    storage = ResearchArtifactStorage(tmp_path)
    resolved = storage.resolve_memo(
        SCOPE,
        ArtifactRef(artifactId="memo-1", artifactType="internal_research_memo", revision="1", contentHash=digest),
        lookup=lambda _scope, _artifact_id: (_ref("memo.txt"), digest),
    )
    assert resolved.reference.content_hash == digest
    assert resolved.value == SAMPLE


@pytest.mark.parametrize(
    "content_ref",
    [
        "aos://research/org-org/dev-project/../../secret.txt",
        "aos://research/org-org/dev-project/../secret.txt",
        "/etc/passwd",
        "file:///etc/passwd",
        "http://127.0.0.1/memo.txt",
        "https://example.test/memo.txt",
        "aos://research/report.json",
    ],
)
def test_rejects_escape_and_network_refs_without_reading_outside(tmp_path, content_ref):
    root = tmp_path / "root"
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("do-not-read", encoding="utf-8")
    _plant(root, "org-org", "dev-project", "memo.txt", SAMPLE.encode())
    storage = ResearchArtifactStorage(root)
    with pytest.raises(ResearchArtifactStorageBlocked):
        storage.read_text(SCOPE, content_ref)
    assert secret.read_text(encoding="utf-8") == "do-not-read"


def test_symlink_outside_tenant_root_is_rejected(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("do-not-read", encoding="utf-8")
    tenant = tmp_path / "org-org" / "dev-project"
    tenant.mkdir(parents=True)
    (tenant / "memo.txt").symlink_to(secret)
    storage = ResearchArtifactStorage(tmp_path)
    with pytest.raises(ResearchArtifactStorageBlocked):
        storage.read_text(SCOPE, _ref("memo.txt"))
    assert secret.read_text(encoding="utf-8") == "do-not-read"


def test_other_tenant_cannot_read_positive_tenant_bytes(tmp_path):
    _plant(tmp_path, "org-org", "dev-project", "memo.txt", SAMPLE.encode())
    storage = ResearchArtifactStorage(tmp_path)
    with pytest.raises(ResearchArtifactStorageBlocked):
        storage.read_text(OTHER, _ref("memo.txt", SCOPE))
    with pytest.raises(ResearchArtifactStorageBlocked):
        storage.read_text(SCOPE, _ref("memo.txt", OTHER))


def test_hash_mismatch_non_utf8_and_oversize_do_not_return_body(tmp_path):
    storage = ResearchArtifactStorage(tmp_path)
    _plant(tmp_path, "org-org", "dev-project", "memo.txt", SAMPLE.encode())
    digest = hashlib.sha256(SAMPLE.encode()).hexdigest()
    with pytest.raises(ResearchArtifactStorageBlocked):
        storage.resolve_memo(
            SCOPE,
            ArtifactRef(artifactId="memo-1", artifactType="internal_research_memo", revision="1", contentHash="ab" * 32),
            lookup=lambda _scope, _artifact_id: (_ref("memo.txt"), digest),
        )
    _plant(tmp_path, "org-org", "dev-project", "binary.txt", b"\xff")
    with pytest.raises(ResearchArtifactStorageBlocked):
        storage.read_text(SCOPE, _ref("binary.txt"))
    huge = tmp_path / "org-org" / "dev-project" / "huge.txt"
    huge.write_bytes(b"a" * (2_097_152 + 1))
    with pytest.raises(ResearchArtifactStorageBlocked):
        storage.read_text(SCOPE, _ref("huge.txt"))


def test_blank_or_missing_root_stays_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("AOS_RESEARCH_ARTIFACT_ROOT", "   ")
    assert configured_artifact_hash_resolver() is None
    missing = tmp_path / "missing-root"
    monkeypatch.setenv("AOS_RESEARCH_ARTIFACT_ROOT", str(missing))
    assert configured_artifact_hash_resolver() is None
    monkeypatch.setenv("AOS_RESEARCH_ARTIFACT_ROOT", str(tmp_path / "memo.txt"))
    (tmp_path / "memo.txt").write_text(SAMPLE, encoding="utf-8")
    assert os.environ["AOS_RESEARCH_ARTIFACT_ROOT"]
    assert configured_artifact_hash_resolver() is None
