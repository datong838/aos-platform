"""Original Receipt SQL over twelve PG owners; named boundary follows d4c2."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import psycopg

from test_analysis_snapshot_readiness_twelve_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,
    prepared_case,assessment_case,journal_case,object_case,completed_group,bridge_case,
    business_case,fact_case,evidence_case,query_case,quality_case,business_evidence_case,readiness_case,
)
from aos_api.ecommerce_analysis_snapshot_readiness import AnalysisSnapshotReadiness
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.source_readiness_receipt_store import SourceReadinessReceiptStore


@pytest.fixture
def receipt_case(readiness_case,monkeypatch):
    conn,state,context,call=readiness_case
    schema=context.source._schema
    root=Path(__file__).resolve().parents[2]/'alembic/versions'
    conn.execute('RESET ROLE')
    conn.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public')
    nodes=ast.walk(ast.parse((root/'228asset0_evidence_snapshot.py').read_text()))
    function=next(n.value for n in nodes if isinstance(n,ast.Constant) and isinstance(n.value,str)
        and n.value.strip().startswith('CREATE OR REPLACE FUNCTION canonical_asset_registry_jsonb('))
    conn.execute(function)
    spec=importlib.util.spec_from_file_location('snapshot_readiness_receipt_ddl',root/'ar2_009_source_readiness_receipt.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    def execute(statement):
        statement=statement.replace('public.canonical_asset_registry_jsonb',f'"{schema}".canonical_asset_registry_jsonb')
        statement=statement.replace('search_path=pg_catalog,public',f'search_path=pg_catalog,"{schema}",public')
        return conn.execute(statement)
    module.op=NS(execute=execute);module.upgrade()
    conn.execute('SET ROLE aos_runtime')
    return conn,state,AnalysisSnapshotReadiness(context),call


def test_original_receipt_put_current_read_and_exact_body_replay(receipt_case):
    conn,state,owner,call=receipt_case
    saved=owner.put_current(conn,**call)
    assert saved.receipt_ref.authority=='postgres:source_readiness_receipt'
    assert saved.status=='ready' and saved.investigation.covered_fact_count==12
    assert owner.read_current(conn,reference=saved.receipt_ref,**call)==saved
    original=SourceReadinessReceiptStore(HostTransaction(conn),owner.scope)
    with conn.transaction():
        assert original.put(saved.model_copy(update={'receipt_ref':None}))==saved
    with pytest.raises(psycopg.Error,match='immutable'),conn.transaction():
        conn.execute('RESET ROLE')
        conn.execute("UPDATE source_readiness_receipt SET authority='{}'::jsonb")
    with conn.transaction():
        assert original.read_exact(saved.receipt_ref)==saved
    assert conn.execute('SELECT count(*) AS n FROM source_readiness_receipt').fetchone()['n']==1
    assert state['calls']==1


@pytest.mark.parametrize('fault',['policy','binding','source','canary'])
def test_historical_receipt_needs_current_authority(receipt_case,fault):
    from test_analysis_snapshot_source_evidence_pg import revoke
    conn,state,owner,call=receipt_case
    saved=owner.put_current(conn,**call)
    if fault=='policy':state['readiness_raw']=b'{}'
    elif fault=='binding':state['binding_denied']=True
    elif fault=='source':
        body=owner.context.business._record(conn,call['business_ref'])
        from aos_api.business_investigation_shared_contracts import InvestigationExactRef
        revoke(conn,owner.context.source,InvestigationExactRef.model_validate(body['selection']['evidenceRef']))
    elif fault=='canary':conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    with pytest.raises((ValueError,LookupError,PermissionError)):
        owner.read_current(conn,reference=saved.receipt_ref,**call)


def test_saved_receipt_rolls_back_on_late_dependency_change(receipt_case,monkeypatch):
    conn,state,owner,call=receipt_case
    original=SourceReadinessReceiptStore.put
    def put(self,value):
        result=original(self,value);state['binding_denied']=True;return result
    monkeypatch.setattr(SourceReadinessReceiptStore,'put',put)
    with pytest.raises(ValueError):owner.put_current(conn,**call)
    assert conn.execute('SELECT count(*) AS n FROM source_readiness_receipt').fetchone()['n']==0


@pytest.mark.parametrize('fault',[None,'expired','future','extended','requirement','mapping','counts'])
def test_match_current_retains_stricter_receipt_without_refreshing_it(fault):
    from datetime import timedelta
    from tests.test_source_readiness_investigation_projection import envelope,projection
    from aos_api.ecommerce_analysis_snapshot_readiness import _match_current
    saved=envelope(investigation=projection())
    current=saved.model_copy(deep=True)
    current.checked_at+=timedelta(seconds=1)
    current.investigation.evaluated_at=current.checked_at
    for source in current.sources:
        source.checked_at=current.checked_at
        source.freshness_expires_at+=timedelta(seconds=1)
    current.investigation.freshness_expires_at+=timedelta(seconds=1)
    if fault=='expired':saved.sources[0].freshness_expires_at=current.checked_at
    elif fault=='future':saved.checked_at=current.checked_at+timedelta(seconds=1)
    elif fault=='extended':saved.sources[0].freshness_expires_at=current.sources[0].freshness_expires_at+timedelta(seconds=1)
    elif fault=='requirement':current.investigation.requirement_ref.content_hash='f'*64
    elif fault=='mapping':current.sources[0].mapping_ref.content_hash='e'*64
    elif fault=='counts':current.sources[0].counts.source_total=99
    if fault is None:
        before=saved.model_dump()
        _match_current(saved,current)
        assert saved.model_dump()==before
    else:
        with pytest.raises(ValueError):_match_current(saved,current)


def test_old_receipt_deadline_is_checked_after_consumer():
    from tests.test_source_readiness_investigation_projection import envelope,projection
    from aos_api.ecommerce_analysis_snapshot_readiness import _require_unexpired
    saved=envelope(investigation=projection())
    with pytest.raises(ValueError,match='during consumption'):
        _require_unexpired(saved,saved.sources[0].freshness_expires_at)


def test_requirement_projection_preserves_unmet_fact_failure():
    from test_analysis_snapshot_readiness_context_pg import canonical_assembly
    from aos_api.ecommerce_analysis_snapshot_readiness_context import _assemble
    from aos_api.ecommerce_analysis_snapshot_readiness import _with_requirement
    from tests.test_data_requirement_store import requirement
    from aos_api.data_requirement_store import canonical_revision_content_hash
    from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
    data=canonical_assembly.__wrapped__()
    data['quality'].assessment.reasons=('QUALITY_BELOW_THRESHOLD:Weapp',)
    data['business']['factIds'].remove('Weapp')
    value=_assemble(**data)
    req=requirement().model_copy(update={'required_facts':[s.object_type for s in value.sources]})
    req=req.model_copy(update={'content_hash':canonical_revision_content_hash(req)})
    req=DataRequirementRevisionRecord.model_validate(req.model_dump())
    body=data['business']|{'requirementRef':dict(resourceType='DataRequirementRevision',resourceId=req.requirement_id,revision=req.revision,contentHash=req.content_hash)}
    result=_with_requirement(value,req.model_dump(),body)
    assert result.status=='failed'
    assert result.investigation.covered_fact_count==11
    assert result.investigation.unmet_facts==['Weapp']
    body['requirementRef']['contentHash']='sha256:'+'f'*64
    with pytest.raises(ValueError):_with_requirement(value,req.model_dump(),body)
