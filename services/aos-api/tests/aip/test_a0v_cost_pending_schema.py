"""Rollback-only schema test against the named A0-V recovery container."""
import importlib.util
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(os.getenv('AOS_A0V_SCHEMA_TEST') != '1', reason='explicit recovery schema opt-in')


def test_pending_cost_sql_guard_and_downgrade():
    from psycopg import sql, errors
    root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(root / 'scripts'))
    try:
        from a0v_canonical_ecommerce_first_install import container_database_connect_factory
    finally:
        sys.path.pop(0)
    path = root / 'services/aos-api/alembic/versions/a0v_002_cost_pending.py'
    spec = importlib.util.spec_from_file_location('cost_pending_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connect = container_database_connect_factory(context='colima-aos-extension', container='aos-a0v-recovery-pg', database_name='aos_meta_head')
    with connect() as conn:
        try:
            schema = 'pending_test_' + uuid4().hex
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
            conn.execute('CREATE TABLE aip_budget_reservation (LIKE public.aip_budget_reservation INCLUDING CONSTRAINTS INCLUDING DEFAULTS)')
            conn.execute('CREATE TABLE aip_budget_reservation_event (LIKE public.aip_budget_reservation_event INCLUDING CONSTRAINTS INCLUDING DEFAULTS)')
            class Ops:
                def execute(self, query): conn.execute(query)
            migration.op = Ops()
            migration.upgrade()
            conn.execute('CREATE TRIGGER guard_test BEFORE UPDATE ON aip_budget_reservation FOR EACH ROW EXECUTE FUNCTION guard_ar2_budget_reservation_update()')
            conn.execute("""INSERT INTO aip_budget_reservation(org_id,project_id,reservation_id,invocation_id,operation_id,invocation_key,task_ref,policy_ref,pricing_ref,approval_ref,currency,upper_bound_minor,state,provider_request_receipt_ref,request_hash,content_hash)
                VALUES('org-org','dev-project',%s,%s,'op','key','{}','{}','{}','{}','CNY',100,'submitted','{}',%s,%s)""", (uuid4(),uuid4(),'a'*64,'sha256:'+'a'*64))
            update_suffix = ",revision=revision+1,content_hash='sha256:" + 'c'*64 + "'"
            with pytest.raises(errors.RaiseException), conn.transaction():
                conn.execute("UPDATE aip_budget_reservation SET state='cost_pending',provider_receipt_ref='{}',usage_receipt_refs='[{\"id\":1},{\"id\":1}]'" + update_suffix)
            conn.execute("UPDATE aip_budget_reservation SET state='cost_pending',provider_receipt_ref='{}',usage_receipt_refs='[{\"id\":1}]',revision=revision+1,content_hash=%s", ('sha256:'+'b'*64,))
            for change in ("state='submitted'", "state='released'", "state='settled',actual_minor=0,usage_receipt_refs='[{\"id\":2}]'", "state='settled',actual_minor=0,operation_id='changed'"):
                with pytest.raises(errors.RaiseException), conn.transaction():
                    conn.execute('UPDATE aip_budget_reservation SET ' + change + update_suffix)
            with pytest.raises(errors.RaiseException), conn.transaction():
                migration.downgrade()
            conn.execute("UPDATE aip_budget_reservation SET state='settled',actual_minor=5" + update_suffix)
            migration.downgrade()
        finally:
            conn.rollback()
