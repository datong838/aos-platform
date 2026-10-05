"""Source approval and original withdrawal must be ordered by actual database locks."""
from contextlib import contextmanager
from threading import Event,Thread
import time
from uuid import uuid4

import pytest

from tests.aip.test_provider_capacity_source_action_pg import source_inputs,source_proposal
from tests.aip.test_provider_capacity_action_pg import drafted
from tests.aip.test_provider_capacity_request_pg import original_inputs,SCOPE


def test_source_reader_first_orders_original_revoke_after_approval(source_proposal,monkeypatch):
    from aos_api.db import connect
    from aos_api.aip_provider_capacity_source_action import decide_provider_capacity_source
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from tests.aip.test_evidence_bundle_provenance_pg import ACTOR
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    _,checker,candidate,_,proposal,decision=source_proposal
    with connect(SCOPE) as conn:
        evidence=conn.execute('SELECT request_json FROM aip_provider_capacity_candidate WHERE candidate_id=%s',
            (candidate.basis_ref.asset_id,)).fetchone()['request_json']['candidate']['evidenceRef']
    paused,release,writer_started,writer_done=Event(),Event(),Event(),Event()
    results={};count=0
    original=ProviderCapacityCandidateStore._evidence

    def pause_after_reads(conn,scope,ref):
        nonlocal count
        original(conn,scope,ref);count+=1
        if count==2:
            paused.set()
            if not release.wait(8):raise RuntimeError('reader timing timeout')
    monkeypatch.setattr(ProviderCapacityCandidateStore,'_evidence',staticmethod(pause_after_reads))

    @contextmanager
    def reader_connect(scope):
        with connect(scope) as conn:
            results['reader_pid']=conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            yield conn

    @contextmanager
    def writer_connect(scope):
        with connect(scope) as conn:
            results['writer_pid']=conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            writer_started.set();yield conn

    def reader():
        try:results['approval']=decide_provider_capacity_source(checker,proposal.proposal.id,'ordered-source-'+uuid4().hex,decision,connect_factory=reader_connect)
        except BaseException as exc:results['reader_error']=exc

    def writer():
        try:results['withdrawal']=AipProductionContractStore(connect_factory=writer_connect).revoke_evidence_bundle(
            SCOPE,ACTOR,evidence['assetId'],'concurrent-source-revoke-'+uuid4().hex,
            RevokeEvidenceBundleRequest(expectedRevision=evidence['revision'],expectedContentHash=evidence['contentHash'],reason='isolated concurrent Source withdrawal'))
        except BaseException as exc:results['writer_error']=exc
        finally:writer_done.set()

    rt=Thread(target=reader);wt=Thread(target=writer)
    rt.start()
    try:
        assert paused.wait(8),results
        wt.start();assert writer_started.wait(8)
        deadline=time.monotonic()+4;observed_lock=None
        while time.monotonic()<deadline and not writer_done.is_set():
            with isolated_owner() as conn:
                row=conn.execute('SELECT wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE pid=%s',
                    (results['writer_pid'],)).fetchone()
            if row and row['wait_event_type']=='Lock':observed_lock=dict(row);break
            time.sleep(.02)
        was_ordered=observed_lock is not None and results['reader_pid'] in observed_lock['blockers'] and not writer_done.is_set()
    finally:
        release.set();rt.join(10)
        if wt.ident is not None:wt.join(10)
    assert not rt.is_alive() and not wt.is_alive()
    assert 'reader_error' not in results and 'writer_error' not in results,results
    assert results['approval'].proposal.status.value=='approved'
    assert results['withdrawal'].revoked is True
    assert was_ordered, 'actual withdrawal committed while reader paused; reader subsequently committed approved event'


def evidence_ref(candidate):
    from aos_api.db import connect
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    with connect(SCOPE) as conn:
        return FormalExactRef.model_validate(conn.execute('SELECT request_json FROM aip_provider_capacity_candidate WHERE candidate_id=%s',
            (candidate.basis_ref.asset_id,)).fetchone()['request_json']['candidate']['evidenceRef'])


def epoch(ref,scope=SCOPE):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    with isolated_owner() as conn:
        row=conn.execute('SELECT epoch FROM public.aip_capacity_evidence_epoch WHERE org_id=%s AND project_id=%s AND bundle_id=%s',
            (*scope.key,ref.asset_id)).fetchone()
        return None if row is None else row['epoch']


def test_original_withdrawal_committed_after_serial_snapshot_denies_source_approval(source_proposal):
    from aos_api.db import connect,connect_serializable
    from aos_api.aip_provider_capacity_source_action import decide_provider_capacity_source,ProviderCapacitySourceActionBlocked
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from tests.aip.test_evidence_bundle_provenance_pg import ACTOR
    _,checker,candidate,_,proposal,decision=source_proposal
    ref=evidence_ref(candidate)
    with connect(SCOPE) as conn:before=conn.execute('SELECT count(*) AS n FROM aip_action_approval_event').fetchone()['n']
    with connect_serializable(SCOPE) as conn:
        conn.execute('SELECT clock_timestamp() AS established_snapshot').fetchone()
        AipProductionContractStore().revoke_evidence_bundle(SCOPE,ACTOR,ref.asset_id,'writer-first-'+uuid4().hex,
            RevokeEvidenceBundleRequest(expectedRevision=ref.revision,expectedContentHash=ref.content_hash,reason='isolated post-snapshot withdrawal'))
        @contextmanager
        def same_connection(scope):
            assert scope==SCOPE
            yield conn
        with pytest.raises(ProviderCapacitySourceActionBlocked):
            decide_provider_capacity_source(checker,proposal.proposal.id,'stale-snapshot-'+uuid4().hex,decision,connect_factory=same_connection)
        conn.rollback()
    with connect(SCOPE) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_action_approval_event').fetchone()['n']==before
        assert conn.execute('SELECT status FROM aip_action_proposal WHERE proposal_id=%s',(proposal.proposal.id,)).fetchone()['status']=='drafted'
    assert epoch(ref)==1


def test_direct_sql_rollback_duplicate_and_original_replay_do_not_invent_epoch(source_inputs):
    from aos_api.db import connect
    from aos_api.aip_provider_capacity_evidence_fence import lock_capacity_evidence_refs
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from tests.aip.test_evidence_bundle_provenance_pg import ACTOR
    _,_,candidate,_=source_inputs
    ref=evidence_ref(candidate)
    with connect(SCOPE) as conn:
        assert lock_capacity_evidence_refs(conn,SCOPE,[ref])[ref.asset_id]==0
        conn.commit()
    event_id='epoch-revoke-'+uuid4().hex
    sql="INSERT INTO aip_evidence_bundle_revoke_event(org_id,project_id,event_id,bundle_id,revision,content_hash,reason,actor) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING"
    params=(*SCOPE.key,event_id,ref.asset_id,ref.revision,ref.content_hash,'isolated epoch test',ACTOR)
    with connect(SCOPE) as conn:
        conn.execute(sql,params);conn.rollback()
    assert epoch(ref)==0
    with connect(SCOPE) as conn:
        conn.execute(sql,params);conn.commit()
    assert epoch(ref)==1
    with connect(SCOPE) as conn:
        conn.execute(sql,params);conn.commit()
    assert epoch(ref)==1
    body=RevokeEvidenceBundleRequest(expectedRevision=ref.revision,expectedContentHash=ref.content_hash,reason='existing SQL withdrawal')
    key='epoch-original-replay-'+uuid4().hex;store=AipProductionContractStore()
    assert store.revoke_evidence_bundle(SCOPE,ACTOR,ref.asset_id,key,body).revoked
    assert store.revoke_evidence_bundle(SCOPE,ACTOR,ref.asset_id,key,body).revoked
    assert epoch(ref)==1


@pytest.mark.parametrize('fault',['table_acl','column_acl','function_acl','function_body','trigger','owner_flags','owner_membership','owner_extra_acl'])
def test_actual_boundary_drift_is_rejected_without_new_approval(source_proposal,fault):
    from aos_api.aip_provider_capacity_source_action import decide_provider_capacity_source,ProviderCapacitySourceActionBlocked
    from aos_api.db import connect
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    _,checker,_,_,proposal,decision=source_proposal
    function='public.aos_capacity_evidence_epoch_lock(text,text,text)'
    with connect(SCOPE) as conn:before=conn.execute('SELECT count(*) AS n FROM aip_action_approval_event').fetchone()['n']
    with isolated_owner() as conn:
        original=None
        if fault=='table_acl':conn.execute('GRANT SELECT ON public.aip_capacity_evidence_epoch TO aos_runtime')
        elif fault=='column_acl':conn.execute('GRANT UPDATE(epoch) ON public.aip_capacity_evidence_epoch TO aos_runtime')
        elif fault=='function_acl':conn.execute(f'GRANT EXECUTE ON FUNCTION {function} TO PUBLIC')
        elif fault=='function_body':
            original=conn.execute('SELECT pg_get_functiondef(%s::regprocedure) AS definition',(function,)).fetchone()['definition']
            conn.execute('CREATE OR REPLACE FUNCTION public.aos_capacity_evidence_epoch_lock(p_org text,p_project text,p_id text) RETURNS bigint '
                'LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$ BEGIN RETURN 0; END $$')
        elif fault=='trigger':conn.execute('ALTER TABLE public.aip_evidence_bundle_revoke_event DISABLE TRIGGER capacity_evidence_epoch_touch_a0v149')
        elif fault=='owner_flags':conn.execute('ALTER ROLE aos_capacity_evidence_epoch_owner LOGIN')
        elif fault=='owner_membership':conn.execute('GRANT aos_capacity_evidence_epoch_owner TO aos_runtime')
        else:conn.execute('GRANT SELECT ON public.meta_membership TO aos_capacity_evidence_epoch_owner')
    try:
        with pytest.raises(ProviderCapacitySourceActionBlocked):
            decide_provider_capacity_source(checker,proposal.proposal.id,'epoch-drift-'+uuid4().hex,decision)
        with connect(SCOPE) as conn:assert conn.execute('SELECT count(*) AS n FROM aip_action_approval_event').fetchone()['n']==before
    finally:
        with isolated_owner() as conn:
            if fault=='table_acl':conn.execute('REVOKE SELECT ON public.aip_capacity_evidence_epoch FROM aos_runtime')
            elif fault=='column_acl':conn.execute('REVOKE UPDATE(epoch) ON public.aip_capacity_evidence_epoch FROM aos_runtime')
            elif fault=='function_acl':conn.execute(f'REVOKE EXECUTE ON FUNCTION {function} FROM PUBLIC')
            elif fault=='function_body':conn.execute(original)
            elif fault=='trigger':conn.execute('ALTER TABLE public.aip_evidence_bundle_revoke_event ENABLE TRIGGER capacity_evidence_epoch_touch_a0v149')
            elif fault=='owner_flags':conn.execute('ALTER ROLE aos_capacity_evidence_epoch_owner NOLOGIN')
            elif fault=='owner_membership':conn.execute('REVOKE aos_capacity_evidence_epoch_owner FROM aos_runtime')
            else:conn.execute('REVOKE SELECT ON public.meta_membership FROM aos_capacity_evidence_epoch_owner')


def test_runtime_table_writes_and_source_canary_reader_are_denied(source_inputs):
    import psycopg
    from aos_api.db import connect
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_provider_capacity_evidence_fence import lock_capacity_evidence_refs,CapacityEvidenceFenceBlocked
    ref=evidence_ref(source_inputs[2])
    for sql in ('SELECT * FROM public.aip_capacity_evidence_epoch','DELETE FROM public.aip_capacity_evidence_epoch',
        'UPDATE public.aip_capacity_evidence_epoch SET epoch=0','TRUNCATE public.aip_capacity_evidence_epoch'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connect(SCOPE) as conn:conn.execute(sql)
    with connect(TenantScope('dev-org','dev-project')) as conn:
        with pytest.raises(CapacityEvidenceFenceBlocked):lock_capacity_evidence_refs(conn,TenantScope('dev-org','dev-project'),[ref])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute('SELECT public.aos_capacity_evidence_epoch_lock(%s,%s,%s)',
            ('dev-org','dev-project',ref.asset_id))


def test_simultaneous_first_readers_keep_one_epoch_and_fail_closed_on_serial_conflict(original_inputs):
    from threading import Barrier
    import psycopg
    from aos_api.db import connect_serializable
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_provider_capacity_evidence_fence import lock_capacity_evidence_refs,CapacityEvidenceFenceBlocked
    evidence=original_inputs[2]
    ref=FormalExactRef.model_validate(dict(assetType='EvidenceBundleRevision',assetId=evidence.bundle_id,
        revision=evidence.revision,contentHash=evidence.content_hash))
    assert epoch(ref) is None
    barrier=Barrier(2);success=[];errors=[]
    def reader():
        try:
            with connect_serializable(SCOPE) as conn:
                conn.execute('SELECT clock_timestamp() AS established_snapshot').fetchone()
                barrier.wait(6)
                value=lock_capacity_evidence_refs(conn,SCOPE,[ref])[ref.asset_id]
                conn.commit();success.append(value)
        except BaseException as exc:errors.append(exc)
    threads=[Thread(target=reader),Thread(target=reader)]
    for thread in threads:thread.start()
    for thread in threads:thread.join(10)
    assert not any(thread.is_alive() for thread in threads)
    assert success==[0] and len(errors)==1, (success,[type(e).__name__ for e in errors])
    assert isinstance(errors[0],CapacityEvidenceFenceBlocked)
    assert isinstance(errors[0].__cause__,psycopg.errors.SerializationFailure)
    assert epoch(ref)==0


def test_nonpositive_tenant_original_revoke_and_sql_insert_remain_supported(monkeypatch):
    from aos_api.db import connect
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from tests.aip import test_evidence_bundle_provenance_pg as original
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    scope=TenantScope('org-epoch-ordinary-'+uuid4().hex,'dev-project')
    with isolated_owner() as conn:
        conn.execute('INSERT INTO twa_org(id,name) VALUES(%s,%s)',(scope.org_id,'test-only ordinary tenant'))
        conn.execute('INSERT INTO twa_workspace(org_id,project_id,name) VALUES(%s,%s,%s)',(*scope.key,'test-only'))
    monkeypatch.setattr(original,'SCOPE',scope)
    store,key,body=original.build_inputs.__wrapped__()
    first=store.build_evidence_bundle(scope,original.ACTOR,key,body)
    second=store.build_evidence_bundle(scope,original.ACTOR,key+'.second',body)
    request=RevokeEvidenceBundleRequest(expectedRevision=first.revision,expectedContentHash=first.content_hash,reason='ordinary tenant withdrawal')
    assert store.revoke_evidence_bundle(scope,original.ACTOR,first.bundle_id,key+'.revoke',request).revoked
    with connect(scope) as conn:
        conn.execute('INSERT INTO aip_evidence_bundle_revoke_event(org_id,project_id,event_id,bundle_id,revision,content_hash,reason,actor) '
            'VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(*scope.key,'ordinary-epoch-'+uuid4().hex,second.bundle_id,second.revision,
                second.content_hash,'ordinary SQL withdrawal',original.ACTOR))
        conn.commit()
    for bundle in (first,second):
        ref=FormalExactRef.model_validate(dict(assetType='EvidenceBundleRevision',assetId=bundle.bundle_id,revision=bundle.revision,contentHash=bundle.content_hash))
        assert epoch(ref,scope)==1
        assert store.get_evidence_bundle(scope,bundle.bundle_id,bundle.revision).revoked


def test_native_autocommit_cannot_claim_epoch_held_through_caller_commit(source_inputs):
    from aos_api.db import connect
    from aos_api.aip_provider_capacity_evidence_fence import lock_capacity_evidence_refs,CapacityEvidenceFenceBlocked
    ref=evidence_ref(source_inputs[2])
    with connect(SCOPE) as conn:
        conn.rollback();conn.autocommit=True
        conn.execute('SET ROLE aos_runtime')
        conn.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)",SCOPE.key)
        assert conn.autocommit is True
        assert conn.execute('SELECT current_user AS role').fetchone()['role']=='aos_runtime'
        with pytest.raises(CapacityEvidenceFenceBlocked):lock_capacity_evidence_refs(conn,SCOPE,[ref])


def test_epoch_rls_policy_drift_is_not_hidden_by_force_rls_flag(source_inputs):
    from aos_api.db import connect
    from aos_api.aip_provider_capacity_evidence_fence import lock_capacity_evidence_refs,CapacityEvidenceFenceBlocked
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    ref=evidence_ref(source_inputs[2])
    with isolated_owner() as conn:conn.execute('ALTER POLICY capacity_evidence_epoch_scope ON public.aip_capacity_evidence_epoch USING(true)')
    try:
        with connect(SCOPE) as conn:
            with pytest.raises(CapacityEvidenceFenceBlocked):lock_capacity_evidence_refs(conn,SCOPE,[ref])
    finally:
        with isolated_owner() as conn:conn.execute("ALTER POLICY capacity_evidence_epoch_scope ON public.aip_capacity_evidence_epoch "
            "USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))")


@pytest.mark.parametrize('mode',['idle','repeatable_read','read_only'])
def test_native_unsupported_caller_transaction_is_denied(source_inputs,mode):
    from psycopg import IsolationLevel
    from aos_api.db import connect
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.aip_provider_capacity_evidence_fence import lock_capacity_evidence_refs,CapacityEvidenceFenceBlocked
    ref=evidence_ref(source_inputs[2])
    with connect(SCOPE) as conn:
        conn.rollback()
        if mode=='repeatable_read':conn.isolation_level=IsolationLevel.REPEATABLE_READ
        elif mode=='read_only':conn.read_only=True
        if mode!='idle':apply_asset_transaction_scope(conn,org_id=SCOPE.org_id,project_id=SCOPE.project_id)
        with pytest.raises(CapacityEvidenceFenceBlocked):lock_capacity_evidence_refs(conn,SCOPE,[ref])


def test_first_writer_epoch_initialization_after_serial_snapshot_is_not_invisible(original_inputs):
    from aos_api.db import connect,connect_serializable
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_provider_capacity_evidence_fence import lock_capacity_evidence_refs,CapacityEvidenceFenceBlocked
    from tests.aip.test_evidence_bundle_provenance_pg import ACTOR
    evidence=original_inputs[2]
    ref=FormalExactRef.model_validate(dict(assetType='EvidenceBundleRevision',assetId=evidence.bundle_id,
        revision=evidence.revision,contentHash=evidence.content_hash))
    assert epoch(ref) is None
    with connect_serializable(SCOPE) as reader:
        reader.execute('SELECT clock_timestamp() AS established_snapshot').fetchone()
        with connect(SCOPE) as writer:
            writer.execute('INSERT INTO aip_evidence_bundle_revoke_event(org_id,project_id,event_id,bundle_id,revision,content_hash,reason,actor) '
                'VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(*SCOPE.key,'first-writer-'+uuid4().hex,ref.asset_id,ref.revision,
                    ref.content_hash,'first epoch initialization',ACTOR))
            writer.commit()
        with pytest.raises(CapacityEvidenceFenceBlocked):lock_capacity_evidence_refs(reader,SCOPE,[ref])
        reader.rollback()
    assert epoch(ref)==1


def test_reader_epoch_initialization_rolls_back_with_caller(original_inputs):
    from aos_api.db import connect
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_provider_capacity_evidence_fence import lock_capacity_evidence_refs
    evidence=original_inputs[2]
    ref=FormalExactRef.model_validate(dict(assetType='EvidenceBundleRevision',assetId=evidence.bundle_id,
        revision=evidence.revision,contentHash=evidence.content_hash))
    assert epoch(ref) is None
    with connect(SCOPE) as conn:
        assert lock_capacity_evidence_refs(conn,SCOPE,[ref])[ref.asset_id]==0
        conn.rollback()
    assert epoch(ref) is None


def test_source_review_locks_distinct_old_request_account_and_basis_evidence(source_inputs):
    from aos_api.db import connect
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate,ProviderCapacityBasisCandidate
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore
    from aos_api.aip_provider_capacity_source_action import propose_provider_capacity_source
    from aos_api.aip_provider_capacity_evidence_fence import lock_capacity_evidence_refs
    from tests.aip import test_evidence_bundle_provenance_pg as original
    maker,_,candidate,_=source_inputs
    old_ref=evidence_ref(candidate)
    with connect(SCOPE) as conn:
        account=ProviderPhysicalAccountCandidate.model_validate(conn.execute('SELECT request_json FROM aip_provider_capacity_candidate WHERE candidate_id=%s',
            (candidate.physical_account_ref.asset_id,)).fetchone()['request_json']['candidate'])
        basis=ProviderCapacityBasisCandidate.model_validate(conn.execute('SELECT request_json FROM aip_provider_capacity_candidate WHERE candidate_id=%s',
            (candidate.basis_ref.asset_id,)).fetchone()['request_json']['candidate'])
    refs=[]
    for _ in range(2):
        store,key,body=original.build_inputs.__wrapped__()
        bundle=store.build_evidence_bundle(SCOPE,original.ACTOR,key,body)
        refs.append(FormalExactRef.model_validate(dict(assetType='EvidenceBundleRevision',assetId=bundle.bundle_id,
            revision=bundle.revision,contentHash=bundle.content_hash)))
    store=ProviderCapacityCandidateStore()
    account=account.model_copy(update={'evidence_ref':refs[0]})
    row=store.create_account(SCOPE,maker,'distinct-account-'+uuid4().hex,account)
    account_ref=candidate.physical_account_ref.model_copy(update={'asset_id':row['candidate_id'],'content_hash':row['content_hash']})
    basis=basis.model_copy(update={'physical_account_ref':account_ref,'evidence_ref':refs[1]})
    row=store.create_basis(SCOPE,maker,'distinct-basis-'+uuid4().hex,basis)
    candidate=candidate.model_copy(update={'physical_account_ref':account_ref,
        'basis_ref':candidate.basis_ref.model_copy(update={'asset_id':row['candidate_id'],'content_hash':row['content_hash']})})
    assert len({ref.asset_id for ref in [old_ref,*refs]})==3
    assert all(epoch(ref) is None for ref in [old_ref,*refs])
    proposal=propose_provider_capacity_source(maker,candidate,'three-epochs-'+uuid4().hex,candidate.valid_until)
    assert proposal.proposal.policy_snapshot['executionAllowed'] is False
    assert all(epoch(ref)==0 for ref in [old_ref,*refs])
    with connect(SCOPE) as conn:
        locked=lock_capacity_evidence_refs(conn,SCOPE,[refs[1],old_ref,refs[0],refs[1]])
        assert list(locked)==sorted({ref.asset_id for ref in [old_ref,*refs]})
        conn.rollback()
