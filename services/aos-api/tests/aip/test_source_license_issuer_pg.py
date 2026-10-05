"""Source issuance contract and isolated PostgreSQL acceptance (b89)."""
import pytest
from pydantic import ValidationError

from aos_api.aip_license_source_issuer_contracts import (
    SourceLicenseIssuanceCommand, source_license_issuance_binding,
)
from aos_api.tenant_scope import TenantScope


def _command(**overrides):
    body = {
        'schemaVersion': 1, 'bearerToken': 'aaa.bbb.ccc',
        'orgId': 'org-org', 'projectId': 'dev-project', 'idempotencyKey': 'issue-1',
        'approvedProposal': {'resourceType': 'ActionProposal', 'resourceId': 'proposal-1',
                             'revision': 2, 'contentHash': 'a' * 64},
    }
    body.update(overrides)
    return body


@pytest.mark.parametrize('field,value', [
    ('actor', 'owner'), ('roles', ['owner']), ('requestedGrant', {}),
    ('schemaVersion', True), ('orgId', ' org-org'), ('idempotencyKey', 'issue 1'),
])
def test_source_issuance_rejects_caller_authority_or_inexact_command(field, value):
    with pytest.raises(ValidationError):
        SourceLicenseIssuanceCommand.model_validate(_command(**{field: value}))


@pytest.mark.parametrize('field,value', [
    ('resourceType', 'EvidenceBundleRevision'), ('resourceId', 'proposal 1'),
    ('revision', 1), ('revision', True), ('revision', '2'),
    ('contentHash', 'sha256:' + 'a' * 64),
])
def test_source_issuance_requires_exact_approved_proposal(field, value):
    body = _command()
    body['approvedProposal'][field] = value
    with pytest.raises(ValidationError):
        SourceLicenseIssuanceCommand.model_validate(body)


def test_source_issuance_binding_covers_scope_actor_and_complete_ref_without_secret_or_key():
    scope = TenantScope('org-org', 'dev-project')
    command = SourceLicenseIssuanceCommand.model_validate(_command())
    original = source_license_issuance_binding(scope, 'maker-1', command)
    assert original.authorization == 'ISSUANCE_REQUEST_ONLY_NO_START'
    changed_key = SourceLicenseIssuanceCommand.model_validate(
        _command(idempotencyKey='issue-2', bearerToken='ddd.eee.fff'))
    assert source_license_issuance_binding(scope, 'maker-1', changed_key) == original
    assert source_license_issuance_binding(scope, 'maker-2', command) != original
    changed_ref = _command()
    changed_ref['approvedProposal']['revision'] = 3
    assert source_license_issuance_binding(scope, 'maker-1',
        SourceLicenseIssuanceCommand.model_validate(changed_ref)) != original
    assert 'aaa.bbb.ccc' not in repr(command)
    with pytest.raises(ValueError, match='SOURCE_LICENSE_ISSUANCE_REQUEST_INVALID'):
        source_license_issuance_binding(TenantScope('dev-org', 'dev-project'), 'maker-1', command)


def test_source_issuance_binding_revalidates_constructed_or_copied_models():
    command = SourceLicenseIssuanceCommand.model_validate(_command())
    corrupted = command.model_copy(update={'approved_proposal':
        command.approved_proposal.model_copy(update={'revision': True})})
    with pytest.raises(ValueError, match='SOURCE_LICENSE_ISSUANCE_REQUEST_INVALID'):
        source_license_issuance_binding(TenantScope('org-org', 'dev-project'), 'maker-1', corrupted)
    for actor in ('unknown', 'maker 1', ''):
        with pytest.raises(ValueError, match='SOURCE_LICENSE_ISSUANCE_REQUEST_INVALID'):
            source_license_issuance_binding(TenantScope('org-org', 'dev-project'), actor, command)


@pytest.mark.parametrize('field,value', [
    ('resourceId', 'proposal-2'), ('revision', 3), ('contentHash', 'b' * 64),
])
def test_source_issuance_binding_changes_for_each_approved_reference_field(field, value):
    scope = TenantScope('org-org', 'dev-project')
    original = SourceLicenseIssuanceCommand.model_validate(_command())
    changed = _command()
    changed['approvedProposal'][field] = value
    assert source_license_issuance_binding(scope, 'maker-1', original) != (
        source_license_issuance_binding(scope, 'maker-1',
            SourceLicenseIssuanceCommand.model_validate(changed)))


def test_source_issuance_binding_changes_for_tenant_and_rejects_subclasses():
    scope = TenantScope('org-org', 'dev-project')
    original = SourceLicenseIssuanceCommand.model_validate(_command())
    canary = SourceLicenseIssuanceCommand.model_validate(_command(orgId='dev-org'))
    assert source_license_issuance_binding(scope, 'maker-1', original) != (
        source_license_issuance_binding(TenantScope('dev-org', 'dev-project'), 'maker-1', canary))

    class DerivedCommand(SourceLicenseIssuanceCommand):
        pass

    with pytest.raises(ValueError, match='SOURCE_LICENSE_ISSUANCE_REQUEST_INVALID'):
        source_license_issuance_binding(scope, 'maker-1', DerivedCommand.model_validate(_command()))


ISSUER = 'aos_source_license_issuer'


def test_source_license_issuer_acl_is_separate_and_login_closed():
    from tests.aip.test_network_consumer_boundary_pg import isolated_owner
    with isolated_owner() as conn:
        row = conn.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,'
            'rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s', (ISSUER,)).fetchone()
        assert row is not None
        assert not any(row.values())
        assert conn.execute('SELECT count(*) AS n FROM pg_auth_members WHERE '
            'roleid=%s::regrole OR member=%s::regrole', (ISSUER, ISSUER)).fetchone()['n'] == 0
        for table in ('aip_license_source_issuance', 'aip_license_source_head', 'aip_agent_registry_receipt'):
            assert conn.execute("SELECT has_table_privilege(%s,%s,'INSERT') AS allowed",
                (ISSUER, table)).fetchone()['allowed']
            assert not conn.execute("SELECT has_table_privilege(%s,%s,'UPDATE,DELETE') AS allowed",
                (ISSUER, table)).fetchone()['allowed']
        for table in ('aip_action_proposal', 'aip_action_draft', 'aip_action_approval_event',
                      'aip_action_event', 'aip_evidence_bundle_revoke_event'):
            assert not conn.execute("SELECT has_table_privilege(%s,%s,'INSERT,UPDATE,DELETE') AS allowed",
                (ISSUER, table)).fetchone()['allowed']


def test_issuer_read_lock_grants_do_not_allow_owner_mutation():
    import psycopg
    from psycopg import sql
    from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
    with isolated_owner() as conn:
        conn.execute("INSERT INTO meta_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,'b89-lock-owner','owner') ON CONFLICT DO NOTHING", SCOPE.key)
        conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(ISSUER)))
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SOURCE_ISSUER_READ_LOCK_ONLY'):
            conn.execute('UPDATE public.meta_membership SET subject=subject WHERE org_id=%s AND project_id=%s', SCOPE.key)
        conn.rollback()


def test_private_source_issuer_rejects_unverified_context_before_queries():
    from aos_api.aip_license_source_issuer import issue_source_license_in_transaction, SourceLicenseIssuanceBlocked
    with pytest.raises(SourceLicenseIssuanceBlocked, match='PRIVATE_ISSUER_CONTEXT_REQUIRED'):
        issue_source_license_in_transaction(conn=None, principal=None,
            command=SourceLicenseIssuanceCommand.model_validate(_command()), loader=None, release_policy=None)


@pytest.mark.parametrize('attribute', ['LOGIN', 'INHERIT', 'SUPERUSER', 'CREATEDB', 'CREATEROLE', 'REPLICATION', 'BYPASSRLS'])
def test_source_issuer_migration_rejects_unsafe_existing_role(monkeypatch, attribute):
    import importlib.util
    from pathlib import Path
    import psycopg
    from tests.aip.test_network_consumer_boundary_pg import isolated_owner
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/a0v_142_source_license_issuer_boundary.py'
    spec = importlib.util.spec_from_file_location('source_issuer_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with isolated_owner() as conn:
        monkeypatch.setattr(migration.op, 'execute', conn.execute)
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SOURCE_ISSUER_RESERVED_IDENTITY_DRIFT'):
            with conn.transaction():
                conn.execute(f'ALTER ROLE {ISSUER} {attribute}')
                migration.upgrade()
        assert conn.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls '
            'FROM pg_roles WHERE rolname=%s', (ISSUER,)).fetchone() == {
                'rolcanlogin': False, 'rolinherit': False, 'rolsuper': False, 'rolcreatedb': False,
                'rolcreaterole': False, 'rolreplication': False, 'rolbypassrls': False}


@pytest.mark.parametrize('role,operation,reason', [
    ('aos_runtime', 'source_license.issue', 'INDEPENDENT_ISSUER_REQUIRED'),
    (ISSUER, 'agent_instance.create', 'RECEIPT_OPERATION_REQUIRED'),
])
def test_reserved_receipt_operation_cannot_borrow_another_writer(role, operation, reason):
    import psycopg
    from psycopg import sql
    from uuid import uuid4
    from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
    with isolated_owner() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(role)))
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        key = 'b89-reserved-' + uuid4().hex
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match=reason):
            conn.execute("INSERT INTO public.aip_agent_registry_receipt "
                "(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,resource_ref,result_ref,status,created_by,created_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,'{}','{}','applied','test-only',clock_timestamp())",
                (*SCOPE.key, key, operation, key, 'a' * 64))
        conn.rollback()


@pytest.mark.parametrize('changed_table', ['asset_bundle_version', 'asset_bundle_evidence'])
def test_selected_registry_row_locks_reject_a_post_snapshot_committed_change(changed_table):
    """Native SERIAL behavior on canonical draft fixtures, not release authority."""
    from types import SimpleNamespace
    from uuid import uuid4
    import psycopg
    from aos_api.aip_license_source_issuer import _lock_selected_registry
    from aos_api.asset_registry.composition_contracts import CompositionLockPayload, CompositionRequest
    from aos_api.asset_registry.composition_store import PostgresCompositionStore
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from tests.asset_registry.test_installation_store import _composition_inputs, _create_request
    from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
    bundle, version = uuid4(), uuid4()
    identifier = 'solution.b89.' + uuid4().hex
    with isolated_owner() as admin:
        for table, values in [('twa_org', ('org-org', 'test-only')), ('meta_org', ('org-org', 'test-only'))]:
            admin.execute(f'INSERT INTO {table}(id,name) VALUES(%s,%s) ON CONFLICT DO NOTHING', values)
        for table in ('twa_workspace', 'meta_workspace'):
            admin.execute(f'INSERT INTO {table}(org_id,project_id,name) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',
                (*SCOPE.key, 'test-only'))
        admin.execute("INSERT INTO public.asset_bundle(bundle_pk,publisher,bundle_id,kind,display_name) "
            "VALUES(%s,'aos',%s,'SolutionPack','b89 canonical draft fixture')", (bundle, identifier))
        admin.execute("INSERT INTO public.asset_bundle_version(version_pk,bundle_pk,version,manifest_json,content_hash,created_by) "
            "VALUES(%s,%s,'1.0.0','{}',%s,'b89-test-only')", (version, bundle, 'sha256:' + 'a' * 64))
        admin.execute("INSERT INTO public.asset_bundle_evidence(version_pk,evidence_type,artifact_ref,artifact_hash,status,"
            "observed_at,expires_at,updated_by) VALUES(%s,'sbom','b89-test-only',%s,'valid',"
            "clock_timestamp()-interval '1 minute',clock_timestamp()+interval '1 hour','b89-test-only')",
            (version, 'sha256:' + 'b' * 64))
    request, snapshot, payload = _composition_inputs()
    raw = request.model_dump(mode='json', by_alias=True)
    raw['requested'][0]['id'] = identifier
    request = CompositionRequest.model_validate(raw)
    raw = payload.model_dump(mode='json', by_alias=True)
    raw['request'] = request.lock_request().model_dump(mode='json', by_alias=True)
    raw['resolved'][0]['id'] = identifier
    payload = CompositionLockPayload.model_validate(raw)
    composition = PostgresCompositionStore().create_or_get(org_id=SCOPE.org_id, project_id=SCOPE.project_id,
        request=request, snapshot=snapshot, payload=payload, created_by='b89-test-only')
    installation = PostgresInstallationStore().create_draft(org_id=SCOPE.org_id, project_id=SCOPE.project_id,
        request=_create_request(composition.composition_id), requested_by='b89-test-only')
    with isolated_owner() as reader:
        reader.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        reader.execute('SELECT version_pk FROM public.asset_bundle_version WHERE version_pk=%s', (version,)).fetchone()
        with isolated_owner() as writer:
            if changed_table == 'asset_bundle_version':
                writer.execute('UPDATE public.asset_bundle_version SET updated_at=clock_timestamp() WHERE version_pk=%s', (version,))
            else:
                writer.execute("UPDATE public.asset_bundle_evidence SET status='expired',updated_at=clock_timestamp() "
                    "WHERE version_pk=%s", (version,))
        with pytest.raises(psycopg.errors.SerializationFailure):
            _lock_selected_registry(reader, SCOPE, SimpleNamespace(installation_id=installation.installation_id))
        reader.rollback()


def test_source_receipt_without_issuance_and_head_cannot_commit():
    import psycopg
    from psycopg import sql
    from uuid import uuid4
    from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
    with pytest.raises(psycopg.errors.CheckViolation, match='SOURCE_ISSUER_ATOMIC_TRIPLE_REQUIRED'):
        with isolated_owner() as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
            conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(ISSUER)))
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
            key = 'b89-orphan-' + uuid4().hex
            conn.execute("INSERT INTO public.aip_agent_registry_receipt "
                "(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,resource_ref,result_ref,status,created_by,created_at) "
                "VALUES(%s,%s,%s,'source_license.issue',%s,%s,'{}','{}','applied','test-only',clock_timestamp())",
                (*SCOPE.key, key, key, 'a' * 64))


def assert_signed_original_source_issuance(approved, maker, loader, release_policy, *, approval_password):
    """Real JWT/SCRAM and original signed installation; test identities only."""
    import secrets
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from uuid import uuid4
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict
    from aos_api import aip_license_source_issuer as module
    from aos_api.db import get_dsn
    from aos_api.auth import Principal
    from aos_api.aip_license_source_proposal import SourceLicenseProposalBlocked
    from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
    from tests.aip.test_source_license_approval_pg import isolated_source_oidc
    parameters = conninfo_to_dict(get_dsn())
    assert parameters['dbname'].startswith('aos_test_') and parameters['dbname'].endswith('_ti4_test')
    password = secrets.token_urlsafe(32)
    with isolated_owner() as admin:
        admin.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(ISSUER), sql.Literal(password)))
    try:
        with TemporaryDirectory(prefix='b89-source-issuer-') as directory, isolated_source_oidc(maker) as token:
            folder = Path(directory)
            folder.chmod(0o700)
            secret = folder / 'source.pgpass'
            host, port = '127.0.0.1', int(parameters['port'])
            secret.write_text(f"{host}:{port}:{parameters['dbname']}:{ISSUER}:{password}\n")
            secret.chmod(0o600)
            config = module.SourceIssuerDatabaseConfig(host, port, parameters['dbname'], secret)
            command = SourceLicenseIssuanceCommand(schemaVersion=1, bearerToken=token,
                orgId=SCOPE.org_id, projectId=SCOPE.project_id, idempotencyKey='b89-issue-' + uuid4().hex,
                approvedProposal={'resourceType': 'ActionProposal', 'resourceId': approved.proposal.id,
                    'revision': approved.proposal.version, 'contentHash': approved.proposal.proposal_hash})
            principal = module.authenticate_source_license_command(command)
            assert principal.subject == maker and principal.token_kind == 'oidc'
            def counts():
                with isolated_owner() as observer:
                    return tuple(observer.execute(f'SELECT count(*) AS n FROM public.{table}' +
                        (" WHERE operation='source_license.issue'" if table == 'aip_agent_registry_receipt' else '')).fetchone()['n']
                        for table in ('aip_license_source_issuance', 'aip_license_source_head', 'aip_agent_registry_receipt'))
            assert counts() == (0, 0, 0)
            with module.connect_source_issuer(config, SCOPE) as conn:
                args = dict(conn=conn, principal=principal, command=command, loader=loader, release_policy=release_policy)
                for revision, digest in [(99, command.approved_proposal.content_hash),
                                         (command.approved_proposal.revision, '0' * 64)]:
                    invalid = command.model_copy(update={'approved_proposal': command.approved_proposal.model_copy(
                        update={'revision': revision, 'content_hash': digest})})
                    with pytest.raises(module.SourceLicenseIssuanceBlocked, match='EXACT_APPROVED_MAKER_REQUIRED'):
                        with conn.transaction(): module.issue_source_license_in_transaction(**{**args, 'command': invalid})
                with pytest.raises(module.SourceLicenseIssuanceBlocked, match='EXACT_APPROVED_MAKER_REQUIRED'):
                    with conn.transaction():
                        module.issue_source_license_in_transaction(**{**args, 'principal': Principal(subject='wrong-maker',
                            org_id=SCOPE.org_id, project_id=SCOPE.project_id, token_kind='oidc')})
                with pytest.raises(SourceLicenseProposalBlocked, match='INDEPENDENT_APPROVAL_IDENTITY_REQUIRED'):
                    with conn.transaction():
                        conn.execute('SET LOCAL search_path=pg_temp,public,pg_catalog')
                        module.issue_source_license_in_transaction(**args)
            assert counts() == (0, 0, 0)
            _assert_original_approval_expiry_and_withdrawal(approved, maker, approval_password,
                config, token, loader, release_policy)
            assert counts() == (0, 0, 0)
            # The real response is constructed before caller commit. A response
            # construction error must leave all three records absent.
            with pytest.MonkeyPatch.context() as patch:
                def broken_response(*args, **kwargs):
                    raise RuntimeError('test-only response construction failure')
                patch.setattr(module, 'SourceLicenseIssuanceResult', broken_response)
                with pytest.raises(RuntimeError, match='response construction failure'):
                    module.execute_source_license_issuance(command, database=config, loader=loader, release_policy=release_policy)
            assert counts() == (0, 0, 0)
            with pytest.raises(RuntimeError, match='caller rollback'):
                with module.connect_source_issuer(config, SCOPE) as conn:
                    module.issue_source_license_in_transaction(conn=conn, principal=principal, command=command,
                        loader=loader, release_policy=release_policy)
                    raise RuntimeError('test-only caller rollback')
            assert counts() == (0, 0, 0)
            # A separate test-only deferred constraint rejects the real COMMIT.
            # Original guards remain enabled; the connector must roll back all
            # three writes even though response construction already succeeded.
            trigger = 'b89_commit_failure_' + uuid4().hex[:12]
            with isolated_owner() as admin:
                admin.execute(sql.SQL("CREATE FUNCTION public.{}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                    "RAISE EXCEPTION 'b89 test-only deferred commit failure' USING ERRCODE='23514'; END $$").format(sql.Identifier(trigger)))
                admin.execute(sql.SQL('CREATE CONSTRAINT TRIGGER {} AFTER INSERT ON public.aip_license_source_issuance '
                    'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.{}()').format(
                    sql.Identifier(trigger), sql.Identifier(trigger)))
            try:
                with pytest.raises(psycopg.errors.CheckViolation, match='deferred commit failure'):
                    module.execute_source_license_issuance(command, database=config, loader=loader, release_policy=release_policy)
                assert counts() == (0, 0, 0)
            finally:
                with isolated_owner() as admin:
                    admin.execute(sql.SQL('DROP TRIGGER {} ON public.aip_license_source_issuance').format(sql.Identifier(trigger)))
                    admin.execute(sql.SQL('DROP FUNCTION public.{}()').format(sql.Identifier(trigger)))
            from concurrent.futures import ThreadPoolExecutor
            from queue import Queue
            from tests.aip.test_aip_license_source_authority_pg import raw_revoke, wait_blocked
            pids = Queue()
            grant = approved.proposal.payload['requestedGrant']
            checker = approved.approvals[0].actor.actor_id
            def writer(kind):
                with isolated_owner() as writer_conn:
                    writer_conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
                    pids.put(writer_conn.info.backend_pid)
                    try:
                        if kind in ('maker', 'checker'):
                            writer_conn.execute('DELETE FROM public.meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                                (*SCOPE.key, maker if kind == 'maker' else checker))
                        elif kind == 'installation':
                            writer_conn.execute('SELECT installation_id FROM public.bundle_installation WHERE org_id=%s AND project_id=%s '
                                'AND installation_id=%s FOR UPDATE', (*SCOPE.key, grant['installationId']))
                        elif kind == 'revoke':
                            raw_revoke(writer_conn, grant['source']['resourceId'], content_hash=grant['source']['contentHash'])
                        else:
                            # Actual evidence status mutation uses the original
                            # statement lock and rolls back after the issuer commits.
                            writer_conn.execute("""UPDATE public.asset_bundle_evidence e SET status='revoked',
                                revoked_at=clock_timestamp(),updated_at=clock_timestamp(),updated_by='b89-test-only',
                                status_reason='isolated writer rollback' FROM public.asset_bundle_version v
                                JOIN public.asset_bundle b ON b.bundle_pk=v.bundle_pk WHERE e.version_pk=v.version_pk
                                AND b.publisher=%s AND b.bundle_id=%s AND v.version=%s AND e.status='valid'""",
                                (grant['releaseRef']['publisher'], grant['releaseRef']['bundleId'], grant['releaseRef']['version']))
                    finally:
                        writer_conn.rollback()
            futures = []
            def competing_issuer():
                try:
                    with module.connect_source_issuer(config, SCOPE) as competing:
                        pids.put(competing.info.backend_pid)
                        module.issue_source_license_in_transaction(conn=competing, principal=principal,
                            command=command.model_copy(update={'idempotency_key': 'b89-first-race-' + uuid4().hex}),
                            loader=loader, release_policy=release_policy)
                    pytest.fail('competing first issuer committed a second license')
                except psycopg.errors.SerializationFailure as failure:
                    return failure.sqlstate
            with ThreadPoolExecutor(max_workers=6) as pool:
                try:
                    with module.connect_source_issuer(config, SCOPE) as conn:
                        issued = module.issue_source_license_in_transaction(conn=conn, principal=principal, command=command,
                            loader=loader, release_policy=release_policy)
                        futures = [pool.submit(writer, kind) for kind in ('maker', 'checker', 'installation', 'revoke', 'registry')]
                        futures.append(pool.submit(competing_issuer))
                        writer_pids = [pids.get(timeout=6) for _ in futures]
                        with isolated_owner() as observer:
                            wait_blocked(observer, writer_pids, conn.info.backend_pid, futures)
                    for future in futures[:-1]:
                        future.result(timeout=8)
                    assert futures[-1].result(timeout=8) == '40001'
                finally:
                    for future in futures:
                        future.result(timeout=8)
            assert issued.authorization == 'RESTRICTED_SOURCE_LICENSE_ONLY_NO_START'
            assert issued.receipt.operation == 'source_license.issue'
            assert issued.source.owner_authorization_ref['maker'] == maker
            assert issued.source.owner_authorization_ref['checker'] == approved.approvals[0].actor.actor_id
            assert issued.source.owner_authorization_ref['approvalEventId'] == approved.approvals[0].id
            assert issued.source.epoch == 0
            assert issued.source.expires_at <= approved.approvals[0].expires_at
            assert counts() == (1, 1, 1)
            # Legacy table-owner fixture is not an original authorized grant.
            # A real issuer must not promote it merely by inserting a head.
            with isolated_owner() as adversary:
                adversary.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                old = adversary.execute('SELECT * FROM public.aip_license_source_issuance WHERE issuance_id=%s',
                    (issued.source.issuance_id,)).fetchone()
                legacy = {**old, 'issuance_id': 'b89-legacy-' + uuid4().hex,
                    'owner_authorization_ref': {'test': 'legacy-owner-fixture'}}
                from psycopg.types.json import Jsonb
                adversary.execute(sql.SQL('INSERT INTO public.aip_license_source_issuance ({}) VALUES ({})').format(
                    sql.SQL(',').join(map(sql.Identifier, legacy)), sql.SQL(',').join(sql.Placeholder() for _ in legacy)),
                    [Jsonb(value) if isinstance(value, dict) else value for value in legacy.values()])
                adversary.execute('DELETE FROM public.aip_license_source_head WHERE org_id=%s AND project_id=%s AND bundle_id=%s',
                    (*SCOPE.key, old['bundle_id']))
                adversary.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(ISSUER)))
                adversary.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
                try:
                    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='EXACT_HEAD_REQUIRED'):
                        adversary.execute('INSERT INTO public.aip_license_source_head '
                            '(org_id,project_id,bundle_id,revision,content_hash,issuance_id,epoch) VALUES(%s,%s,%s,%s,%s,%s,0)',
                            (*SCOPE.key, old['bundle_id'], old['revision'], old['content_hash'], legacy['issuance_id']))
                finally:
                    adversary.rollback()
            assert counts() == (1, 1, 1)
            replay = module.execute_source_license_issuance(command, database=config, loader=loader, release_policy=release_policy)
            assert replay == issued and counts() == (1, 1, 1)
            changed_ref = command.model_copy(update={'approved_proposal': command.approved_proposal.model_copy(
                update={'content_hash': '0' * 64})})
            with pytest.raises(module.SourceLicenseIssuanceConflict, match='IDEMPOTENCY_CONFLICT'):
                module.execute_source_license_issuance(changed_ref, database=config, loader=loader, release_policy=release_policy)
            for owner in (maker, checker):
                with isolated_owner() as admin:
                    admin.execute('DELETE FROM public.meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                        (*SCOPE.key, owner))
                try:
                    with pytest.raises(module.SourceLicenseIssuanceBlocked, match='BOTH_CURRENT_OWNERS_REQUIRED'):
                        module.execute_source_license_issuance(command, database=config, loader=loader, release_policy=release_policy)
                    assert counts() == (1, 1, 1)
                finally:
                    with isolated_owner() as admin:
                        admin.execute("INSERT INTO public.meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",
                            (*SCOPE.key, owner))
            other_key = command.model_copy(update={'idempotency_key': 'b89-other-' + uuid4().hex})
            with pytest.raises(module.SourceLicenseIssuanceConflict, match='ALREADY_ISSUED'):
                module.execute_source_license_issuance(other_key, database=config, loader=loader, release_policy=release_policy)
            with module.connect_source_issuer(config, SCOPE) as conn:
                from aos_api.aip_license_source_authority import read_license_source_fact
                from aos_api.aip_production_contracts import ExactRevisionRef
                fact = read_license_source_fact(conn, SCOPE,
                    ExactRevisionRef.model_validate(approved.proposal.payload['requestedGrant']['source']),
                    checked_at=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
                assert fact == issued.source
            with module.connect_source_issuer(config, TenantScope('dev-org', 'dev-project')) as canary:
                for table in ('aip_license_source_issuance', 'aip_license_source_head', 'aip_agent_registry_receipt'):
                    assert canary.execute(f'SELECT count(*) AS n FROM public.{table}').fetchone()['n'] == 0
            assert counts() == (1, 1, 1)
            for drift, reason in [('installation', 'INSTALLATION_LOCK_MISSING'),
                                  ('policy', 'CURRENT_SIGNED_POLICY_UNAVAILABLE'),
                                  ('revoke', 'SOURCE_INELIGIBLE')]:
                with isolated_owner() as mutator:
                    mutator.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                    mutator.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
                    if drift == 'installation':
                        # Respect the original immediate monotonic guard;
                        # leave the new revision/event intentionally incomplete
                        # inside this fault transaction and always roll it back.
                        mutator.execute('UPDATE public.bundle_installation SET etag_version=etag_version+1, '
                            'current_revision=current_revision+1,updated_at=clock_timestamp() '
                            'WHERE org_id=%s AND project_id=%s AND installation_id=%s',
                            (*SCOPE.key, grant['installationId']))
                    elif drift == 'policy':
                        mutator.execute("""UPDATE public.asset_bundle_evidence e SET status='revoked',
                            revoked_at=clock_timestamp(),updated_at=clock_timestamp(),updated_by='b89-test-only',
                            status_reason='isolated policy rollback' FROM public.asset_bundle_version v
                            JOIN public.asset_bundle b ON b.bundle_pk=v.bundle_pk WHERE e.version_pk=v.version_pk
                            AND b.publisher=%s AND b.bundle_id=%s AND v.version=%s AND e.status='valid'""",
                            (grant['releaseRef']['publisher'], grant['releaseRef']['bundleId'], grant['releaseRef']['version']))
                    else:
                        raw_revoke(mutator, grant['source']['resourceId'], content_hash=grant['source']['contentHash'])
                        from aos_api.aip_license_source_authority import LicenseSourceUnavailable
                        with pytest.raises(LicenseSourceUnavailable, match='LICENSE_SOURCE_REVOKED'):
                            read_license_source_fact(mutator, SCOPE, fact.source,
                                checked_at=mutator.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
                        assert mutator.execute('SELECT epoch FROM public.aip_license_source_head WHERE issuance_id=%s',
                            (issued.source.issuance_id,)).fetchone()['epoch'] == 1
                    mutator.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(ISSUER)))
                    mutator.execute('SET LOCAL search_path=pg_catalog,public,pg_temp')
                    try:
                        expected_error = module.SourceLicenseIssuanceBlocked if drift == 'installation' else SourceLicenseProposalBlocked
                        with pytest.raises(expected_error, match=reason):
                            module.issue_source_license_in_transaction(conn=mutator, principal=principal, command=command,
                                loader=loader, release_policy=release_policy)
                    finally:
                        mutator.rollback()
                assert counts() == (1, 1, 1)
            restored = module.execute_source_license_issuance(command, database=config, loader=loader, release_policy=release_policy)
            assert restored == issued
    finally:
        with isolated_owner() as admin:
            admin.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(ISSUER)))


def _assert_original_approval_expiry_and_withdrawal(approved, maker, approval_password,
                                                  config, maker_token, loader, release_policy):
    import time
    from datetime import timedelta
    from uuid import uuid4
    import psycopg
    from psycopg.rows import dict_row
    from aos_api import aip_license_source_issuer as module
    from aos_api.db import get_dsn
    from aos_api.tenant_scope import apply_transaction_scope
    from aos_api.aip_license_source_approval import (
        propose_authenticated_source_license_in_transaction, approve_source_license_in_transaction,
        authenticate_source_license_command,
    )
    from aos_api.aip_license_source_proposal import SourceLicenseProposalBlocked
    from aos_api.aip_license_source_proposal_contracts import (
        SourceLicenseMakerCommand, SourceLicenseApprovalCommand, SourceLicenseProposalRequest,
    )
    from aos_api.aip_action_models import DecideActionProposalRequest, WithdrawActionProposalRequest
    from aos_api.aip_action_store import AipActionStore
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from tests.aip.test_network_consumer_boundary_pg import SCOPE
    from tests.aip.test_source_license_approval_pg import isolated_source_oidc, isolated_source_approval_connection
    checker = approved.approvals[0].actor.actor_id
    for mode in ('expired', 'withdrawn'):
        with psycopg.connect(get_dsn(), row_factory=dict_row) as maker_conn:
            maker_conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
            apply_transaction_scope(maker_conn, SCOPE)
            raw = dict(approved.proposal.payload['requestedGrant'])
            if mode == 'expired':
                raw['proposalExpiresAt'] = maker_conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'] + timedelta(seconds=3)
            maker_command = SourceLicenseMakerCommand(schemaVersion=1, bearerToken=maker_token,
                orgId=SCOPE.org_id, projectId=SCOPE.project_id, idempotencyKey='b89-' + mode + '-' + uuid4().hex,
                request=SourceLicenseProposalRequest.model_validate(raw))
            proposal = propose_authenticated_source_license_in_transaction(maker_command, conn=maker_conn,
                loader=loader, release_policy=release_policy)
        with isolated_source_oidc(checker) as checker_token, isolated_source_approval_connection(approval_password) as checker_conn:
            approval_command = SourceLicenseApprovalCommand(schemaVersion=1, bearerToken=checker_token,
                orgId=SCOPE.org_id, projectId=SCOPE.project_id, idempotencyKey='b89-check-' + uuid4().hex,
                proposalId=proposal.proposal.id, decision=DecideActionProposalRequest(expectedProposalVersion=1,
                    expectedProposalHash=proposal.proposal.proposal_hash, decision='approved'))
            authorized = approve_source_license_in_transaction(conn=checker_conn,
                principal=authenticate_source_license_command(approval_command), proposal_id=proposal.proposal.id,
                idempotency_key=approval_command.idempotency_key, decision=approval_command.decision,
                loader=loader, release_policy=release_policy)
        issue_command = SourceLicenseIssuanceCommand(schemaVersion=1, bearerToken=maker_token,
            orgId=SCOPE.org_id, projectId=SCOPE.project_id, idempotencyKey='b89-deny-' + uuid4().hex,
            approvedProposal={'resourceType': 'ActionProposal', 'resourceId': authorized.proposal.id,
                'revision': authorized.proposal.version, 'contentHash': authorized.proposal.proposal_hash})
        if mode == 'withdrawn':
            with psycopg.connect(get_dsn(), row_factory=dict_row) as maker_conn:
                maker_conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
                apply_transaction_scope(maker_conn, SCOPE)
                AipActionStore(TransactionBoundConnectFactory(HostTransaction(maker_conn), SCOPE)).withdraw(
                    SCOPE, maker, authorized.proposal.id, 'b89-withdraw-event-' + uuid4().hex,
                    WithdrawActionProposalRequest(expectedProposalVersion=authorized.proposal.version,
                        expectedProposalHash=authorized.proposal.proposal_hash, reason='test-only approved withdrawal'))
            with pytest.raises(module.SourceLicenseIssuanceBlocked, match='EXACT_APPROVED_MAKER_REQUIRED'):
                module.execute_source_license_issuance(issue_command, database=config, loader=loader, release_policy=release_policy)
        else:
            # The response can be valid before commit and expire while the
            # caller still holds the transaction. The DB commit gate must
            # reject the whole original triple using its live clock.
            with pytest.raises(psycopg.errors.CheckViolation, match='SOURCE_ISSUER_ATOMIC_TRIPLE_REQUIRED'):
                with module.connect_source_issuer(config, SCOPE) as observer:
                    result = module.issue_source_license_in_transaction(conn=observer,
                        principal=module.authenticate_source_license_command(issue_command), command=issue_command,
                        loader=loader, release_policy=release_policy)
                    assert result.source.expires_at == authorized.proposal.expires_at
                    deadline = time.monotonic() + 5
                    while observer.execute('SELECT clock_timestamp() AS now').fetchone()['now'] < authorized.proposal.expires_at:
                        assert time.monotonic() < deadline
                        time.sleep(0.02)
            with pytest.raises(SourceLicenseProposalBlocked, match='REQUEST_WINDOW_EXPIRED'):
                module.execute_source_license_issuance(issue_command, database=config, loader=loader, release_policy=release_policy)
