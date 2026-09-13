from copy import deepcopy

import pytest
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from test_ui_read_host_role_pg import host_role,api_role,admission,queue,attempt_case,database,host,caller,pytestmark
from test_ui_read_admission_pg import SchemaConnection
from test_analyst_workspace_view import snapshot,projector
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.extension_runtime.analyst_workspace_snapshot import read_host_analyst_workspace_snapshot
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.tenant_scope import TenantScope

SCOPE=TenantScope('org-org','dev-project')
TABLES=('ecommerce_investigation_case_head','ecommerce_investigation_case_revision',
        'ecommerce_investigation_run','ecommerce_investigation_run_state_head')


@pytest.fixture
def host_snapshot(host_role):
    owner,_,schema,_=host_role
    for statement in [
        'CREATE TABLE ecommerce_investigation_case_head(org_id text,project_id text,case_id text,current_revision int,updated_at timestamptz)',
        'CREATE TABLE ecommerce_investigation_case_revision(org_id text,project_id text,case_id text,revision int,authority_data jsonb)',
        'CREATE TABLE ecommerce_investigation_run(org_id text,project_id text,case_id text,run_id text,created_at timestamptz,authority_data jsonb)',
        'CREATE TABLE ecommerce_investigation_run_state_head(org_id text,project_id text,run_id text,authority_data jsonb)',
    ]:owner.execute(statement)
    for table in TABLES:owner.execute(sql.SQL('GRANT SELECT ON {} TO aos_runtime').format(sql.Identifier(table)))
    value=snapshot()['cases'][0];case=value['case'];run=value['runs'][0]['authority'];state=value['runs'][0]['state']
    def add_case(identity,org='org-org'):
        payload=deepcopy(case);payload['caseId']=identity
        if payload['priorRef']:payload['priorRef']['resourceId']=identity
        payload['contentHash']=canonical_sha256({k:v for k,v in payload.items() if k!='contentHash'})
        owner.execute('INSERT INTO ecommerce_investigation_case_head VALUES(%s,%s,%s,%s,now())',(org,'dev-project',identity,case['revision']))
        owner.execute('INSERT INTO ecommerce_investigation_case_revision VALUES(%s,%s,%s,%s,%s)',(org,'dev-project',identity,case['revision'],Jsonb(payload)))
    add_case(case['caseId']);add_case('foreign-case','dev-org')
    owner.execute('INSERT INTO ecommerce_investigation_run VALUES(%s,%s,%s,%s,now(),%s)',(*SCOPE.key,case['caseId'],run['runId'],Jsonb(run)))
    owner.execute('INSERT INTO ecommerce_investigation_run_state_head VALUES(%s,%s,%s,%s)',(*SCOPE.key,run['runId'],Jsonb(state)))
    return host_role,add_case


def read(conn,case,subject='reader'):
    conn.row_factory=dict_row
    return read_host_analyst_workspace_snapshot(conn=SchemaConnection(conn,case[2]),scope=SCOPE,
        subject=subject,required_markings=('public',))


def test_non_superuser_host_reads_one_snapshot_and_package_projection(host_snapshot,projector):
    case,add_case=host_snapshot
    with host(case) as conn:
        first=read(conn,case)
        output=projector(first)
        assert output['caseCount']==1 and output['runCount']==1 and output['executionAllowed'] is False
        add_case('case-later')
        assert len(read(conn,case)['cases'])==1
        assert conn.execute("SELECT has_any_column_privilege(current_user,'meta_membership','UPDATE') AS allowed").fetchone()['allowed'] is False
    with host(case) as conn:assert len(read(conn,case)['cases'])==2


def test_snapshot_rejects_subject_mismatch_and_api_role(host_snapshot):
    case,_=host_snapshot
    with host(case) as conn:
        with pytest.raises(RuntimeConflict):read(conn,case,subject='other')
    with caller(case,repeatable=True) as conn:
        with pytest.raises(RuntimeConflict):read(conn,case)
