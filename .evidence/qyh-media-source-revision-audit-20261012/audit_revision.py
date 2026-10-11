"""Read original publication sequence metadata; never create reference authority."""
import json
import subprocess
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import a0v_qyh_restored_http as gate

SQL="""BEGIN READ ONLY;
SELECT json_build_object(
 'database',current_database(), 'cluster',(SELECT system_identifier::text FROM pg_control_system()),
 'schema',(SELECT version_num FROM alembic_version),
 'columns',(SELECT json_agg(x ORDER BY column_name) FROM (SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='asset_bundle_version_event')x),
 'constraints',(SELECT json_agg(x ORDER BY conname) FROM (SELECT c.conname,pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c WHERE c.conrelid='asset_bundle_version_event'::regclass)x),
 'triggers',(SELECT json_agg(x ORDER BY tgname) FROM (SELECT t.tgname,t.tgenabled,pg_get_triggerdef(t.oid) AS definition,md5(pg_get_functiondef(t.tgfoid)) AS function_hash FROM pg_trigger t WHERE t.tgrelid='asset_bundle_version_event'::regclass AND NOT t.tgisinternal)x),
 'versions',(SELECT json_agg(x ORDER BY bundle_id,version,sequence) FROM (
  SELECT b.bundle_id,v.version,v.status,v.content_hash,e.sequence,e.from_status,e.to_status,e.evidence_revision,
    e.evidence_snapshot IS NOT NULL AS has_snapshot,
    e.evidence_revision='sha256:'||repeat('0',64) AS legacy_zero_sentinel
  FROM asset_bundle b JOIN asset_bundle_version v USING(bundle_pk)
  LEFT JOIN asset_bundle_version_event e USING(version_pk)
  WHERE b.publisher='aos' AND ((b.bundle_id='domain.ecommerce.core' AND v.version IN ('1.4.3','1.4.4'))
  OR (b.bundle_id='platform.ecommerce.niushop' AND v.version IN ('1.23.2','1.23.3'))
  OR (b.bundle_id='solution.ecommerce.growth' AND v.version IN ('1.13.0','1.13.1'))
  OR (b.bundle_id='solution.ecommerce.operations-base' AND v.version='1.2.2'))
 )x));
COMMIT;"""


def read():
    r=subprocess.run(['docker','--context',gate.CONTEXT,'exec','-i',gate.TARGET,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d',gate.EXPECTED['database']],input=SQL,capture_output=True,text=True,timeout=30)
    if r.returncode:raise RuntimeError('Registry read-only metadata query failed')
    return json.loads(r.stdout)


def main():
    output=OUT/'revision-audit.json'
    assert not output.exists(),'Existing result: reconcile only'
    gate.preflight(ROOT/'.evidence/qyh-full-system-restoration-20261011/private/restored-identity.json')
    first,second=read(),read();assert first==second
    assert first['database']==gate.EXPECTED['database'] and first['cluster']==gate.EXPECTED['cluster'] and first['schema']==gate.EXPECTED['schema']
    report={'metadata':first,'twoIndependentReadsEqual':True,'databaseWrites':0,'registryTransitions':0,'referenceAuthorityCreated':False,'snapshotSequenceIsNotSignatureApproval':True,'legacySentinelCannotAuthorizeMedia':True}
    with output.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({'events':len(first['versions'] or []),'columns':len(first['columns']),'triggers':len(first['triggers']),'writes':0}))

if __name__=='__main__':main()
