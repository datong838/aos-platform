import os
from uuid import uuid4

import psycopg
import pytest
from aos_api.extension_runtime.runtime_resource_health import current_resources_live
from aos_api.extension_runtime.runtime_view import RuntimeViewReader
from test_runtime_installations_api import _ReadyRuntimeConnection,_Result,_InstallationReader,INSTALLATION_ID


@pytest.mark.parametrize('count,live',[(0,False),(3,False),(3,None)])
def test_lost_resources_close_ui_before_resolver(count,live):
    class Connection(_ReadyRuntimeConnection):
        def execute(self,query,params):
            if 'FROM extension_runtime_resource_lease' in query:return _Result({'resource_count':count,'live':live})
            return super().execute(query,params)
    reader=RuntimeViewReader(installation_reader=_InstallationReader(),connect_factory=Connection,
        ui_session_resolver=lambda **kw:pytest.fail('lost resources reached UI resolver'))
    view=reader.get_installation(installation_id=INSTALLATION_ID,org_id='org-org',project_id='dev-project',roles=['admin'],markings=[])
    assert view.effectiveState=='needs_attention' and view.ui is None
    assert view.allowedActions==('disable',) and '恢复对账' in view.reasons[0]
    assert view.binding.enabled is True  # read projection does not rewrite facts


@pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PG required')
@pytest.mark.parametrize('defect',[None,'empty','released','expired','cleanup','container','claimed','null-expiry','operation','tenant','project','generation','installation','mixed-null'])
def test_current_exact_resource_liveness_query(defect):
    installation,generation,operation=uuid4(),uuid4(),uuid4()
    with psycopg.connect(os.environ['AOS_DATABASE_URL']) as conn:
        conn.execute('CREATE TEMP TABLE extension_runtime_operation(org_id text,project_id text,operation_id uuid,installation_id uuid,kind text,status text,phase text) ON COMMIT DROP')
        conn.execute('CREATE TEMP TABLE extension_runtime_resource_lease(org_id text,project_id text,operation_id uuid,generation uuid,observed_release boolean,cleanup_state text,container_id text,create_claimed_at timestamptz,expires_at timestamptz) ON COMMIT DROP')
        conn.execute("INSERT INTO extension_runtime_operation VALUES ('org-org','dev-project',%s,%s,'runtime-apply','succeeded','succeeded')",(operation,installation))
        if defect!='empty':
            conn.execute("INSERT INTO extension_runtime_resource_lease VALUES ('org-org','dev-project',%s,%s,false,'pending','owned-container',clock_timestamp(),clock_timestamp()+interval '5 minutes')",(operation,generation))
        statements={
            'released':"UPDATE extension_runtime_resource_lease SET observed_release=true",
            'expired':"UPDATE extension_runtime_resource_lease SET expires_at=clock_timestamp()-interval '1 second'",
            'cleanup':"UPDATE extension_runtime_resource_lease SET cleanup_state='uncertain'",
            'container':"UPDATE extension_runtime_resource_lease SET container_id=NULL",
            'claimed':"UPDATE extension_runtime_resource_lease SET create_claimed_at=NULL",
            'null-expiry':"UPDATE extension_runtime_resource_lease SET expires_at=NULL",
            'operation':"UPDATE extension_runtime_operation SET status='failed'",
            'mixed-null':"INSERT INTO extension_runtime_resource_lease SELECT org_id,project_id,operation_id,generation,observed_release,cleanup_state,container_id,create_claimed_at,NULL FROM extension_runtime_resource_lease",
        }
        if defect in statements:conn.execute(statements[defect])
        assert current_resources_live(conn,org_id='canary' if defect=='tenant' else 'org-org',
            project_id='other' if defect=='project' else 'dev-project',
            installation_id=uuid4() if defect=='installation' else installation,
            generation=uuid4() if defect=='generation' else generation) is (defect is None)
