"""Archived local Growth signature in a disposable full-schema installation DB."""
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from psycopg.conninfo import conninfo_to_dict

from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.installation_revalidation import _record_from_row
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_snapshot import _SNAPSHOT_QUERY
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.db import connect
from aos_api.ecommerce_growth_registration_qualification import require_growth_registration_claims
from aos_api.extension_runtime.admission import admit_runtime_artifact
from aos_api.extension_runtime.oci_driver import OciDriver
from aos_api.extension_runtime.schema_conditions import admit_schema_requirements
from aos_api.tenant_scope import TenantScope


pytestmark = pytest.mark.skipif(
    os.getenv('AOS_EXTENSION_PG_TEST') != '1' or os.getenv('AOS_EXTENSION_OCI_TEST') != '1'
    or not os.getenv('AOS_GROWTH112_SIGNED_RECEIPT'),
    reason='disposable PG, isolated OCI and explicit archived signed receipt required',
)
ROOT = Path(__file__).resolve().parents[4]
SCOPE = TenantScope('org-org', 'dev-project')


def _load_script(name):
    path = ROOT / 'scripts' / name
    spec = importlib.util.spec_from_file_location(name.removesuffix('.py'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_signed_growth_release_reaches_approved_installation_in_full_schema(tmp_path):
    database = conninfo_to_dict(os.environ['AOS_DATABASE_URL'])['dbname']
    assert database.startswith('aos_test_') and database.endswith('_ti4_test')
    signed = _load_script('a0v_growth_112_successor_clone.py').check_signed_receipt(
        Path(os.environ['AOS_GROWTH112_SIGNED_RECEIPT']), expected_growth='1.12.0',
    )
    trust = FileTrustRootProvider(signed['trust_path']).snapshot()
    loader = ManifestLoader({signed['source_alias']: signed['signed_tree']}, trust_roots=trust)
    registry = RegistryService(
        store=PostgresRegistryStore(connect), loader=loader, trust_roots=trust,
    )
    with connect(SCOPE) as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','isolated test') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated test') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_org(id,name) VALUES('org-org','isolated test') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated test') ON CONFLICT DO NOTHING")
    for relative, bundle_id, version, _ in signed['builder'].ALL_CASES:
        source_ref = f"bundle://{signed['source_alias']}/{relative}"
        loaded = loader.load(source_ref)
        identity = dict(publisher='aos', bundle_id=bundle_id)
        access = dict(publisher_scopes={'aos'})
        registry.create_bundle(**identity, kind=loaded.manifest.kind,
                               display_name=loaded.manifest.metadata.display_name, actor='test-author',
                               roles={'developer'}, **access)
        registry.create_version(**identity, source_ref=source_ref,
                                actor='test-author', roles={'developer'}, **access)
        registry.validate(**identity, version=version,
                          actor='test-validator', roles={'developer'}, **access)
        registry.publish(**identity, version=version,
                         actor='test-publisher', roles={'asset-publisher'}, **access)
    installed = _load_script('a0v_canonical_ecommerce_first_install.py').create_approved_first_installation(
        connect_factory=connect, state_dir=tmp_path,
        core_version='1.4.0', adapter_version='1.23.0', growth_version='1.12.0',
        operations_version='1.2.0', trust_path=signed['trust_path'],
        idempotency_prefix='test-growth-112-full-schema',
        overlay_revision='test-growth-112-full-schema',
        maker_actor='test-author', checker_actor='test-reviewer',
    )
    assert installed['installationState'] == 'approved'
    assert installed['installationEtag'] == 3
    lock = PostgresCompositionStore(connect).get_lock(
        org_id=SCOPE.org_id, project_id=SCOPE.project_id,
        composition_id=installed['compositionId'], revision=installed['lockRevision'],
    )
    selected = [member for member in lock.payload.resolved
                if member.id == 'solution.ecommerce.growth']
    assert len(selected) == 1
    assert require_growth_registration_claims(selected[0]).startswith('sha256:')
    resolved = {member.id: member for member in lock.payload.resolved}
    with connect(SCOPE) as conn:
        current_records = {
            row['bundle_id']: _record_from_row(row)
            for row in conn.execute(_SNAPSHOT_QUERY).fetchall()
        }
    for relative, bundle_id, _version, _package in signed['builder'].RUNTIME_CASES:
        root = signed['signed_tree'] / relative
        record = current_records[bundle_id]
        artifact = lambda path, limit: (root / path).read_bytes()
        requirements = admit_schema_requirements(
            record=record, selected=resolved[bundle_id],
            policy=ReleasePolicy(trust_roots=trust), checked_at=datetime.now(timezone.utc),
            read_artifact=artifact,
        )
        assert len(requirements) == 1
        admitted = admit_runtime_artifact(
            record=record, selected=resolved[bundle_id],
            policy=ReleasePolicy(trust_roots=trust), checked_at=datetime.now(timezone.utc),
            read_artifact=artifact, platform='linux/arm64',
            driver=OciDriver(context='colima-aos-extension'),
        )
        assert admitted.image_id == json.loads(
            (root / 'artifacts/runtime-image-index.json').read_text())['images'][0]['configDigest']
        assert admitted.package_hash == record.content_hash
    with connect(SCOPE) as conn:
        assert conn.execute('''SELECT count(*) AS n FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s''',
            (*SCOPE.key, installed['installationId'])).fetchone()['n'] == 0
        assert conn.execute("SELECT count(*) AS n FROM bundle_installation WHERE org_id='dev-org'").fetchone()['n'] == 0
