"""Read original experiment only; never replay its operations or count pytest DBs."""
import ast
import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/aos-api'))
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractNotFound
from aos_api.tenant_scope import TenantScope

OUT = Path(__file__).parent
SCOPE = TenantScope('org-org', 'dev-project')
TARGET = 'qyh-source-boundary-clone-20261011'
DB = 'qyh_source_contract_20261011'


@contextmanager
def connection(scope):
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=DB,
                         user='qyh_restored_api_login', row_factory=dict_row) as conn:
        conn.read_only = True
        conn.execute('SET LOCAL ROLE aos_runtime')
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
        identity = conn.execute("SELECT current_database() AS db,current_user AS role,current_setting('transaction_read_only') AS readonly,system_identifier::text AS cluster FROM pg_control_system()").fetchone()
        assert identity == {'db': DB, 'role': 'aos_runtime', 'readonly': 'on', 'cluster': '7695416748450308141'}
        yield conn


def observe(scope):
    store = AipProductionContractStore(connection)
    with connection(scope) as conn:
        receipts = conn.execute("SELECT operation,count(*) AS n FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND created_by='clone:test' GROUP BY operation ORDER BY operation", scope.key).fetchall()
        facts = {}
        for name, query in {
            'frozenEvalRevisions': "SELECT count(*) AS n FROM aip_eval_contract_revision WHERE org_id=%s AND project_id=%s AND lifecycle='frozen'",
            'gateSets': "SELECT count(*) AS n FROM aip_media_gate_set_decision WHERE org_id=%s AND project_id=%s",
            'mediaProfiles': "SELECT count(*) AS n FROM aip_media_gate_profile_revision WHERE org_id=%s AND project_id=%s",
            'reviewRules': "SELECT count(*) AS n FROM aip_review_rule_revision WHERE org_id=%s AND project_id=%s",
            'freshAvailableSkillBindings': "SELECT count(*) AS n FROM aip_skill_binding WHERE org_id=%s AND project_id=%s AND status='active' AND readiness='available' AND dependency_snapshot_hash IS NOT NULL AND readiness_expires_at>clock_timestamp()",
        }.items():
            facts[name] = conn.execute(query, scope.key).fetchone()['n']
        runs = conn.execute("SELECT status,count(*) AS n FROM aip_task_run WHERE org_id=%s AND project_id=%s GROUP BY status ORDER BY status", scope.key).fetchall()
        tasks = conn.execute("SELECT status,count(*) AS n FROM aip_task WHERE org_id=%s AND project_id=%s GROUP BY status ORDER BY status", scope.key).fetchall()
    try:
        context = store.get_production_context(scope, 'ctx-daeec3f5a06049a08783')
        plan = store.get_responsibility_plan(scope, context.responsibility_plan_ref.resource_id, context.responsibility_plan_ref.revision)
        with connection(scope) as conn:
            task = conn.execute('SELECT version,status FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s', (*scope.key, context.task_id)).fetchone()
        dependency = {'task': task, 'historicalContextReadiness': context.readiness.value,
                      'planId': plan.plan_id, 'planRevision': plan.revision,
                      'planLifecycle': plan.lifecycle.value, 'planReadiness': plan.readiness.value,
                      'planBlockers': [b.code for b in plan.blockers]}
    except ProductionContractNotFound:
        dependency = {'originalContextVisible': False}
    return {'scope': scope.key, 'receiptOperations': receipts, 'facts': facts,
            'runStates': runs, 'taskStates': tasks, 'compileDependencies': dependency}


def main():
    assert not (OUT / 'current.json').exists(), 'Existing readback: reconcile, never overwrite'
    identity = json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',
        '--format','{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}', TARGET], text=True))
    assert identity['Id'] == '381ac0fd489c72a5cad26a962dd59ba749d027bb61ab779703d1eb4bdb197b93'
    assert identity['Mounts'] == [] and identity['Ports'] == {'5432/tcp': [{'HostIp':'127.0.0.1','HostPort':'18431'}]}
    source = ROOT / 'services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py'
    catalog = next(ast.literal_eval(node.value) for node in ast.parse(source.read_text()).body
                   if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CONTRACT_OPERATIONS' for t in node.targets))
    first, second = observe(SCOPE), observe(SCOPE)
    assert first == second
    canary = observe(TenantScope('dev-org','dev-project'))
    assert canary['receiptOperations'] == [] and canary['compileDependencies'] == {'originalContextVisible': False}
    actual = {r['operation'] for r in first['receiptOperations']}
    result = {'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'originalExperiment': first, 'canary': canary,
              'catalogOperations': len(catalog), 'actualOperationKinds': len(actual),
              'remaining': sorted(set(catalog)-actual), 'independentReadbacksEqual': True,
              'recentPytestReceiptsCountedHere': False, 'databaseWrites':0,
              'wholeSourceCompatibilityAccepted':False, 'businessRestorationAccepted':False}
    with (OUT / 'current.json').open('x') as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'actualOperationKinds':len(actual),'facts':first['facts'],'compile':first['compileDependencies'],'remaining':result['remaining']},ensure_ascii=False))


if __name__ == '__main__':
    main()
