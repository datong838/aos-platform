import importlib.util
import os
from types import SimpleNamespace
import pytest
from psycopg import errors
from test_aip_budget_reservation_pg import database, ROOT

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PG opt-in')


def test_existing_runs_remain_unknown_and_proven_stop_prevents_downgrade(database):
    database.owner.execute('CREATE TABLE meta_schedule_run(id text PRIMARY KEY)')
    database.owner.execute("INSERT INTO meta_schedule_run VALUES('historical')")
    spec=importlib.util.spec_from_file_location('stopped_migration',ROOT/'alembic/versions/a0v_008_schedule_executor_stopped.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=database.owner.execute)
    migration.upgrade()
    assert database.owner.execute('SELECT executor_stopped FROM meta_schedule_run').fetchone()['executor_stopped'] is False
    migration.downgrade();migration.upgrade()
    with pytest.raises(errors.NotNullViolation),database.owner.transaction():
        database.owner.execute('UPDATE meta_schedule_run SET executor_stopped=NULL')
    database.owner.execute('UPDATE meta_schedule_run SET executor_stopped=true')
    with pytest.raises(errors.ObjectNotInPrerequisiteState),database.owner.transaction():
        migration.downgrade()
    assert database.owner.execute('SELECT executor_stopped FROM meta_schedule_run').fetchone()['executor_stopped'] is True
