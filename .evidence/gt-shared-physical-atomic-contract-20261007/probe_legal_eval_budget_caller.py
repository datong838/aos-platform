"""Original Eval budget hold on real published/application sources, no execution."""
from pathlib import Path
import sys,json,tempfile,hashlib
from contextlib import contextmanager
from datetime import datetime,UTC
import psycopg
from psycopg.rows import dict_row
base=Path(__file__).resolve().parent;repo=base.parents[1];sys.path.insert(0,str(repo/'services/aos-api'))
from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore,ModelEvalBudgetBlocked
from aos_api.tenant_scope import TenantScope,apply_transaction_scope
r=json.loads((base/'legal-eval-application-result-r3.json').read_text());scope=TenantScope('org-org','dev-project')
assert r['database'].startswith('aos_test_');attempt=base/'legal-eval-budget-caller-attempt.json';assert not attempt.exists(),'prior attempt must be reconciled, never replayed'
@contextmanager
def connect(scope=scope,readonly=False):
    with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=r['database'],passfile=str(Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'),row_factory=dict_row) as c:
        c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE '+('READ ONLY' if readonly else 'READ WRITE'))
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']=='7693564235776004128'
        c.execute('SET LOCAL ROLE aos_runtime');apply_transaction_scope(c,scope)
        try:yield c
        finally:c.rollback()
def snapshot():
    with connect(readonly=True) as c:
        buckets=c.execute("SELECT bucket_kind,account_id,period_start,currency,held_minor,submitted_minor,settled_minor,unknown_minor,version FROM aip_budget_bucket ORDER BY bucket_kind,account_id,period_start,currency").fetchall()
        counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in ['aip_model_eval_budget_reservation','aip_model_eval_budget_reservation_bucket','aip_agent_run']}
        return {'buckets':buckets,'counts':counts}
with connect(readonly=True) as c:
    a=c.execute('SELECT approval_event_id FROM aip_action_approval_event WHERE proposal_id=%s',(r['proposal_id'],)).fetchall();assert len(a)==1;approval=a[0]['approval_event_id']
    assert c.execute('SELECT expires_at>clock_timestamp() AS valid FROM aip_model_eval_request WHERE request_id=%s',(r['request_id'],)).fetchone()['valid']
before=snapshot();assert before['counts']['aip_model_eval_budget_reservation']==0
store=AipModelEvalBudgetReservationStore();neg=[]
for tenant,event in [(scope,'not-an-approval'),(TenantScope('dev-org','dev-project'),approval)]:
    with connect(tenant) as c:
        try:store.hold(c,tenant,r['request_id'],event)
        except ModelEvalBudgetBlocked as exc:neg.append(str(exc))
        else:raise AssertionError('wrong approval/canary must deny')
with connect() as c:
    identity=c.execute('SELECT txid_current() AS xid,pg_backend_pid() AS pid').fetchone()
    store.hold(c,scope,r['request_id'],approval)
    assert c.execute('SELECT txid_current() AS xid,pg_backend_pid() AS pid').fetchone()==identity
    assert c.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation').fetchone()['n']==1
    c.rollback()
assert snapshot()==before
attempt.write_text(json.dumps({'status':'COMMIT_ATTEMPTED','database':r['database'],'request_id':r['request_id'],'time':datetime.now(UTC).isoformat()},indent=2)+'\n')
with connect() as c:
    held=store.hold(c,scope,r['request_id'],approval);identity=c.execute('SELECT txid_current() AS xid,pg_backend_pid() AS pid').fetchone()
    c.commit()
attempt.write_text(json.dumps({'status':'COMMIT_CONFIRMED','database':r['database'],'request_id':r['request_id'],'reservation_id':str(held['reservation_id']),'native_identity':identity},indent=2)+'\n')
with connect() as c:
    replay=store.hold(c,scope,r['request_id'],approval);assert replay['reservation_id']==held['reservation_id'];c.rollback()
after=snapshot();assert after['counts']=={'aip_model_eval_budget_reservation':1,'aip_model_eval_budget_reservation_bucket':3,'aip_agent_run':0}
with connect(readonly=True) as c:
    links=c.execute('SELECT bucket_kind,account_id,reserved_minor FROM aip_model_eval_budget_reservation_bucket WHERE reservation_id=%s ORDER BY bucket_kind',(held['reservation_id'],)).fetchall();assert len(links)==3 and all(x['reserved_minor']==10 for x in links)
    assert all(x['held_minor']==10 for x in after['buckets'])
    model_gate=c.execute("SELECT count(*) AS n FROM aip_release_gate_decision WHERE target_ref->>'assetId'=%s",(r['model_id'],)).fetchone()['n'];assert model_gate==0
with connect(TenantScope('dev-org','dev-project'),True) as c:
    assert c.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation').fetchone()['n']==0
report={'status':'ORIGINAL_LEGAL_APPLICATION_BUDGET_CALLER_VERIFIED','database':r['database'],'request_id':r['request_id'],'reservation_id':str(held['reservation_id']),'negative_gates':neg,'rollback_full_snapshot_equal':True,'commit_identity':identity,'replay_same_reservation':True,'before':before,'after':after,'links':links,'model_quality_gates':model_gate,'source_sha256':hashlib.sha256((repo/'services/aos-api/aos_api/aip_model_eval_budget_reservation.py').read_bytes()).hexdigest(),'limitations':['Original budget foundation only: no signed capacity Source/shared physical ledger/unique Intent','No Model execution or quality result','Native owned admin SCRAM then SET LOCAL runtime; not formal service identity']}
(base/'legal-eval-budget-caller.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
print(json.dumps({'status':report['status'],'hold':1,'buckets':3,'rollback':True,'replay':True,'model_execution':False}))
