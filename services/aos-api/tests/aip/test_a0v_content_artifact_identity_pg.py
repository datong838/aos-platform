import os
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_aip_budget_reservation_pg import database,runtime_connection
from aos_api.aip_task_store import AipTaskStore,AipTaskTransitionBlocked,AipTaskNotFound
from aos_api.tenant_scope import TenantScope

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PostgreSQL opt-in')


def test_artifact_owner_stable_identity_and_legacy_random_path(database):
    database.owner.execute('CREATE TABLE aip_task_run(org_id text,project_id text,run_id text)')
    database.owner.execute('CREATE TABLE aip_artifact (LIKE public.aip_artifact INCLUDING ALL)')
    database.owner.execute('GRANT SELECT ON aip_task_run TO aos_runtime')
    database.owner.execute('GRANT SELECT,INSERT ON aip_artifact TO aos_runtime')
    scope=TenantScope('org-org','dev-project')
    database.owner.execute("INSERT INTO aip_task_run VALUES('org-org','dev-project','run')")
    store=AipTaskStore(runtime_connection(database))
    identity='artifact-'+'a'*20
    payload={'contentHash':'b'*64,'metadata':{'body':'可读的业务内容','artifactRef':identity}}
    def save(_):return store.record_artifact(scope,'run','test','content',payload,artifact_id=identity)
    with ThreadPoolExecutor(max_workers=2) as executor: assert list(executor.map(save,range(2)))==[identity,identity]
    assert database.owner.execute('SELECT count(*) AS n FROM aip_artifact').fetchone()['n']==1
    assert save(0)==identity
    with pytest.raises(AipTaskTransitionBlocked):
        store.record_artifact(scope,'run','test','content',payload|{'metadata':{'body':'漂移'}},artifact_id=identity)
    with pytest.raises(AipTaskNotFound):
        store.record_artifact(TenantScope('dev-org','dev-project'),'run','test','content',payload,artifact_id=identity)
    with pytest.raises(AipTaskNotFound):
        store.record_artifact(scope,'missing','test','content',payload,artifact_id=identity)
    first=store.record_artifact(scope,'run','test','content',payload)
    second=store.record_artifact(scope,'run','test','content',payload)
    assert first!=second and first!=identity
