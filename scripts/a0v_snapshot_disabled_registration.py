"""One-time disabled configuration through original API; unknown writes read back only."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def matches(expected, actual):
    if type(expected) is dict:
        return type(actual) is dict and all(k in actual and matches(v, actual[k]) for k,v in expected.items())
    if type(expected) is list:
        return type(actual) is list and len(expected)==len(actual) and all(matches(a,b) for a,b in zip(expected,actual))
    if type(expected) is bool or expected is None:
        return type(actual) is type(expected) and expected==actual
    return expected==actual


def register_once(intent_path, method, path, body, *, api, read):
    from a0v_qyh_current_product_event_first_chain import freeze_or_match
    intent = dict(method=method,path=path,body=body)
    existed = intent_path.exists()
    if existed:
        freeze_or_match(intent_path,intent)
    actual = read()
    if actual is not None:
        if not matches(body,actual):
            raise ValueError('existing configuration differs')
        return dict(confirmed=True,submitted=False)
    if existed:
        raise ValueError('original configuration write unconfirmed; no resend')
    freeze_or_match(intent_path,intent)
    try:
        api(method,path,body)
    except Exception:
        # Failure may follow commit; authoritative readback is the only next action.
        pass
    actual = read()
    if actual is None:
        raise ValueError('original configuration write unconfirmed; no resend')
    if not matches(body,actual):
        raise ValueError('persisted configuration differs')
    return dict(confirmed=True,submitted=True)


def run():
    from datetime import datetime,timezone
    from a0v_formal_text_model_renewal import database_connect
    from a0v_qyh_current_product_event_first_chain import api, freeze_or_match
    from aos_api.asset_registry.canonical_json import canonical_sha256
    evidence = ROOT/'.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION'
    saved=json.loads((evidence/'y5b-current-signed-preview.json').read_text())
    preview=saved['preview'];body={k:v for k,v in preview.items() if k!='previewHash'}
    if canonical_sha256(body)!=preview['previewHash'] or preview['executionAuthorized'] is not False:
        raise ValueError('preview integrity differs')
    from aos_api.source_readiness_contracts import CANONICAL_QYH_PIPELINE_IDS
    if tuple(m['pipelineId'] for m in preview['members'])!=CANONICAL_QYH_PIPELINE_IDS:
        raise ValueError('canonical complete preview required')
    state=ROOT.parent/'.aos-recovery-20260916/state/y5-real-configuration/intents'
    scope=('org-org','dev-project');ref=saved['installationRef'];connect=database_connect('aos_meta_head')
    def query(sql,params=()):
        with connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            row=c.execute('''SELECT r.state,r.lock_hash,i.current_revision,b.generation,b.enabled,b.operation_fence
                FROM bundle_installation i JOIN bundle_installation_revision r
                ON (i.org_id,i.project_id,i.installation_pk,i.current_revision)=(r.org_id,r.project_id,r.installation_pk,r.revision)
                JOIN extension_runtime_binding b ON (b.org_id,b.project_id,b.installation_id,b.installation_revision)=
                (i.org_id,i.project_id,i.installation_id,i.current_revision)
                WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',(*scope,ref['installationId'])).fetchall()
            if (len(row)!=1 or row[0]['state']!='active' or row[0]['lock_hash']!=ref['lockHash']
                or row[0]['current_revision']!=ref['revision'] or str(row[0]['generation'])!='5295b81e-6005-4c2e-befc-3323f1456b8c'
                or row[0]['enabled'] is not True or row[0]['operation_fence'] is not False):
                raise ValueError('current installation/generation differs')
            return [dict(r) for r in c.execute(sql,params).fetchall()]
    def counts():
        return query('''SELECT (SELECT count(*) FROM meta_schedule_run WHERE org_id=%s AND project_id=%s) AS runs,
            (SELECT count(*) FROM pipeline_controlled_source_claim WHERE org_id=%s AND project_id=%s) AS source_claims''',scope+scope)[0]
    before=counts();freeze_or_match(state/'source-baseline.json',before)
    results=[]
    for member in preview['members'][2:]:
        pipeline=member['pipelineId'];graph=member['graph']
        pipeline_body=dict(id=pipeline,sourceId='niushop-qyh',target='dataset',
                           datasetRid='ri.dataset.'+pipeline.lower(),objectTypeHint=member['objectType'],name=graph['name'])
        def read_pipeline():
            rows=query('''SELECT id,source_id AS "sourceId",target,dataset_rid AS "datasetRid",
                object_type_hint AS "objectTypeHint",name FROM meta_pipeline
                WHERE org_id=%s AND project_id=%s AND id=%s''',(*scope,pipeline))
            return rows[0] if rows else None
        pipeline_result=register_once(state/(pipeline+'-pipeline.json'),'POST','/v1/pipelines',pipeline_body,
                                      api=api,read=read_pipeline)
        datasets=query('''SELECT rid,pipeline_id,source_id FROM meta_dataset
            WHERE org_id=%s AND project_id=%s AND rid=%s''',(*scope,pipeline_body['datasetRid']))
        if (len(datasets)!=1 or datasets[0]['pipeline_id']!=pipeline or datasets[0]['source_id']!='niushop-qyh'):
            raise ValueError('original dataset registration unconfirmed; no resend')
        def read_graph():
            rows=query('SELECT payload FROM phase5_pipeline_graph WHERE org_id=%s AND project_id=%s AND pipeline_id=%s',(*scope,pipeline))
            return rows[0]['payload'] if rows else None
        result=register_once(state/(pipeline+'-graph.json'),'PUT','/v1/pipelines/'+pipeline+'/graph',graph,api=api,read=read_graph)
        schedule=dict(member['schedule'],id='sch-'+pipeline.lower()+'-snapshot-y5-20260916')
        if schedule['enabled'] is not False or schedule['ingest'] is not None:
            raise ValueError('disabled non-ingest schedule required')
        def read_schedule():
            rows=query('SELECT id,pipeline_id AS "pipelineId",name,enabled,cron,ingest FROM meta_schedule WHERE org_id=%s AND project_id=%s AND id=%s',(*scope,schedule['id']))
            return rows[0] if rows else None
        intent_path=state/(pipeline+'-schedule.json')
        # One specifically diagnosed failed transaction, never a generic unknown retry.
        rejected_path=state/(pipeline+'-schedule-rejected-fk.json')
        if rejected_path.exists():
            rejection=json.loads(rejected_path.read_text())
            expected=dict(method='POST',path='/v1/schedules',body=schedule)
            if (pipeline!='P03-product-sku-qyh' or rejection.get('outcome')!='DATABASE_FOREIGN_KEY_REJECTED'
                or rejection.get('intent')!=expected or json.loads(intent_path.read_text())!=expected
                or rejection.get('databaseEvidence')!='2026-09-16 10:23:32.861 UTC [723514] ERROR:  insert or update on table "meta_schedule" violates foreign key constraint "fk_meta_schedule_pipeline_ti4d7"'):
                raise ValueError('exact original rejection proof differs')
            intent_path=state/(pipeline+'-schedule-retry-after-fk.json')
        registration=register_once(intent_path,'POST','/v1/schedules',schedule,api=api,read=read_schedule)
        results.append(dict(pipelineId=pipeline,pipeline=pipeline_result,graph=result,schedule=registration))
        print(json.dumps(results[-1]),flush=True)
    after=counts()
    if after!=before:raise ValueError('source execution counts changed')
    result=dict(observedAt=datetime.now(timezone.utc).isoformat(),previewHash=preview['previewHash'],results=results,
                before=before,after=after,sourceCalls=0,newSchedulesEnabled=False,businessChainComplete=False)
    (evidence/'y5c2-api-registration-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    sys.dont_write_bytecode=True
    run()
