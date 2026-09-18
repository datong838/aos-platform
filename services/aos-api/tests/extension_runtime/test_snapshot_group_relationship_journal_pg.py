"""Immutable relationship journal with original PG inputs and explicit asset fixtures."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import psycopg
from psycopg.types.json import Jsonb
import pytest
from test_lifecycle_pg import database,pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from test_snapshot_group_assessment_owner_pg import assessment_case
from aos_api.pipeline_snapshot_group_assessment_owner import (
    CurrentSnapshotGroupAssessmentMaterial,assessment_payload,
)
from aos_api.pipeline_snapshot_group_relationship_journal import PipelineSnapshotGroupRelationshipJournal
from aos_api.source_read_observation import observed_rows_hash

@pytest.fixture
def journal_case(assessment_case):
    executor,conn,args,state,owner,ref=assessment_case
    conn.execute('RESET ROLE')
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_046_snapshot_group_relationships.py'
    spec=importlib.util.spec_from_file_location('group_relationship_schema',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module.upgrade();conn.execute('SET ROLE aos_runtime')
    executor.prepare(**args)
    return conn,args|{'policy_ref':ref},state,PipelineSnapshotGroupRelationshipJournal(claims=executor._claims),executor


def test_original_preparation_commit_and_exact_replay(journal_case):
    conn,args,state,journal,_=journal_case
    with conn.transaction():first=journal.prepare(conn,**args)
    with conn.transaction():again=journal.prepare(conn,**args)
    with conn.transaction():read=journal.read_current(conn,**args)
    assert first.created and not again.created and read==again
    assert first.payload==again.payload and first.assessment_hash==again.assessment_hash
    assert len(first.payload['candidateLinks'])==1 and state['calls']==1
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_relationship').fetchone()['n']==1


def test_missing_preparation_read_never_creates(journal_case):
    conn,args,state,journal,_=journal_case
    with pytest.raises(LookupError),conn.transaction():journal.read_current(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_relationship').fetchone()['n']==0
    assert state['calls']==1


def test_outer_rollback_and_retry_do_not_read_source(journal_case):
    conn,args,state,journal,_=journal_case
    with pytest.raises(RuntimeError,match='rollback'),conn.transaction():
        journal.prepare(conn,**args);raise RuntimeError('rollback')
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_relationship').fetchone()['n']==0
    with conn.transaction():assert journal.prepare(conn,**args).created
    assert state['calls']==1


def test_caught_post_save_denial_cannot_commit_preparation(journal_case):
    conn,args,state,journal,executor=journal_case;calls=0
    def denied_after_save(*a,**kw):
        nonlocal calls
        calls+=1
        if calls==2:raise PermissionError('fixture policy revoked after insert')
    executor._claims._controls._selections._release_policy.evaluate=denied_after_save
    with conn.transaction():
        with pytest.raises(PermissionError):journal.prepare(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_relationship').fetchone()['n']==0
    assert state['calls']==1


def test_history_is_immutable_and_tenant_isolated(journal_case):
    conn,args,_,journal,_=journal_case
    with conn.transaction():journal.prepare(conn,**args)
    for statement in ('UPDATE pipeline_snapshot_group_relationship SET policy_hash=policy_hash','DELETE FROM pipeline_snapshot_group_relationship','TRUNCATE pipeline_snapshot_group_relationship'):
        with pytest.raises(psycopg.Error),conn.transaction():conn.execute(statement)
    with conn.transaction():
        conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_relationship').fetchone()['n']==0
    conn.execute('RESET ROLE')
    with pytest.raises(psycopg.Error),conn.transaction():conn.execute('UPDATE pipeline_snapshot_group_relationship SET policy_hash=policy_hash')
    conn.execute('SET ROLE aos_runtime')

@pytest.mark.parametrize('fault',['manifest','tenant','group','claim','time','policy','extra','deleted_link','boolean_count'])
def test_database_rejects_unbound_or_invalid_assessment(journal_case,fault):
    conn,args,_,journal,_=journal_case
    with conn.transaction():current=journal._assessments.run_current(conn,**args,execute=lambda v:v)
    body=deepcopy(assessment_payload(current));manifest=current.input.manifest_hash;policy_hash=current.assessment.policy_hash
    if fault=='manifest':manifest=body['inputManifestHash']='sha256:'+'f'*64
    elif fault=='tenant':body['tenant']['orgId']='other'
    elif fault=='group':body['groupId']='00000000-0000-4000-8000-000000000000'
    elif fault=='claim':body['claimRequestHash']='sha256:'+'f'*64
    elif fault=='time':body['readStartedAt']='2000-01-01T00:00:00+00:00'
    elif fault=='policy':body['policyHash']='sha256:'+'f'*64
    elif fault=='extra':body['extra']='not allowed'
    elif fault=='deleted_link':body['candidateLinks'][0]['is_deleted']=True
    else:body['counts']['Shop.hasWeapp']['matched']=True
    with pytest.raises(psycopg.Error),conn.transaction():
        conn.execute('INSERT INTO pipeline_snapshot_group_relationship(org_id,project_id,group_id,input_manifest_hash,policy_ref,policy_hash,assessment_hash,assessment) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
            (*args['scope'].key,args['group_id'],manifest,Jsonb(body['policyRef']),policy_hash,observed_rows_hash([body]),Jsonb(body)))
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_relationship').fetchone()['n']==0


def test_shape_valid_but_false_counts_cannot_be_consumed_as_current(journal_case):
    from aos_api.ec_ingress_journal import IngressJournalConflict
    conn,args,state,journal,_=journal_case
    with conn.transaction():current=journal._assessments.run_current(conn,**args,execute=lambda v:v)
    body=deepcopy(assessment_payload(current));body['counts']['Shop.hasWeapp']['missingParent']=2
    # Schema cannot recompute business truth. The current Owner must do so.
    with conn.transaction():
        conn.execute('INSERT INTO pipeline_snapshot_group_relationship(org_id,project_id,group_id,input_manifest_hash,policy_ref,policy_hash,assessment_hash,assessment) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
            (*args['scope'].key,args['group_id'],current.input.manifest_hash,Jsonb(body['policyRef']),body['policyHash'],observed_rows_hash([body]),Jsonb(body)))
    with pytest.raises(IngressJournalConflict,match='RELATIONSHIP_PREPARATION_DRIFT'),conn.transaction():journal.read_current(conn,**args)
    assert state['calls']==1


def test_saved_recovery_persists_outside_assessment_without_recomputing(journal_case,monkeypatch):
    conn,args,_,journal,executor=journal_case
    with conn.transaction():
        current=journal._assessments.run_current(conn,**args,execute=lambda value:value)
        policy=journal._assessments._policies._load(conn,args['scope'],current.input.group,current.policy_ref)
    material=CurrentSnapshotGroupAssessmentMaterial(current.input,current.policy_ref,policy)
    monkeypatch.setattr(executor._claims,'_recovery',object())
    monkeypatch.setattr(journal._assessments,'materialize_current',lambda *a,**kw:material)
    monkeypatch.setattr(journal._assessments,'assess_materialized',
        lambda value:pytest.fail('assessment must remain outside persistence transaction'))
    with conn.transaction():saved=journal.prepare_assessed_current(conn,current,**args)
    assert saved.created and saved.assessment_hash==current.content_hash


def test_saved_recovery_rejects_material_drift_before_persistence(journal_case,monkeypatch):
    from aos_api.ec_ingress_journal import IngressJournalConflict
    conn,args,_,journal,executor=journal_case
    with conn.transaction():
        current=journal._assessments.run_current(conn,**args,execute=lambda value:value)
        policy=journal._assessments._policies._load(conn,args['scope'],current.input.group,current.policy_ref)
    changed=replace(current.input,manifest_hash='sha256:'+'f'*64)
    monkeypatch.setattr(executor._claims,'_recovery',object())
    monkeypatch.setattr(journal._assessments,'materialize_current',lambda *a,**kw:
        CurrentSnapshotGroupAssessmentMaterial(changed,current.policy_ref,policy))
    with pytest.raises(IngressJournalConflict,match='MATERIAL_CHANGED'),conn.transaction():
        journal.prepare_assessed_current(conn,current,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_relationship').fetchone()['n']==0
