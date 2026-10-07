"""Actual original approved test request, runtime INSERT and hold; drift window rollback."""
from pathlib import Path
import json
from contextlib import contextmanager
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row
import pytest
from legal_eval_bucket_application import create_application
from tests.aip.test_budget_cost_consumer_pg import caller
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore,ModelEvalBudgetBlocked
from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope,apply_transaction_scope
pytest_plugins=('tests.conftest',)
def test_eval_hold_rejects_missing_shared_buckets(caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path):
    create_application(caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path)
    base=Path(__file__).parent;a=json.loads((base/'legal-eval-bucket-application.json').read_text());scope=TenantScope('org-org','dev-project')
    with psycopg.connect(get_dsn(),row_factory=dict_row) as admin:
        event=admin.execute('SELECT approval_event_id FROM aip_action_approval_event WHERE proposal_id=%s',(a['proposal_id'],)).fetchone()['approval_event_id']
    @contextmanager
    def tx():
        with psycopg.connect(get_dsn(),row_factory=dict_row) as c:
            c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ WRITE');c.execute('SET LOCAL ROLE aos_runtime');apply_transaction_scope(c,scope)
            try:yield c
            finally:c.rollback()
    store=AipModelEvalBudgetReservationStore()
    with tx() as c:
        h=store.hold(c,scope,a['request_id'],event)
        replay=store.hold(c,scope,a['request_id'],event)
        assert replay['reservation_id']==h['reservation_id']
        assert c.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',(a['request_id'],)).fetchone()['n']==1
        row=c.execute('SELECT * FROM aip_model_eval_budget_reservation WHERE reservation_id=%s',(h['reservation_id'],)).fetchone()
        c.execute('UPDATE aip_budget_bucket SET held_minor=0,version=version+1,updated_at=clock_timestamp() WHERE org_id=%s AND project_id=%s',scope.key)
        with pytest.raises(ModelEvalBudgetBlocked,match='bucket'):
            store.hold(c,scope,a['request_id'],event)
    with tx() as c:
        assert c.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',(a['request_id'],)).fetchone()['n']==0
        row=dict(row)
        cols=list(row);values=[Jsonb(v) if isinstance(v,dict) else v for v in row.values()]
        c.execute(sql.SQL('INSERT INTO aip_model_eval_budget_reservation ({}) VALUES ({})').format(sql.SQL(',').join(map(sql.Identifier,cols)),sql.SQL(',').join(sql.Placeholder() for _ in cols)),values)
        try:
            with pytest.raises(ModelEvalBudgetBlocked,match='bucket'):
                store.hold(c,scope,a['request_id'],event)
        finally:
            c.rollback()
            with psycopg.connect(get_dsn(),row_factory=dict_row) as read:
                read.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY')
                count=read.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',(a['request_id'],)).fetchone()['n'];assert count==0
                (base/'eval-hold-bucket-native-rollback.json').write_text(json.dumps(dict(request_id=a['request_id'],reservation_rows=count,provider_calls=0))+'\n');read.rollback()
