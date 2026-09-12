"""Explicit opt-in, rollback-only checks on the isolated known pre-retirement state."""
import importlib.util
import os
from pathlib import Path
import pytest
import psycopg
from psycopg import sql

pytestmark = pytest.mark.skipif(os.getenv('AOS_NEVER_ENABLED_RETIRE_TEST') != '1', reason='explicit isolated acceptance required')
ROOT = Path(__file__).resolve().parents[4]
INSTALLATION = '3d267738-ba0a-49ef-812b-d6b72d3374fd'


@pytest.mark.parametrize('case', ['valid','configuration','unreleased','unresolved','enable_history','wrong_tenant','wrong_revision'])
def test_actual_database_retirement_branch_rolls_back(case):
    spec=importlib.util.spec_from_file_location('retire_first',ROOT/'scripts/a0v_canonical_ecommerce_first_install.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    connect=module.container_database_connect_factory(context='colima-aos-extension',container='aos-a0v-recovery-pg',database_name='aos_meta_head')
    with connect() as conn:
        with conn.transaction():
            state=conn.execute('SELECT current_revision FROM bundle_installation WHERE installation_id=%s',(INSTALLATION,)).fetchone()
            assert state['current_revision']==7, 'acceptance is only valid before exact retirement'
            if case=='configuration':
                conn.execute("UPDATE extension_runtime_binding SET config_ref='{}' WHERE installation_id=%s",(INSTALLATION,))
            elif case=='unreleased':
                conn.execute("UPDATE extension_runtime_resource_lease SET observed_release=false WHERE operation_id IN (SELECT operation_id FROM extension_runtime_operation WHERE installation_id=%s)",(INSTALLATION,))
            elif case in {'unresolved','enable_history'}:
                conn.execute("UPDATE extension_runtime_operation SET status=%s,kind=%s WHERE installation_id=%s AND operation_id=%s",
                    ('running' if case=='unresolved' else 'failed','runtime-verify' if case=='unresolved' else 'enable',INSTALLATION,'ba9af262-a5bb-4448-a0bf-d393317dabe2'))
            conn.execute(sql.SQL('SET LOCAL SESSION AUTHORIZATION {}').format(sql.Identifier('aos_a0v_installation_20260912')))
            conn.execute('SET LOCAL ROLE aos_app')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id','dev-project',true)",('dev-org' if case=='wrong_tenant' else 'org-org',))
            statement='SELECT * FROM extension_runtime_uninstall_commit_ar2_018(%s,%s,%s)'
            parameters=(INSTALLATION,6 if case=='wrong_revision' else 7,'a0v-ecommerce-growth-1.4-runtime-owner')
            if case=='valid':
                result=conn.execute(statement,parameters).fetchone()
                assert result['applied'] is True
                assert result['receipt_data']['authorityData']['retirementKind']=='never_enabled'
            else:
                with pytest.raises(psycopg.Error) as caught: conn.execute(statement,parameters)
                assert caught.value.sqlstate == ('40001' if case in {'wrong_tenant','wrong_revision'} else '55000')
            raise psycopg.Rollback()
