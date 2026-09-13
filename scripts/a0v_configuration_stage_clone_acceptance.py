"""One retained staging exercise on the restored clone; never a main consumer."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import a0v_configuration_stage_deploy as deployment

TASK='A0V-CONFIGURATION-STAGE-CLONE-ACCEPTANCE-20260914'
INSTALLATION='97aeb2e7-59ba-40f6-89a3-fb0293bc0497'
SUBJECT='a0v-ecommerce-growth-1.4-runtime-owner'
KEY='clone-configuration-stage-acceptance-20260914-v1'


def require_lease():
    leases=json.loads((deployment.ROOT.parent/'docs/palantier/AOS项目开发上下文/memory/leases.json').read_text())['leases']
    found=[item for item in leases if item['task_id']==TASK]
    if (len(found)!=1 or found[0]['owner']!='m1' or found[0]['status']!='ACTIVE'
        or datetime.fromisoformat(found[0]['lease_expires_at'])<=datetime.now(timezone.utc)
        or subprocess.check_output(['git','branch','--show-current'],cwd=deployment.ROOT,text=True).strip()!='m1'):
        raise ValueError('clone acceptance lease required')


def runtime_connection():
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.conninfo import conninfo_to_dict
    from a0v_ecommerce_runtime_host import DEFAULT_CREDENTIALS, _load_credentials
    identity=_load_credentials(DEFAULT_CREDENTIALS)['runtime']
    params=conninfo_to_dict(identity['dsn'])
    params.update(dbname=deployment.CLONE,password=identity['password'])
    @contextmanager
    def connect():
        with psycopg.connect(**params,row_factory=dict_row) as conn:
            if conn.info.dbname!=deployment.CLONE or conn.info.dbname==deployment.storage.MAIN:
                raise ValueError('clone-only runtime connection required')
            yield conn
    return connect,identity['role']


def main():
    from psycopg import sql
    from aos_api.tenant_scope import TenantScope
    from aos_api.extension_runtime.configuration_stage_connection import CREDENTIAL_FILE
    from aos_api.extension_runtime.configuration_stage_http_service import ConfigurationStageHttpService
    from aos_api.extension_runtime.configuration_stage_contracts import ConfigurationStageRequest
    from aos_api.extension_runtime.configuration_source_catalog import read_source_catalog
    from aos_api.extension_runtime.configuration_stage_consumer import ConfigurationStageConsumer
    from aos_api.extension_runtime.configuration_authorization import CurrentConfigurationPermission
    from aos_api.aip_runtime_configuration_sources import build_current_configuration_authorization
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.extension_runtime.runtime_host import RuntimeHost, RuntimeTenantAssignment
    require_lease()
    scope=TenantScope('org-org','dev-project')
    intent=deployment.STATE/'clone-acceptance-intent.json'
    if intent.exists():raise ValueError('retained intent requires readback, never resubmit')
    with deployment.storage.connect(deployment.storage.MAIN) as conn:main_before=deployment.storage.fingerprint(conn)
    connect,role=runtime_connection()
    with deployment.storage.connect(deployment.CLONE) as conn:
        if deployment.storage.version(conn)!=['a0v_038']:raise ValueError('clone schema differs')
        if conn.execute('SELECT count(*) AS n FROM extension_runtime_configuration_stage_request').fetchone()['n']!=0:raise ValueError('clone queue not empty')
        conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(deployment.CLONE),sql.Identifier(role)))
        row=conn.execute('''SELECT i.current_revision,i.etag_version,b.generation,b.revision
            FROM bundle_installation i JOIN extension_runtime_binding b USING(org_id,project_id,installation_id)
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',(*scope.key,INSTALLATION)).fetchall()
        if len(row)!=1:raise ValueError('one exact clone binding required')
        row=row[0]
        view=SimpleNamespace(installationId=INSTALLATION,installationRevision=row['current_revision'],installationEtag=row['etag_version'],
            binding=SimpleNamespace(generation=str(row['generation']),revision=row['revision']))
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
        catalog=read_source_catalog(conn,org_id=scope.org_id,project_id=scope.project_id,view=view)
        if len(catalog.roles)!=1 or len(catalog.policies)!=1:raise ValueError('unambiguous real clone sources required')
        config_before=conn.execute('SELECT count(*) AS n FROM extension_runtime_configuration').fetchone()['n']
    request=ConfigurationStageRequest(schemaVersion="aos.runtime-configuration-stage/v1",action="stage-configuration",target=catalog.target,roleRefs=tuple(item.ref for item in catalog.roles),policyRef=catalog.policies[0].ref)
    deployment.protected_write(intent,dict(key=KEY,request=request.model_dump(mode='json'),mainBefore=main_before))
    previous=os.environ.get(CREDENTIAL_FILE)
    os.environ[CREDENTIAL_FILE]=str(deployment.STATE/'configuration-stage-clone-identity.json')
    service=ConfigurationStageHttpService()
    try:
        accepted=service.enqueue(scope=scope,subject=SUBJECT,idempotency_key=KEY,request=request)
        authority=build_current_configuration_authorization(permission=CurrentConfigurationPermission(installation_store=PostgresInstallationStore(connect_factory=connect)))
        consumer=ConfigurationStageConsumer(connect=connect,authorize=authority)
        assignment=RuntimeTenantAssignment(scope=scope,consumers=(consumer,))
        async def consume():
            host=RuntimeHost(assignments=lambda:(assignment,))
            try:
                first=await host.run_once()
                second=await host.run_once()
                return first,second
            finally:await host.stop()
        first,second=asyncio.run(consume())
        result=service.get(scope=scope,subject=SUBJECT,request_id=accepted['requestId'])
        found=service.find(scope=scope,subject=SUBJECT,idempotency_key=KEY)
        if result!=found:raise ValueError('original key and ID differ')
        if any(item is not None for tick in second.tenants for item in tick.deliveries):raise ValueError('replay consumed again')
    finally:
        if previous is None:os.environ.pop(CREDENTIAL_FILE,None)
        else:os.environ[CREDENTIAL_FILE]=previous
    with deployment.storage.connect(deployment.CLONE) as conn:
        config_after=conn.execute('SELECT count(*) AS n FROM extension_runtime_configuration').fetchone()['n']
        queue_count=conn.execute('SELECT count(*) AS n FROM extension_runtime_configuration_stage_request').fetchone()['n']
    with deployment.storage.connect(deployment.storage.MAIN) as conn:
        if deployment.storage.fingerprint(conn)!=main_before:raise ValueError('main fingerprint changed')
        if conn.execute('SELECT count(*) AS n FROM extension_runtime_configuration_stage_request').fetchone()['n']!=0:raise ValueError('main queue changed')
    if queue_count!=1 or config_after-config_before!=(1 if result['state']=='succeeded' else 0):raise ValueError('clone effect count differs')
    proof=dict(outcome='CLONE_CONFIGURATION_STAGE_OBSERVED',database=deployment.CLONE,receipt=result,
        configurationDelta=config_after-config_before,queueCount=queue_count,repeatTickConsumed=False,
        originalKeyReadbackMatches=True,mainBusinessFingerprintUnchanged=True,mainQueueCount=0,
        liveBusinessAcceptance=False,at=datetime.now(timezone.utc).isoformat())
    deployment.protected_write(deployment.STATE/'clone-acceptance-proof.json',proof)
    print(json.dumps(proof,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps(dict(outcome='CLONE_ACCEPTANCE_NEEDS_READBACK',errorType=type(exc).__name__)))
        raise SystemExit(2) from None
