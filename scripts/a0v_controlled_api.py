"""Fixed diagnostic API metadata connection plus independent controlled runtime."""
import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

from a0v_ecommerce_runtime_host import (
    ROOT, API, DEFAULT_CREDENTIALS, EXPECTED_ROLES, _configure_environment, _safe_error_chain,
)

BUNDLE_ROOT = ROOT.parent/'.aos-recovery-20260912/state/niushop-1.4-registry/signed-bundles-niushop-1.4'
TRUST_ROOTS = ROOT.parent/'.aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install/signing/trust-roots.json'
API_FLAGS = {
    'AOS_DB_MIGRATION_MODE': 'disabled',
    'AOS_QYH_CRON_ENABLED': 'false',
    'AOS_SNAPSHOT_GROUP_WORKER_ENABLED': 'false',
    'AOS_AIP_LOGIC_AUTOMATION_ENABLED': 'false',
    'AOS_AIP_TEXT_HEALTH_MAINTENANCE_ENABLED': 'false',
    'AOS_EXTENSION_RUNTIME_HOST_ENABLED': '0',
    'AOS_JDBC_SSH_PREBUILD_ENABLED': 'false',
}


def require_leases():
    path = ROOT.parent/'docs/palantier/AOS项目开发上下文/memory/leases.json'
    leases = {item['task_id']: item for item in json.loads(path.read_text())['leases']}
    lease = leases['A0V-CONTROLLED-API-START-20260913']
    if (lease['owner'] != 'm1' or lease['status'] != 'ACTIVE'
            or datetime.fromisoformat(lease['lease_expires_at']) <= datetime.now(timezone.utc)):
        raise ValueError('controlled API lease unavailable')
    if subprocess.check_output(['git','branch','--show-current'], cwd=ROOT, text=True).strip() != 'm1':
        raise ValueError('controlled API requires m1')


def configure_environment():
    require_leases()
    _configure_environment(DEFAULT_CREDENTIALS, bundle_root=BUNDLE_ROOT, trust_roots_file=TRUST_ROOTS)
    os.environ.update(API_FLAGS)


def preflight():
    configure_environment()
    sys.path.insert(0, str(API))
    from aos_api import db
    from aos_api.extension_runtime.runtime_connections import (
        runtime_web_identity_connection, runtime_worker_connection,
    )
    # Preserve the existing local diagnostic metadata connection. The Host's
    # Web isolation probe is intentionally not a functional legacy API login.
    from a0v_formal_text_model_renewal import database_connect
    from psycopg.conninfo import make_conninfo
    with database_connect('aos_meta_head')() as conn:
        metadata_dsn = make_conninfo(**conn.info.get_parameters(), password=conn.info.password)
        metadata_identity = dict(conn.execute("""SELECT session_user,current_user,current_database(),
            rolsuper,rolbypassrls FROM pg_roles WHERE rolname=session_user""").fetchone())
    if metadata_identity['current_database'] != 'aos_meta_head':
        raise ValueError('local metadata target differs')
    db.get_dsn = lambda: metadata_dsn
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.storage_ports import require_runtime_role
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.pipeline_control_service import PipelineControlServiceFactory
    from aos_api.tenant_scope import TenantScope
    identities = {'localDiagnosticMetadata': metadata_identity}
    with runtime_web_identity_connection() as conn:
        web = dict(conn.execute("SELECT session_user,current_user,current_database(),pg_has_role(session_user,'aos_runtime','MEMBER') AS runtime_member").fetchone())
        if web['session_user'] != EXPECTED_ROLES['web'] or web['current_database'] != 'aos_meta_head' or web['runtime_member'] is not False:
            raise ValueError('web identity readiness differs')
        identities['hostWebIsolationProbe'] = web
    scope = dict(org_id='org-org', project_id='dev-project')
    with consumer_connection(runtime_worker_connection, scope) as conn:
        require_runtime_role(conn, **scope, protected_tables=('public.pipeline_schedule_control_binding','public.pipeline_controlled_source_claim'))
        runtime = dict(conn.execute('SELECT session_user,current_user,current_database()').fetchone())
        if runtime['session_user'] != EXPECTED_ROLES['runtime'] or runtime['current_user'] != 'aos_runtime' or runtime['current_database'] != 'aos_meta_head':
            raise ValueError('runtime identity readiness differs')
        identities['runtime'] = runtime
    plane = build_runtime_control_plane(disable_dependent=EcommerceGrowthDisableDependent())
    if type(plane.pipeline_control_factory) is not PipelineControlServiceFactory:
        raise ValueError('pipeline factory unavailable')
    plane.pipeline_control_factory.build(TenantScope(**scope))
    return dict(outcome='CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN', at=datetime.now(timezone.utc).isoformat(),
        identities=identities, bundleRoot=str(BUNDLE_ROOT), trustRoots=str(TRUST_ROOTS), flags=API_FLAGS,
        localDiagnostic=True, productionWebIdentityComplete=False, sourceCalls=0, runsCreated=0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check','serve'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = preflight()
    except Exception as error:
        result = dict(outcome='STOPPED_FOR_INSPECTION', errorChain=_safe_error_chain(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if result['outcome'] != 'CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN':
        raise SystemExit(1)
    if args.action == 'serve':
        for name in ('httpx','httpcore'):
            logging.getLogger(name).setLevel(logging.WARNING)
        from aos_api import main as api_main
        import uvicorn
        uvicorn.run(api_main.app, host='127.0.0.1', port=18181, log_level='warning', access_log=False)


if __name__ == '__main__':
    main()
