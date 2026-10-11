"""Read existing isolated receipts only; never rerun the original operations."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
OLD=ROOT/'.evidence/qyh-source-boundary-rehearsal-20261011'
TARGET='qyh-source-boundary-clone-20261011'
DB='qyh_source_contract_20261011'
CONTEXT='colima-aos-extension'

def docker(*args,input=None):
    p=subprocess.run(['docker','--context',CONTEXT,*args],input=input,capture_output=True,text=True,timeout=30)
    if p.returncode:raise RuntimeError('Read-only container query failed; no replay')
    return p.stdout


def main():
    output=OUT/'current-coverage.json'
    assert not output.exists(),'Existing readback: reconcile only'
    identity=json.loads(docker('inspect','--format','{"Id":{{json .Id}},"Image":{{json .Image}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}',TARGET))
    restored=json.loads((ROOT/'.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    assert identity['Id']==restored['container']['Id'] and identity['Image']==restored['container']['Image']
    assert not identity['Mounts'] and identity['Ports']=={'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'18431'}]}
    protocol=ROOT/'services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py'
    tree=ast.parse(protocol.read_text())
    catalog=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CONTRACT_OPERATIONS' for t in n.targets))
    store=ROOT/'services/aos-api/aos_api/aip_production_contract_store.py'
    calls=[n for n in ast.walk(ast.parse(store.read_text())) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='_receipt']
    operations={n.args[2].value for n in calls if len(n.args)>2 and isinstance(n.args[2],ast.Constant) and isinstance(n.args[2].value,str)}
    assert operations==set(catalog) and len(catalog)==30
    query="""BEGIN READ ONLY;
SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'database',current_database(),
'operations',(SELECT json_agg(x ORDER BY operation) FROM (SELECT operation,count(*) AS n FROM aip_production_contract_receipt WHERE org_id='org-org' AND project_id='dev-project' AND created_by='clone:test' GROUP BY operation) x),
'impactReceipts',(SELECT json_agg(x ORDER BY idempotency_key) FROM (SELECT operation,idempotency_key,result_ref FROM aip_production_contract_receipt WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key IN ('qyh-impact-create','qyh-impact-revise')) x),
'failedImpactReceipts',(SELECT count(*) FROM aip_production_contract_receipt WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key IN ('qyh-impact-rollback','qyh-impact-freeze-denied','qyh-impact-stale','qyh-impact-canary')),
'counts',json_build_object('receipts',(SELECT count(*) FROM aip_production_contract_receipt),'runs',(SELECT count(*) FROM aip_task_run),'steps',(SELECT count(*) FROM aip_step_run)));
COMMIT;"""
    def read():return json.loads(docker('exec','-i',TARGET,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d',DB,input=query))
    first,second=read(),read();assert first==second
    assert first['database']==DB and first['cluster']==restored['cloneIdentity']['cluster']
    result=json.loads((OLD/'impact-preview-business-result.json').read_text())
    assert first['failedImpactReceipts']==0 and len(first['impactReceipts'])==2
    for receipt,name in zip(first['impactReceipts'],['created','revised']):
        expected=result[name]
        assert receipt['result_ref']=={'resourceType':'ImpactPreviewRevision','resourceId':expected['previewId'],'revision':expected['revision'],'contentHash':expected['contentHash']}
    assert first['counts']['runs']==result['finalCounts']['aip_task_run'] and first['counts']['steps']==result['finalCounts']['aip_step_run']
    actual={r['operation']:r['n'] for r in first['operations']};previous=json.loads((OLD/'contract-operation-coverage-r8.json').read_text())
    assert not (set(actual)-set(catalog))
    current={**previous,'actualCurrentExperimentalReceiptOperations':actual,'remainingWithoutCurrentPositiveReceipt':sorted(set(catalog)-set(actual)),
        'newlyReconciledSinceR8':sorted(set(actual)-set(previous['actualCurrentExperimentalReceiptOperations'])),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'exactCloneTargetVerified':True,'twoIndependentQueriesEqual':True,'impactReceiptReferencesExact':True,
        'failedImpactOperationsNoReceipts':True,'runAndStepCountsUnchanged':True,
        'databaseWrites':0,'originalOperationReplay':False,'wholeSourceCompatibilityAccepted':False,
        'formalRestorationAccepted':False,'protocolIsProductionMigration':False,
        'sourceHashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [protocol,store,OLD/'impact-preview-business-result.json',OLD/'impact-preview-independent-readback.json']}}
    assert len(actual)==24 and len(current['remainingWithoutCurrentPositiveReceipt'])==6
    with output.open('x') as f:json.dump(current,f,ensure_ascii=False,indent=2)
    print(json.dumps({'actualOperations':len(actual),'remaining':current['remainingWithoutCurrentPositiveReceipt'],'newlyReconciled':current['newlyReconciledSinceR8'],'writes':0}))

if __name__=='__main__':main()
