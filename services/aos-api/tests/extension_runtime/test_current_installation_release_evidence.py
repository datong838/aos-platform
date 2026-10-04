"""Read-only current installation release evidence; never a startup permission."""

import importlib.util
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.asset_registry.signature import FrozenTrustRootProvider
from aos_api.extension_runtime.current_installation_release_evidence import (
    CurrentReleaseEvidenceBlocked,
    read_current_installation_release_evidence,
    read_current_runtime_image_evidence,
)
from aos_api.extension_runtime import current_installation_release_evidence as release_evidence
from aos_api.extension_runtime.oci_driver import OciDriver
from aos_api.tenant_scope import TenantScope


ROOT = Path(__file__).resolve().parents[4]
RECEIPT = os.getenv("AOS_E17_READONLY_SIGNED_RECEIPT")
pytestmark = pytest.mark.skipif(not RECEIPT, reason="explicit read-only signed preview receipt required")


def _current_inputs():
    spec = importlib.util.spec_from_file_location(
        "current_preview_for_release_evidence", ROOT / "scripts/a0v_current_preview_http.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    parameters, report = module.preflight(signed_receipt=Path(RECEIPT))
    trust = FileTrustRootProvider(Path(report["trustRoots"])).snapshot()
    return (
        lambda: psycopg.connect(**parameters, row_factory=dict_row),
        ReleasePolicy(trust_roots=trust),
        ManifestLoader({"a0v-current": Path(report["signedRoot"])}, trust_roots=trust),
        report,
    )


def test_current_signed_installation_is_evidence_only():
    connect, policy, loader, report = _current_inputs()
    view = read_current_installation_release_evidence(
        connect_factory=connect,
        scope=TenantScope("org-org", "dev-project"),
        installation_id=report["installationId"],
        release_policy=policy,
        loader=loader,
    )
    assert view.authorization == "EVIDENCE_ONLY_NO_START"
    assert view.installation_id == report["installationId"]
    assert view.current_revision == 3
    assert view.active_revision is None
    assert len(view.releases) == report["publishedVersions"]
    assert any(item.bundle_id == "solution.ecommerce.growth" for item in view.releases)
    assert not hasattr(view, "ready") and not hasattr(view, "enabled")
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="INSTALLATION_NOT_ACTIVE"):
        read_current_runtime_image_evidence(
            connect_factory=connect,
            scope=TenantScope("org-org", "dev-project"),
            installation_id=report["installationId"],
            expected_generation="00000000-0000-0000-0000-000000000000",
            release_policy=policy, loader=loader,
            driver=OciDriver(context="colima-aos-extension"), platform="linux/arm64",
        )


def test_current_approved_installation_cannot_be_unique_active_capability_source():
    connect, policy, loader, _report = _current_inputs()
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="ACTIVE_INSTALLATION_MISSING"):
        release_evidence.read_unique_active_installation_release_evidence(
            connect_factory=connect,
            scope=TenantScope("org-org", "dev-project"),
            publisher="aos", bundle_id="solution.ecommerce.growth",
            version="1.11.0",
            content_hash="sha256:3d8817e01f53690adbd58698951c226e8c3917304a9ec4d7eee37d64bf02b328",
            release_policy=policy, loader=loader,
        )


def test_unique_active_capability_source_rejects_wrong_hash_and_other_tenant():
    connect, policy, loader, _report = _current_inputs()
    common = dict(
        connect_factory=connect, publisher="aos", bundle_id="solution.ecommerce.growth",
        version="1.11.0", release_policy=policy, loader=loader,
    )
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="ACTIVE_INSTALLATION_MISSING"):
        release_evidence.read_unique_active_installation_release_evidence(
            scope=TenantScope("org-org", "dev-project"),
            content_hash="sha256:" + "0" * 64, **common,
        )
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="ACTIVE_INSTALLATION_MISSING"):
        release_evidence.read_unique_active_installation_release_evidence(
            scope=TenantScope("dev-org", "dev-project"),
            content_hash="sha256:3d8817e01f53690adbd58698951c226e8c3917304a9ec4d7eee37d64bf02b328",
            **common,
        )


def test_unique_active_capability_source_rejects_ambiguous_installation_before_signed_read():
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @contextmanager
        def transaction(self):
            yield

        def execute(self, query, params=None):
            if "SELECT DISTINCT i.installation_id" in query:
                assert "i.active_revision=i.current_revision" in query
                assert "r.state='active'" in query
                assert "member->>'kind'='SolutionPack'" in query
                assert "member->>'contentHash'=%s" in query
                assert "LIMIT 2" in query
                assert params[:2] == ("org-org", "dev-project")
            return self

        def fetchall(self):
            return [
                {"installation_id": "00000000-0000-0000-0000-000000000001"},
                {"installation_id": "00000000-0000-0000-0000-000000000002"},
            ]

    _connect, policy, loader, _report = _current_inputs()
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="ACTIVE_INSTALLATION_AMBIGUOUS"):
        release_evidence.read_unique_active_installation_release_evidence(
            connect_factory=lambda: Connection(),
            scope=TenantScope("org-org", "dev-project"),
            publisher="aos", bundle_id="solution.ecommerce.growth",
            version="1.11.0",
            content_hash="sha256:3d8817e01f53690adbd58698951c226e8c3917304a9ec4d7eee37d64bf02b328",
            release_policy=policy, loader=loader,
        )


def test_current_approved_preview_cannot_select_formal_runtime():
    connect, policy, loader, report = _current_inputs()
    spec = importlib.util.spec_from_file_location(
        "current_preview_for_formal_selector", ROOT / "scripts/a0v_current_preview_http.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    with pytest.raises(module.PreviewBlocked, match="FORMAL_RELEASE_EVIDENCE_INVALID"):
        module.select_formal_current_release(
            connect_factory=connect, scope=TenantScope("org-org", "dev-project"),
            installation_id=report["installationId"],
            expected_generation="00000000-0000-0000-0000-000000000000",
            release_policy=policy, loader=loader,
            driver=OciDriver(context="colima-aos-extension"), platform="linux/arm64",
        )


def test_other_tenant_cannot_read_installation():
    connect, policy, loader, report = _current_inputs()
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="INSTALLATION_MISSING"):
        read_current_installation_release_evidence(
            connect_factory=connect,
            scope=TenantScope("dev-org", "dev-project"),
            installation_id=report["installationId"],
            release_policy=policy,
            loader=loader,
        )


def test_untrusted_release_cannot_make_evidence_view():
    connect, _policy, loader, report = _current_inputs()
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="RELEASE_EVIDENCE_INVALID"):
        read_current_installation_release_evidence(
            connect_factory=connect,
            scope=TenantScope("org-org", "dev-project"),
            installation_id=report["installationId"],
            release_policy=ReleasePolicy(trust_roots=FrozenTrustRootProvider({})),
            loader=loader,
        )


def test_missing_signed_source_cannot_make_evidence_view():
    connect, policy, _loader, report = _current_inputs()
    trust = FileTrustRootProvider(Path(report["trustRoots"])).snapshot()
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="RELEASE_EVIDENCE_INVALID"):
        read_current_installation_release_evidence(
            connect_factory=connect,
            scope=TenantScope("org-org", "dev-project"),
            installation_id=report["installationId"],
            release_policy=policy,
            loader=ManifestLoader({}, trust_roots=trust),
        )
