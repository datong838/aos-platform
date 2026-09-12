"""Full isolated clone, rollback-only negative authority checks."""
import os
from pathlib import Path
import sys
import pytest
import psycopg
from psycopg import sql

pytestmark=pytest.mark.skipif(os.getenv('AOS_CONFIGURED_RETIREMENT_TEST')!='1',reason='explicit complete clone required')
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
from a0v_configured_retirement_acceptance import connect,CLONE,INSTALLATION


@pytest.mark.parametrize('case',['valid','unreleased','unresolved','enable_history','wrong_config','wrong_tenant','wrong_revision','missing_proof','binding_revision','epoch'])
def test_retirement_requires_exact_disabled_unactivated_authority(case):
    with connect(CLONE) as conn:
        with conn.transaction():
            assert conn.execute('SELECT current_revision FROM bundle_installation WHERE installation_id=%s',(INSTALLATION,)).fetchone()['current_revision']==5
            if case=='unreleased':
                conn.execute('UPDATE extension_runtime_resource_lease SET observed_release=false WHERE operation_id IN (SELECT operation_id FROM extension_runtime_operation WHERE installation_id=%s)',(INSTALLATION,))
            if case in ('unresolved','enable_history'):
                conn.execute('UPDATE extension_runtime_operation SET status=%s,phase=%s WHERE installation_id=%s AND kind=\'enable\'',('accepted' if case=='unresolved' else 'succeeded','accepted' if case=='unresolved' else 'succeeded',INSTALLATION))
            if case=='wrong_config':
                conn.execute("UPDATE extension_runtime_binding SET config_ref=jsonb_set(config_ref,'{hash}',to_jsonb(%s::text)) WHERE installation_id=%s",('sha256:'+'b'*64,INSTALLATION))
            if case=='missing_proof':conn.execute("UPDATE extension_runtime_operation SET status='failed' WHERE installation_id=%s AND kind='disable'",(INSTALLATION,))
            if case=='binding_revision':conn.execute('UPDATE extension_runtime_binding SET revision=revision+1 WHERE installation_id=%s',(INSTALLATION,))
            if case=='epoch':conn.execute('UPDATE extension_runtime_binding SET execution_epoch=execution_epoch+1 WHERE installation_id=%s',(INSTALLATION,))
            conn.execute(sql.SQL('SET LOCAL SESSION AUTHORIZATION {}').format(sql.Identifier('aos_a0v_installation_20260912')))
            conn.execute('SET LOCAL ROLE aos_app')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id','dev-project',true)",('dev-org' if case=='wrong_tenant' else 'org-org',))
            statement='SELECT * FROM extension_runtime_uninstall_commit_ar2_018(%s,%s,%s)'
            parameters=(INSTALLATION,4 if case=='wrong_revision' else 5,'a0v-ecommerce-growth-1.4-runtime-owner')
            if case=='valid':
                result=conn.execute(statement,parameters).fetchone()
                assert result['applied'] is True
                authority=result['receipt_data']['authorityData']
                assert authority['retirementKind']=='configured_unactivated'
                assert authority['configRef']['configurationId']=='5cc4bf8e-770c-4a23-8ef2-c6a523482017'
                assert authority['disableOperationId']=='294359fc-4a51-4406-994f-bdc85e312881'
            else:
                with pytest.raises(psycopg.Error) as error:conn.execute(statement,parameters)
                assert error.value.sqlstate==('40001' if case in ('wrong_tenant','wrong_revision') else '55000')
            raise psycopg.Rollback()
