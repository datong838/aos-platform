"""Signed candidate/schema compatibility audit; no publication or business calls."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, UTC

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
FROZEN = ROOT / '.evidence/qyh-current160-fresh-rehearsal-20261012/private/source161/services/aos-api'
sys.path.insert(0, str(FROZEN))
sys.path.insert(0, str(ROOT / 'scripts'))
os.environ['AOS_DOTENV_DISABLED'] = '1'
from psycopg import sql
from psycopg.pq import TransactionStatus
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.composition_contracts import RegistrySnapshot, CompositionRequest
from aos_api.asset_registry.resolver import resolve
from aos_api.extension_runtime.schema_conditions import admit_schema_requirements
from aos_api.extension_runtime.schema_registry import require_installed, SchemaRequirement
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
import aos_api
assert Path(aos_api.__file__).resolve().is_relative_to(FROZEN)


def save(name, value):
    with (OUT / name).open('x') as stream:
        json.dump(value, stream, indent=2)


class NativeRows:
    def __init__(self, rows): self.rows = rows
    def fetchone(self): return self.rows[0] if self.rows else None


class NativeReadTransaction:
    """One live psql backend, with observed BEGIN and read-only identity."""
    def __init__(self, container, database, label):
        self.log = (OUT / 'private' / (label + '.log')).open('xb')
        os.chmod(self.log.name, 0o600)
        self.process = subprocess.Popen(['docker','--context','colima-aos-extension','exec','-i',container,
            'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d',database],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True)
        self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
        self.control("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL ROLE aos_runtime; SET LOCAL statement_timeout='10s'; SET LOCAL aos.org_id='org-org'; SET LOCAL aos.project_id='dev-project';")
        identity = self.execute("SELECT pg_backend_pid() AS pid,current_user AS role,current_setting('transaction_isolation') AS isolation,current_setting('transaction_read_only') AS readonly").fetchone()
        assert identity['role']=='aos_runtime' and identity['isolation']=='repeatable read' and identity['readonly']=='on'
        self.identity = identity
        self.info.transaction_status = TransactionStatus.INTRANS

    def control(self, text):
        marker = 'audit_' + uuid4().hex
        self.process.stdin.write(text + '\n\\echo ' + marker + '\n')
        self.process.stdin.flush()
        lines=[]
        while True:
            line=self.process.stdout.readline()
            assert line, 'Native SQL backend ended; inspect private log without retry'
            if line.strip()==marker: return lines
            if line.strip(): lines.append(line.strip())

    def execute(self, query, params=()):
        parts=query.rstrip().rstrip(';').split('%s')
        assert len(parts)==len(params)+1
        statement=parts[0]
        for value, tail in zip(params,parts[1:]): statement+=sql.Literal(value).as_string()+tail
        assert statement.lstrip().upper().startswith('SELECT ')
        lines=self.control("SELECT coalesce(json_agg(row_to_json(r)),'[]') FROM ("+statement+") r;")
        assert len(lines)==1
        return NativeRows(json.loads(lines[0]))

    def close(self):
        assert self.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']==self.identity['pid']
        self.control('ROLLBACK;')
        self.info.transaction_status=TransactionStatus.IDLE
        self.process.stdin.close()
        assert self.process.wait(timeout=15)==0
        self.log.close()


def main():
    assert not (OUT / 'audit-intent.json').exists(), 'Reconcile prior audit before retry'
    (OUT/'private').mkdir(mode=0o700)
    common=ROOT/'.evidence/qyh-full-system-restoration-20261011'
    bundle_root=common/'selected-public-bundles'
    trust=FileTrustRootProvider(common/'restoration-public-trust-roots.json').snapshot()
    loader=ManifestLoader({'a0v-qyh-current':bundle_root,'a0v-canonical':bundle_root},trust_roots=trust)
    policy=ReleasePolicy(trust_roots=trust)
    spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build_ecommerce_runtime_candidates.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    previous=json.loads((common/'selected-public-root-terminal.json').read_text())['versions']
    bundles={r['id']:loader.load('bundle://a0v-qyh-current/'+r['id']+'/'+r['version']) for r in previous}
    now=datetime.now(UTC)
    candidates=[]
    records={}
    for row in previous:
        b=bundles[row['id']];assert b.content_hash==row['contentHash']
        record=builder._release_record(b)  # Existing diagnostic projection; no Registry mutation.
        records[row['id']]=record
        approved=policy.evaluate(record,checked_at=now)
        candidates.append(builder._snapshot_candidate(b,approved))
    snapshot=RegistrySnapshot.build(candidates=candidates,checked_at=now)
    request=CompositionRequest.model_validate({'requested':[{'publisher':'aos','id':bid,'version':bundles[bid].manifest.metadata.version} for bid in ('platform.ecommerce.niushop','solution.ecommerce.operations-base','solution.ecommerce.growth')],
        'platformApiVersion':'1.7.0','platformRelease':'aos-platform/1.7.0','environment':'dev','registrySnapshotHash':snapshot.snapshot_hash,'currentInstallationRef':None})
    composition=resolve(request,snapshot,None);selected={r.id:r for r in composition.resolved}
    requirements=[];rows=[]
    for bid,bundle in bundles.items():
        root=bundle_root/bid/bundle.manifest.metadata.version
        required=admit_schema_requirements(record=records[bid],selected=selected[bid],policy=policy,checked_at=now,
            read_artifact=lambda path,limit,root=root:(root/path).read_bytes())
        requirements.extend(required)
        rows.append({'id':bid,'version':bundle.manifest.metadata.version,'contentHash':bundle.content_hash,
                     'requirements':[{'packageId':r.package_id,'schemaVersion':r.schema_version,'migrationHash':r.migration_hash} for r in required]})
    assert len(rows)==4 and len(requirements)==3
    save('audit-intent.json',{'candidateDiagnosticOnly':True,'packageSignaturesRechecked':4,'schemaRequirements':3,
        'actualSourceMigrated':False,'registryPublishAllowed':False,'businessCallsAllowed':False})
    observations=[]
    connections=[]
    try:
        for name,database,label in [('qyh-restored-pg-20261011','aos_meta_head','source159'),
                                     ('qyh-current159-exact-restore-20261012','qyh_current160_fresh_rehearsal_20261012','owned161')]:
            conn=NativeReadTransaction(name,database,label);connections.append(conn)
            require_installed(conn,requirements)
            wrong=SchemaRequirement(requirements[0].package_id,requirements[0].schema_version,'sha256:'+'0'*64)
            try: require_installed(conn,[wrong])
            except RuntimeConflict: rejected=True
            else: rejected=False
            assert rejected
            version=conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']
            observations.append({'database':database,'version':version,'role':conn.identity['role'],'readonly':True,
                                 'threeExactNativeRequirementsPass':True,'sameVersionWrongHashRejected':True})
        table_query="""SELECT n.nspname AS schema,c.relname AS name,
          (SELECT json_agg(json_build_array(a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped) AS columns
          FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' ORDER BY n.nspname,c.relname"""
        function_query="""SELECT n.nspname||'.'||p.proname||'('||pg_get_function_identity_arguments(p.oid)||')' AS key,pg_get_functiondef(p.oid) AS definition FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND p.prokind IN ('f','p','w') ORDER BY key"""
        source_tables=connections[0].execute(table_query).rows;target_tables=connections[1].execute(table_query).rows
        indexed={(r['schema'],r['name']):r for r in target_tables}
        assert len(source_tables)==647 and all(indexed[(r['schema'],r['name'])]==r for r in source_tables)
        source_functions=connections[0].execute(function_query).rows;target_functions=connections[1].execute(function_query).rows
        indexed={r['key']:r for r in target_functions}
        differences=[r['key'] for r in source_functions if indexed.get(r['key'])!=r]
        save('native-function-differences.json',{'oldFunctionCount':len(source_functions),'differences':differences})
        assert not differences, 'Original function definition drift; compatibility incomplete'
        save('result.json',{'candidateDiagnosticOnly':True,'fourExactBundleSignaturesAndResolutionPass':True,'packages':rows,
            'nativeReadonlySchemaObservations':observations,'all647OldTableColumnLayoutsEqual':True,
            'oldFunctionCount':len(source_functions),'allOldFunctionDefinitionsEqual':True,
            'normalStoreWriteCompatibilityAccepted':False,'actualRegistryPublicationAccepted':False,
            'actualSourceMigrated':False,'eightWorkshopsAccepted':False,'businessEffects':0})
        print(json.dumps({'signedCandidates':4,'exactSchemas':3,'oldTableLayoutsEqual':647,
                          'oldFunctionDefinitionsEqual':len(source_functions),'actualPublication':False}),flush=True)
    finally:
        for conn in connections: conn.close()


if __name__=='__main__': main()
