"""Reconcile original staging readiness on the restored volume, without mutations."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import release_transition as T
from aos_api.extension_runtime.configuration_stage_preflight import (
    configuration_source_acl_ready, configuration_stage_ready,
)

TASK = Path(__file__).resolve().parent
OUTPUT = TASK / 'configuration-stage-recovery-audit.json'
SOURCES = ('aip_responsibility_plan_head', 'aip_responsibility_plan_revision',
           'aip_production_contract_receipt')


def inspect():
    with T.factory() as conn:
        conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        source_rows = conn.execute('''SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,
            pg_has_role(session_user,c.relowner,'MEMBER') AS owns,
            has_table_privilege('aos_runtime',c.oid,'SELECT') AS readable,
            has_table_privilege('aos_runtime',c.oid,'INSERT') AS insertable,
            has_table_privilege('aos_runtime',c.oid,'UPDATE') AS updatable,
            has_table_privilege('aos_runtime',c.oid,'DELETE') AS deletable,
            has_table_privilege('aos_runtime',c.oid,'TRUNCATE') AS truncatable
            FROM pg_class c WHERE c.oid=ANY(ARRAY[
            to_regclass('public.aip_responsibility_plan_head'),
            to_regclass('public.aip_responsibility_plan_revision'),
            to_regclass('public.aip_production_contract_receipt')]) ORDER BY c.relname''').fetchall()
        assert {row['relname'] for row in source_rows} == set(SOURCES)
        functions = conn.execute('''SELECT p.proname,p.prosecdef,
            has_function_privilege('aos_configuration_stage_api',p.oid,'EXECUTE') AS stage_execute,
            has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_execute
            FROM pg_proc p WHERE p.proname IN (
            'extension_configuration_stage_enqueue_a0v_037',
            'extension_configuration_stage_query_a0v_037',
            'extension_configuration_stage_lookup_a0v_038') ORDER BY p.proname''').fetchall()
        assert len(functions) == 3
        role = conn.execute('''SELECT rolname,rolcanlogin,rolsuper,rolbypassrls,rolinherit
            FROM pg_roles WHERE rolname='aos_configuration_stage_transport_20260914' ''').fetchone()
        read_only = conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']
        assert read_only == 'on'
        source_ready = configuration_source_acl_ready(conn)
        conn.rollback()
        # The original selector requires an idle connection. Read-only is session
        # default for this audit; avoid pretending a writer is safe based on RLS alone.
        conn.execute('SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY')
        conn.commit()
        stage_ready = configuration_stage_ready(conn)
        conn.rollback()
        return {'sourceAcl': source_rows, 'fixedApiFunctions': functions,
            'retainedTransportRole': role, 'sourceAclReady': source_ready,
            'originalStagePreflightReady': stage_ready,
            'unsafeSourcePrivileges': {row['relname']: [key for key in
                ('insertable','updatable','deletable','truncatable') if row[key]]
                for row in source_rows}, 'sourceReadTransactionReadOnly': True}


if __name__ == '__main__':
    assert not OUTPUT.exists(), 'Existing evidence: reconcile only'
    identity = T.H.preflight(TASK / 'private/restored-identity.json')
    first, second = inspect(), inspect()
    assert first == second
    state = T.ROOT.parent / '.aos-recovery-20260913/state/configuration-stage-deployment'
    report = {'observedAt': datetime.now(timezone.utc).isoformat(),
        'head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=T.ROOT, text=True).strip(),
        'volume': identity['volume'], 'scope': ['org-org','dev-project'],
        'observations': first, 'independentReadsStable': True,
        'declaredIdentityFileExists': {name: (state/name).is_file() for name in
            ('configuration-stage-main-identity.json','configuration-stage-clone-identity.json')},
        'historicalCredentialFilesOpened': False, 'credentialValuesEmitted': False,
        'businessWrites': 0, 'privilegeChanges': 0,
        'hostStarted': False, 'fullRestorationAccepted': False,
        'sourceSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with OUTPUT.open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'sourceAclReady': first['sourceAclReady'],
        'originalStagePreflightReady': first['originalStagePreflightReady'],
        'unsafeSourcePrivileges': first['unsafeSourcePrivileges'],
        'declaredIdentityFileExists': report['declaredIdentityFileExists']}))
