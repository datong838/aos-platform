"""Rollback-only faithful-clone rehearsal of the original SQL protocol.

Session authorization is test impersonation, not formal LOGIN authentication.
"""
import ast
import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'services/aos-api'),
               str(ROOT / '.evidence/qyh-full-system-restoration-20261011')]
import promote_stage_transport as S
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.tenant_scope import TenantScope

R = Path(__file__).resolve().parent
TARGET = 'qyh-source-boundary-clone-20261011'
SOURCE = ROOT / 'services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py'


def main():
    assert not (R / 'intent.json').exists(), 'Existing attempt: reconcile, do not replay'
    restored = json.loads((ROOT / '.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    item = json.loads(S.run(['inspect', '--format', '{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}', TARGET]))
    assert item['Id'] == restored['container']['Id'] and item['Mounts'] == []
    assert item['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18431'}]}
    before = S.P.M.fingerprint(TARGET)
    metadata = S.D.metadata(TARGET)
    tree = ast.parse(SOURCE.read_text())
    catalog = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
               if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
               and n.targets[0].id in ('PLAN_OPERATIONS', 'CONTRACT_OPERATIONS')}
    fixture = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'protocol')
    expressions = [n.args[0] for n in ast.walk(fixture) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute) and n.func.attr == 'execute'
                   and n.args and isinstance(n.args[0], ast.JoinedStr)]
    assert len(expressions) == 1, 'Original protocol SQL changed: review before execution'
    names = {'plan_role', 'content_role', 'contract_role',
             'plan_operation_sql', 'contract_operation_sql'}
    assert all(isinstance(n.value, ast.Name) and n.value.id in names
               and n.conversion == -1 and n.format_spec is None
               for n in ast.walk(expressions[0]) if isinstance(n, ast.FormattedValue)), 'Unexpected executable interpolation'
    token = 'qyh_rehearsal_' + uuid4().hex[:12]
    roles = {p: token + '_' + p for p in ('plan', 'content', 'contract')}
    with (R / 'intent.json').open('x') as out:
        json.dump({'containerId': item['Id'], 'cluster': restored['cloneIdentity']['cluster'],
                   'protocolHash': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                   'transactionCommitAllowed': False, 'testImpersonationOnly': True}, out, indent=2)
    conn = psycopg.connect(host='127.0.0.1', port=18431, dbname='aos_meta_head', user='aos_app', row_factory=dict_row)
    results = []
    try:
        assert conn.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster'] == restored['cloneIdentity']['cluster']
        context = {p + '_role': roles[p] for p in roles}
        for kind in ('plan', 'contract'):
            context[kind + '_operation_sql'] = sql.SQL(',').join(sql.Literal(x) for x in catalog[kind.upper() + '_OPERATIONS']).as_string(conn)
        guard = eval(compile(ast.Expression(expressions[0]), str(SOURCE), 'eval'), {'__builtins__': {}}, context)
        for role in roles.values():
            conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(role)))
            conn.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(role)))
        tables = ('aip_responsibility_plan_head', 'aip_responsibility_plan_revision', 'aip_production_contract_receipt')
        for table in tables:
            conn.execute(sql.SQL('REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {} FROM aos_runtime').format(sql.Identifier(table)))
        for table, privileges, purpose in (
            (tables[0], 'SELECT,INSERT,UPDATE', 'plan'),
            (tables[1], 'SELECT,INSERT', 'plan'),
            (tables[2], 'SELECT,INSERT', 'plan'),
            (tables[2], 'SELECT,INSERT', 'content'),
            (tables[2], 'SELECT,INSERT', 'contract'),
        ):
            role = roles[purpose]
            conn.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(role)))
            conn.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier(token + '_' + purpose + '_' + str(tables.index(table))), sql.Identifier(table), sql.Identifier(role)))
        conn.execute(guard)
        for i, table in enumerate(tables):
            events = 'INSERT OR UPDATE OR DELETE' if i == 0 else 'INSERT'
            conn.execute(sql.SQL('CREATE TRIGGER {} BEFORE {} ON {} FOR EACH ROW EXECUTE FUNCTION s3owe_guard()').format(sql.Identifier(token + '_' + str(i)), sql.SQL(events), sql.Identifier(table)))
        store = AipProductionContractStore()

        def probe(label, role, operation, expected, org='org-org'):
            conn.execute('RESET SESSION AUTHORIZATION')
            conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(role)))
            conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
            state = None
            try:
                with conn.transaction():
                    key = token + '-' + label
                    if operation == 'head':
                        conn.execute('INSERT INTO aip_responsibility_plan_head(org_id,project_id,plan_id,current_revision,version) VALUES(%s,%s,%s,1,1)', (org, 'dev-project', key))
                    else:
                        store._receipt(conn, TenantScope(org, 'dev-project'), operation, key, 'a' * 64,
                                       {'resourceType': 'ResponsibilityPlanRevision', 'resourceId': key, 'revision': 1, 'contentHash': 'a' * 64}, 'clone:test')
            except psycopg.Error as error:
                state = error.sqlstate
            results.append({'label': label, 'sqlstate': state, 'expected': expected})
            assert state == expected, results[-1]

        probe('runtime-head', 'aos_runtime', 'head', '42501')
        probe('runtime-receipt', 'aos_runtime', 'responsibility_plan.create', '42501')
        probe('plan-head', roles['plan'], 'head', None)
        probe('plan-receipt', roles['plan'], 'responsibility_plan.create', None)
        probe('content-receipt', roles['content'], 'content_draft.register', None)
        probe('contract-receipt', roles['contract'], 'task_brief.create', None)
        probe('content-forged-plan', roles['content'], 'responsibility_plan.create', '42501')
        probe('contract-forged-content', roles['contract'], 'content_draft.register', '42501')
        probe('plan-forged-contract', roles['plan'], 'task_brief.create', '42501')
        probe('unknown-operation', roles['contract'], 'unregistered.operation', '42501')
        probe('canary', roles['plan'], 'responsibility_plan.create', '42501', org='dev-org')
    finally:
        conn.rollback()
        conn.close()
    assert S.P.M.fingerprint(TARGET) == before, 'Data changed: reconcile only'
    assert S.D.metadata(TARGET) == metadata, 'Metadata changed: reconcile only'
    result = {'cases': results, 'full647RollbackExact': True, 'allOriginalMetadataExact': True,
              'currentDatabaseTouched': False, 'formalLoginAuthenticated': False,
              'originalStoreFullCompatibilityAccepted': False, 'fullRestorationAccepted': False}
    with (R / 'result.json').open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
