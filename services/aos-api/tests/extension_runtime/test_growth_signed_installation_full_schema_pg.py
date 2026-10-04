"""Local Growth 1.12/1.13 signatures in a disposable full-schema installation DB."""
import asyncio
import importlib.util
import hashlib
import json
import os
import secrets
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.installation_revalidation import _record_from_row
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.errors import RevisionConflictError
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_snapshot import _SNAPSHOT_QUERY
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.control_policy import APPLY_INSTALLATION_OPERATION, VERIFY_INSTALLATION_OPERATION
from aos_api.asset_registry.signature import FileTrustRootProvider, FrozenTrustRootProvider
from aos_api.db import connect, connect_read_only, get_dsn
from aos_api.aip_responsibility_template_authority import (
    ActiveBIBusinessResolver, ApprovedBIPreparationResolver,
)
from aos_api.aip_business_investigation_responsibility_template import BI_ROLE_BLUEPRINTS
from aos_api.auth import Principal
from aos_api.aip_bi_plan_issuer_connection import (
    connect_bi_issuer_read_only, connect_bi_issuer_write,
)
from aos_api.aip_bi_plan_issuer_contracts import BIIssuerRebindCommand
from aos_api.aip_bi_plan_issuer_process import (
    BIIssuerProcessBlocked, BIIssuerProcessConfig, build_bi_issuer_dispatcher,
)
from aos_api.aip_production_contract_store import (
    ProductionContractConflict, ProductionContractDependencyBlocked,
    ProductionContractIdempotencyConflict,
    ProductionContractNotFound, SignedBIPlanRebindReceiptReader,
)
from aos_api.ecommerce_business_investigation_aip_authority import (
    SignedBIPlanActiveRebindService, SignedBIPlanPreparationService,
)
from aos_api.ecommerce_growth_registration_qualification import require_growth_registration_claims
from aos_api.extension_runtime.admission import admit_runtime_artifact
from aos_api.extension_runtime.oci_driver import OciDriver
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.extension_runtime.current_installation_release_evidence import (
    CurrentReleaseEvidenceBlocked,
    _read_unique_active_in_transaction,
    read_current_installation_release_evidence,
    read_unique_active_installation_release_evidence,
    read_current_runtime_image_evidence,
)
from aos_api.extension_runtime.lifecycle_service import RuntimeLifecycleService
from aos_api.extension_runtime.preparation_worker import PreparationWorker
from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator
from aos_api.extension_runtime.schema_conditions import CurrentSchemaConditions, admit_schema_requirements
from aos_api.extension_runtime.schema_registry import apply_once, require_installed
from aos_api.tenant_scope import TenantScope
from plan_restricted_issuer_case import (
    assert_original_plan_store_with_restricted_login, cleanup_restricted_issuer_case,
)
from plan_restricted_evaluate_case import assert_restricted_blocked_evaluate_composes_lock


pytestmark = pytest.mark.skipif(
    os.getenv('AOS_EXTENSION_PG_TEST') != '1' or os.getenv('AOS_EXTENSION_OCI_TEST') != '1'
    or not (os.getenv('AOS_GROWTH112_SIGNED_RECEIPT') or os.getenv('AOS_GROWTH113_SIGNED_RECEIPT')),
    reason='disposable PG, isolated OCI and explicit local signed receipt required',
)
ROOT = Path(__file__).resolve().parents[4]
SCOPE = TenantScope('org-org', 'dev-project')


def _load_script(name):
    path = ROOT / 'scripts' / name
    spec = importlib.util.spec_from_file_location(name.removesuffix('.py'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _signed_release():
    growth_113 = os.getenv('AOS_GROWTH113_SIGNED_RECEIPT')
    if growth_113 and os.getenv('AOS_GROWTH112_SIGNED_RECEIPT'):
        raise ValueError('choose one local signed Growth receipt')
    if not growth_113:
        signed = _load_script('a0v_growth_112_successor_clone.py').check_signed_receipt(
            Path(os.environ['AOS_GROWTH112_SIGNED_RECEIPT']), expected_growth='1.12.0',
        )
        return signed, '1.12.0'
    receipt = json.loads(Path(growth_113).read_text())
    builder = _load_script('build_ecommerce_growth_1_13_candidates.py').load_builder()
    signed_tree = Path(receipt['signedTree'])
    trust_path = signed_tree.parent / 'trust-roots.json'
    assert receipt['outcome'] == 'SIGNED_TREE_GREEN'
    assert receipt['keyId'] == 'a0v-local-ecommerce-growth-1-13-v1'
    assert receipt['signedTreeHash'] == builder._tree_hash(signed_tree)
    trust = FileTrustRootProvider(trust_path).snapshot()
    root = trust.get_trust_root(publisher='aos', key_id=receipt['keyId'])
    assert root is not None and root.revision == receipt['trustRootRevision']
    loader = ManifestLoader({'a0v-growth-113': signed_tree}, trust_roots=trust)
    policy = ReleasePolicy(trust_roots=trust)
    for relative, bundle_id, _, _ in builder.ALL_CASES:
        loaded = loader.load(f'bundle://a0v-growth-113/{relative}')
        assert loaded.content_hash == receipt['contentHashes'][bundle_id]
        policy.evaluate(builder._release_record(loaded), checked_at=datetime.now(timezone.utc))
    return dict(receipt=receipt, signed_tree=signed_tree, trust_path=trust_path,
                builder=builder, source_alias='a0v-growth-113'), '1.13.0'


def test_signed_growth_release_reaches_approved_installation_in_full_schema(
    tmp_path, request, monkeypatch,
):
    database = conninfo_to_dict(os.environ['AOS_DATABASE_URL'])['dbname']
    assert database.startswith('aos_test_') and database.endswith('_ti4_test')
    signed, growth_version = _signed_release()
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
        core_version='1.4.0', adapter_version='1.23.0', growth_version=growth_version,
        operations_version='1.2.0', trust_path=signed['trust_path'],
        idempotency_prefix=f'test-growth-{growth_version}-full-schema',
        overlay_revision=f'test-growth-{growth_version}-full-schema',
        maker_actor='test-author', checker_actor='test-reviewer',
    )
    assert installed['installationState'] == 'approved'
    assert installed['installationEtag'] == 3
    selected_template = ApprovedBIPreparationResolver(
        connect_factory=connect,
        registry_connect_factory=connect,
        release_root=signed['signed_tree'], trust_roots=trust,
        source_alias=signed['source_alias'],
    ).select(SCOPE)
    assert selected_template is not None
    assert selected_template.installation_id == installed['installationId']
    assert selected_template.template_ref.resource_id == (
        f"bundle://{signed['source_alias']}/solution.ecommerce.growth/"
        f"{growth_version}/content/responsibility-templates/business-investigation.readonly.json"
    )
    active_resolver = ActiveBIBusinessResolver(
        connect_factory=connect, registry_connect_factory=connect,
        release_root=signed['signed_tree'], trust_roots=trust,
        source_alias=signed['source_alias'],
    )
    assert active_resolver.select(SCOPE) is None
    assert ApprovedBIPreparationResolver(
        connect_factory=connect, registry_connect_factory=connect,
        release_root=signed['signed_tree'],
        trust_roots=FrozenTrustRootProvider({}), source_alias=signed['source_alias'],
    ).select(SCOPE) is None
    assert ApprovedBIPreparationResolver(
        connect_factory=connect, registry_connect_factory=connect,
        release_root=signed['signed_tree'], trust_roots=trust,
        source_alias=signed['source_alias'],
    ).select(TenantScope('dev-org', 'dev-project')) is None
    # Six active instances are isolated test prerequisites; their direct fixture
    # setup is not evidence of a current formal AgentInstance product flow.
    with connect(SCOPE) as conn:
        conn.execute("""INSERT INTO aip_agent_template_revision
            (template_id,revision,display_name,role_key,lifecycle,source_ref,
             source_license,manifest,content_hash,created_by)
            VALUES('test-bi-plan-active-handoff',1,'isolated BI handoff',
                   'content_officer','published','{}','internal','{}',%s,'test-author')""",
            ('b' * 64,))
        for _, _, instance_id, _, _ in BI_ROLE_BLUEPRINTS:
            conn.execute("""INSERT INTO aip_agent_instance
                (org_id,project_id,instance_id,template_id,template_revision,
                 status,overlay,version,created_by)
                VALUES(%s,%s,%s,'test-bi-plan-active-handoff',1,
                       'active','{}',1,'test-author')""",
                (*SCOPE.key, instance_id))
    restricted_bi = None
    if growth_version == '1.13.0':
        restricted_bi = assert_original_plan_store_with_restricted_login(
            selected_template, signed, trust, installed, retain_active=True)
        def cleanup_restricted_bi():
            with psycopg.connect(get_dsn(), autocommit=True) as admin:
                cleanup_restricted_issuer_case(admin, restricted_bi[1])
        request.addfinalizer(cleanup_restricted_bi)
    principal = Principal(
        subject='test-author', org_id=SCOPE.org_id, project_id=SCOPE.project_id,
        roles=['admin'], token_kind='oidc',
    )
    prepare_key = f'test-growth-{growth_version}-bi-plan-prepare'
    prepared_plan = SignedBIPlanPreparationService(
        connect_factory=connect,
        preparation_resolver=ApprovedBIPreparationResolver(
            connect_factory=connect, registry_connect_factory=connect,
            release_root=signed['signed_tree'], trust_roots=trust,
            source_alias=signed['source_alias'],
        ),
    ).prepare(
        SCOPE, installation_id=installed['installationId'],
        expected_etag_version=installed['installationEtag'],
        principal=principal, idempotency_key=prepare_key,
    )
    assert prepared_plan.lifecycle.value == 'draft'
    assert prepared_plan.template_ref == selected_template.template_ref
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
        if growth_version == '1.13.0' and bundle_id == 'solution.ecommerce.growth':
            def corrupted_image_index(path, limit):
                raw = artifact(path, limit)
                return raw + b' ' if path == 'artifacts/runtime-image-index.json' else raw
            with pytest.raises(ValueError, match='artifact bytes differ from signed release'):
                admit_runtime_artifact(
                    record=record, selected=resolved[bundle_id],
                    policy=ReleasePolicy(trust_roots=trust), checked_at=datetime.now(timezone.utc),
                    read_artifact=corrupted_image_index, platform='linux/arm64',
                    driver=OciDriver(context='colima-aos-extension'),
                )
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
        **action, kind='runtime-apply', idempotency_key=f'test-growth-{growth_version}-runtime-apply',
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
                idempotency_key=f'test-growth-{growth_version}-runtime-verify',
                if_match=f'"{applied.etag_version}"', preparation_admission=lambda: True,
            )
            verified = await job.verify(
                operation_id=requested.response_json['operationId'],
                expected_revision=requested.response_json['revision'],
            )
            assert verified.state == 'active' and verified.active_revision is not None
            active_template = active_resolver.select(SCOPE)
            assert active_template is not None
            assert active_template.installation_id == installed['installationId']
            assert active_template.template_ref == selected_template.template_ref.model_copy(
                update={'revision': verified.current_revision},
            )
            # BI preparation pins the approved installation revision.
            # An active business reader must reject that stale exact ref; a
            # separate governed rebind is required before freezing the Plan.
            assert selected_template.template_ref.revision != verified.current_revision
            assert active_resolver.resolve(SCOPE, selected_template.template_ref) is False
            assert active_resolver.resolve(SCOPE, active_template.template_ref) is True
            if restricted_bi is not None:
                issuer_config, _, issuer_plan, issuer_prepare = restricted_bi
                restricted_active = ActiveBIBusinessResolver(
                    connect_factory=lambda scope: connect_bi_issuer_read_only(
                        issuer_config, scope),
                    registry_connect_factory=lambda: connect_bi_issuer_read_only(
                        issuer_config, SCOPE),
                    release_root=signed['signed_tree'], trust_roots=trust,
                    source_alias=signed['source_alias'],
                    registry_prepared_transaction=True, restricted_bi_scope=SCOPE,
                )
                assert restricted_active.select(SCOPE) is not None
                issuer_rebind_key = 's3owad-restricted-bi-rebind'
                issuer_rebind = SignedBIPlanActiveRebindService(
                    connect_factory=lambda scope: connect_bi_issuer_write(
                        issuer_config, scope), active_resolver=restricted_active)
                issuer_args = dict(
                    installation_id=installed['installationId'],
                    plan_id=issuer_plan.plan_id,
                    prepare_key=issuer_prepare['idempotency_key'],
                    expected_etag_version=verified.etag_version,
                    expected_plan_version=issuer_plan.version,
                    principal=issuer_prepare['principal'],
                    idempotency_key=issuer_rebind_key,
                )
                with pytest.raises(psycopg.errors.InsufficientPrivilege,
                                   match='installation unavailable'):
                    issuer_rebind.rebind(SCOPE, **{
                        **issuer_args, 'expected_etag_version': verified.etag_version + 1})
                with pytest.raises(ProductionContractNotFound):
                    issuer_rebind.rebind(SCOPE, **{
                        **issuer_args, 'prepare_key': 's3owad-missing-prepare'})
                with pytest.raises(PermissionError, match='formal authenticated actor'):
                    issuer_rebind.rebind(TenantScope('dev-org', 'dev-project'), **issuer_args)
                with psycopg.connect(get_dsn(), autocommit=True) as admin:
                    admin.execute('''REVOKE EXECUTE ON FUNCTION
                        public.aos_bi_plan_release_lock_a0v_139(text,text)
                        FROM aos_bi_plan_issuer''')
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        issuer_rebind.rebind(SCOPE, **issuer_args)
                    admin.execute('''GRANT EXECUTE ON FUNCTION
                        public.aos_bi_plan_release_lock_a0v_139(text,text)
                        TO aos_bi_plan_issuer''')
                with pytest.raises(psycopg.Error, match='PLAN_FORCED_ROLLBACK'):
                    issuer_rebind.rebind(SCOPE, **{
                        **issuer_args, 'idempotency_key': 's3owi-forced-rollback'})
                with connect(SCOPE) as conn:
                    assert conn.execute('''SELECT current_revision FROM
                        aip_responsibility_plan_head WHERE org_id=%s AND project_id=%s
                        AND plan_id=%s''', (*SCOPE.key, issuer_plan.plan_id)
                    ).fetchone()['current_revision'] == issuer_plan.revision
                    assert conn.execute('''SELECT count(*) AS n FROM
                        aip_production_contract_receipt WHERE org_id=%s AND project_id=%s
                        AND operation='bi_responsibility_plan.rebind' AND
                        idempotency_key IN ('s3owi-forced-rollback',%s)''',
                        (*SCOPE.key, issuer_rebind_key)).fetchone()['n'] == 0
                attempt_dir = tmp_path / 'bi-issuer-attempts'
                attempt_dir.mkdir(mode=0o700)
                process_config = BIIssuerProcessConfig(
                    socket_path=tmp_path / 'bi-issuer.sock',
                    api_uid=os.geteuid() + 1, issuer_uid=os.geteuid(),
                    ipc_gid=os.getegid(), database=issuer_config, scope=SCOPE,
                    attempt_directory=attempt_dir,
                )
                dispatch = build_bi_issuer_dispatcher(
                    process_config, release_root=signed['signed_tree'],
                    trust_roots=trust, source_alias=signed['source_alias'],
                )
                command = BIIssuerRebindCommand.model_validate(dict(
                    schemaVersion=1, bearerToken='test.only.jwt',
                    orgId=SCOPE.org_id, projectId=SCOPE.project_id,
                    installationId=installed['installationId'],
                    expectedETagVersion=verified.etag_version,
                    expectedPlanVersion=issuer_plan.version,
                    planId=issuer_plan.plan_id,
                    prepareIdempotencyKey=issuer_prepare['idempotency_key'],
                    idempotencyKey=issuer_rebind_key,
                ))
                from aos_api import aip_bi_plan_issuer_service as issuer_service
                original_rebind = SignedBIPlanActiveRebindService.rebind
                calls = []
                def committed_but_ack_lost(service, *args, **kwargs):
                    calls.append(kwargs['idempotency_key'])
                    original_rebind(service, *args, **kwargs)
                    raise ConnectionError('test-only response lost after commit')
                with monkeypatch.context() as patch:
                    patch.setattr(issuer_service, 'authenticate_bi_issuer_request',
                                  lambda _: issuer_prepare['principal'])
                    patch.setattr(SignedBIPlanActiveRebindService, 'rebind',
                                  committed_but_ack_lost)
                    first_outcome = dispatch(command)
                assert first_outcome.status == 'observed'
                assert first_outcome.receipt.result_ref.resource_id == issuer_plan.plan_id
                with monkeypatch.context() as patch:
                    patch.setattr(issuer_service, 'authenticate_bi_issuer_request',
                                  lambda _: issuer_prepare['principal'])
                    patch.setattr(SignedBIPlanActiveRebindService, 'rebind',
                                  lambda *a, **k: pytest.fail('unknown commit was resent'))
                    repeated_outcome = dispatch(command)
                    changed_outcome = dispatch(command.model_copy(update={
                        'expected_plan_version': issuer_plan.version + 1}))
                assert repeated_outcome.status == 'observed'
                assert changed_outcome.status == 'conflict'
                assert calls == [issuer_rebind_key]
                with pytest.raises(BIIssuerProcessBlocked,
                                   match='BI_ISSUER_PROCESS_SCOPE_REQUIRED'):
                    dispatch(command.model_copy(update={'org_id': 'dev-org'}))
                missing_command = command.model_copy(update={
                    'idempotency_key': 's3owae-missing-prepare',
                    'prepare_key': 's3owae-unissued-prepare',
                })
                with monkeypatch.context() as patch:
                    patch.setattr(issuer_service, 'authenticate_bi_issuer_request',
                                  lambda _: issuer_prepare['principal'])
                    assert dispatch(missing_command).status == 'unresolved'
                    patch.setattr(SignedBIPlanActiveRebindService, 'rebind',
                                  lambda *a, **k: pytest.fail('unresolved attempt was resent'))
                    assert dispatch(missing_command).status == 'unresolved'
                markers = list(attempt_dir.glob('*.json'))
                assert len(markers) == 2
                assert all('test.only.jwt' not in item.read_text() for item in markers)
                issuer_rebound = issuer_rebind.rebind(SCOPE, **issuer_args)
                assert issuer_rebound.plan_id == issuer_plan.plan_id
                assert issuer_rebound.template_ref == active_template.template_ref
                assert issuer_rebind.rebind(SCOPE, **issuer_args).revision == issuer_rebound.revision
                issuer_readback = SignedBIPlanRebindReceiptReader(
                    connect_factory=lambda scope: connect_bi_issuer_read_only(
                        issuer_config, scope), restricted_bi_scope=SCOPE,
                ).read(SCOPE, principal=issuer_prepare['principal'],
                       idempotency_key=issuer_rebind_key)
                assert issuer_readback.result_ref.resource_id == issuer_plan.plan_id
                assert issuer_readback.result_ref.revision == issuer_rebound.revision
                assert issuer_readback.rebind_binding.prepare_receipt_id
                assert issuer_readback.original_preparation_verified is True
                assert issuer_readback.plan_revision_verified is True
                with pytest.raises(ProductionContractIdempotencyConflict):
                    issuer_rebind.rebind(SCOPE, **{
                        **issuer_args, 'expected_plan_version': issuer_rebound.version})
                with pytest.raises(ProductionContractConflict, match='Plan head changed'):
                    issuer_rebind.rebind(SCOPE, **{
                        **issuer_args, 'idempotency_key': 's3owad-stale-plan'})
                with psycopg.connect(get_dsn(), autocommit=True) as admin:
                    admin.execute('''REVOKE EXECUTE ON FUNCTION
                        public.aos_bi_plan_membership_read_a0v_138(text,text,text)
                        FROM aos_bi_plan_issuer''')
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        SignedBIPlanRebindReceiptReader(
                            connect_factory=lambda scope: connect_bi_issuer_read_only(
                                issuer_config, scope), restricted_bi_scope=SCOPE,
                        ).read(SCOPE, principal=issuer_prepare['principal'],
                               idempotency_key=issuer_rebind_key)
                    admin.execute('''GRANT EXECUTE ON FUNCTION
                        public.aos_bi_plan_membership_read_a0v_138(text,text,text)
                        TO aos_bi_plan_issuer''')
            rebind_service = SignedBIPlanActiveRebindService(
                connect_factory=connect, active_resolver=active_resolver,
            )
            rebind_key = f'test-growth-{growth_version}-bi-plan-rebind'
            rebind_args = dict(
                installation_id=installed['installationId'],
                plan_id=prepared_plan.plan_id, prepare_key=prepare_key,
                expected_etag_version=verified.etag_version,
                expected_plan_version=prepared_plan.version,
                principal=principal, idempotency_key=rebind_key,
            )
            rebound = rebind_service.rebind(SCOPE, **rebind_args)
            replay = rebind_service.rebind(SCOPE, **rebind_args)
            assert replay.revision == rebound.revision
            readback = SignedBIPlanRebindReceiptReader(
                connect_factory=connect_read_only,
            ).read(SCOPE, principal=principal, idempotency_key=rebind_key)
            assert readback.result_ref.resource_id == rebound.plan_id
            assert readback.result_ref.revision == rebound.revision
            assert readback.rebind_binding.prepare_receipt_id
            assert readback.rebind_binding.active_template_ref == rebound.template_ref
            assert readback.original_preparation_verified is True
            assert readback.plan_revision_verified is True
            assert readback.current_admission_verified is False
            from aos_api.ecommerce_business_investigation_aip_authority import (
                SignedBIPlanActiveFreezeService,
            )
            freeze_key = f'test-growth-{growth_version}-bi-plan-freeze'
            freeze_service = SignedBIPlanActiveFreezeService(
                connect_factory=connect, active_resolver=active_resolver,
            )
            freeze_args = dict(
                installation_id=installed['installationId'],
                plan_id=rebound.plan_id, rebind_key=rebind_key,
                expected_etag_version=verified.etag_version,
                expected_plan_version=rebound.version,
                principal=principal, idempotency_key=freeze_key,
            )
            with pytest.raises(ProductionContractDependencyBlocked, match='SKILL_BINDING_NOT_ACTIVE'):
                freeze_service.freeze(SCOPE, **freeze_args)
            with pytest.raises(ProductionContractNotFound, match='rebind receipt'):
                freeze_service.freeze(SCOPE, **{**freeze_args, 'rebind_key': f'{rebind_key}-missing'})
            with pytest.raises(RevisionConflictError):
                freeze_service.freeze(SCOPE, **{
                    **freeze_args, 'expected_etag_version': verified.etag_version + 1})
            with pytest.raises(ProductionContractConflict, match='signed active'):
                SignedBIPlanActiveFreezeService(
                    connect_factory=connect,
                    active_resolver=ActiveBIBusinessResolver(
                        connect_factory=connect, registry_connect_factory=connect,
                        release_root=signed['signed_tree'],
                        trust_roots=FrozenTrustRootProvider({}),
                        source_alias=signed['source_alias'],
                    ),
                ).freeze(SCOPE, **freeze_args)
            with pytest.raises(PermissionError, match='formal authenticated actor'):
                freeze_service.freeze(SCOPE, **{**freeze_args, 'principal': Principal(
                    subject='test-author', org_id=SCOPE.org_id,
                    project_id=SCOPE.project_id, roles=['admin'], token_kind='dev')})
            with pytest.raises(PermissionError, match='formal authenticated actor'):
                freeze_service.freeze(TenantScope('dev-org', 'dev-project'), **freeze_args)
            with connect(SCOPE) as conn:
                assert conn.execute("""SELECT count(*) AS n FROM aip_production_contract_receipt
                    WHERE org_id=%s AND project_id=%s
                      AND operation='bi_responsibility_plan.freeze'
                      AND idempotency_key=%s""", (*SCOPE.key, freeze_key)).fetchone()['n'] == 0
                assert conn.execute("""SELECT current_revision FROM aip_responsibility_plan_head
                    WHERE org_id=%s AND project_id=%s AND plan_id=%s""",
                    (*SCOPE.key, rebound.plan_id)).fetchone()['current_revision'] == rebound.revision
            with pytest.raises(ProductionContractNotFound):
                SignedBIPlanRebindReceiptReader(
                    connect_factory=connect_read_only,
                ).read(SCOPE, principal=principal, idempotency_key=f'{rebind_key}-missing')
            with pytest.raises(ProductionContractIdempotencyConflict):
                rebind_service.rebind(
                    SCOPE, **{**rebind_args, 'expected_plan_version': rebound.version},
                )
            with pytest.raises(ProductionContractConflict, match='Plan head changed'):
                rebind_service.rebind(
                    SCOPE, **{**rebind_args, 'idempotency_key': f'{rebind_key}-new'},
                )
            with pytest.raises(RevisionConflictError):
                rebind_service.rebind(
                    SCOPE, **{**rebind_args, 'expected_etag_version': verified.etag_version + 1},
                )
            with pytest.raises(ProductionContractNotFound):
                rebind_service.rebind(
                    SCOPE, **{**rebind_args, 'prepare_key': f'{prepare_key}-other'},
                )
            with pytest.raises(ProductionContractConflict, match='signed active'):
                SignedBIPlanActiveRebindService(
                    connect_factory=connect,
                    active_resolver=ActiveBIBusinessResolver(
                        connect_factory=connect, registry_connect_factory=connect,
                        release_root=signed['signed_tree'],
                        trust_roots=FrozenTrustRootProvider({}),
                        source_alias=signed['source_alias'],
                    ),
                ).rebind(SCOPE, **rebind_args)
            with pytest.raises(RuntimeConflict):
                rebind_service.rebind(SCOPE, **{
                    **rebind_args,
                    'principal': Principal(
                        subject='test-reviewer', org_id=SCOPE.org_id,
                        project_id=SCOPE.project_id, roles=['admin'], token_kind='oidc',
                    ),
                })
            with pytest.raises(PermissionError, match='formal authenticated actor'):
                rebind_service.rebind(SCOPE, **{
                    **rebind_args,
                    'principal': Principal(
                        subject='test-author', org_id=SCOPE.org_id,
                        project_id=SCOPE.project_id, roles=['admin'], token_kind='dev',
                    ),
                })
            with pytest.raises(PermissionError, match='formal authenticated actor'):
                rebind_service.rebind(TenantScope('dev-org', 'dev-project'), **rebind_args)
            assert rebound.lifecycle.value == 'draft'
            assert rebound.template_ref == active_template.template_ref
            assert rebound.revision == prepared_plan.revision + 1
            with connect(SCOPE) as conn:
                receipt = conn.execute("""SELECT result_ref FROM aip_production_contract_receipt
                    WHERE org_id=%s AND project_id=%s
                      AND operation='bi_responsibility_plan.rebind'
                      AND idempotency_key=%s""",
                    (*SCOPE.key, rebind_key),
                ).fetchone()
            assert receipt is not None
            assert receipt['result_ref']['resourceId'] == prepared_plan.plan_id
            assert ApprovedBIPreparationResolver(
                connect_factory=connect, registry_connect_factory=connect,
                release_root=signed['signed_tree'], trust_roots=trust,
                source_alias=signed['source_alias'],
            ).select(SCOPE) is None
            assert ActiveBIBusinessResolver(
                connect_factory=connect, registry_connect_factory=connect,
                release_root=signed['signed_tree'],
                trust_roots=FrozenTrustRootProvider({}), source_alias=signed['source_alias'],
            ).select(SCOPE) is None
            assert active_resolver.select(TenantScope('dev-org', 'dev-project')) is None
            with connect(SCOPE) as conn:
                binding = conn.execute('''SELECT generation,installation_revision,package_lock_ref,
                    observed_state,enabled,operation_fence
                    FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s
                    AND installation_id=%s''', (*SCOPE.key, installed['installationId'])).fetchone()
                generations = conn.execute('''SELECT DISTINCT generation FROM extension_runtime_resource_lease
                    WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
                    (*SCOPE.key, accepted.response_json['operationId'])).fetchall()
                assert len(generations) == 1
                assert binding == {
                    'generation': generations[0]['generation'],
                    'installation_revision': verified.current_revision,
                    'package_lock_ref': {'lockHash': lock.lock_hash},
                    'observed_state': 'ready', 'enabled': False, 'operation_fence': True,
                }
                assert conn.execute('''SELECT count(*) AS n FROM extension_operation_dispatch_binding
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s''',
                    (*SCOPE.key, installed['installationId'])).fetchone()['n'] == 0
                assert conn.execute("SELECT count(*) AS n FROM bundle_installation WHERE org_id='dev-org'").fetchone()['n'] == 0
            if growth_version == '1.13.0':
                view = read_current_installation_release_evidence(
                    connect_factory=lambda: psycopg.connect(get_dsn(), row_factory=dict_row),
                    scope=SCOPE, installation_id=installed['installationId'],
                    release_policy=policy, loader=loader,
                )
                assert view.authorization == 'EVIDENCE_ONLY_NO_START'
                assert view.active_revision == view.current_revision
                assert any(item.bundle_id == 'solution.ecommerce.growth'
                           and item.version == '1.13.0' for item in view.releases)
                growth = next(item for item in view.releases
                              if item.bundle_id == 'solution.ecommerce.growth')
                selected_view = read_unique_active_installation_release_evidence(
                    connect_factory=lambda: psycopg.connect(get_dsn(), row_factory=dict_row),
                    scope=SCOPE, publisher=growth.publisher,
                    bundle_id=growth.bundle_id, version=growth.version,
                    content_hash=growth.content_hash,
                    release_policy=policy, loader=loader,
                )
                assert selected_view.authorization == 'EVIDENCE_ONLY_NO_START'
                assert selected_view.installation_id == view.installation_id
                assert selected_view.lock_hash == view.lock_hash
                with psycopg.connect(get_dsn(), row_factory=dict_row) as evidence_conn:
                    evidence_conn.read_only = True
                    with evidence_conn.transaction():
                        evidence_conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                        in_transaction = _read_unique_active_in_transaction(
                            evidence_conn, scope=SCOPE, publisher=growth.publisher,
                            bundle_id=growth.bundle_id, version=growth.version,
                            content_hash=growth.content_hash,
                            release_policy=policy, loader=loader,
                        )
                        assert in_transaction.installation_id == selected_view.installation_id
                        assert in_transaction.lock_hash == selected_view.lock_hash
                        assert in_transaction.authorization == 'EVIDENCE_ONLY_NO_START'
                        assert evidence_conn.execute('SELECT 1 AS alive').fetchone()['alive'] == 1
                restricted_parts = conninfo_to_dict(get_dsn())
                role = 'aos_e17_source_' + uuid4().hex[:12]
                password = secrets.token_urlsafe(32)
                restricted_parts.update(user=role, password=password)
                source_tables = (
                    'bundle_installation', 'bundle_installation_revision',
                    'bundle_composition', 'bundle_composition_lock',
                    'asset_bundle', 'asset_bundle_version',
                    'asset_bundle_artifact', 'asset_bundle_evidence',
                )
                scoped_tables = source_tables[:4]
                policy_name = 's3owaob39_' + role.rsplit('_', 1)[-1]
                lock_function = 'aos_e17_install_lock_' + role.rsplit('_', 1)[-1]
                lock_query = sql.SQL('''SELECT public.{}(
                    %s::text,%s::text,%s::uuid,%s::bigint) AS installation_pk''').format(
                    sql.Identifier(lock_function))
                with psycopg.connect(get_dsn()) as admin:
                    admin.execute(sql.SQL('''CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER
                        NOBYPASSRLS PASSWORD {}''').format(
                        sql.Identifier(role), sql.Literal(password)))
                    admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(
                        sql.Identifier(role)))
                try:
                    with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                        with pytest.raises(psycopg.errors.InsufficientPrivilege):
                            with limited.transaction():
                                _read_unique_active_in_transaction(
                                    limited, scope=SCOPE, publisher=growth.publisher,
                                    bundle_id=growth.bundle_id, version=growth.version,
                                    content_hash=growth.content_hash,
                                    release_policy=policy, loader=loader,
                                )
                    with psycopg.connect(get_dsn()) as admin:
                        for table in source_tables:
                            admin.execute(sql.SQL('GRANT SELECT ON {} TO {}').format(
                                sql.Identifier(table), sql.Identifier(role)))
                        for table in scoped_tables:
                            admin.execute(sql.SQL('''CREATE POLICY {} ON {} TO {}
                                USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
                                   AND project_id=NULLIF(current_setting('aos.project_id',true),''))''').format(
                                sql.Identifier(policy_name), sql.Identifier(table),
                                sql.Identifier(role)))
                    with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                        with limited.transaction():
                            limited.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                            identity = limited.execute('''SELECT current_user AS login,
                                pg_has_role(current_user,'aos_runtime','member') AS runtime_member,
                                current_setting('transaction_read_only') AS readonly''').fetchone()
                            assert identity == {'login': role, 'runtime_member': False,
                                                'readonly': 'off'}
                            for table in source_tables:
                                privileges = limited.execute('''SELECT
                                    has_table_privilege(current_user,%s,'INSERT') AS insert_ok,
                                    has_table_privilege(current_user,%s,'UPDATE') AS update_ok,
                                    has_table_privilege(current_user,%s,'DELETE') AS delete_ok''',
                                    (table, table, table)).fetchone()
                                assert privileges == {'insert_ok': False,
                                                      'update_ok': False, 'delete_ok': False}
                            restricted_view = _read_unique_active_in_transaction(
                                limited, scope=SCOPE, publisher=growth.publisher,
                                bundle_id=growth.bundle_id, version=growth.version,
                                content_hash=growth.content_hash,
                                release_policy=policy, loader=loader,
                            )
                            assert restricted_view.installation_id == selected_view.installation_id
                            assert restricted_view.authorization == 'EVIDENCE_ONLY_NO_START'
                            assert limited.execute('SELECT count(*) AS n FROM bundle_installation'
                                                   ).fetchone()['n'] == 1
                            assert limited.execute('SELECT 1 AS alive').fetchone()['alive'] == 1
                            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                                with limited.transaction():
                                    limited.execute('''SELECT 1 FROM bundle_installation
                                        WHERE org_id=%s AND project_id=%s
                                          AND installation_id=%s FOR SHARE''',
                                        (*SCOPE.key, installed['installationId']))
                            with psycopg.connect(get_dsn(), autocommit=True) as contender:
                                contender.execute("SET lock_timeout='250ms'")
                                assert contender.execute('''SELECT 1 AS acquired
                                    FROM bundle_installation WHERE org_id=%s AND project_id=%s
                                      AND installation_id=%s FOR UPDATE''',
                                    (*SCOPE.key, installed['installationId'])).fetchone()[0] == 1
                                with pytest.raises(psycopg.errors.LockNotAvailable):
                                    contender.execute('SELECT pg_advisory_xact_lock(228, 1)')
                    with psycopg.connect(get_dsn(), autocommit=True) as contender:
                        contender.execute("SET lock_timeout='250ms'")
                        assert contender.execute('''SELECT 1 AS acquired FROM bundle_installation
                            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
                            (*SCOPE.key, installed['installationId'])).fetchone()[0] == 1
                        contender.execute('SELECT pg_advisory_xact_lock(228, 1)')
                    for wrong_scope, wrong_hash in (
                        (TenantScope('dev-org', 'dev-project'), growth.content_hash),
                        (SCOPE, 'sha256:' + '0' * 64),
                    ):
                        with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                            with limited.transaction():
                                limited.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                                with pytest.raises(CurrentReleaseEvidenceBlocked,
                                                   match='ACTIVE_INSTALLATION_MISSING'):
                                    _read_unique_active_in_transaction(
                                        limited, scope=wrong_scope,
                                        publisher=growth.publisher,
                                        bundle_id=growth.bundle_id, version=growth.version,
                                        content_hash=wrong_hash,
                                        release_policy=policy, loader=loader,
                                    )
                                if wrong_scope != SCOPE:
                                    assert limited.execute(
                                        'SELECT count(*) AS n FROM bundle_installation'
                                    ).fetchone()['n'] == 0
                    with psycopg.connect(get_dsn()) as admin:
                        admin.execute(sql.SQL('''CREATE FUNCTION public.{}(
                            p_org text,p_project text,p_installation uuid,p_etag bigint)
                            RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
                            SET search_path=pg_catalog AS $$
                            DECLARE found_pk uuid; found_etag bigint;
                                    active_rev bigint; current_rev bigint; revision_state text;
                            BEGIN
                              IF session_user IS DISTINCT FROM {}
                                 OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
                                 OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project
                                 OR current_setting('transaction_isolation') <> 'serializable'
                                 OR current_setting('transaction_read_only') <> 'off' THEN
                                RAISE EXCEPTION 'installation unavailable' USING ERRCODE='42501';
                              END IF;
                              SELECT i.installation_pk,i.etag_version,i.active_revision,
                                     i.current_revision,r.state
                                INTO found_pk,found_etag,active_rev,current_rev,revision_state
                                FROM public.bundle_installation i
                                JOIN public.bundle_installation_revision r
                                  ON r.org_id=i.org_id AND r.project_id=i.project_id
                                 AND r.installation_pk=i.installation_pk
                                 AND r.revision=i.current_revision
                               WHERE i.org_id=p_org AND i.project_id=p_project
                                 AND i.installation_id=p_installation
                               FOR SHARE OF i;
                              IF found_pk IS NULL OR found_etag IS DISTINCT FROM p_etag
                                 OR active_rev IS NULL OR active_rev IS DISTINCT FROM current_rev
                                 OR revision_state IS DISTINCT FROM 'active' THEN
                                RAISE EXCEPTION 'installation unavailable' USING ERRCODE='42501';
                              END IF;
                              RETURN found_pk;
                            END $$''').format(sql.Identifier(lock_function), sql.Literal(role)))
                        admin.execute(sql.SQL('''REVOKE ALL ON FUNCTION public.{}(
                            text,text,uuid,bigint) FROM PUBLIC''').format(
                            sql.Identifier(lock_function)))
                    with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                        with pytest.raises(psycopg.errors.InsufficientPrivilege):
                            with limited.transaction():
                                limited.execute(lock_query, (*SCOPE.key,
                                    installed['installationId'], selected_view.etag_version))
                    with psycopg.connect(get_dsn()) as admin:
                        admin.execute(sql.SQL('''GRANT EXECUTE ON FUNCTION public.{}(
                            text,text,uuid,bigint) TO {}''').format(
                            sql.Identifier(lock_function), sql.Identifier(role)))
                    for selected_scope, installation_id, etag in (
                        (None, installed['installationId'], selected_view.etag_version),
                        (TenantScope('dev-org', 'dev-project'),
                         installed['installationId'], selected_view.etag_version),
                        (SCOPE, str(uuid4()), selected_view.etag_version),
                        (SCOPE, installed['installationId'], selected_view.etag_version + 1),
                    ):
                        with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                            with limited.transaction():
                                limited.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                                if selected_scope is not None:
                                    limited.execute('''SELECT
                                        set_config('aos.org_id',%s,true),
                                        set_config('aos.project_id',%s,true)''',
                                        selected_scope.key)
                                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                                    with limited.transaction():
                                        limited.execute(lock_query, (
                                            *(selected_scope or SCOPE).key,
                                            installation_id, etag,
                                        ))
                    with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                        with limited.transaction():
                            limited.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                            _read_unique_active_in_transaction(
                                limited, scope=SCOPE, publisher=growth.publisher,
                                bundle_id=growth.bundle_id, version=growth.version,
                                content_hash=growth.content_hash,
                                release_policy=policy, loader=loader,
                            )
                            locked_pk = limited.execute(
                                lock_query, (*SCOPE.key, installed['installationId'],
                                             selected_view.etag_version),
                            ).fetchone()['installation_pk']
                            assert locked_pk is not None
                            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                                with limited.transaction():
                                    limited.execute('''UPDATE bundle_installation
                                        SET etag_version=etag_version
                                        WHERE org_id=%s AND project_id=%s
                                          AND installation_id=%s''',
                                        (*SCOPE.key, installed['installationId']))
                            with psycopg.connect(get_dsn(), autocommit=True) as contender:
                                contender.execute("SET lock_timeout='250ms'")
                                with pytest.raises(psycopg.errors.LockNotAvailable):
                                    contender.execute('''SELECT 1 FROM bundle_installation
                                        WHERE org_id=%s AND project_id=%s
                                          AND installation_id=%s FOR UPDATE''',
                                        (*SCOPE.key, installed['installationId']))
                                with pytest.raises(psycopg.errors.LockNotAvailable):
                                    contender.execute('SELECT pg_advisory_xact_lock(228, 1)')
                    with psycopg.connect(get_dsn(), autocommit=True) as contender:
                        contender.execute("SET lock_timeout='250ms'")
                        assert contender.execute('''SELECT 1 FROM bundle_installation
                            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
                            (*SCOPE.key, installed['installationId'])).fetchone() is not None
                        contender.execute('SELECT pg_advisory_xact_lock(228, 1)')
                    assert_restricted_blocked_evaluate_composes_lock(
                        scope=SCOPE, role=role, restricted_parts=restricted_parts,
                        lock_function=lock_function, installation=installed['installationId'],
                        etag=selected_view.etag_version, growth=growth,
                    )
                finally:
                    with psycopg.connect(get_dsn()) as admin:
                        admin.execute(sql.SQL('''DROP FUNCTION IF EXISTS public.{}(
                            text,text,uuid,bigint)''').format(sql.Identifier(lock_function)))
                        for table in scoped_tables:
                            admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(
                                sql.Identifier(policy_name), sql.Identifier(table)))
                        admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
                        admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
                    with psycopg.connect(get_dsn()) as admin:
                        assert admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',
                                             (role,)).fetchone() is None
                        assert admin.execute('SELECT to_regprocedure(%s)', (
                            f'public.{lock_function}(text,text,uuid,bigint)',
                        )).fetchone()[0] is None
                with pytest.raises(CurrentReleaseEvidenceBlocked, match='ACTIVE_INSTALLATION_MISSING'):
                    read_unique_active_installation_release_evidence(
                        connect_factory=lambda: psycopg.connect(get_dsn(), row_factory=dict_row),
                        scope=SCOPE, publisher=growth.publisher,
                        bundle_id=growth.bundle_id, version=growth.version,
                        content_hash='sha256:' + '0' * 64,
                        release_policy=policy, loader=loader,
                    )
                runtime_view = read_current_runtime_image_evidence(
                    connect_factory=lambda: psycopg.connect(get_dsn(), row_factory=dict_row),
                    scope=SCOPE, installation_id=installed['installationId'],
                    expected_generation=str(binding['generation']), release_policy=policy,
                    loader=loader, driver=OciDriver(context=context), platform='linux/arm64',
                )
                assert runtime_view.authorization == 'EVIDENCE_ONLY_NO_START'
                assert runtime_view.release_evidence.active_revision == runtime_view.release_evidence.current_revision
                assert runtime_view.binding_generation == str(binding['generation'])
                assert runtime_view.schema_head == 'a0v_135'
                assert len(runtime_view.images) == 3
                assert {item.bundle_id for item in runtime_view.images} == set(runtime_view.release_evidence.runtime_members)
                assert all(item.image_digest.startswith('sha256:') and item.config_digest.startswith('sha256:')
                           for item in runtime_view.images)
                preview = _load_script('a0v_current_preview_http.py')
                formal = preview.select_formal_current_release(
                    connect_factory=lambda: psycopg.connect(get_dsn(), row_factory=dict_row),
                    scope=SCOPE, installation_id=installed['installationId'],
                    expected_generation=str(binding['generation']), release_policy=policy,
                    loader=loader, driver=OciDriver(context=context), platform='linux/arm64',
                )
                assert formal['authorization'] == 'PREFLIGHT_ONLY_NO_RUNTIME_START'
                assert formal['installationId'] == installed['installationId']
                assert formal['growthVersion'] == '1.13.0'
                assert formal['bindingGeneration'] == str(binding['generation'])
                assert formal['schemaHead'] == 'a0v_135'
                assert len(formal['images']) == 3
                # A resource observed released is no longer an Owner candidate,
                # even if its cleanup state and lease deadline remain unchanged.
                with connect(SCOPE) as conn:
                    released = conn.execute('''UPDATE extension_runtime_resource_lease
                        SET observed_release=true
                        WHERE org_id=%s AND project_id=%s AND operation_id=%s
                          AND generation=%s AND observed_release=false
                        RETURNING resource_id''',
                        (*SCOPE.key, accepted.response_json['operationId'],
                         binding['generation'])).fetchall()
                assert released
                try:
                    with pytest.raises(CurrentReleaseEvidenceBlocked,
                                       match='RUNTIME_RESOURCE_NOT_LIVE'):
                        read_current_runtime_image_evidence(
                            connect_factory=lambda: psycopg.connect(get_dsn(), row_factory=dict_row),
                            scope=SCOPE, installation_id=installed['installationId'],
                            expected_generation=str(binding['generation']), release_policy=policy,
                            loader=loader, driver=OciDriver(context=context), platform='linux/arm64',
                        )
                finally:
                    with connect(SCOPE) as conn:
                        conn.execute('''UPDATE extension_runtime_resource_lease
                            SET observed_release=false
                            WHERE org_id=%s AND project_id=%s AND operation_id=%s
                              AND generation=%s''',
                            (*SCOPE.key, accepted.response_json['operationId'],
                             binding['generation']))
                with pytest.raises(preview.PreviewBlocked, match='FORMAL_RELEASE_EVIDENCE_INVALID'):
                    preview.select_formal_current_release(
                        connect_factory=lambda: psycopg.connect(get_dsn(), row_factory=dict_row),
                        scope=SCOPE, installation_id=installed['installationId'],
                        expected_generation='00000000-0000-0000-0000-000000000000',
                        release_policy=policy, loader=loader,
                        driver=OciDriver(context=context), platform='linux/arm64',
                    )
                with pytest.raises(CurrentReleaseEvidenceBlocked, match='RUNTIME_GENERATION_MISMATCH'):
                    read_current_runtime_image_evidence(
                        connect_factory=lambda: psycopg.connect(get_dsn(), row_factory=dict_row),
                        scope=SCOPE, installation_id=installed['installationId'],
                        expected_generation='00000000-0000-0000-0000-000000000000',
                        release_policy=policy, loader=loader,
                        driver=OciDriver(context=context), platform='linux/arm64',
                    )
            else:
                preview = _load_script('a0v_current_preview_http.py')
                with pytest.raises(preview.PreviewBlocked, match='FORMAL_GROWTH_RELEASE_MISSING'):
                    preview.select_formal_current_release(
                        connect_factory=lambda: psycopg.connect(get_dsn(), row_factory=dict_row),
                        scope=SCOPE, installation_id=installed['installationId'],
                        expected_generation=str(binding['generation']),
                        release_policy=policy, loader=loader,
                        driver=OciDriver(context=context), platform='linux/arm64',
                    )
            return str(binding['generation'])
        finally:
            await job.stop()
    verified_generation = asyncio.run(prepare_and_verify())
    if growth_version == '1.13.0':
        with pytest.raises(CurrentReleaseEvidenceBlocked, match='RUNTIME_BINDING_DRIFT'):
            read_current_runtime_image_evidence(
                connect_factory=lambda: psycopg.connect(get_dsn(), row_factory=dict_row),
                scope=SCOPE, installation_id=installed['installationId'],
                expected_generation=verified_generation, release_policy=policy,
                loader=loader, driver=OciDriver(context=context), platform='linux/arm64',
            )
    assert owned_containers() == before_containers
