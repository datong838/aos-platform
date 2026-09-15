"""Real signed service transactions; dedicated disposable DB, no OCI acceptance."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from tests.asset_registry.test_m2_core_integration import FixedLoader
from test_admission import fixture as signed_fixture
from test_product_event_current_approval_pg import governed, service_case, stored, pair, body
from aos_api.aip_action_store import AipActionStore
from aos_api.aip_action_models import CreateActionProposalRequest, DecideActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.asset_registry.composition_contracts import (
    CompositionRequest, CreateInstallationRequest, ApproveInstallationRequest, InstallationEventEvidence)
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.contracts import LoadedBundle
from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.installation_evidence import build_event_evidence
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.resolver import resolve
from aos_api.asset_registry.signature import FrozenTrustRootProvider
from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchLifecycle, EventControlDispatchRequest
from aos_api.ecommerce_growth_registration_qualification import _API_PATHS
from aos_api.ecommerce_growth_cutover_proposal_gate import action_snapshot_from_row
from aos_api.ecommerce_product_event_approval import _HASH_FIELDS
from aos_api.ecommerce_product_event_control_qualified_owner import CONTROL_CONTRACT, CONTROL_CONTRACT_PATH
from aos_api.extension_runtime.runtime_release_artifacts import CurrentRuntimeReleaseArtifacts
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def service_database():
    # Clone only the standard disposable template, never a business database.
    from psycopg.conninfo import make_conninfo
    original = os.environ['AOS_DATABASE_URL']
    parts = conninfo_to_dict(original)
    assert parts['dbname'].endswith('_ti4_test')
    name = 'dispatch_service_'+uuid4().hex+'_ti4_test'
    admin = {**parts, 'dbname': 'postgres'}
    with psycopg.connect(**admin, autocommit=True) as current:
        current.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(
            sql.Identifier(name), sql.Identifier(parts['dbname'])))
    os.environ['AOS_DATABASE_URL'] = make_conninfo(**{**parts, 'dbname': name})
    try:
        yield os.environ['AOS_DATABASE_URL']
    finally:
        os.environ['AOS_DATABASE_URL'] = original
        with psycopg.connect(**admin, autocommit=True) as current:
            current.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s', (name,))
            current.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


@pytest.mark.parametrize('fault', ['none', 'artifact', 'revoked', 'receipt_failure', 'late_expiry'])
def test_signed_service_uses_actual_approval_and_independent_receipt(service_database, governed, tmp_path, fault):
    conn, command = governed
    conn.execute('RESET ROLE')
    conn.commit()
    scope = TenantScope('org-org', 'dev-project')

    @contextmanager
    def admin_connect(*_):
        with psycopg.connect(service_database, row_factory=dict_row,
                options='-c aos.org_id=org-org -c aos.project_id=dev-project') as current:
            yield current

    def manifest(value):
        value['metadata']['id'] = 'solution.ecommerce.growth'
        value['spec']['exports']['schemas'] = [CONTROL_CONTRACT_PATH]
        value['spec']['contributions'] = [dict(kind='api', operationId=operation,
            method='POST', path=path, mode='exclusive') for operation, path in {
                **_API_PATHS, 'ecommerce_growth_event_control': '/ecommerce/growth/investigations/events/control'}.items()]

    def artifacts(files):
        files[CONTROL_CONTRACT_PATH] = json.dumps(CONTROL_CONTRACT).encode()

    args, files = signed_fixture(artifacts, transform_manifest=manifest, now=datetime.now(timezone.utc))
    record = args['record']
    root = args['policy']._trust_roots.root
    roots = FrozenTrustRootProvider({(record.publisher, root.key_id): root})
    policy = ReleasePolicy(trust_roots=roots)
    directory = tmp_path / 'growth'
    directory.mkdir()
    for relative, content in files.items():
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    source = 'bundle://service/growth'
    loaded = LoadedBundle(sourceRef=source, manifest=record.manifest,
        artifacts=[{**item, 'artifactRef': source+'/'+item['relativePath']} for item in record.artifacts],
        evidence=record.evidence, contentHash=record.content_hash, signature=record.signature,
        loadedAt=datetime.now(timezone.utc))
    registry = RegistryService(store=PostgresRegistryStore(admin_connect),
        loader=FixedLoader(loaded, roots), trust_roots=roots)
    identity = dict(publisher=record.publisher, bundle_id=record.manifest.metadata.id)
    access = dict(publisher_scopes={record.publisher})
    registry.create_bundle(**identity, kind='SolutionPack', display_name=record.manifest.metadata.display_name, actor='author', roles={'developer'}, **access)
    registry.create_version(**identity, source_ref=source, actor='author', roles={'developer'}, **access)
    registry.validate(**identity, version=record.manifest.metadata.version, actor='validator', roles={'developer'}, **access)
    registry.publish(**identity, version=record.manifest.metadata.version, actor='publisher', roles={'asset-publisher'}, **access)
    snapshot = RegistrySnapshotReader(connect_factory=admin_connect, release_policy=policy).read()
    composition = CompositionRequest(requested=[dict(publisher=record.publisher, id=record.manifest.metadata.id,
        version=record.manifest.metadata.version)], platformApiVersion='1.7.0', platformRelease='aos-platform/1.7.0',
        environment='dev', registrySnapshotHash=snapshot.snapshot_hash, currentInstallationRef=None)
    lock = PostgresCompositionStore(admin_connect).create_or_get(org_id=scope.org_id, project_id=scope.project_id,
        request=composition, snapshot=snapshot, payload=resolve(composition, snapshot, None), created_by='author')
    store = PostgresInstallationStore(admin_connect)
    installed = store.create_draft(org_id=scope.org_id, project_id=scope.project_id,
        request=CreateInstallationRequest(compositionId=lock.composition_id, lockRevision=lock.revision,
            overlayRevision='service-test', displayName='service fixture'), requested_by='author')
    for phase in ('submit', 'approve', 'apply', 'verify'):
        with admin_connect() as current:
            locked = store.lock_for_transition_in_transaction(current, org_id=scope.org_id, project_id=scope.project_id,
                installation_id=installed.installation_id, expected_etag_version=installed.etag_version)
            if phase == 'submit':
                installed = store.append_submit_in_transaction(current, locked=locked, actor='author')
            elif phase == 'approve':
                installed = store.append_approval_in_transaction(current, locked=locked, actor='reviewer',
                    request=ApproveInstallationRequest(lockHash=lock.lock_hash, permissionDiffHash=lock.permission_diff_hash,
                        migrationPlanHash=lock.migration_plan_hash, contributionDiffHash=lock.contribution_diff_hash))
            else:
                evidence = build_event_evidence(evidence_type='dry_apply' if phase == 'apply' else 'verification',
                    installation_id=installed.installation_id, from_revision=installed.current_revision,
                    to_revision=installed.current_revision+1, lock_hash=lock.lock_hash,
                    permission_diff_hash=lock.permission_diff_hash, migration_plan_hash=lock.migration_plan_hash,
                    contribution_diff_hash=lock.contribution_diff_hash, decision_id=installed.decision.decision_id,
                    observed_at=datetime.now(timezone.utc))
                installed = getattr(store, 'append_'+phase+'_in_transaction')(current, locked=locked, actor='author', evidence=evidence)
    generation, group = uuid4(), uuid4()
    with admin_connect() as current:
        current.execute('''INSERT INTO extension_runtime_binding(org_id,project_id,installation_id,generation,
            installation_revision,package_lock_ref,profile_ref,config_ref,execution_epoch,desired_state,observed_state,
            enabled,operation_fence,revision) VALUES(%s,%s,%s,%s,%s,'{}','internal-python-v1','{}',3,'enabled','ready',true,false,6)''',
            (*scope.key, installed.installation_id, generation, installed.current_revision))
        for operation in _API_PATHS:
            current.execute('''INSERT INTO extension_operation_dispatch_binding(org_id,project_id,operation_id,
                handler_kind,installation_id,generation,execution_epoch,operation_fence,revision,cutover_group_id,
                cutover_group_revision,updated_by) VALUES(%s,%s,%s,'extension',%s,%s,3,false,2,%s,11,'fixture-host')''',
                (*scope.key, operation, installed.installation_id, generation, group))
    request = dict(schemaVersion='aos.ecommerce.event-control-dispatch/v1', phase='expand',
        installationRef=dict(installationId=str(installed.installation_id), revision=installed.current_revision,
            lockHash=lock.lock_hash, overlayRevision='service-test'), generation=str(generation), executionEpoch=3,
        runtimeRevision=6, cutoverGroupId=str(group), expectedGroupRevision=11,
        caseId=command['caseAuthority']['caseId'], schedulePolicyId=command['policy']['schedulePolicyId'], idempotencyKey='service-expand')
    action = dict(id='ecommerce_growth_event_dispatch', name='dispatch', object_type='Case', parameters=[], required_markings=[], submission_criteria=[])
    payload = dict(caseId=request['caseId'], schedulePolicyId=request['schedulePolicyId'], dispatchIntent=request)
    action_snapshot = action_snapshot_from_row(action)
    risk = classify_action_risk(action['id'], action_snapshot, payload, None)
    with admin_connect() as current:
        current.execute("UPDATE meta_membership SET role='owner' WHERE subject='fixture-maker'")
        current.execute("INSERT INTO meta_action_type(id,name,object_type,parameters,required_markings,submission_criteria) VALUES(%s,%s,%s,'[]','[]','[]')", (action['id'], action['name'], action['object_type']))
        # Establish the fixture Policy through its guarded storage function, preserving Case history.
        policy_body=command['policy']|{'tenant':dict(orgId=scope.org_id,projectId=scope.project_id)}
        case_body=command['caseAuthority']|{'tenant':dict(orgId=scope.org_id,projectId=scope.project_id)}
        current.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
        current.execute('SET LOCAL ROLE aos_runtime')
        current.execute('SELECT * FROM ecommerce_product_event_policy_put_a0v_040(%s,%s,%s,%s,%s,%s)',
            ('service-policy',command['expectedPolicyRevision'],command['expectedCaseVersion'],
             canonical_hash(dict(policy=policy_body,case=case_body),prefixed=True),Jsonb(policy_body),Jsonb(case_body)))
    @contextmanager
    def proposal_connect(*_):
        with admin_connect() as current:
            current.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
            current.execute('SET LOCAL ROLE aos_runtime')
            yield current
    aip=AipActionStore(proposal_connect)
    proposed=aip.create_proposal(scope,'fixture-maker','service-dispatch-proposal',
        CreateActionProposalRequest(actionTypeId=action['id'],purpose='real service review',payload=payload),action_snapshot,risk)
    aip.decide(scope,'fixture-approver',proposed.proposal.id,'service-approve',
        DecideActionProposalRequest(expectedProposalVersion=proposed.proposal.version,
            expectedProposalHash=proposed.proposal.proposal_hash,decision='approved'),actor_roles=('approver',))
    with admin_connect() as current:
        event=current.execute('SELECT * FROM aip_action_approval_event WHERE proposal_id=%s',(proposed.proposal.id,)).fetchone()
    request['approvalRef'] = dict(resourceType='ActionApprovalEvent', resourceId=event['approval_event_id'],
        revision=event['proposal_version'], contentHash=canonical_hash({key:event[key] for key in _HASH_FIELDS}, prefixed=True))
    role = 'service_test_'+uuid4().hex
    with psycopg.connect(service_database, autocommit=True) as current:
        current.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS').format(sql.Identifier(role)))
        current.execute(sql.SQL('GRANT aos_runtime,aos_extension_maintainer TO {}').format(sql.Identifier(role)))
    @contextmanager
    def runtime_connect():
        parts = conninfo_to_dict(service_database)
        with psycopg.connect(**{**parts, 'user': role}, options='-c role=aos_runtime', row_factory=dict_row) as current:
            yield current
    try:
        service = EventControlDispatchLifecycle(connect=runtime_connect,
            installation_store=PostgresInstallationStore(runtime_connect),
            artifacts=CurrentRuntimeReleaseArtifacts(connect=runtime_connect, scope=scope,
                loader=ManifestLoader({'service': tmp_path}, trust_roots=roots)), release_policy=policy)
        parsed = EventControlDispatchRequest.model_validate(request)
        if fault == 'artifact':
            (directory / CONTROL_CONTRACT_PATH).write_bytes(b'{}')
        if fault == 'revoked':
            with admin_connect() as current:
                current.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'")
        if fault in {'receipt_failure', 'late_expiry'}:
            with admin_connect() as current:
                statement = ("RAISE EXCEPTION 'test receipt insertion failed';" if fault == 'receipt_failure'
                    else "UPDATE public.aip_action_proposal SET expires_at=clock_timestamp()-interval '1 second' WHERE action_type_id='ecommerce_growth_event_dispatch';")
                current.execute('CREATE FUNCTION public.test_receipt_fault() RETURNS trigger LANGUAGE plpgsql '
                    'SECURITY DEFINER SET search_path=pg_catalog,public AS $$ BEGIN '+statement+' RETURN NEW; END $$')
                current.execute('CREATE TRIGGER test_receipt_fault BEFORE INSERT ON extension_event_control_dispatch_receipt '
                                'FOR EACH ROW EXECUTE FUNCTION public.test_receipt_fault()')
        if fault != 'none':
            with pytest.raises((AssetRegistryError, ValueError, PermissionError, psycopg.Error)):
                service.transition(scope=scope, request=parsed, actor='fixture-host')
            with admin_connect() as current:
                assert current.execute('SELECT count(*) AS n FROM extension_event_control_dispatch_receipt').fetchone()['n'] == 0
                assert current.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n'] == 9
                if fault == 'revoked':
                    current.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES('org-org','dev-project','fixture-approver','approver')")
                if fault in {'receipt_failure', 'late_expiry'}:
                    current.execute('DROP TRIGGER test_receipt_fault ON extension_event_control_dispatch_receipt')
                    current.execute('DROP FUNCTION public.test_receipt_fault()')
            if fault == 'artifact':
                (directory / CONTROL_CONTRACT_PATH).write_bytes(files[CONTROL_CONTRACT_PATH])
        receipt = service.transition(scope=scope, request=parsed, actor='fixture-host')
        replay = service.transition(scope=scope, request=parsed, actor='fixture-host')
        assert replay['receiptId'] == receipt['receiptId'] and replay['replayed']
        with admin_connect() as current:
            assert current.execute('SELECT count(*) AS n FROM extension_event_control_dispatch_receipt').fetchone()['n'] == 1
            assert current.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n'] == 10
    finally:
        with psycopg.connect(service_database, autocommit=True) as current:
            current.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
