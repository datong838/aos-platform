"""Owned tmpfs only: exact original W6-05 DDL and original nonempty producer."""
from pathlib import Path
import ast, contextlib, datetime, hashlib, importlib.util, json, os, secrets, subprocess, sys, time
import psycopg
from psycopg import IsolationLevel, sql
from psycopg.rows import dict_row

E = Path(__file__).resolve().parent
R = E.parents[1]
os.environ.update(AOS_DATABASE_URL='postgresql://placeholder@127.0.0.1:1/unused', AOS_DOTENV_DISABLED='1')
sys.path.insert(0, str(R/'services/aos-api'))
sys.path.insert(0, str(R/'scripts/memory'))
import memoryctl as m
from aos_api.ecommerce_price_research_readonly import PriceResearchReadonlyReader, PriceResearchReadonlyError, MAX_ROW_BYTES
from aos_api.ecommerce_workshop_price_research import EcommerceWorkshopPriceResearchService, PreparePriceResearchBatchRequest, FreezePriceResearchBatchRequest
spec = importlib.util.spec_from_file_location('price_original_cases', R/'services/aos-api/tests/aip/test_w6_05_price_research.py')
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)
OWNER = 'codex-01a13484-f019-7d82-94ce-812396db9124'
NAME, PORT = 'qyh-price-bounded-native-20261015-r1', 18618
IMAGE = 'sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
TABLE = 'ecommerce_price_research_batch_revision'
SCOPE = cases.TenantScope('dev-org', 'fixture-project')

def docker(*args):
    return subprocess.run(['docker', '--context', 'colima-aos-extension', *args], capture_output=True, text=True)

def save(name, value):
    m.scan_secrets(value)
    with (E/name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush(); os.fsync(f.fileno())

leases = m.load_leases(m.DEFAULT_PATHS)['leases']
lease = next(x for x in leases if x['task_id'] == E.name)
assert lease['owner'] == OWNER and lease['base_revision'] == 'AOS-002032'
assert datetime.datetime.fromisoformat(lease['lease_expires_at']) > datetime.datetime.now(datetime.timezone.utc)
assert m.load_authority(m.DEFAULT_PATHS)['project_revision'] == 'AOS-002032'
assert not (E/'native-r1-intent.json').exists() and docker('inspect', NAME).returncode != 0
assert not subprocess.run(['lsof', '-t', f'-iTCP:{PORT}', '-sTCP:LISTEN'], capture_output=True, text=True).stdout.strip()
password = secrets.token_hex(24)
save('native-r1-intent.json', dict(name=NAME, owner=OWNER, tmpfs=True, port=PORT, originalVolumeTouched=False))
created = docker('run', '-d', '--name', NAME, '--label', 'aos.owner='+OWNER, '--label', 'aos.task='+E.name, '--tmpfs', '/var/lib/postgresql/data:rw,size=512m', '-p', f'127.0.0.1:{PORT}:5432', '-e', 'POSTGRES_PASSWORD='+password, IMAGE)
assert created.returncode == 0
cid = created.stdout.strip()
save('native-r1-created.json', dict(containerId=cid, name=NAME, owner=OWNER))
args = dict(host='127.0.0.1', port=PORT, dbname='postgres', password=password, row_factory=dict_row, connect_timeout=1)
try:
    for _ in range(100):
        try:
            with psycopg.connect(user='postgres', **args) as c: c.execute('SELECT 1')
            break
        except psycopg.OperationalError: time.sleep(.1)
    else: raise RuntimeError('fixture startup unresolved')
    with psycopg.connect(user='postgres', **args) as c:
        c.execute('CREATE ROLE aos_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS')
        c.execute(sql.SQL('CREATE ROLE fixture_reader LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}').format(sql.Literal(password)))
        c.execute('GRANT aos_runtime TO fixture_reader')
        c.execute('CREATE TABLE meta_workspace(org_id text,project_id text,PRIMARY KEY(org_id,project_id))')
        c.execute('INSERT INTO meta_workspace VALUES(%s,%s),(%s,%s)', (*SCOPE.key, 'foreign-fixture', SCOPE.project_id))
        source = (R/'services/aos-api/alembic/versions/w6_005_price_research.py').read_text()
        tree = ast.parse(source)
        nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name == 'upgrade') or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TABLES' for t in n.targets))]
        class Op:
            def execute(self, statement): c.execute(statement)
        env = {'op': Op()}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'exact-owned-w6_005-ddl', 'exec'), env)
        env['upgrade']()
        cases.NOW = c.execute('SELECT transaction_timestamp() AS now').fetchone()['now'] - datetime.timedelta(seconds=5)
    stores = []
    original_store = cases.Store
    class CaptureStore(original_store):
        def __init__(self): super().__init__(); stores.append(self)
    cases.Store = CaptureStore
    cases.SCOPE = SCOPE
    cases.test_full_prepare_freeze_conserves_items_and_has_zero_side_effects()
    own_store = stores[-1]
    first_prepared, first_frozen = own_store.batches['price-batch-1']
    def seed(item):
        with psycopg.connect(user='postgres', **args) as c:
            c.execute(f'INSERT INTO {TABLE}(org_id,project_id,batch_id,revision,content_hash,authority_data,created_at) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s)', (item.tenant.org_id, item.tenant.project_id, item.batch_id, item.revision, item.content_hash, item.model_dump_json(by_alias=True), item.created_at))
    for item in own_store.batches['price-batch-1']: seed(item)
    cases.SCOPE = cases.TenantScope('foreign-fixture', SCOPE.project_id)
    cases.test_full_prepare_freeze_conserves_items_and_has_zero_side_effects()
    for item in stores[-1].batches['price-batch-1']: seed(item)
    cases.SCOPE = SCOPE
    injected, observations = [False], []
    def concurrent_producer():
        mapping = {'briefRef':'brief', 'evalRef':'eval', 'responsibilityPlanRef':'responsibilityPlan', 'profileRef':'profile', 'monitoringPolicyRef':'monitoringPolicy', 'capacitySnapshotRef':'capacitySnapshot', 'budgetSnapshotRef':'budgetSnapshot', 'logicRef':'logic', 'agentBindingRef':'agentBinding'}
        request = PreparePriceResearchBatchRequest(batchId='price-batch-2', skillRefs=first_prepared.skill_refs, items=first_prepared.items, **{k:first_prepared.exact_refs[v] for k,v in mapping.items()})
        with psycopg.connect(user='postgres', **args) as c: now = c.execute('SELECT transaction_timestamp() AS now').fetchone()['now']
        service = EcommerceWorkshopPriceResearchService(own_store)
        prepared = service.prepare_batch(SCOPE, request, 'fixture-operator', now=now)
        frozen = service.freeze_batch(SCOPE, prepared.batch_id, FreezePriceResearchBatchRequest(expectedVersion=prepared.version, expectedContentHash=prepared.content_hash, exactRefs=prepared.exact_refs), 'fixture-operator', now=now)
        seed(prepared); seed(frozen)
    @contextlib.contextmanager
    def connection(scope):
        assert scope == SCOPE
        with psycopg.connect(user='fixture_reader', **args) as c:
            c.read_only = True; c.isolation_level = IsolationLevel.REPEATABLE_READ
            c.execute('SET LOCAL ROLE aos_runtime')
            c.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
            observations.append(dict(c.execute("SELECT current_user AS role,current_setting('transaction_read_only') AS readonly,current_setting('transaction_isolation') AS isolation").fetchone()))
            class Probe:
                read_only=c.read_only; autocommit=c.autocommit; isolation_level=c.isolation_level
                def execute(self, statement, params=()):
                    result = c.execute(statement, params)
                    if 'transaction_timestamp() AS cutoff' in statement and not injected[0]:
                        injected[0]=True; concurrent_producer()
                    return result
            yield Probe()
    reader = PriceResearchReadonlyReader(connect_factory=connection)
    first, second = reader.read(SCOPE), reader.read(SCOPE)
    assert first.latest_batch.batch_id == 'price-batch-1' and second.latest_batch.batch_id == 'price-batch-2'
    assert first.latest_batch.lifecycle == second.latest_batch.lifecycle == 'frozen'
    assert not first.allowed_commands and not second.allowed_commands
    with psycopg.connect(user='fixture_reader', **args) as c:
        c.read_only=True; c.isolation_level=IsolationLevel.REPEATABLE_READ
        c.execute('SET LOCAL ROLE aos_runtime')
        c.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        assert c.execute(f'SELECT count(*) AS n FROM {TABLE}').fetchone()['n'] == 4
        try: c.execute(f'INSERT INTO {TABLE} SELECT * FROM {TABLE}')
        except psycopg.Error as error: state=error.sqlstate; c.rollback()
        else: raise AssertionError('native write not denied')
    assert state == '25006'
    original = second.latest_batch.model_dump(mode='json', by_alias=True)
    def change_latest(payload):
        with psycopg.connect(user='postgres', **args) as c:
            c.execute(f'UPDATE {TABLE} SET authority_data=%s::jsonb WHERE org_id=%s AND project_id=%s AND batch_id=%s AND revision=2', (json.dumps(payload), *SCOPE.key, 'price-batch-2'))
    change_latest({**original, 'createdBy': 'x'*(MAX_ROW_BYTES+1)})
    try: reader.read(SCOPE)
    except PriceResearchReadonlyError as error: oversize_code=error.code
    else: raise AssertionError('oversize payload exposed')
    assert oversize_code == 'PRICE_RESEARCH_READ_LIMIT_EXCEEDED'
    change_latest({**original, 'createdBy':'fixture@example.invalid'})
    try: reader.read(SCOPE)
    except PriceResearchReadonlyError as error: privacy_code=error.code
    else: raise AssertionError('private actor exposed')
    assert privacy_code == 'PRICE_RESEARCH_READ_PRIVACY_UNAVAILABLE'
    save('native-r1-result.json', dict(containerId=cid, fixtureOnlyNotOriginalSchema=True, exactW6DdlSha=hashlib.sha256(source.encode()).hexdigest(), sourceSha=hashlib.sha256((R/'services/aos-api/aos_api/ecommerce_price_research_readonly.py').read_bytes()).hexdigest(), originalProducerUsed=True, originalVolumeTouched=False, realUserApproval=False, snapshotBatchIds=[first.latest_batch.batch_id,second.latest_batch.batch_id], nonemptyFrozenWithPreparedAncestor=True, observations=observations, foreignRowsHiddenWithoutWhere=True, writeDeniedSqlstate=state, oversizeSqlCaseError=oversize_code, privacyError=privacy_code, commandsEmpty=True))
    print(json.dumps(dict(snapshot=['price-batch-1','price-batch-2'], writeDenied=state, oversize=oversize_code, privacy=privacy_code, originalVolumeTouched=False)))
finally:
    owned = json.loads(docker('inspect', NAME).stdout)[0]
    assert owned['Id'] == cid and owned['Config']['Labels']['aos.owner'] == OWNER
    assert docker('stop', NAME).returncode == 0
    after = json.loads(docker('inspect', NAME).stdout)[0]
    assert after['Id'] == cid and not after['State']['Running']
    save('native-r1-stopped.json', dict(containerId=cid, stopped=True, originalVolumeTouched=False))
