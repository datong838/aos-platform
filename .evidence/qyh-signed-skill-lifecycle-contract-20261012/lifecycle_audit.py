"""Read committed Skill lifecycle code and owned clone ACL, without execution."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent


def committed(path):
    raw = subprocess.check_output(['git', 'show', 'HEAD:' + path], cwd=ROOT)
    return raw, ast.parse(raw.decode('utf-8-sig'))


def observe():
    with psycopg.connect(host='127.0.0.1', port=18431,
                         dbname='qyh_source_contract_20261011', user='aos_app',
                         row_factory=dict_row) as conn:
        conn.isolation_level = IsolationLevel.REPEATABLE_READ
        conn.read_only = True
        assert conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'
        assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == '7695416748450308141'
        if not conn.execute("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_aip_eval_writer') AS present").fetchone()['present']:
            return {'rolePresent': False, 'tablePrivileges': None}
        rows = conn.execute("""SELECT table_name,
            has_table_privilege('aos_aip_eval_writer', table_name, 'SELECT') AS can_select,
            has_table_privilege('aos_aip_eval_writer', table_name, 'INSERT') AS can_insert,
            has_table_privilege('aos_aip_eval_writer', table_name, 'UPDATE') AS can_update
            FROM unnest(ARRAY['aip_eval_run','aip_eval_run_event',
                'aip_eval_report_revision','aip_eval_execution_receipt',
                'aip_eval_case_execution_proof']) AS table_name ORDER BY table_name""").fetchall()
        return {'rolePresent': True, 'tablePrivileges': rows}


if __name__ == '__main__':
    assert not (OUT / 'observed.json').exists(), 'Do not replace an observation'
    container = json.loads(subprocess.check_output([
        'docker', '--context', 'colima-aos-extension', 'inspect',
        'qyh-source-boundary-clone-20261011'], text=True))[0]
    assert container['Id'] == '381ac0fd489c72a5cad26a962dd59ba749d027bb61ab779703d1eb4bdb197b93'
    assert container['Image'] == 'sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
    assert container['State']['Running'] and not container['Mounts']
    prefix = 'services/aos-api/aos_api/'
    evidence = {}
    for name in ['aip_eval_runner.py', 'aip_eval_writer_atomic.py',
                 'aip_eval_writer_authority_preflight.py', 'aip_eval_authority_store.py']:
        raw, tree = committed(prefix + name)
        findings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name in {'run', 'persist_signed_skill_eval_report',
                                 'preflight_skill_eval_writer_authority',
                                 'create_eval_run', 'transition_eval_run'}:
                    calls = []
                    for call in ast.walk(node):
                        if isinstance(call, ast.Call):
                            func = call.func
                            label = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ''
                            if label in {'commit', '_append_report', 'transition_eval_run',
                                         'preflight_skill_eval_writer_authority'}:
                                calls.append({'name': label, 'line': call.lineno})
                    findings.append({'function': node.name, 'line': node.lineno, 'calls': calls})
        evidence[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'functions': findings}
    first, second = observe(), observe()
    assert first == second
    result = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'code': evidence, 'writerTablePrivileges': first, 'twoViewsEqual': True,
              'databaseReadOnly': True, 'isolation': 'repeatable read',
              'businessExecutions': 0, 'currentDatabaseChanged': False,
              'formalProducerImplemented': False}
    with (OUT / 'observed.json').open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'writerTablePrivileges': first, 'twoViewsEqual': True}))
