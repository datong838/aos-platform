import json
from contextlib import contextmanager

import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from test_lifecycle_pg import database, pytestmark as pg_required
from test_configuration_store_pg import configuration_case
from test_configuration_stage_schema_pg import stage
from test_configuration_stage_api_pg import api
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.configuration_stage_contracts import ConfigurationStageRequest
from aos_api.extension_runtime.configuration_stage_connection import CREDENTIAL_FILE, configuration_stage_connection
from aos_api.extension_runtime.configuration_stage_http_service import ConfigurationStageHttpService


@pg_required
@pytest.mark.parametrize('defect', (None,'inherit','extra-role','admin-option'))
def test_real_restricted_login_and_service_sql(api,database,tmp_path,monkeypatch,defect):
    conn,_,body,role=api
    conn.execute(sql.SQL('ALTER ROLE {} LOGIN').format(sql.Identifier(role)))
    if defect=='inherit': conn.execute(sql.SQL('ALTER ROLE {} INHERIT').format(sql.Identifier(role)))
    if defect=='extra-role': conn.execute(sql.SQL('GRANT pg_read_all_data TO {}').format(sql.Identifier(role)))
    if defect=='admin-option': conn.execute(sql.SQL('GRANT aos_configuration_stage_api TO {} WITH ADMIN OPTION').format(sql.Identifier(role)))
    path=tmp_path/'identity.json'
    path.write_text(json.dumps(dict(schemaVersion='aos.runtime-configuration-api-identity/v1', role=role,
        dsn=make_conninfo(host='127.0.0.1',port=18432,dbname='postgres',user=role))))
    path.chmod(0o600);monkeypatch.setenv(CREDENTIAL_FILE,str(path));monkeypatch.delenv('AOS_OPENFGA_API_URL',raising=False)
    @contextmanager
    def scoped(**kwargs):
        with configuration_stage_connection(**kwargs) as db:
            class Schema:
                def execute(self,q,p): return db.execute(q.replace('public.',database[2]+'.'),p)
            yield Schema()
    service=ConfigurationStageHttpService(connect=scoped)
    args=dict(scope=TenantScope('org-org','dev-project'),subject='test-actor')
    if defect:
        with pytest.raises(RuntimeError,match='not permitted'):
            service.enqueue(**args,idempotency_key='api',request=ConfigurationStageRequest.model_validate_json(json.dumps(body)))
        return
    receipt=service.enqueue(**args,idempotency_key='api',request=ConfigurationStageRequest.model_validate_json(json.dumps(body)))
    assert receipt['state']=='requested'
    status=service.get(**args,request_id=receipt['requestId'])
    assert status['requestId']==receipt['requestId'] and status['result'] is None
    assert status['tenant']==dict(orgId='org-org',projectId='dev-project')


def test_remote_authority_rejects_local_connection_before_reading_credentials(monkeypatch):
    monkeypatch.setenv('AOS_OPENFGA_API_URL','http://not-contacted.invalid')
    with pytest.raises(RuntimeError,match='remote configuration authority'):
        with configuration_stage_connection(scope=TenantScope('org-org','dev-project'),subject='test-actor'): pass
