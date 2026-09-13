import pytest
from fastapi.testclient import TestClient

from test_lifecycle_pg import database, pytestmark
from test_configuration_store_pg import configuration_case
from test_configuration_catalog import snapshot
from current_configuration_sources_case import install_current_configuration_sources
from test_runtime_installations_api import _app,_view,_control_plane,INSTALLATION_ID
from aos_api.extension_runtime.configuration_source_catalog import read_source_catalog
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


@pytest.fixture
def sources(configuration_case,database):
    conn,args=configuration_case
    conn.execute('RESET ROLE')
    _,refs=install_current_configuration_sources(conn,database[2])
    view=snapshot(args);view.binding.generation=str(view.binding.generation)
    return conn,view,refs


def read(sources,**changes):
    conn,view,_=sources
    return read_source_catalog(conn,**(dict(org_id='org-org',project_id='dev-project',view=view)|changes))


def test_current_source_candidates_are_exact_and_do_not_expose_bodies(sources):
    catalog=read(sources);_,view,refs=sources
    assert catalog.target.generation==view.binding.generation
    assert catalog.roles[0].ref==refs['role'] and catalog.policies[0].ref==refs['policy']
    assert not catalog.rolesHasMore and not catalog.policiesHasMore
    raw=catalog.model_dump_json()
    assert 'budgetRef' not in raw and 'networkPolicyRef' not in raw and 'slots' not in raw


@pytest.mark.parametrize('table',('aip_responsibility_plan_head','aip_runtime_policy_head'))
def test_noncurrent_sources_are_not_candidates(sources,table):
    from psycopg import sql
    conn,_,_=sources;conn.execute('RESET ROLE')
    conn.execute(sql.SQL('UPDATE {} SET current_revision=2').format(sql.Identifier(table)))
    conn.execute('SET ROLE aos_runtime')
    catalog=read(sources)
    assert (len(catalog.roles),len(catalog.policies))==((0,1) if table=='aip_responsibility_plan_head' else (1,0))


def test_negative_tenant_and_changed_binding_fail_closed(sources):
    with pytest.raises(RuntimeConflict):read(sources,org_id='dev-org')
    sources[1].binding.revision=2
    with pytest.raises(RuntimeConflict):read(sources)


def test_no_binding_has_no_candidates(sources):
    sources[1].binding=None
    result=read(sources)
    assert result.target is None and result.roles==() and result.policies==()


def test_source_limit_is_honestly_reported(sources):
    conn,_,_=sources;conn.execute('RESET ROLE')
    for i in range(50):
        for table in ('aip_responsibility_plan_head','aip_responsibility_plan_revision'):
            from psycopg import sql
            conn.execute(sql.SQL("INSERT INTO {t} SELECT (jsonb_populate_record(NULL::{t},to_jsonb(r)||jsonb_build_object('plan_id',%s::text))).* FROM {t} r WHERE plan_id='qyh-runtime-roles'").format(t=sql.Identifier(table)),(f'copy-{i}',))
    conn.execute('SET ROLE aos_runtime')
    result=read(sources)
    assert len(result.roles)==50 and result.rolesHasMore is True


def test_source_http_uses_current_principal(sources):
    result=read(sources)
    plane=_control_plane()
    calls=[]
    def listing(**kwargs):calls.append(kwargs);return result
    plane.view_reader.list_configuration_sources=listing
    response=TestClient(_app(plane)).get('/v1/bundle-runtime-installations/'+INSTALLATION_ID+'/configuration-sources?orgId=dev-org')
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert calls[0]['org_id']=='org-org'


@pytest.mark.parametrize('kind', ('role_draft','policy_suspended','policy_kill'))
def test_inactive_or_killed_sources_are_not_offered(sources,kind):
    conn,_,_=sources;conn.execute('RESET ROLE')
    if kind=='role_draft':
        conn.execute("INSERT INTO aip_responsibility_plan_revision SELECT (jsonb_populate_record(NULL::aip_responsibility_plan_revision,to_jsonb(r)||jsonb_build_object('revision',2,'lifecycle','draft'))).* FROM aip_responsibility_plan_revision r")
        conn.execute('UPDATE aip_responsibility_plan_head SET current_revision=2')
    else:
        from aos_api.aip_model_runtime_store import canonical_hash
        from psycopg.types.json import Jsonb
        payload = conn.execute('SELECT payload FROM aip_runtime_policy_revision').fetchone()[0]
        payload = dict(payload, revision=2, lifecycle='suspended' if kind=='policy_suspended' else 'active',
                       killSwitchEnabled=kind=='policy_kill')
        payload['contentHash'] = canonical_hash({key:value for key,value in payload.items()
            if key not in {'tenant','revision','contentHash','createdBy','createdAt'}})
        conn.execute("""INSERT INTO aip_runtime_policy_revision
            SELECT (jsonb_populate_record(NULL::aip_runtime_policy_revision,
                to_jsonb(r)||%s::jsonb)).* FROM aip_runtime_policy_revision r""",
            (Jsonb(dict(revision=2, lifecycle=payload['lifecycle'], payload=payload,
                        content_hash=payload['contentHash'])),))
        conn.execute('UPDATE aip_runtime_policy_head SET current_revision=2')
    conn.execute('SET ROLE aos_runtime')
    result=read(sources)
    assert (not result.roles) if kind=='role_draft' else (not result.policies)
