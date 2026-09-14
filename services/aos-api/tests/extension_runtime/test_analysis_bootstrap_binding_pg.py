"""Current source/compile/preview binding in real isolated storage; source fixtures remain."""
import pytest
from uuid import uuid4
from test_analysis_startup_preview_pg import (
    preview_case,preview,compilation_case,publications,context_publication,context_case,startup_case,
    analysis_case,consumer_case,host_case,control_governed,governed,service_case,stored,pair,body,
)


def bound(data,prepared,execute=lambda value:value):
    from aos_api.ecommerce_analysis_bootstrap_authority import AnalysisBootstrapCurrentBinding
    conn,analysis,claimed,_,_=data
    return AnalysisBootstrapCurrentBinding(analysis).run_current(conn,claimed=claimed,
        intent=prepared['bootstrapIntent'],preview_ref=prepared['startupPreviewRef'],execute=execute)


def test_bootstrap_binding_reads_actual_lineage(preview_case):
    result=preview(preview_case,execute=lambda prepared:bound(preview_case,prepared))
    assert result['task']['task_id']==result['intent']['compilationReceipt']['taskId']
    assert result['plan']['approval_status']=='draft'


@pytest.mark.parametrize('fault',['control-ref','plan','evidence','parent-review'])
def test_bootstrap_binding_rejects_current_drift(preview_case,fault):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    conn,analysis,_,_,_=preview_case
    def prepared(value):
        if fault=='control-ref':
            value['bootstrapIntent']['sourceControlReceiptRef']['contentHash']='sha256:'+'a'*64
            value['bootstrapIntent']['contentHash']=canonical_sha256({k:v for k,v in value['bootstrapIntent'].items() if k!='contentHash'})
        def mutate(current):
            if fault=='plan':conn.execute("UPDATE aip_plan_revision SET approval_status='approved' WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s",(*analysis.scope.key,current['plan']['plan_revision_id']))
            elif fault=='evidence':conn.execute("""INSERT INTO aip_evidence_revoke_event
                (org_id,project_id,event_id,evidence_id,revision,content_hash,reason,actor)
                VALUES(%s,%s,%s,%s,1,%s,'fixture revoke','fixture')""",
                (*analysis.scope.key,uuid4().hex,current['evidence']['evidence_id'],current['evidence']['content_hash']))
            elif fault=='parent-review':
                conn.execute('RESET ROLE')
                conn.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'")
                conn.execute('SET LOCAL ROLE aos_runtime')
            return current
        return bound(preview_case,value,execute=mutate)
    with pytest.raises((ValueError,PermissionError)),conn.transaction():preview(preview_case,execute=prepared)
    assert conn.execute('SELECT count(*) AS n FROM aip_business_investigation_compile_receipt WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==0


@pytest.mark.parametrize('field',['caseRef','idempotencyKey'])
def test_bootstrap_binding_requires_original_request_lineage(preview_case,monkeypatch,field):
    from copy import deepcopy
    from aos_api.ecommerce_analysis_bootstrap_authority import AnalysisBootstrapCurrentBinding
    original=AnalysisBootstrapCurrentBinding._read
    def changed(self,conn,snapshot,intent,preview_ref):
        altered=deepcopy(snapshot)
        if field=='caseRef':altered['request']['caseRef']['resourceId']='other-case'
        else:altered['request']['idempotencyKey']='other-event-target'
        return original(self,conn,altered,intent,preview_ref)
    monkeypatch.setattr(AnalysisBootstrapCurrentBinding,'_read',changed)
    with pytest.raises(ValueError,match='original analysis request'):
        preview(preview_case,execute=lambda value:bound(preview_case,value))
