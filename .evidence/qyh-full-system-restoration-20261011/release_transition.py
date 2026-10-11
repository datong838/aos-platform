"""Exact local Registry maintenance using retained and current signed releases."""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

R = Path(__file__).resolve().parent
ROOT = R.parents[1]
os.environ['AOS_DOTENV_DISABLED'] = '1'
sys.path.insert(0, str(ROOT / 'services/aos-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
import a0v_qyh_restored_http as H
import a0v_canonical_ecommerce_first_install as OLD
import prepare_volume as P
from psycopg import connect
from psycopg.rows import dict_row
from aos_api.asset_registry.errors import AssetNotFoundError
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.signature import FileTrustRootProvider

LEGACY = ROOT.parent / '.aos-recovery-20260920/state/q-advisor-baseline'
LEGACY_ROOT = LEGACY / 'bn-canonical-alias-registry/signed-bundles'
LEGACY_TRUST = LEGACY / 'bm-trust-root-rotation/signing/trust-roots.json'
CURRENT = ROOT.parent / 'aos-recovery/.aos-qyh-core143-signing-state-20261011-r1'
CASES = [('a0v-qyh-current','domain.ecommerce.core','1.4.3',False),
         ('a0v-canonical','platform.ecommerce.niushop','1.23.2',True),
         ('a0v-qyh-current','solution.ecommerce.growth','1.13.0',False),
         ('a0v-canonical','solution.ecommerce.operations-base','1.2.2',True)]
TRUST = R / 'restoration-public-trust-roots.json'
ACTOR = 'qyh-user-authorized-restoration-maintainer-20261011'

def record(name, body):
    path = R / name
    with path.open('x') as stream:
        stream.write(json.dumps(body,ensure_ascii=False,default=str,indent=2)+'\n')

@contextmanager
def factory():
    data = json.loads((R/'private/restored-identity.json').read_text())
    with connect(host=data['host'],port=data['port'],dbname=data['dbname'],user=data['user'],
                 passfile=data['pgpassfile'],row_factory=dict_row,autocommit=True) as conn:
        conn.execute('SET ROLE aos_runtime')
        conn.autocommit = False
        yield conn

def prepare_trust():
    roots = json.loads(LEGACY_TRUST.read_text())['trustRoots'] + json.loads((CURRENT/'trust-roots.json').read_text())['trustRoots']
    assert len(roots) == 2 and len({(i['publisher'],i['keyId']) for i in roots}) == 2
    body = {'trustRoots': roots}
    if TRUST.exists():
        assert json.loads(TRUST.read_text()) == body, 'Trust set drift'
    else:
        record(TRUST.name, body)

def preflight():
    identity = H.preflight(R/'private/restored-identity.json')
    prepare_trust()
    trust = FileTrustRootProvider(TRUST).snapshot()
    loader = ManifestLoader({'a0v-canonical':LEGACY_ROOT,'a0v-qyh-current':CURRENT/'signed-bundles'},trust_roots=trust)
    policy = ReleasePolicy(trust_roots=trust)
    store = PostgresRegistryStore(connect_factory=factory)
    rows, loaded = [], []
    for alias,bundle_id,version,retained in CASES:
        bundle = loader.load(f'bundle://{alias}/{bundle_id}/{version}')
        policy.evaluate(OLD._load_builder()._release_record(bundle),checked_at=datetime.now(UTC))
        try:
            existing = store.get_version(bundle_id,version,publisher='aos')
        except AssetNotFoundError:
            existing = None
        if retained:
            assert existing is not None and existing['status'] == 'published'
            OLD.assert_registry_version_exact(existing,OLD._expected_registry_version(bundle))
            assert existing['signature'] == bundle.signature.model_dump(mode='json',by_alias=True), 'Retained signature differs'
        else:
            assert existing is None, 'New coordinate exists: reconcile, never mutate'
        rows.append({'id':bundle_id,'version':version,'contentHash':bundle.content_hash,
                     'sourceRef':bundle.source_ref,'retainedPublished':retained,'moduleCount':len(bundle.workshop_modules)})
        loaded.append(bundle)
    assert sum(x['moduleCount'] for x in rows) == 8
    return loader,trust,store,loaded,{'outcome':'QIYUEHUI_CURRENT_RELEASE_COMBINATION_PREFLIGHT_GREEN',
        'identity':identity['identity'],'versions':rows,'databaseWrites':0,
        'apiStarted':False,'runtimeAuthorized':False}

def apply(loader, trust, store, loaded, report):
    # A fresh full backup captures the live name and restricted role as well as
    # all retained historical rows. No original database is altered.
    identity = P.native_identity(TARGET := H.TARGET)
    assert identity['activeOtherConnections'] == 0 and identity['disabledBindings'] is True
    before = P.M.fingerprint(TARGET)
    assert before == json.loads((R/'volume-fingerprint-after-name.json').read_text())
    record('registry-transition-intent.json',{'authority':'2026-10-11 explicit full Qiyuehui restoration',
        'database':identity,'task':'qyh-full-system-restoration-20261011',
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'versions':report['versions'],'phase':'FRESH_BACKUP_BEFORE_TWO_NEW_COORDINATES',
        'hostStart':False,'businessExecutionAuthority':False})
    manifest = {}
    for filename, command in [('registry-before.dump',['pg_dump','-U','aos_app','-d','aos_meta_head','-Fc']),
                              ('registry-before-globals.sql',['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'])]:
        path=R/'private'/filename
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:
            proc=subprocess.run(['docker','--context',H.CONTEXT,'exec',TARGET,*command],stdout=stream,stderr=subprocess.PIPE,timeout=180)
        assert proc.returncode == 0, 'Fresh backup failed: reconcile only'
        copy=path.with_name(path.name+'.second-copy')
        fd=os.open(copy,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(path.read_bytes())
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest==hashlib.sha256(copy.read_bytes()).hexdigest()
        manifest[filename]={'sha256':digest,'bytes':path.stat().st_size,'secondChecksumCopy':True}
    assert P.M.fingerprint(TARGET)==before
    record('registry-transition-backup.json',manifest)
    def clock():
        with factory() as conn:return conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    service=RegistryService(store=store,loader=loader,clock=clock,trust_roots=trust)
    published=[]
    for case,bundle in zip(CASES,loaded):
        alias,bundle_id,version,retained=case
        if not retained:
            # Bundles already exist. Do not create duplicate global identities.
            store.get_bundle(bundle_id,publisher='aos')
            for action in ('create','validate','publish'):
                stem=f'registry-{bundle_id}-{version}-{action}'
                record(stem+'-intent.json',{'id':bundle_id,'version':version,'action':action,'actor':ACTOR})
                if action=='create':
                    result=service.create_version(publisher='aos',bundle_id=bundle_id,source_ref=bundle.source_ref,
                        actor=ACTOR,roles=OLD.REGISTRY_CREATE_ROLES,publisher_scopes=OLD.PUBLISHER_SCOPES)
                else:
                    roles=OLD.REGISTRY_PUBLISH_ROLES if action=='publish' else OLD.REGISTRY_CREATE_ROLES
                    result=getattr(service,action)(publisher='aos',bundle_id=bundle_id,version=version,
                        actor=ACTOR,roles=roles,publisher_scopes=OLD.PUBLISHER_SCOPES)
                record(stem+'-terminal.json',{'status':result['status'],'contentHash':result['contentHash']})
        result=store.get_version(bundle_id,version,publisher='aos')
        OLD.assert_registry_version_exact(result,OLD._expected_registry_version(bundle))
        assert result['status']=='published'
        assert result['signature']==bundle.signature.model_dump(mode='json',by_alias=True)
        published.append({'id':bundle_id,'version':version,'contentHash':result['contentHash'],'retained':retained})
    after=P.M.fingerprint(TARGET)
    assert len(before)==len(after)==647
    changed=[b['table'] for b,a in zip(before,after) if b!=a]
    allowed={'public.asset_bundle_version','public.asset_bundle_version_event','public.asset_bundle_dependency',
             'public.asset_bundle_artifact','public.asset_bundle_evidence'}
    assert set(changed)<=allowed, 'Unexpected table difference; reconcile only'
    report={'outcome':'QIYUEHUI_CURRENT_RELEASE_COMBINATION_PUBLISHED_GREEN','published':published,
        'newVersionCount':2,'oldVersionsChanged':False,'changedTables':changed,
        'tableCount':647,'hostStarted':False,'apiStarted':False,'providerInvocations':0,
        'originalDatabasesTouched':False,'businessExecutionAuthorized':False}
    record('registry-transition-terminal.json',report)
    record('volume-fingerprint-after-registry.json',after)
    return report

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    assert not (R/'registry-transition-intent.json').exists(), 'Existing publication intent: reconcile only'
    loader,trust,store,loaded,report=preflight()
    if (R/'current-release-combination-preflight.json').exists():
        previous=json.loads((R/'current-release-combination-preflight.json').read_text())
        assert previous['identity']==report['identity'] and previous['versions']==report['versions']
    else:
        record('current-release-combination-preflight.json',report)
    if not args.apply:
        print(report['outcome']);raise SystemExit(0)
    print(apply(loader,trust,store,loaded,report)['outcome'])
