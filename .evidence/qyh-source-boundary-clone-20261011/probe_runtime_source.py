"""Actual clone API identity probe; all attempted writes are rolled back."""
import json
import argparse
from pathlib import Path
import sys
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'services/aos-api'),str(ROOT/'.evidence/qyh-full-system-restoration-20261011')]
import promote_stage_transport as S
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.tenant_scope import TenantScope

R=Path(__file__).resolve().parent
TARGET='qyh-source-boundary-clone-20261011'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--revision',choices=['r2'],required=True)
    args=parser.parse_args()
    intent=R/f'runtime-source-red-{args.revision}-intent.json'
    assert not intent.exists(),'Prior probe requires reconciliation, not replay'
    restored=json.loads((R/'restore-verified.json').read_text())
    item=json.loads(S.run(['inspect','--format','{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}',TARGET]))
    assert item['Id']==restored['container']['Id'] and item['Mounts']==[]
    assert item['Ports']=={'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'18431'}]}
    before=S.P.M.fingerprint(TARGET)
    token='qyh-clone-probe-'+uuid4().hex
    with intent.open('x') as out:
        json.dump({'target':TARGET,'containerId':item['Id'],'cluster':restored['cloneIdentity']['cluster'],'key':token,'commitAllowed':False,'currentDatabaseTouched':False},out,indent=2)
    conn=psycopg.connect(host='127.0.0.1',port=18431,dbname='aos_meta_head',user='qyh_restored_api_login',row_factory=dict_row)
    conn.read_only=False
    result={'login':None,'role':None,'headAccepted':False,'receiptAccepted':False,'sqlstate':None,'committed':False,'canaryRejectedSqlstate':None}
    try:
        assert conn.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster']==restored['cloneIdentity']['cluster']
        conn.execute('SET LOCAL ROLE aos_runtime')
        apply_asset_transaction_scope(conn,org_id='org-org',project_id='dev-project')
        identity=conn.execute('SELECT session_user AS login,current_user AS role').fetchone()
        assert identity=={'login':'qyh_restored_api_login','role':'aos_runtime'}
        result.update(identity)
        conn.execute('INSERT INTO aip_responsibility_plan_head(org_id,project_id,plan_id,current_revision,version) VALUES(%s,%s,%s,1,1)',('org-org','dev-project',token))
        result['headAccepted']=True
        store=AipProductionContractStore()
        ref={'resourceType':'ResponsibilityPlanRevision','resourceId':token,'revision':1,'contentHash':'a'*64}
        store._receipt(conn,TenantScope('org-org','dev-project'),'responsibility_plan.create',token,'a'*64,ref,'clone:unauthorized-runtime')
        result['receiptAccepted']=True
        try:
            with conn.transaction():
                store._receipt(conn,TenantScope('dev-org','dev-project'),'responsibility_plan.create',token+'-canary','a'*64,ref,'clone:unauthorized-runtime')
        except psycopg.Error as error:
            result['canaryRejectedSqlstate']=error.sqlstate
    except psycopg.Error as error:
        result['sqlstate']=error.sqlstate
    finally:
        conn.rollback();conn.close()
    assert S.P.M.fingerprint(TARGET)==before,'Probe rollback differs: no retry'
    result['full647RollbackExact']=True
    result['runtimeSourceBoundaryClosed']=not (result['headAccepted'] or result['receiptAccepted'])
    result['passwordAuthenticationProven']=False
    with (R/f'runtime-source-red-{args.revision}-result.json').open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    print(json.dumps(result))
