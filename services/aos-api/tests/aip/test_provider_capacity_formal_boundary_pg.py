"""Private Source approved-claim reads do not verify suppliers or issue capacity."""
from contextlib import contextmanager
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from tests.aip.test_provider_capacity_source_action_pg import source_inputs,source_proposal
from tests.aip.test_provider_capacity_action_pg import drafted
from tests.aip.test_provider_capacity_request_pg import original_inputs,SCOPE
from tests.aip._runtime_guard_history_fixture import isolated_owner

ISSUER='aos_provider_capacity_issuer'


@pytest.fixture
def approved_command(source_proposal,https_signer):
    from aos_api.aip_provider_capacity_source_action import decide_provider_capacity_source
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand
    from aos_api.aip_action_store import canonical_hash
    maker,checker,candidate,_,proposal,decision=source_proposal
    result=decide_provider_capacity_source(checker,proposal.proposal.id,'source-approved-'+uuid4().hex,decision)
    sign,_=https_signer
    command=ProviderCapacityIssuanceCommand.model_validate(dict(schemaVersion=1,tenant=candidate.tenant.model_dump(by_alias=True),
        bearerToken=sign(maker.subject),idempotencyKey='private-claim-'+uuid4().hex,
        approvedProposal=dict(assetType='ActionProposal',assetId=result.proposal.id,revision=2,contentHash=result.proposal.proposal_hash),
        approvalEvent=dict(assetType='ActionApprovalEvent',assetId=result.approvals[0].id,revision=1,
            contentHash=canonical_hash(result.approvals[0].model_dump(mode='json',by_alias=True))),
        supplierAttestationRef=dict(assetType='SupplierCapacityAttestationRevision',assetId='test-only-unverified',revision=1,contentHash='a'*64),
        sourcePolicyRef=dict(assetType='ProviderCapacitySourcePolicyRevision',assetId='test-only-unverified',revision=1,contentHash='b'*64)))
    return maker,checker,candidate,result,command


@pytest.fixture
def private_database(approved_command,tmp_path):
    from aos_api.aip_provider_capacity_issuer_connection import ProviderCapacityIssuerDatabaseConfig
    import secrets
    parts=conninfo_to_dict(os.environ['AOS_DATABASE_URL']);password=secrets.token_urlsafe(24)
    assert parts['dbname'].startswith('aos_test_')
    directory=tmp_path/'capacity-private';directory.mkdir(mode=0o700)
    path=directory/'passfile';path.write_text(':'.join((parts['host'],parts['port'],parts['dbname'],ISSUER,password))+'\n');path.chmod(0o600)
    with isolated_owner() as conn:
        conn.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(ISSUER),sql.Literal(password)))
    try:
        yield ProviderCapacityIssuerDatabaseConfig(parts['host'],int(parts['port']),parts['dbname'],path)
    finally:
        with isolated_owner() as conn:conn.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(ISSUER)))
        path.unlink()


def test_actual_private_scram_reads_original_approved_source_claims_without_grant(approved_command,private_database):
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims
    maker,_,candidate,result,command=approved_command
    with connect_capacity_issuer(private_database,SCOPE) as conn:
        identity=conn.execute('SELECT session_user AS login,current_user AS role,current_database() AS db').fetchone()
        assert identity==dict(login=ISSUER,role=ISSUER,db=private_database.database)
        assert conn.pgconn.used_password is True
        fact=read_capacity_approved_claims(conn,command)
        assert fact.authorization=='APPROVED_CLAIMS_ONLY_NO_CAPACITY_NO_START'
        assert fact.maker==maker.subject and fact.source==candidate
        assert fact.approved_proposal==command.approved_proposal and fact.approval_event==command.approval_event
        assert fact.supplier_verified is False and fact.execution_allowed is False
        assert conn.execute('SELECT count(*) AS n FROM aip_action_approval_event WHERE proposal_id=%s',(result.proposal.id,)).fetchone()['n']==1


def test_private_time_zone_is_utc_despite_test_login_default(approved_command, private_database):
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims
    with isolated_owner() as owner:
        row = owner.execute("SELECT rolconfig FROM pg_roles WHERE rolname=%s", (ISSUER,)).fetchone()
        assert row["rolconfig"] is None  # Never replace an existing test role configuration.
        owner.execute("ALTER ROLE aos_provider_capacity_issuer SET TimeZone='Asia/Shanghai'")
    try:
        with connect_capacity_issuer(private_database, SCOPE) as conn:
            assert conn.execute("SELECT current_setting('TimeZone') AS zone").fetchone()["zone"] == "UTC"
            assert read_capacity_approved_claims(conn, approved_command[-1]).maker == approved_command[0].subject
    finally:
        with isolated_owner() as owner:
            owner.execute("ALTER ROLE aos_provider_capacity_issuer RESET TimeZone")


def test_private_time_zone_drift_rejected_before_approved_claims(approved_command, private_database):
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_formal_boundary import require_capacity_issuer_identity, ProviderCapacityFormalBoundaryBlocked
    with connect_capacity_issuer(private_database, SCOPE) as conn:
        conn.execute("SET LOCAL TimeZone='Asia/Shanghai'")
        with pytest.raises(ProviderCapacityFormalBoundaryBlocked, match="CAPACITY_ISSUER_PRIVATE_IDENTITY_REQUIRED"):
            require_capacity_issuer_identity(conn, SCOPE)


@pytest.mark.parametrize('fault',['runtime','canary','autocommit','idle','role_switch'])
def test_private_read_rejects_wrong_actual_caller_context(approved_command,private_database,fault):
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims,ProviderCapacityFormalBoundaryBlocked
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer,ProviderCapacityIssuerConnectionBlocked
    from aos_api.db import connect
    from aos_api.tenant_scope import TenantScope
    command=approved_command[-1]
    if fault=='canary':
        with pytest.raises(ProviderCapacityIssuerConnectionBlocked):
            with connect_capacity_issuer(private_database,TenantScope('dev-org','dev-project')):pass
        return
    context=connect(SCOPE) if fault=='runtime' else connect_capacity_issuer(private_database,SCOPE)
    with context as conn:
        if fault in {'autocommit','idle'}:
            conn.rollback()
            if fault=='autocommit':conn.autocommit=True
        elif fault=='role_switch':
            # A private login cannot borrow runtime membership.
            with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute('SET ROLE aos_runtime')
            conn.rollback();return
        with pytest.raises(ProviderCapacityFormalBoundaryBlocked):read_capacity_approved_claims(conn,command)


@pytest.mark.parametrize('table,column', [('meta_membership','subject'),('aip_provider_instance_head','provider_instance_id'),
    ('aip_action_proposal','proposal_id'),('meta_object_type','id'),('meta_action_type','id')])
def test_private_row_lock_column_grant_never_allows_actual_noop_mutation(approved_command,private_database,table,column):
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    maker,_,candidate,result,_=approved_command
    identities={'meta_membership':maker.subject,'aip_provider_instance_head':candidate.physical_account_ref.asset_id,
        'aip_action_proposal':result.proposal.id,'meta_object_type':'ProviderCapacitySourceReview',
        'meta_action_type':'aip_review_provider_capacity_source'}
    if table=='aip_provider_instance_head':
        from aos_api.db import connect
        with connect(SCOPE) as conn:
            identities[table]=conn.execute('SELECT provider_instance_id FROM aip_provider_instance_head ORDER BY provider_instance_id LIMIT 1').fetchone()['provider_instance_id']
    with connect_capacity_issuer(private_database,SCOPE) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(sql.SQL('UPDATE public.{} SET {}={} WHERE {}=%s').format(*map(sql.Identifier,[table,column,column,column])),(identities[table],))
        conn.rollback()


@pytest.mark.parametrize('fault',['extra_table_grant','column_grant','function_grant','trigger_disabled','role_membership','policy'])
def test_actual_private_boundary_drift_denies_claim_read(approved_command,private_database,fault):
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer,ProviderCapacityIssuerConnectionBlocked
    from aos_api.aip_provider_capacity_formal_boundary import ProviderCapacityFormalBoundaryBlocked
    alterations={
      'extra_table_grant':(f'GRANT SELECT ON public.aip_task TO {ISSUER}',f'REVOKE SELECT ON public.aip_task FROM {ISSUER}'),
      'column_grant':(f'GRANT UPDATE(role) ON public.meta_membership TO {ISSUER}',f'REVOKE UPDATE(role) ON public.meta_membership FROM {ISSUER}'),
      'function_grant':('GRANT EXECUTE ON FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) TO PUBLIC','REVOKE EXECUTE ON FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) FROM PUBLIC'),
      'trigger_disabled':('ALTER TABLE public.meta_membership DISABLE TRIGGER capacity_issuer_read_lock_only_a0v150','ALTER TABLE public.meta_membership ENABLE TRIGGER capacity_issuer_read_lock_only_a0v150'),
      'role_membership':(f'GRANT aos_runtime TO {ISSUER}',f'REVOKE aos_runtime FROM {ISSUER}'),
      'policy':('ALTER POLICY capacity_issuer_scope_a0v150 ON public.meta_membership USING(true)',"ALTER POLICY capacity_issuer_scope_a0v150 ON public.meta_membership USING(org_id='org-org' AND project_id='dev-project' AND org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))")}
    change,restore=alterations[fault]
    with isolated_owner() as conn:conn.execute(change)
    try:
        with pytest.raises((ProviderCapacityIssuerConnectionBlocked,ProviderCapacityFormalBoundaryBlocked)):
            with connect_capacity_issuer(private_database,SCOPE):pass
    finally:
        with isolated_owner() as conn:conn.execute(restore)


@pytest.mark.parametrize('fault',['proposal_hash','event_hash','different_event','provider_head','evidence_revoke','maker_role','checker_role'])
def test_private_claim_read_rechecks_original_approval_and_dependencies(approved_command,private_database,fault):
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims,ProviderCapacityFormalBoundaryBlocked
    maker,checker,candidate,_,command=approved_command
    if fault=='proposal_hash':command=command.model_copy(update={'approved_proposal':command.approved_proposal.model_copy(update={'content_hash':'f'*64})})
    elif fault=='event_hash':command=command.model_copy(update={'approval_event':command.approval_event.model_copy(update={'content_hash':'f'*64})})
    elif fault=='different_event':command=command.model_copy(update={'approval_event':command.approval_event.model_copy(update={'asset_id':uuid4().hex})})
    else:
        with isolated_owner() as conn:
            if fault in {'maker_role','checker_role'}:
                conn.execute("UPDATE meta_membership SET role='member' WHERE org_id=%s AND project_id=%s AND subject=%s",(*SCOPE.key,maker.subject if fault=='maker_role' else checker.subject))
            elif fault=='provider_head':
                row=conn.execute('SELECT request_json FROM aip_provider_capacity_candidate WHERE candidate_id=%s',(candidate.physical_account_ref.asset_id,)).fetchone()
                ref=row['request_json']['candidate']['providerRefs'][0]
                conn.execute('UPDATE aip_provider_instance_head SET current_revision=99 WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s',(*SCOPE.key,ref['assetId']))
            else:
                from aos_api.aip_production_contract_store import AipProductionContractStore
                from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
                from tests.aip.test_evidence_bundle_provenance_pg import ACTOR
                row=conn.execute('SELECT request_json FROM aip_provider_capacity_candidate WHERE candidate_id=%s',(candidate.basis_ref.asset_id,)).fetchone()
                ref=row['request_json']['candidate']['evidenceRef']
                AipProductionContractStore().revoke_evidence_bundle(SCOPE,ACTOR,ref['assetId'],'private-claim-revoke-'+uuid4().hex,
                    RevokeEvidenceBundleRequest(expectedRevision=ref['revision'],expectedContentHash=ref['contentHash'],reason='isolated private claim currentness'))
        # Per-test fixture identities/dependencies are unique; no production data.
    with connect_capacity_issuer(private_database,SCOPE) as conn:
        with pytest.raises(ProviderCapacityFormalBoundaryBlocked):read_capacity_approved_claims(conn,command)



def test_private_sql_rls_does_not_inherit_broad_legacy_public_policy(approved_command,private_database):
    from psycopg.rows import dict_row
    with isolated_owner() as conn:
        conn.execute("INSERT INTO meta_org(id,name) VALUES('dev-org','isolated canary') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('dev-org','dev-project','isolated canary') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES('dev-org','dev-project',%s,'owner')",('private-canary-'+uuid4().hex,))
    # Native SQL checks DB isolation independently from Python identity checks.
    with psycopg.connect(host=private_database.host,port=private_database.port,dbname=private_database.database,
        user=ISSUER,passfile=str(private_database.passfile),require_auth='scram-sha-256',row_factory=dict_row) as conn:
        conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
        assert conn.execute("SELECT count(*) AS n FROM meta_membership WHERE org_id='dev-org'").fetchone()['n']==0
        conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        assert conn.execute("SELECT count(*) AS n FROM meta_membership").fetchone()['n']==0


@pytest.mark.parametrize('function_name', [
    'extension_dispatch_cutover_history_guard_ar2_014',
    'extension_dispatch_lifecycle_history_guard_ar2_017',
    'extension_event_control_dispatch_history_guard_a0v_054',
    'extension_runtime_uninstall_consistency_ar2_018',
    'snapshot_stalled_group_terminal_guard_a0v_091',
    'snapshot_unaccepted_group_terminal_guard_a0v_083',
    'unaccepted_analysis_terminal_guard_a0v_060',
])
def test_private_login_cannot_attach_legacy_definer_to_own_temporary_table(approved_command, private_database, function_name):
    # Exercise PostgreSQL's actual CREATE TRIGGER permission gate, outside the
    # Python identity checker; a catalog allowlist alone is insufficient.
    with psycopg.connect(host=private_database.host, port=private_database.port,
                         dbname=private_database.database, user=ISSUER,
                         passfile=str(private_database.passfile), require_auth='scram-sha-256') as conn:
        conn.execute('CREATE TEMP TABLE capacity_legacy_attachment_probe(id integer)')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(sql.SQL('CREATE TRIGGER legacy_attachment BEFORE INSERT ON capacity_legacy_attachment_probe '
                                 'FOR EACH ROW EXECUTE FUNCTION public.{}()').format(sql.Identifier(function_name)))
        conn.rollback()


@pytest.mark.parametrize('fault', ['table', 'column', 'public_table', 'schema_usage'])
def test_private_boundary_rejects_nonpublic_same_name_and_public_usage(approved_command, private_database, fault):
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer, ProviderCapacityIssuerConnectionBlocked
    schema='capacity_acl_probe_'+uuid4().hex
    with isolated_owner() as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO PUBLIC').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('CREATE TABLE {}.meta_membership(subject text)').format(sql.Identifier(schema)))
        conn.execute(sql.SQL("INSERT INTO {}.meta_membership VALUES('foreign-private-row')").format(sql.Identifier(schema)))
        if fault!='schema_usage':
            grant='UPDATE(subject)' if fault=='column' else 'SELECT'
            recipient='PUBLIC' if fault=='public_table' else ISSUER
            conn.execute(sql.SQL('GRANT '+grant+' ON {}.meta_membership TO '+recipient).format(sql.Identifier(schema)))
    try:
        if fault in {'table','public_table'}:
            # Prove the extra capability through native SQL before the audit.
            with psycopg.connect(host=private_database.host,port=private_database.port,
                    dbname=private_database.database,user=ISSUER,passfile=str(private_database.passfile),
                    require_auth='scram-sha-256') as raw:
                assert raw.execute(sql.SQL('SELECT subject FROM {}.meta_membership').format(sql.Identifier(schema))).fetchone()==('foreign-private-row',)
        with pytest.raises(ProviderCapacityIssuerConnectionBlocked):
            with connect_capacity_issuer(private_database,SCOPE):pass
    finally:
        with isolated_owner() as conn:conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_private_reader_first_holds_original_withdrawal_until_caller_commit(approved_command, private_database, monkeypatch):
    from threading import Event,Thread
    import time
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims
    from aos_api import aip_provider_capacity_source_action as source_action
    from aos_api.db import connect
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from tests.aip.test_evidence_bundle_provenance_pg import ACTOR
    from tests.aip.test_provider_capacity_evidence_epoch_pg import evidence_ref
    ref=evidence_ref(approved_command[2])
    paused,release,started,done=Event(),Event(),Event(),Event()
    results={}
    original=source_action.lock_capacity_evidence_refs
    def lock_then_pause(conn,scope,refs):
        original(conn,scope,refs)
        results['reader_pid']=conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        paused.set()
        if not release.wait(8):raise RuntimeError('private reader timing timeout')
    monkeypatch.setattr(source_action,'lock_capacity_evidence_refs',lock_then_pause)
    @contextmanager
    def writer_connect(scope):
        with connect(scope) as conn:
            results['writer_pid']=conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            started.set();yield conn
    def reader():
        try:
            with connect_capacity_issuer(private_database,SCOPE) as conn:
                results['claims']=read_capacity_approved_claims(conn,approved_command[-1])
        except BaseException as exc:results['reader_error']=exc
    def writer():
        try:
            results['withdrawal']=AipProductionContractStore(connect_factory=writer_connect).revoke_evidence_bundle(
                SCOPE,ACTOR,ref.asset_id,'private-reader-revoke-'+uuid4().hex,
                RevokeEvidenceBundleRequest(expectedRevision=ref.revision,expectedContentHash=ref.content_hash,reason='isolated private reader withdrawal competition'))
        except BaseException as exc:results['writer_error']=exc
        finally:done.set()
    rt,wt=Thread(target=reader),Thread(target=writer)
    rt.start();blocked=False
    try:
        assert paused.wait(8),results
        wt.start();assert started.wait(8)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline and not done.is_set():
            with isolated_owner() as owner:
                row=owner.execute('SELECT pg_blocking_pids(%s) AS blockers',(results['writer_pid'],)).fetchone()
            if results['reader_pid'] in row['blockers']:blocked=True;break
            time.sleep(.02)
        assert blocked and not done.is_set(),'original withdrawal did not wait for the actual private reader'
    finally:
        release.set();rt.join(10)
        if wt.ident is not None:wt.join(10)
    assert not rt.is_alive() and not wt.is_alive()
    assert 'reader_error' not in results and 'writer_error' not in results,results
    assert results['claims'].execution_allowed is False
    assert results['withdrawal'].revoked is True
    with connect_capacity_issuer(private_database,SCOPE) as conn:
        from aos_api.aip_provider_capacity_formal_boundary import ProviderCapacityFormalBoundaryBlocked
        with pytest.raises(ProviderCapacityFormalBoundaryBlocked):read_capacity_approved_claims(conn,approved_command[-1])
        conn.rollback()


def test_original_withdrawal_after_private_serial_snapshot_blocks_claims(approved_command, private_database):
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims,ProviderCapacityFormalBoundaryBlocked
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from tests.aip.test_evidence_bundle_provenance_pg import ACTOR
    from tests.aip.test_provider_capacity_evidence_epoch_pg import evidence_ref
    ref=evidence_ref(approved_command[2])
    with connect_capacity_issuer(private_database,SCOPE) as conn:
        conn.execute('SELECT clock_timestamp()').fetchone()
        result=AipProductionContractStore().revoke_evidence_bundle(SCOPE,ACTOR,ref.asset_id,'private-writer-first-'+uuid4().hex,
            RevokeEvidenceBundleRequest(expectedRevision=ref.revision,expectedContentHash=ref.content_hash,reason='isolated stale private serial snapshot'))
        assert result.revoked is True
        with pytest.raises(ProviderCapacityFormalBoundaryBlocked):read_capacity_approved_claims(conn,approved_command[-1])
        conn.rollback()


@pytest.mark.parametrize('privilege',['UPDATE','INSERT','REFERENCES'])
def test_private_boundary_rejects_public_column_privilege_on_allowed_table(approved_command,private_database,privilege):
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer,ProviderCapacityIssuerConnectionBlocked
    with isolated_owner() as conn:conn.execute(sql.SQL('GRANT '+privilege+'(role) ON public.meta_membership TO PUBLIC'))
    try:
        with psycopg.connect(host=private_database.host,port=private_database.port,dbname=private_database.database,
                user=ISSUER,passfile=str(private_database.passfile),require_auth='scram-sha-256') as raw:
            assert raw.execute("SELECT has_column_privilege(current_user,'public.meta_membership','role',%s)",(privilege,)).fetchone()==(True,)
        with pytest.raises(ProviderCapacityIssuerConnectionBlocked):
            with connect_capacity_issuer(private_database,SCOPE):pass
    finally:
        with isolated_owner() as conn:conn.execute(sql.SQL('REVOKE '+privilege+'(role) ON public.meta_membership FROM PUBLIC'))


def test_private_boundary_rejects_guard_moved_to_foreign_same_name_table(approved_command,private_database):
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer,ProviderCapacityIssuerConnectionBlocked
    schema='capacity_trigger_probe_'+uuid4().hex
    with isolated_owner() as conn:
        original=conn.execute("SELECT pg_get_triggerdef(oid) AS definition FROM pg_trigger WHERE tgrelid='public.meta_membership'::regclass AND tgname='capacity_issuer_read_lock_only_a0v150'").fetchone()['definition']
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('CREATE TABLE {}.meta_membership(subject text)').format(sql.Identifier(schema)))
        conn.execute('DROP TRIGGER capacity_issuer_read_lock_only_a0v150 ON public.meta_membership')
        conn.execute(sql.SQL('CREATE TRIGGER capacity_issuer_read_lock_only_a0v150 BEFORE INSERT OR UPDATE OR DELETE ON {}.meta_membership '
                             'FOR EACH ROW EXECUTE FUNCTION public.capacity_issuer_read_lock_only_a0v150()').format(sql.Identifier(schema)))
    try:
        with pytest.raises(ProviderCapacityIssuerConnectionBlocked):
            with connect_capacity_issuer(private_database,SCOPE):pass
    finally:
        with isolated_owner() as conn:
            conn.execute(original)
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


@pytest.mark.parametrize('function_name,table,fields,normal,invalid,error', [
    ('extension_dispatch_cutover_history_guard_ar2_014','extension_dispatch_cutover_operation',
     "kind text DEFAULT 'activate',status text DEFAULT 'prepared',org_id text DEFAULT 'org-org',project_id text DEFAULT 'dev-project',cutover_operation_id uuid DEFAULT gen_random_uuid()",
     "UPDATE pg_temp.extension_dispatch_cutover_operation SET status='prepared'",
     "UPDATE pg_temp.extension_dispatch_cutover_operation SET status='draining'",'23514'),
    ('extension_dispatch_lifecycle_history_guard_ar2_017','extension_dispatch_lifecycle_operation',
     "status text DEFAULT 'prepared',org_id text DEFAULT 'org-org',project_id text DEFAULT 'dev-project',runtime_operation_id uuid DEFAULT gen_random_uuid()",
     "UPDATE pg_temp.extension_dispatch_lifecycle_operation SET status='prepared'",
     "UPDATE pg_temp.extension_dispatch_lifecycle_operation SET status='fenced'",'23514'),
    ('extension_event_control_dispatch_history_guard_a0v_054','extension_event_control_dispatch_receipt',
     'id integer DEFAULT 1',None,"UPDATE pg_temp.extension_event_control_dispatch_receipt SET id=2",'55000'),
    ('extension_runtime_uninstall_consistency_ar2_018','extension_runtime_binding',
     "desired_state text DEFAULT 'enabled',observed_state text DEFAULT 'ready',enabled boolean DEFAULT true,operation_fence boolean DEFAULT false,revision bigint DEFAULT 1,installation_revision bigint DEFAULT 1,installation_id uuid DEFAULT gen_random_uuid(),generation uuid DEFAULT gen_random_uuid(),package_lock_ref jsonb DEFAULT '{}',profile_ref text DEFAULT 'internal-python-v1',config_ref jsonb DEFAULT '{}',execution_epoch bigint DEFAULT 1,resource_handle_ref jsonb DEFAULT '{}'",
     "UPDATE pg_temp.extension_runtime_binding SET desired_state='enabled'",
     "UPDATE pg_temp.extension_runtime_binding SET desired_state='uninstalled'",'23514'),
    ('snapshot_unaccepted_group_terminal_guard_a0v_083','meta_schedule_run',
     "status text DEFAULT 'running',error_code text,org_id text DEFAULT 'org-org',project_id text DEFAULT 'dev-project',id text DEFAULT 'isolated-trigger-no-run'",
     "UPDATE pg_temp.meta_schedule_run SET status='running'",
     "UPDATE pg_temp.meta_schedule_run SET status='failed',error_code='SOURCE_BUDGET_REJECTED_BEFORE_GROUP_CLAIM'",'55000'),
    ('snapshot_stalled_group_terminal_guard_a0v_091','meta_schedule_run',
     "status text DEFAULT 'running',error_code text,org_id text DEFAULT 'org-org',project_id text DEFAULT 'dev-project',id text DEFAULT 'isolated-trigger-no-run'",
     "UPDATE pg_temp.meta_schedule_run SET status='running'",
     "UPDATE pg_temp.meta_schedule_run SET status='failed',error_code='STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS'",'55000'),
    ('unaccepted_analysis_terminal_guard_a0v_060','automation_occurrence',
     "status text DEFAULT 'needs_attention',org_id text DEFAULT 'org-org',project_id text DEFAULT 'dev-project',occurrence_id uuid DEFAULT gen_random_uuid()",
     "UPDATE pg_temp.automation_occurrence SET status='needs_attention'",
     "UPDATE pg_temp.automation_occurrence SET status='cancelled'",'55000'),
])
def test_a150_original_trigger_execution_preserves_runtime_normal_and_refusal(function_name,table,fields,normal,invalid,error):
    with isolated_owner() as conn:
        assert conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_151'
        original=conn.execute("SELECT pg_get_triggerdef(t.oid) AS definition FROM pg_trigger t "
            "WHERE t.tgrelid=%s::regclass AND t.tgfoid=%s::regprocedure ORDER BY t.oid LIMIT 1",
            ('public.'+table,'public.'+function_name+'()')).fetchone()
        assert original is not None
        # The current migration's actual registered definition is preserved:
        # event kind, column list, timing and deferral; only target is a probe.
        definition=original['definition']
        old_target=' ON public.'+table+' '
        if old_target not in definition:old_target=' ON '+table+' '
        assert old_target in definition
        conn.execute(sql.SQL('CREATE TEMP TABLE {} ({})').format(sql.Identifier(table),sql.SQL(fields)))
        conn.execute(sql.SQL('INSERT INTO pg_temp.{} DEFAULT VALUES').format(sql.Identifier(table)))
        conn.execute(definition.replace(old_target,' ON pg_temp.'+table+' ',1))
        conn.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE ON pg_temp.{} TO aos_runtime').format(sql.Identifier(table)))
        conn.execute('SET LOCAL ROLE aos_runtime')
        assert conn.execute("SELECT has_function_privilege(current_user,%s,'EXECUTE') AS allowed",
                            ('public.'+function_name+'()',)).fetchone()['allowed'] is False
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        if normal is not None:
            conn.execute(normal)
            conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
            assert conn.execute(sql.SQL('SELECT count(*) AS n FROM pg_temp.{}').format(sql.Identifier(table))).fetchone()['n']==1
        with pytest.raises(psycopg.Error) as caught:
            conn.execute(invalid)
            conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
        assert caught.value.sqlstate==error
        conn.rollback()


def test_original_approved_event_sql_full_body_matches_native_refs(approved_command, private_database):
    """Independent S08 computation probe; no SQL approval or publication grant."""
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_action_store import AipActionStore, canonical_hash
    from aos_api.asset_registry.canonical_json import canonical_json
    command = approved_command[-1]
    refs = [command.approval_event, approved_command[2].allocation_approval_ref]
    with connect_capacity_issuer(private_database, SCOPE) as conn:
        for ref in refs:
            row = conn.execute("""WITH original AS (
                SELECT e.*, CASE WHEN expires_at IS NULL THEN NULL ELSE
                  to_char(expires_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS') ||
                  CASE WHEN to_char(expires_at AT TIME ZONE 'UTC','US')='000000' THEN ''
                    ELSE '.' || to_char(expires_at AT TIME ZONE 'UTC','US') END || 'Z' END AS expiry,
                  to_char(created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS') ||
                  CASE WHEN to_char(created_at AT TIME ZONE 'UTC','US')='000000' THEN ''
                    ELSE '.' || to_char(created_at AT TIME ZONE 'UTC','US') END || 'Z' AS created
                FROM public.aip_action_approval_event e
                WHERE org_id=%s AND project_id=%s AND approval_event_id=%s
              ), body AS (
                SELECT proposal_id,jsonb_build_object(
                  'id',approval_event_id,'proposalId',proposal_id,'proposalVersion',proposal_version,
                  'proposalHash',proposal_hash,'decision',decision,
                  'actor',jsonb_build_object('actorType','user','actorId',actor_id),'reason',reason,
                  'expiresAt',expiry,'createdAt',created,'actionBindingHash',action_binding_hash,
                  'approvalPolicyHash',approval_policy_hash,'slotId',slot_id,
                  'eligibilitySnapshotHash',eligibility_snapshot_hash) AS value,
                  to_jsonb(expires_at) AS default_expiry,to_jsonb(created_at) AS default_created
                FROM original
              ) SELECT proposal_id,value,public.canonical_asset_registry_jsonb(value) AS canonical,
                encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(value),'UTF8'),'sha256'),'hex') AS hash,
                encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(
                  value || jsonb_build_object('expiresAt',default_expiry,'createdAt',default_created)),
                  'UTF8'),'sha256'),'hex') AS default_time_hash
              FROM body""", (*SCOPE.key, ref.asset_id)).fetchone()
            assert row is not None
            snapshots = AipActionStore()._bundle(conn, SCOPE, row['proposal_id']).approvals
            snapshot = next(item for item in snapshots if item.id == ref.asset_id)
            expected = snapshot.model_dump(mode='json', by_alias=True)
            assert row['value'] == expected
            assert row['canonical'].encode('utf-8') == canonical_json(expected)
            assert row['hash'] == canonical_hash(expected) == ref.content_hash
            assert row['default_time_hash'] != ref.content_hash
            assert len(expected) == 13
            for field in expected:
                changed = conn.execute("""SELECT encode(public.digest(convert_to(
                    public.canonical_asset_registry_jsonb(%s::jsonb || jsonb_build_object(%s::text,'changed')),
                    'UTF8'),'sha256'),'hex') AS hash""",
                    (row['canonical'], field)).fetchone()
                assert changed['hash'] != ref.content_hash, field


def test_publication_original_event_projection_matches_both_refs(approved_command, private_database):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_APPROVAL_EVENT_PROJECTION_SQL
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_action_store import AipActionStore
    from aos_api.asset_registry.canonical_json import canonical_json
    with connect_capacity_issuer(private_database,SCOPE) as conn:
        for ref in [approved_command[-1].approval_event, approved_command[2].allocation_approval_ref]:
            row = conn.execute(CAPACITY_APPROVAL_EVENT_PROJECTION_SQL,
                dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,approval_event_id=ref.asset_id)).fetchone()
            assert row is not None
            expected = next(item for item in AipActionStore()._bundle(conn,SCOPE,row['proposal_id']).approvals
                            if item.id==ref.asset_id).model_dump(mode='json',by_alias=True)
            assert row['value']==expected and len(row['value'])==13
            assert row['canonical'].encode()==canonical_json(expected)
            assert row['hash']==ref.content_hash
        params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,approval_event_id=approved_command[-1].approval_event.asset_id)
        assert conn.execute(CAPACITY_APPROVAL_EVENT_PROJECTION_SQL,{**params,'org_id':'dev-org'}).fetchone() is None
        assert conn.execute(CAPACITY_APPROVAL_EVENT_PROJECTION_SQL,{**params,'approval_event_id':uuid4().hex}).fetchone() is None
        conn.execute("SET LOCAL TimeZone='Asia/Shanghai'")
        assert conn.execute(CAPACITY_APPROVAL_EVENT_PROJECTION_SQL,params).fetchone() is None


@pytest.mark.parametrize('timestamp_literal', ['infinity','-infinity','10000-01-01 00:00:00+00','0001-01-01 00:00:00+00 BC'])
@pytest.mark.parametrize('field',['created_at','expires_at'])
def test_publication_event_projection_rejects_python_time_domain(approved_command, timestamp_literal, field):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_APPROVAL_EVENT_PROJECTION_SQL
    with isolated_owner() as conn:
        conn.execute("SET LOCAL TimeZone='UTC'")
        conn.execute('CREATE TEMP TABLE approval_projection_probe (LIKE public.aip_action_approval_event INCLUDING ALL)')
        ref=approved_command[-1].approval_event
        params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,approval_event_id=ref.asset_id)
        conn.execute('INSERT INTO approval_projection_probe SELECT * FROM public.aip_action_approval_event '
                     'WHERE org_id=%(org_id)s AND project_id=%(project_id)s AND approval_event_id=%(approval_event_id)s',params)
        statement=CAPACITY_APPROVAL_EVENT_PROJECTION_SQL.replace('FROM public.aip_action_approval_event e','FROM pg_temp.approval_projection_probe e')
        assert conn.execute(statement,params).fetchone() is not None
        conn.execute(sql.SQL('UPDATE pg_temp.approval_projection_probe SET {}=%s::timestamptz').format(sql.Identifier(field)),(timestamp_literal,))
        assert conn.execute(statement,params).fetchone() is None
        conn.rollback()


@pytest.mark.parametrize('microsecond',[0,1,100000,999999])
def test_publication_event_projection_nullable_fields_original_model(approved_command,microsecond):
    from datetime import datetime,UTC
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_APPROVAL_EVENT_PROJECTION_SQL
    from aos_api.asset_registry.canonical_json import canonical_json
    from aos_api.aip_action_store import canonical_hash
    original=approved_command[3].approvals[0]
    timestamp=datetime(2020,1,1,microsecond=microsecond,tzinfo=UTC)
    expected=original.model_copy(update=dict(created_at=timestamp,expires_at=None,action_binding_hash=None,
        approval_policy_hash=None,eligibility_snapshot_hash=None,slot_id=None,reason='')).model_dump(mode='json',by_alias=True)
    with isolated_owner() as conn:
        conn.execute("SET LOCAL TimeZone='UTC'")
        conn.execute('CREATE TEMP TABLE approval_projection_probe (LIKE public.aip_action_approval_event INCLUDING ALL)')
        params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,approval_event_id=original.id)
        conn.execute('INSERT INTO approval_projection_probe SELECT * FROM public.aip_action_approval_event '
                     'WHERE org_id=%(org_id)s AND project_id=%(project_id)s AND approval_event_id=%(approval_event_id)s',params)
        conn.execute("UPDATE pg_temp.approval_projection_probe SET created_at=%s,expires_at=NULL,action_binding_hash=NULL,"
                     "approval_policy_hash=NULL,eligibility_snapshot_hash=NULL,slot_id=NULL,reason=''",(timestamp,))
        conn.execute('SET LOCAL search_path=pg_temp,pg_catalog')
        statement=CAPACITY_APPROVAL_EVENT_PROJECTION_SQL.replace('FROM public.aip_action_approval_event e','FROM pg_temp.approval_projection_probe e')
        row=conn.execute(statement,params).fetchone()
        assert row is not None and row['value']==expected
        assert row['canonical'].encode()==canonical_json(expected) and row['hash']==canonical_hash(expected)
        conn.rollback()
