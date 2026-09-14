"""Actual immutable Evidence/current Store proof; named analysis/pending doubles."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_analysis_fact_quality_context_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,
    prepared_case,assessment_case,journal_case,object_case,completed_group,bridge_case,business_case,fact_case,
)
from aos_api.ecommerce_analysis_snapshot_source_evidence import AnalysisSnapshotSourceEvidence
from aos_api.ecom_consistency_store import EcomConsistencyError
from test_snapshot_group_projection_owner_pg import mutate_store


@pytest.fixture
def evidence_case(fact_case, completed_group):
    conn,state,pending,facts,call=fact_case
    executor=completed_group[0]
    pending['requirement'].update(requirementId='fixture-requirement',revision=1,contentHash='sha256:'+'1'*64)
    root=Path(__file__).resolve().parents[2]/'alembic/versions'
    conn.execute('RESET ROLE')
    from aos_api.twa_pg import TWA_SCHEMA_SQL
    for statement in TWA_SCHEMA_SQL.split(';'):
        if statement.strip().startswith(('CREATE TABLE IF NOT EXISTS twa_org (','CREATE TABLE IF NOT EXISTS twa_workspace (')):
            conn.execute(statement)
    def migrate(name):
        spec=importlib.util.spec_from_file_location('snapshot_evidence_migration',root/name)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    migrate('aip1_001_task_runtime.py')
    tree=ast.parse((root/'aip4_001_eval_lineage_observability_contract.py').read_text())
    guards=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)
        and n.value.strip().startswith('CREATE FUNCTION guard_aip4_append_only()')]
    assert len(guards)==1
    conn.execute(guards[0].replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1))
    migrate('w4_001_evidence_governance_build.py')
    conn.execute('SET ROLE aos_runtime')
    service=AnalysisSnapshotSourceEvidence(facts.analysis,store=executor._store)
    return conn,state,service,call


def test_full_source_evidence_replay_and_current_readback(evidence_case):
    conn,state,service,call=evidence_case
    ref=service.capture_current(conn,**call)
    assert service.capture_current(conn,**call)==ref
    body=service.run_current(conn,evidence_ref=ref,execute=lambda body:body)
    assert len(body['members'])==2 and len(body['inputManifest']['members'])==2
    assert len(body['projection']['members'])==2 and body['factIds']==[]
    assert 'outputRows' not in str(body)
    assert state['calls']==1 and conn.execute('SELECT count(*) AS n FROM aip_evidence').fetchone()['n']==1


def test_evidence_capture_rolls_back_with_outer_failure(evidence_case):
    conn,_,service,call=evidence_case
    with pytest.raises(RuntimeError,match='after capture'),conn.transaction():
        service.capture_current(conn,**call)
        raise RuntimeError('after capture')
    assert conn.execute('SELECT count(*) AS n FROM aip_evidence').fetchone()['n']==0


def revoke(conn,service,ref):
    scope=service.analysis.scope
    conn.execute('INSERT INTO aip_evidence_revoke_event(org_id,project_id,event_id,evidence_id,revision,content_hash,reason,actor) VALUES(%s,%s,%s,%s,1,%s,%s,%s)',
        (*scope.key,'test-revoke',ref.resource_id,ref.content_hash[7:],'test revoke',service.analysis.source.actor))


@pytest.mark.parametrize('during',[False,True])
def test_revocation_is_current_and_not_replaced(evidence_case,during):
    conn,_,service,call=evidence_case;ref=service.capture_current(conn,**call)
    if not during:revoke(conn,service,ref)
    with pytest.raises(ValueError):
        service.run_current(conn,evidence_ref=ref,execute=lambda body:revoke(conn,service,ref) if during else pytest.fail('revoked'))
    if not during:
        with pytest.raises(ValueError):service.capture_current(conn,**call)


def test_canary_cannot_read_positive_tenant_evidence(evidence_case):
    conn,_,service,call=evidence_case;ref=service.capture_current(conn,**call)
    with conn.transaction():
        conn.execute("SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)")
        with pytest.raises((LookupError,PermissionError)):
            service.run_current(conn,evidence_ref=ref,execute=lambda body:pytest.fail('canary read'))


@pytest.mark.parametrize('fault',['policy','body','deferred'])
def test_saved_evidence_still_needs_current_unchanged_consumption(evidence_case,fault):
    conn,state,service,call=evidence_case;ref=service.capture_current(conn,**call)
    if fault=='policy':state['field_raw']=b'{}'
    def consume(body):
        if fault=='body':body['factIds']=['Order']
        if fault=='deferred':return (item for item in [body])
    with pytest.raises(ValueError):service.run_current(conn,evidence_ref=ref,execute=consume)


def test_evidence_does_not_hide_superseded_canonical_objects(evidence_case):
    conn,_,service,call=evidence_case;ref=service.capture_current(conn,**call)
    mutate_store(SimpleNamespace(_store=service._projections._store),service.analysis.scope,
        "UPDATE ecom_object SET payload_hash=repeat('0',64)")
    with pytest.raises(EcomConsistencyError):
        service.run_current(conn,evidence_ref=ref,execute=lambda body:pytest.fail('stale canonical objects'))


def test_policy_drift_after_insert_rolls_back_evidence(evidence_case,monkeypatch):
    conn,state,service,call=evidence_case
    original=service._persist
    def persist_then_drift(db,body):
        result=original(db,body);state['field_raw']=b'{}';return result
    monkeypatch.setattr(service,'_persist',persist_then_drift)
    with pytest.raises(ValueError):service.capture_current(conn,**call)
    assert conn.execute('SELECT count(*) AS n FROM aip_evidence').fetchone()['n']==0


def test_envelope_capacity_preserves_892_entries_and_rejects_oversize():
    """Serialization limit only, deliberately not an 892-row authenticated Store run."""
    from aos_api.ecommerce_analysis_snapshot_source_evidence import _digest
    body={'entries':[{'event':str(i),'hash':'1'*64} for i in range(892)]}
    assert _digest(body).startswith('sha256:') and len(body['entries'])==892
    body['oversize']='x'*2_000_001
    with pytest.raises(ValueError,match='truncation forbidden'):_digest(body)
    assert len(body['entries'])==892
