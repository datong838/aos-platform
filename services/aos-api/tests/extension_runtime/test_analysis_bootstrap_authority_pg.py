"""Current identity in isolated migrated PG; fixture identities grant no live rights."""
import pytest
from psycopg.types.json import Jsonb
from test_product_event_current_approval_pg import governed,service_case,stored,pair,body
from aos_api.ecommerce_growth_cutover_proposal_gate import action_snapshot_from_row
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def review_identity(governed):
    conn,_=governed
    row=dict(id='ecommerce_analysis_bootstrap',name='analysis initialization',object_type='Task',
             parameters=[],required_markings=[],submission_criteria=[])
    conn.execute('RESET ROLE')
    conn.execute('''INSERT INTO meta_action_type(id,name,object_type,parameters,required_markings,submission_criteria)
        VALUES(%s,%s,%s,%s,%s,%s)''',(row['id'],row['name'],row['object_type'],Jsonb([]),Jsonb([]),Jsonb([])))
    conn.execute('SET LOCAL ROLE aos_runtime')
    return conn,action_snapshot_from_row(row)


def check(data,actor='fixture-approver',checker=True,scope=None):
    from aos_api.ecommerce_analysis_bootstrap_authority import require_current_bootstrap_review_identity
    conn,snapshot=data
    return require_current_bootstrap_review_identity(transaction=HostTransaction(conn),
        scope=scope or TenantScope('org-org','dev-project'),actor=actor,maker='fixture-maker',
        action_snapshot=snapshot,checker=checker)


def test_current_distinct_reviewer_and_maker(review_identity):
    assert check(review_identity)==('approver',)
    assert check(review_identity,actor='fixture-maker',checker=False)==('operator',)


@pytest.mark.parametrize('fault',['revoked','wrong-role','maker-revoked','snapshot','missing-action','self-review','wrong-maker','scope','remote'])
def test_current_identity_rejects_drift(review_identity,fault,monkeypatch):
    conn,_=review_identity
    conn.execute('RESET ROLE')
    if fault=='revoked':conn.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'")
    elif fault=='wrong-role':conn.execute("UPDATE meta_membership SET role='viewer' WHERE subject='fixture-approver'")
    elif fault=='maker-revoked':conn.execute("DELETE FROM meta_membership WHERE subject='fixture-maker'")
    elif fault=='snapshot':conn.execute("UPDATE meta_action_type SET name='changed' WHERE id='ecommerce_analysis_bootstrap'")
    elif fault=='missing-action':conn.execute("DELETE FROM meta_action_type WHERE id='ecommerce_analysis_bootstrap'")
    elif fault=='remote':monkeypatch.setenv('AOS_OPENFGA_API_URL','http://fixture.invalid')
    conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises((PermissionError,ValueError)):
        check(review_identity,actor='fixture-maker' if fault=='self-review' else 'fixture-approver',
              checker=fault!='wrong-maker',scope=TenantScope('dev-org','dev-project') if fault=='scope' else None)


@pytest.mark.parametrize('missing',[None,'fixture-maker','fixture-approver'])
def test_review_requires_markings_for_both_identities(review_identity,missing):
    conn,snapshot=review_identity
    from aos_api.aip_budget_reservation_store import canonical_hash
    snapshot['requiredMarkings']=['restricted-bootstrap']
    snapshot['revisionHash']=canonical_hash({k:v for k,v in snapshot.items() if k!='revisionHash'})
    conn.execute('RESET ROLE')
    conn.execute("UPDATE meta_action_type SET required_markings=%s WHERE id='ecommerce_analysis_bootstrap'",(Jsonb(snapshot['requiredMarkings']),))
    for identity in ('fixture-maker','fixture-approver'):
        if identity!=missing:
            conn.execute("INSERT INTO authz_tuple(org_id,project_id,user_key,relation,object_key) VALUES('org-org','dev-project',%s,'bearer','marking:restricted-bootstrap')",('user:'+identity,))
    conn.execute('SET LOCAL ROLE aos_runtime')
    if missing:
        with pytest.raises(PermissionError,match='marking denied'):check(review_identity)
    else:assert check(review_identity)==('approver',)
