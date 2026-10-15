"""Read-only same-day actual runtime and fresh evidence verifier; no effects."""
from pathlib import Path
import json,hashlib,subprocess,sys,struct,io,tarfile
P=Path(__file__).resolve().parent;R=P.parents[2]
def read(p):return json.loads(p.read_text())
def cmd(*args):return subprocess.check_output(args,cwd=R,text=True).strip()
cfg=read(P/'config.json');assert cfg['head']==cmd('git','rev-parse','HEAD') and cmd('git','branch','--show-current')=='m1'
sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
source=guard.require_api_source_candidate(Path(cfg['apiReport']))
runtime=read(P/'current-runtime-listeners-r1.json')
for port,key in [(18080,'api'),(18434,'web')]:
 proc=runtime[key];assert cmd('lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN')==str(proc['pid'])
 assert cmd('ps','-p',str(proc['pid']),'-o','command=')==proc['command']
 cwd=next(x[1:] for x in cmd('lsof','-a','-p',str(proc['pid']),'-d','cwd','-Fn').splitlines() if x.startswith('n'));assert cwd==proc['cwd']
 assert proc['head']==cfg['head']
assert runtime['api']['cwd']==str(source)
wr=read(Path(cfg['webReport']));w=Path(wr['source']);assert wr['head']==cfg['head']
actual={str(f.relative_to(w)):hashlib.sha256(f.read_bytes()).hexdigest() for f in w.rglob('*') if f.is_file()};assert actual==wr['manifest']
archive=subprocess.check_output(['git','archive',cfg['head'],'apps/web','packages/ontology-sdk','packages/ui-kit'],cwd=R)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:expected={i.name:hashlib.sha256(tar.extractfile(i).read()).hexdigest() for i in tar if i.isfile() and not any(x.startswith('.env') for x in Path(i.name).parts)}
assert expected==actual and len(actual)==764
pg=json.loads(cmd('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0]
F=R/'.evidence/qyh-restoration-successor-latest-restart-20261013'
b,a,f=[read(F/(n+'.json')) for n in ['daily-before-20261016','daily-after-pg-20261016','daily-after-final-20261016']]
assert b['fingerprints']==a['fingerprints']==f['fingerprints'] and len(f['fingerprints'])==650
for x in [b,a,f]:
 assert x['containerId']==pg['Id']=='84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c'
 assert x['volume']==pg['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011' and x['native']['cluster']=='7695302940039200809' and x['native']['schema']=='a0v_161' and x['native']['enabledBindings']==0
assert a['pgStartedAt']==f['pgStartedAt']==pg['State']['StartedAt']==read(P/'pg-terminal.json')['startedAfter'] and b['pgStartedAt']!=f['pgStartedAt']
core=read(P/'native-core-read-deny-r1.json');who={'subject':'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657','orgId':'org-org','projectId':'dev-project','tokenKind':'oidc'};assert core['who']==who and core['unknownQuery']['status']==400 and core['anonymousStatus']==401
pages=read(P/'native-eight-pages-r1.json');assert len(pages)==8 and len({x['route'] for x in pages})==8
net=read(P/'native-network-final-r1.json');assert not net['businessNonGet'] and all(x['status']==200 for x in net['normalAuthPosts'])
for x in pages:
 assert x['read']['tenant']=={'orgId':'org-org','projectId':'dev-project'} and x['read']['who']==who and x['dom']['moduleId']=='ecommerce.'+x['module']
 assert any(n['path']=='/api/v1/ecommerce-workshop/views/'+x['module'] and n['method']=='GET' and n['status']==200 for n in net['network'])
interaction=read(P/'native-core-interaction-r1.json');assert interaction['homeRestored'] and interaction['keyboardEnd']['focused'] and interaction['keyboardEnd']['focusVisible']
assert '客户分群' in interaction['nativePointerSelected'] and any(x['type']=='click' and x['trusted'] and '客户分群' in str(x.get('target')) for x in interaction['witness'])
widths=read(P/'customer-three-width-r1.json');assert [x['width'] for x in widths]==[1280,1440,1920] and all(x['documentWidth']==x['width'] and x['panel']['right']==x['width'] for x in widths)
images={}
for path in list(P.glob('actual-*-1440-r1.png'))+list(P.glob('customer-core-*-r1.png')):
 raw=path.read_bytes();size=struct.unpack('>II',raw[16:24]);assert size==((int(path.name.split('-')[2]),720 if '1280' in path.name else 1080 if '1920' in path.name else 900) if path.name.startswith('customer-core') else (1440,900));images[path.name]={'size':size,'sha256':hashlib.sha256(raw).hexdigest()}
assert len(images)==11
report={'head':cfg['head'],'apiPid':runtime['api']['pid'],'webPid':runtime['web']['pid'],'pgStartedAt':pg['State']['StartedAt'],'originalVolume':f['volume'],'apiSourceGuard':True,'webGitManifestDisk764Equal':True,'full650BeforeAfterPgFinalEqual':True,'nativeEightRoots200':True,'exactOriginalOidcTenant':True,'unknownQuery400Anonymous401':True,'corePointerTrustedAndKeyboard':True,'customerThreeWidthNoDocumentOverflow':True,'businessNonGet':[],'images':images,'allVisualPassed':False,'sidebarPointerNavigationPassed':False,'wholeGoalComplete':False}
with (P/'daily-live-verification-r1.json').open('x') as out:json.dump(report,out,indent=2)
print(json.dumps({k:v for k,v in report.items() if k!='images'}))
