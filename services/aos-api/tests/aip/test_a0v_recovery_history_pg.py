import os
import pytest
from test_aip_budget_reservation_pg import database,runtime_connection
from aos_api import qyh_cron_scheduler as scheduler
from aos_api.tenant_scope import TenantScope

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PG opt-in')


def test_history_saved_input_is_bound_to_same_tenant(database,monkeypatch):
    database.owner.execute('CREATE TABLE meta_schedule_run (LIKE public.meta_schedule_run INCLUDING ALL)')
    database.owner.execute('ALTER TABLE meta_schedule_run ADD COLUMN executor_stopped boolean NOT NULL DEFAULT false')
    database.owner.execute('CREATE TABLE ecommerce_ingress_command(org_id text,project_id text,run_id text)')
    database.owner.execute('GRANT SELECT ON meta_schedule_run,ecommerce_ingress_command TO aos_runtime')
    for index,run in enumerate(('ready','canary-only','unknown')):
        database.owner.execute("INSERT INTO meta_schedule_run(id,org_id,project_id,schedule_id,scheduled_for,trigger,status,finished_at,executor_stopped) VALUES(%s,'org-org','dev-project','s',NOW()+(%s * interval '1 second'),'manual','failed',NOW(),%s)",(run,index,run!='unknown'))
    database.owner.execute("INSERT INTO ecommerce_ingress_command VALUES('org-org','dev-project','ready'),('dev-org','dev-project','canary-only'),('org-org','dev-project','unknown')")
    monkeypatch.setattr(scheduler,'connect',runtime_connection(database))
    rows=scheduler.list_runs(TenantScope('org-org','dev-project'),'s')
    hints={row['id']:row['recovery'] for row in rows}
    assert hints=={'ready':{'candidate':True,'reason':'ready'},'canary-only':{'candidate':False,'reason':'input_missing'},'unknown':{'candidate':False,'reason':'executor_unknown'}}
    assert len(scheduler.list_runs(TenantScope('org-org','dev-project'),'s',limit=1))==1
    assert scheduler.list_runs(TenantScope('dev-org','dev-project'),'s')==[]
