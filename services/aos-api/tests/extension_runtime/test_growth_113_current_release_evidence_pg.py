"""Growth 1.13 local signed releases through original isolated Registry/Installation producers."""

import importlib.util
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
import psycopg
from psycopg.rows import dict_row

from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.signature import FileTrustRootProvider, FrozenTrustRootProvider
from aos_api.db import connect, get_dsn
from aos_api.extension_runtime.current_installation_release_evidence import (
    CurrentReleaseEvidenceBlocked,
    read_current_installation_release_evidence,
)
from aos_api.tenant_scope import TenantScope


ROOT = Path(__file__).resolve().parents[4]
RECEIPT = os.getenv("AOS_GROWTH113_SIGNED_RECEIPT")
# The session fixture provides one disposable DB. The full OCI test publishes
# the same four coordinates, so this approved-only path runs in a separate PG session.
pytestmark = pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_PG_TEST") != "1"
    or os.getenv("AOS_EXTENSION_OCI_TEST") == "1" or not RECEIPT,
    reason="approved-only Growth 1.13 path requires a separate disposable PG session",
)
SCOPE = TenantScope("org-org", "dev-project")


def _reader_connect():
    return psycopg.connect(get_dsn(), row_factory=dict_row)


def _script(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_growth_113_exact_current_release_from_original_producers(tmp_path):
    receipt = json.loads(Path(RECEIPT).read_text())
    builder = _script("build_ecommerce_growth_1_13_candidates.py").load_builder()
    signed_tree = Path(receipt["signedTree"])
    trust_path = signed_tree.parent / "trust-roots.json"
    assert receipt["outcome"] == "SIGNED_TREE_GREEN"
    assert receipt["signedTreeHash"] == builder._tree_hash(signed_tree)
    assert receipt["keyId"] == "a0v-local-ecommerce-growth-1-13-v1"
    trust = FileTrustRootProvider(trust_path).snapshot()
    root = trust.get_trust_root(publisher="aos", key_id=receipt["keyId"])
    assert root is not None and root.revision == receipt["trustRootRevision"]
    policy = ReleasePolicy(trust_roots=trust)
    loader = ManifestLoader({"a0v-growth-113": signed_tree}, trust_roots=trust)
    registry = RegistryService(
        store=PostgresRegistryStore(connect), loader=loader, trust_roots=trust,
    )
    with connect(SCOPE) as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','isolated test') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated test') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_org(id,name) VALUES('org-org','isolated test') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated test') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES('org-org','dev-project','test-author','admin') ON CONFLICT DO NOTHING")
    for relative, bundle_id, version, _ in builder.ALL_CASES:
        source_ref = f"bundle://a0v-growth-113/{relative}"
        loaded = loader.load(source_ref)
        assert loaded.content_hash == receipt["contentHashes"][bundle_id]
        policy.evaluate(builder._release_record(loaded), checked_at=datetime.now(timezone.utc))
        identity = dict(publisher="aos", bundle_id=bundle_id)
        access = dict(publisher_scopes={"aos"})
        registry.create_bundle(
            **identity, kind=loaded.manifest.kind,
            display_name=loaded.manifest.metadata.display_name,
            actor="test-author", roles={"developer"}, **access,
        )
        registry.create_version(
            **identity, source_ref=source_ref,
            actor="test-author", roles={"developer"}, **access,
        )
        registry.validate(
            **identity, version=version,
            actor="test-validator", roles={"developer"}, **access,
        )
        registry.publish(
            **identity, version=version,
            actor="test-publisher", roles={"asset-publisher"}, **access,
        )
    installed = _script("a0v_canonical_ecommerce_first_install.py").create_approved_first_installation(
        connect_factory=connect, state_dir=tmp_path,
        core_version="1.4.0", adapter_version="1.23.0",
        growth_version="1.13.0", operations_version="1.2.0",
        trust_path=trust_path, idempotency_prefix="test-growth-113-release-evidence",
        overlay_revision="test-growth-113-release-evidence",
        maker_actor="test-author", checker_actor="test-reviewer",
    )
    view = read_current_installation_release_evidence(
        connect_factory=_reader_connect, scope=SCOPE,
        installation_id=installed["installationId"],
        release_policy=policy, loader=loader,
    )
    assert installed["installationState"] == "approved"
    assert view.authorization == "EVIDENCE_ONLY_NO_START"
    assert view.current_revision == 3 and view.active_revision is None
    assert len(view.releases) == 4
    growth = [item for item in view.releases if item.bundle_id == "solution.ecommerce.growth"]
    assert len(growth) == 1
    assert growth[0].version == "1.13.0"
    assert growth[0].content_hash == receipt["contentHashes"]["solution.ecommerce.growth"]
    with connect(SCOPE) as conn:
        with pytest.raises(psycopg.errors.CheckViolation,
                           match="canonical bundle control-plane rows are immutable"):
            with conn.transaction():
                conn.execute("""UPDATE bundle_installation_revision r
                    SET lock_hash=%s
                    WHERE r.org_id=%s AND r.project_id=%s AND r.revision=%s
                      AND r.installation_pk=(SELECT i.installation_pk FROM bundle_installation i
                        WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s)""",
                    ("sha256:" + "0" * 64, *SCOPE.key, view.current_revision,
                     *SCOPE.key, installed["installationId"]),
                )
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="INSTALLATION_MISSING"):
        read_current_installation_release_evidence(
            connect_factory=_reader_connect, scope=TenantScope("dev-org", "dev-project"),
            installation_id=installed["installationId"],
            release_policy=policy, loader=loader,
        )
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="RELEASE_EVIDENCE_INVALID"):
        read_current_installation_release_evidence(
            connect_factory=_reader_connect, scope=SCOPE,
            installation_id=installed["installationId"],
            release_policy=ReleasePolicy(trust_roots=FrozenTrustRootProvider({})),
            loader=loader,
        )
    tampered_tree = tmp_path / "tampered-signed-tree"
    shutil.copytree(signed_tree, tampered_tree)
    index = tampered_tree / "solution.ecommerce.growth/1.13.0/artifacts/runtime-image-index.json"
    index.write_bytes(index.read_bytes() + b" ")
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="RELEASE_BYTES_DRIFT"):
        read_current_installation_release_evidence(
            connect_factory=_reader_connect, scope=SCOPE,
            installation_id=installed["installationId"],
            release_policy=policy,
            loader=ManifestLoader({"a0v-growth-113": tampered_tree}, trust_roots=trust),
        )
    registry.revoke(
        publisher="aos", bundle_id="solution.ecommerce.growth", version="1.13.0",
        actor="test-publisher", roles={"asset-publisher"},
        publisher_scopes={"aos"}, reason="isolated revocation negative",
    )
    with pytest.raises(CurrentReleaseEvidenceBlocked, match="RELEASE_EVIDENCE_INVALID"):
        read_current_installation_release_evidence(
            connect_factory=_reader_connect, scope=SCOPE,
            installation_id=installed["installationId"],
            release_policy=policy, loader=loader,
        )
