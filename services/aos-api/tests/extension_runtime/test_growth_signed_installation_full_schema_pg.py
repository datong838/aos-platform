"""Archived local Growth signature in a disposable full-schema installation DB."""
import asyncio
import importlib.util
import hashlib
import json
import os
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg.conninfo import conninfo_to_dict

from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.installation_revalidation import _record_from_row
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_snapshot import _SNAPSHOT_QUERY
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.control_policy import APPLY_INSTALLATION_OPERATION, VERIFY_INSTALLATION_OPERATION
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.db import connect
from aos_api.ecommerce_growth_registration_qualification import require_growth_registration_claims
from aos_api.extension_runtime.admission import admit_runtime_artifact
from aos_api.extension_runtime.oci_driver import OciDriver
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.extension_runtime.lifecycle_service import RuntimeLifecycleService
from aos_api.extension_runtime.preparation_worker import PreparationWorker
from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator
from aos_api.extension_runtime.schema_conditions import CurrentSchemaConditions, admit_schema_requirements
from aos_api.extension_runtime.schema_registry import apply_once, require_installed
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
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES('org-org','dev-project','test-author','admin') ON CONFLICT DO NOTHING")
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
    schema_check = _load_script('a0v_ecommerce_schema_receipts.py')
    alembic = Config(str(ROOT / 'services/aos-api/alembic.ini'))
    alembic.set_main_option('script_location', str(ROOT / 'services/aos-api/alembic'))
    graph = ScriptDirectory.from_config(alembic)
    revisions = lambda head: {item.revision for item in graph.walk_revisions(base='base', head=head)}
    with connect(SCOPE) as conn:
        current_records = {
            row['bundle_id']: _record_from_row(row)
            for row in conn.execute(_SNAPSHOT_QUERY).fetchall()
        }
    signed_roots = {bundle_id: signed['signed_tree'] / relative
                    for relative, bundle_id, _, _ in signed['builder'].RUNTIME_CASES}
    def read_member(selected, path, limit):
        raw = (signed_roots[selected.id] / path).read_bytes()
        assert len(raw) <= limit
        return raw
    policy = ReleasePolicy(trust_roots=trust)
    conditions = CurrentSchemaConditions(
        load_record=lambda member: current_records[member.id],
        read_artifact=read_member, policy=policy,
    )
    with connect(SCOPE) as conn:
        with pytest.raises(LookupError, match='required schema migration is not installed'):
            conditions(conn=conn, locked=None, lock=lock, actor='test-author')
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
        with connect() as conn:
            with conn.transaction():
                with pytest.raises(LookupError, match='required schema migration is not installed'):
                    require_installed(conn, requirements)
        raw = (root / 'artifacts/schema-compatibility.json').read_bytes()
        compatibility = json.loads(raw)
        assert requirements[0].migration_hash == 'sha256:' + hashlib.sha256(raw).hexdigest()
        assert compatibility['bundleId'] == bundle_id
        with connect() as conn:
            with conn.transaction():
                assert apply_once(conn, requirements[0],
                    lambda scoped: schema_check.verify_physical(scoped, compatibility, revisions)) is True
                require_installed(conn, requirements)
            conn.execute('SET ROLE aos_runtime')
            with conn.transaction():
                role = conn.execute("SELECT current_user AS role, has_table_privilege(current_user,'extension_schema_installation','INSERT') AS can_insert").fetchone()
                assert role == {'role': 'aos_runtime', 'can_insert': False}
                require_installed(conn, requirements)
                with pytest.raises(PermissionError, match='maintenance schema role required'):
                    apply_once(conn, requirements[0], lambda _: pytest.fail('runtime cannot migrate'))
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

    context = 'colima-aos-extension'
    def owned_containers():
        return set(subprocess.check_output([
            'docker', '--context', context, 'ps', '-aq', '--filter', 'label=aos.extension.owner',
        ], text=True, timeout=15).split())
    before_containers = owned_containers()
    revalidator = RuntimeReleaseRevalidator(release_policy=policy)
    store = PostgresInstallationStore(connect)
    legacy = InstallationService(
        store=store, composition_store=PostgresCompositionStore(connect),
        revalidator=InstallationRevalidator(release_policy=policy), planning_revalidator=revalidator,
    )
    lifecycle = RuntimeLifecycleService(installation_store=store,
                                        installation_reader=legacy, revalidator=revalidator)
    action = dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id,
                  installation_id=installed['installationId'], actor='test-author',
                  roles=['asset-installer'], markings=[])
    accepted = lifecycle.request_preparation(
        **action, kind='runtime-apply', idempotency_key='test-growth112-runtime-apply',
        if_match=f'"{installed["installationEtag"]}"', preparation_admission=lambda: True,
    )

    @contextmanager
    def runtime_connect():
        with connect() as conn:
            conn.execute('SET ROLE aos_runtime')
            conn.commit()
            yield conn

    worker = PreparationWorker(
        connect=runtime_connect, driver=OciDriver(context=context), installation_store=store,
        revalidator=revalidator,
        check_current_permission=CurrentControlPermission(operation=APPLY_INSTALLATION_OPERATION),
        load_record=lambda member: current_records[member.id],
        read_artifact=None, read_member_artifact=read_member,
        policy=policy, platform='linux/arm64', check_current_conditions=conditions,
        check_verification_permission=CurrentControlPermission(operation=VERIFY_INSTALLATION_OPERATION),
    )
    async def prepare_and_verify():
        job = await worker.start(
            **dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
            operation_id=accepted.response_json['operationId'],
            expected_revision=accepted.response_json['revision'],
        )
        try:
            applied = await job.prepared()
            assert applied.state == 'applied' and applied.active_revision is None
            requested = await asyncio.to_thread(
                lifecycle.request_preparation, **action, kind='runtime-verify',
                idempotency_key='test-growth112-runtime-verify',
                if_match=f'"{applied.etag_version}"', preparation_admission=lambda: True,
            )
            verified = await job.verify(
                operation_id=requested.response_json['operationId'],
                expected_revision=requested.response_json['revision'],
            )
            assert verified.state == 'active' and verified.active_revision is not None
            with connect(SCOPE) as conn:
                binding = conn.execute('''SELECT observed_state,enabled,operation_fence
                    FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s
                    AND installation_id=%s''', (*SCOPE.key, installed['installationId'])).fetchone()
                assert binding == {'observed_state': 'ready', 'enabled': False, 'operation_fence': True}
                assert conn.execute('''SELECT count(*) AS n FROM extension_operation_dispatch_binding
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s''',
                    (*SCOPE.key, installed['installationId'])).fetchone()['n'] == 0
                assert conn.execute("SELECT count(*) AS n FROM bundle_installation WHERE org_id='dev-org'").fetchone()['n'] == 0
        finally:
            await job.stop()
    asyncio.run(prepare_and_verify())
    assert owned_containers() == before_containers
