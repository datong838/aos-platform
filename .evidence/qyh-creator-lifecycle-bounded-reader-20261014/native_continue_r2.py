from pathlib import Path
import contextlib,datetime,hashlib,json,subprocess,sys
import psycopg
from psycopg import IsolationLevel,sql
from psycopg.rows import dict_row
R=Path(__file__).resolve().parents[2];E=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'services/aos-api'));sys.path.insert(0,str(R/'services/aos-api/tests/aip'))
from aos_api.ecommerce_workshop_creator_lifecycle_readonly import CreatorLifecycleReadonlyReader,CreatorLifecycleReadonlyError
from aos_api.tenant_scope import TenantScope
from test_creator_lifecycle_read_tenant import item
NAME='qyh-creator-lifecycle-bounded-native-20261014-r1';OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';SCOPE=TenantScope('org-org','dev-project')
def docker(*args):return subprocess.run(['docker','--context','colima-aos-extension',*args],capture_output=True,text=True)
def save(name,value):
 with (E/name).open('x') as f:json.dump(value,f,indent=2);f.write('\n');f.flush()
assert not (E/'native-r2-bootstrap-intent.json').exists(),'existing bootstrap: reconcile only'
recon=json.loads((E/'native-r1-readonly-reconciliation.json').read_text());created=json.loads((E/'native-r1-created.json').read_text());cid=created['containerId'];d=json.loads(docker('inspect',NAME).stdout)[0]
assert d['Id']==cid==recon['containerId'] and d['Config']['Labels']['aos.owner']==OWNER and d['State']['Running'] and recon['scopeRolesBeforeBootstrap']==recon['scopeTablesBeforeBootstrap']==0
assert hashlib.sha256((E/'native_snapshot.py').read_bytes()).hexdigest()=='0759aaa03cbeba25179d1cddf4dc690e6d7a1e2364926092383fe70e9a7d6bd3'
password=next(x.split('=',1)[1] for x in d['Config']['Env'] if x.startswith('POSTGRES_PASSWORD='))
TABLES=(('ecommerce_creator_batch_start_decision_revision', 'decision_id', 'batch_id TEXT', 'latest_start_for_tenant_or_none'), ('ecommerce_creator_lane_observation', 'observation_id', 'decision_id TEXT,lane_id TEXT', 'list_lane_observations'), ('ecommerce_creator_contract_revision', 'collaboration_id', '', 'list_contracts'), ('ecommerce_creator_delivery_observation', 'observation_id', '', 'list_deliveries'), ('ecommerce_creator_relationship_revision', 'relationship_id', '', 'list_relationships'))
save('native-r2-bootstrap-intent.json',{'containerId':cid,'noCreateOrRestart':True,'priorNativeSQLZero':True,'originalVolumeTouched':False})
connect_args = dict(host='127.0.0.1', port=18571, dbname='postgres', password=password, row_factory=dict_row)
with psycopg.connect(user='postgres', **connect_args) as admin:
    admin.execute('CREATE ROLE aos_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS')
    admin.execute(sql.SQL('CREATE ROLE fixture_reader LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}').format(sql.Literal(password)))
    admin.execute('GRANT aos_runtime TO fixture_reader')
    for table, identity, extra, _ in TABLES:
        ddl = sql.SQL('CREATE TABLE {} (org_id TEXT NOT NULL,project_id TEXT NOT NULL,{} TEXT NOT NULL,revision INTEGER NOT NULL,content_hash TEXT NOT NULL,authority_data JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL' + (',' + extra if extra else '') + ',PRIMARY KEY(org_id,project_id,{},revision))').format(sql.Identifier(table), sql.Identifier(identity), sql.Identifier(identity))
        admin.execute(ddl)
        admin.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(table)))
        admin.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(sql.Identifier(table)))
        admin.execute(sql.SQL("CREATE POLICY tenant_scope ON {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier(table)))
        admin.execute(sql.SQL('GRANT SELECT ON {} TO aos_runtime').format(sql.Identifier(table)))

def insert_contract(identity, scope=SCOPE, json_scope=None):
    value = item('list_contracts', json_scope or scope).model_copy(update={'collaboration_id': identity})
    with psycopg.connect(user='postgres', **connect_args) as admin:
        admin.execute('INSERT INTO ecommerce_creator_contract_revision(org_id,project_id,collaboration_id,revision,content_hash,authority_data,created_at) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s)',
                      (*scope.key, identity, value.revision, value.content_hash, json.dumps(value.model_dump(mode='json', by_alias=True)), value.created_at))

insert_contract('original')
insert_contract('foreign', TenantScope('dev-org', 'dev-project'))
observations = []
@contextlib.contextmanager
def factory(scope, *, concurrent=False):
    with psycopg.connect(user='fixture_reader', **connect_args) as conn:
        conn.read_only = True; conn.isolation_level = IsolationLevel.REPEATABLE_READ
        conn.execute('SET LOCAL ROLE aos_runtime')
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
        state = conn.execute("SELECT current_user AS role,current_setting('transaction_read_only') AS readonly,current_setting('transaction_isolation') AS isolation").fetchone()
        observations.append(state)
        class Proxy:
            read_only = True; autocommit = False; isolation_level = IsolationLevel.REPEATABLE_READ
            def execute(self, statement, params=()):
                cursor = conn.execute(statement, params)
                if concurrent and 'transaction_timestamp()' in statement:
                    insert_contract('concurrent')
                return cursor
        yield Proxy()

first = CreatorLifecycleReadonlyReader(connect_factory=lambda scope: factory(scope, concurrent=True)).read(SCOPE)
second = CreatorLifecycleReadonlyReader(connect_factory=factory).read(SCOPE)
assert [x.collaboration_id for x in first.contracts] == ['original']
assert sorted(x.collaboration_id for x in second.contracts) == ['concurrent', 'original']
with factory(SCOPE) as conn:
    visible = conn.execute('SELECT count(*) AS n FROM ecommerce_creator_contract_revision').fetchone()['n']
    assert visible == 2
    try: conn.execute("UPDATE ecommerce_creator_contract_revision SET revision=revision+1")
    except psycopg.Error as error:
        assert error.sqlstate in {'25006', '42501'}
        write_denied = error.sqlstate
    else: raise AssertionError('fixture readonly role unexpectedly wrote')
insert_contract('bad-json-tenant', json_scope=TenantScope('dev-org', 'dev-project'))
try: CreatorLifecycleReadonlyReader(connect_factory=factory).read(SCOPE)
except CreatorLifecycleReadonlyError as error:
    assert error.code == 'CREATOR_LIFECYCLE_READ_AUTHORITY_DRIFT'
    rejected = error.code
else: raise AssertionError('native serialized tenant drift not rejected')
details = json.loads(docker('inspect', NAME).stdout)[0]
assert details['Id'] == cid and details['Config']['Labels']['aos.owner'] == OWNER
assert all(m.get('Name') != 'aos-qyh-history159-prepared-data-20261011' for m in details['Mounts'])
report = dict(containerId=cid, name=NAME, owner=OWNER, tmpfs=True,
              observations=observations, snapshotFirst=1, snapshotAfterConcurrentCommit=2,
              forceRlsForeignRowInvisible=True, writeDeniedSqlstate=write_denied,
              badPayloadRejected=rejected, normalCompleteSnapshot=True,
              originalVolumeTouched=False, originalUserOrBudgetApproval=False,
              currentSourceSha256=hashlib.sha256((R/'services/aos-api/aos_api/ecommerce_workshop_creator_lifecycle_readonly.py').read_bytes()).hexdigest())
save('native-r1-result.json', report)
stopped = docker('stop', '--time', '10', NAME)
assert stopped.returncode == 0, 'fixture stop pending; reconcile known CID'
after = json.loads(docker('inspect', NAME).stdout)[0]
assert after['Id'] == cid and not after['State']['Running']
save('native-r1-stopped.json', dict(containerId=cid, stopped=True, originalVolumeTouched=False))
print(json.dumps(report))
