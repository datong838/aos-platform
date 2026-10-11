"""Original Brief lifecycle through a real fixed LOGIN in a history-cloned DB."""
import ast
import argparse
import hashlib
import json
import secrets
import sys
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'services/aos-api'),
               str(ROOT / '.evidence/qyh-full-system-restoration-20261011')]
import promote_stage_transport as S
from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
from aos_api.aip_source_issuer_connection import SourceIssuerDatabaseConfig, connect_source_issuer_write
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.aip_task_store import AipTaskStore
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_task_models import CreateTaskRequest
from aos_api.aip_production_contracts import CreateBriefRequest, ReviseBriefRequest
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractIdempotencyConflict, ProductionContractNotFound
from aos_api.tenant_scope import TenantScope

R = Path(__file__).resolve().parent
TARGET = 'qyh-source-boundary-clone-20261011'
DB = 'qyh_source_contract_20261011'
ROLE = 'aos_contract_source_issuer'
SCOPE = TenantScope('org-org', 'dev-project')
TABLES = {'aip_task': 'SELECT', 'aip_task_brief_head': 'SELECT,INSERT,UPDATE',
          'aip_task_brief_revision': 'SELECT,INSERT', 'aip_production_contract_receipt': 'SELECT,INSERT'}
SOURCE_TABLES = ('aip_responsibility_plan_head', 'aip_responsibility_plan_revision', 'aip_production_contract_receipt')
PROTOCOL = ROOT / 'services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py'
PREFIX = 'contract'


def record(name, value):
    with (R / (PREFIX + '-' + name + '.json')).open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n')


@contextmanager
def runtime(scope, *, read_only):
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=DB,
                          user='qyh_restored_api_login', row_factory=dict_row) as conn:
        conn.read_only = read_only
        conn.execute('SET LOCAL ROLE aos_runtime')
        apply_asset_transaction_scope(conn, org_id=scope.org_id, project_id=scope.project_id)
        yield conn


def expect_error(kind, action, *, state=None):
    try:
        action()
    except kind as error:
        if state is not None:
            assert error.sqlstate == state
        return type(error).__name__
    raise AssertionError('Required rejection did not occur')


def main():
    global PREFIX
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume-after-table-preflight', action='store_true')
    args = parser.parse_args()
    if args.resume_after_table_preflight:
        PREFIX = 'contract-r2'
        failure = json.loads((R / 'contract-failure.json').read_text())
        assert failure == {'errorType': 'AssertionError', 'sqlstate': None, 'completedCases': [], 'unknownBusinessEffectReplayAllowed': False}
    assert not (R / (PREFIX + '-intent.json')).exists(), 'Existing attempt: reconcile only'
    restored = json.loads((ROOT / '.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    item = json.loads(S.run(['inspect', '--format', '{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}', TARGET]))
    assert item['Id'] == restored['container']['Id'] and item['Mounts'] == []
    assert item['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18431'}]}
    before = S.P.M.fingerprint(TARGET)
    metadata = S.D.metadata(TARGET)
    with psycopg.connect(host='127.0.0.1', port=18431, dbname='postgres', user='aos_app', autocommit=True) as maintenance:
        assert maintenance.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0] == restored['cloneIdentity']['cluster']
        exists = bool(maintenance.execute('SELECT 1 FROM pg_database WHERE datname=%s', (DB,)).fetchone())
        assert exists == args.resume_after_table_preflight
        assert not maintenance.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (ROLE,)).fetchone()
        assert maintenance.execute("SELECT count(*) FROM pg_stat_activity WHERE datname='aos_meta_head'").fetchone()[0] == 0
        if args.resume_after_table_preflight:
            old = json.loads((R / 'contract-intent.json').read_text())
            assert (old['containerId'], old['cluster'], old['database']) == (item['Id'], restored['cloneIdentity']['cluster'], DB)
            saved = S.P.M.DB
            try:
                S.P.M.DB = DB
                assert S.P.M.fingerprint(TARGET) == before, 'Copy differs: no business retry'
            finally:
                S.P.M.DB = saved
        record('intent', {'containerId': item['Id'], 'cluster': restored['cloneIdentity']['cluster'],
                          'database': DB, 'originalCloneDatabaseWrites': False,
                          'currentDatabaseTouched': False, 'role': ROLE,
                          'protocolHash': hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
                          'existingCopyReconciled': args.resume_after_table_preflight})
        if not args.resume_after_table_preflight:
            maintenance.execute(sql.SQL('CREATE DATABASE {} TEMPLATE aos_meta_head OWNER aos_app').format(sql.Identifier(DB)))
    private = R / 'private' / 'contract-identity'
    private.parent.mkdir(mode=0o700, exist_ok=True)
    private.mkdir(mode=0o700, exist_ok=args.resume_after_table_preflight)
    passfile = private / 'contract.pgpass'
    if not args.resume_after_table_preflight:
        with passfile.open('x') as out:
            passfile.chmod(0o600)
            out.write(f'127.0.0.1:18431:{DB}:{ROLE}:{secrets.token_hex(24)}\n')
    config = SourceIssuerDatabaseConfig('contract', BIIssuerDatabaseConfig('127.0.0.1', 18431, DB, passfile.resolve()))
    observed = []
    @contextmanager
    def contract(scope):
        with connect_source_issuer_write(config, scope) as conn:
            identity = conn.execute('SELECT session_user AS login,current_user AS role,current_database() AS db').fetchone()
            assert identity == {'login': ROLE, 'role': ROLE, 'db': DB}
            observed.append(identity)
            yield conn
    def plan_forbidden(scope):
        raise AssertionError('Contract lifecycle attempted Plan connection')
    created_role = False
    cases = []
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=DB, user='aos_app', autocommit=True, row_factory=dict_row) as admin:
        try:
            assert admin.execute("SELECT count(*) AS n FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'").fetchone()['n'] == 647
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
            created_role = True
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table in SOURCE_TABLES:
                admin.execute(sql.SQL('REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {} FROM aos_runtime').format(sql.Identifier(table)))
            for table, privileges in TABLES.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_contract_' + table), sql.Identifier(table), sql.Identifier(ROLE)))
            tree = ast.parse(PROTOCOL.read_text())
            catalog = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ('PLAN_OPERATIONS', 'CONTRACT_OPERATIONS')}
            fixture = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'protocol')
            expressions = [n.args[0] for n in ast.walk(fixture) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'execute' and n.args and isinstance(n.args[0], ast.JoinedStr)]
            assert len(expressions) == 1
            context = {'plan_role': 'aos_bi_plan_issuer', 'content_role': 'aos_content_source_issuer', 'contract_role': ROLE}
            for kind in ('plan', 'contract'):
                context[kind + '_operation_sql'] = sql.SQL(',').join(sql.Literal(x) for x in catalog[kind.upper() + '_OPERATIONS']).as_string(admin)
            assert all(isinstance(n.value, ast.Name) and n.value.id in context and n.conversion == -1 and n.format_spec is None for n in ast.walk(expressions[0]) if isinstance(n, ast.FormattedValue))
            admin.execute(eval(compile(ast.Expression(expressions[0]), str(PROTOCOL), 'eval'), {'__builtins__': {}}, context))
            for i, table in enumerate(SOURCE_TABLES):
                admin.execute(sql.SQL('CREATE TRIGGER {} BEFORE {} ON {} FOR EACH ROW EXECUTE FUNCTION s3owe_guard()').format(sql.Identifier('qyh_contract_guard_' + str(i)), sql.SQL('INSERT OR UPDATE OR DELETE' if i == 0 else 'INSERT'), sql.Identifier(table)))
            task = AipTaskStore(lambda scope: runtime(scope, read_only=False)).create_task(SCOPE, 'clone:test', 'qyh-contract-task', CreateTaskRequest(title='QYH isolated Contract compatibility'))
            store = AipProductionContractStore(lambda scope: runtime(scope, read_only=True), plan_connect_factory=plan_forbidden, contract_connect_factory=contract)
            body = CreateBriefRequest(task_id=task.id, brief_type='ecommerce.analysis', schema_ref=ResourceRef(resource_type='Schema', resource_id='ecommerce.analysis', revision='1', authority='aip'), spec={'goal': 'original QYH Contract transaction'})
            made = store.create_brief(SCOPE, 'clone:test', 'qyh-contract-create', body)
            assert store.create_brief(SCOPE, 'clone:test', 'qyh-contract-create', body).brief_id == made.brief_id
            cases.append('create-and-idempotency')
            cases.append(expect_error(ProductionContractIdempotencyConflict, lambda: store.create_brief(SCOPE, 'clone:test', 'qyh-contract-create', body.model_copy(update={'spec': {'goal': 'drift'}}))))
            revised = store.revise_brief(SCOPE, 'clone:test', made.brief_id, 'qyh-contract-revise', ReviseBriefRequest(**body.model_dump(exclude={'task_id'}), expected_version=made.version))
            frozen = store.freeze_brief(SCOPE, 'clone:test', made.brief_id, revised.version, 'qyh-contract-freeze')
            assert frozen.lifecycle.value == 'frozen' and frozen.revision == 3
            assert store.get_brief(SCOPE, made.brief_id).content_hash == frozen.content_hash
            cases.append('revise-freeze-and-runtime-readback')
            cases.append(expect_error(ProductionContractNotFound, lambda: store.get_brief(TenantScope('dev-org', 'dev-project'), made.brief_id)))
            counts = admin.execute('SELECT (SELECT count(*) FROM aip_task_brief_head) AS heads,(SELECT count(*) FROM aip_task_brief_revision) AS revisions,(SELECT count(*) FROM aip_production_contract_receipt) AS receipts').fetchone()
            admin.execute("CREATE FUNCTION qyh_contract_rollback_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key='qyh-contract-rollback' THEN RAISE EXCEPTION 'CONTRACT_FORCED_ROLLBACK'; END IF; RETURN NEW; END $$")
            admin.execute('CREATE TRIGGER qyh_contract_rollback_guard BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION qyh_contract_rollback_guard()')
            cases.append(expect_error(psycopg.Error, lambda: store.create_brief(SCOPE, 'clone:test', 'qyh-contract-rollback', body), state='P0001'))
            assert counts == admin.execute('SELECT (SELECT count(*) FROM aip_task_brief_head) AS heads,(SELECT count(*) FROM aip_task_brief_revision) AS revisions,(SELECT count(*) FROM aip_production_contract_receipt) AS receipts').fetchone()
            cases.append('forced-failure-all-three-table-rollback')
            def forbidden_receipt(factory, operation, scope=SCOPE):
                with factory(SCOPE) as conn:
                    store._receipt(conn, scope, operation, 'qyh-forged-' + operation + '-' + scope.org_id, 'a' * 64, {'resourceType': 'TaskBriefRevision', 'resourceId': made.brief_id, 'revision': 1, 'contentHash': 'a' * 64}, 'clone:test')
            cases.append(expect_error(psycopg.Error, lambda: forbidden_receipt(lambda scope: runtime(scope, read_only=False), 'task_brief.create'), state='42501'))
            cases.append(expect_error(psycopg.Error, lambda: forbidden_receipt(contract, 'responsibility_plan.create'), state='42501'))
            cases.append(expect_error(psycopg.Error, lambda: forbidden_receipt(contract, 'task_brief.create', TenantScope('dev-org', 'dev-project')), state='42501'))
            assert admin.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE idempotency_key IN ('qyh-contract-create','qyh-contract-revise','qyh-contract-freeze')").fetchone()['n'] == 3
            record('business-result', {'cases': cases, 'connections': observed, 'actualThreeOriginalReceipts': True,
                                       'originalBriefLifecycleAccepted': True, 'sameTenantForgeryRejected': True,
                                       'all29ContractOperationsAccepted': False, 'formalPasswordOrOIDCAuthenticated': False})
        except Exception as error:
            record('failure', {'errorType': type(error).__name__, 'sqlstate': getattr(error, 'sqlstate', None), 'completedCases': cases, 'unknownBusinessEffectReplayAllowed': False})
            raise
        finally:
            if created_role:
                for table in TABLES:
                    admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_contract_' + table), sql.Identifier(table)))
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    assert S.P.M.fingerprint(TARGET) == before
    assert S.D.metadata(TARGET) == metadata
    record('verified', {'originalClone647DataExact': True, 'allOriginalMetadataExact': True,
                        'currentDatabaseTouched': False, 'experimentalDatabaseRetained': DB,
                        'temporaryRoleRemoved': True, 'wholeTaskOrGoalAccepted': False})
    print(json.dumps({'cases': len(cases), 'originalCloneUnchanged': True, 'realFixedLoginConnections': len(observed), 'fullRestorationAccepted': False}))


if __name__ == '__main__':
    main()
