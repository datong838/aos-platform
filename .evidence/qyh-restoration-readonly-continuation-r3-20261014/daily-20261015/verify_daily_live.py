"""Read-only current process/source and already-taken native evidence verification."""
from pathlib import Path
import hashlib,json,subprocess,sys
P=Path(__file__).resolve().parent;R=P.parents[2]
def read(p):return json.loads(p.read_text())
def cmd(*args):return subprocess.check_output(args,cwd=R,text=True).strip()
cfg=read(P/'config.json');assert cfg['head']==cmd('git','rev-parse','HEAD') and cmd('git','branch','--show-current')=='m1'
sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
source=guard.require_api_source_candidate(Path(cfg['apiReport']))
api=read(P/'api-started.json');web=read(P/'web-started.json');wr=read(Path(cfg['webReport']))
assert api['head']==web['head']==wr['head']==cfg['head']
for port,proc in [(18080,api),(18434,web)]:
 assert cmd('lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN')==str(proc['pid'])
 cwd=next(x[1:] for x in cmd('lsof','-a','-p',str(proc['pid']),'-d','cwd','-Fn').splitlines() if x.startswith('n'))
 assert cwd==(str(source) if port==18080 else str(R))
w=Path(wr['source']);assert {str(p.relative_to(w)):hashlib.sha256(p.read_bytes()).hexdigest() for p in w.rglob('*') if p.is_file()}==wr['manifest']
ui=read(R/'.evidence/qyh-creator-workflow-read-failure-ui-20261014/hydration-code-review-manifest-r16.json')
assert all(hashlib.sha256((w/f).read_bytes()).hexdigest()==sha for f,sha in ui['sourceHashes'].items())
fp=R/'.evidence/qyh-restoration-successor-latest-restart-20261013'
b=read(fp/'daily-latest-before-20261015.json');a=read(fp/'daily-after-pg-20261015.json');f=read(fp/'daily-accepted-final-20261015.json')
assert b['fingerprints']==a['fingerprints']==f['fingerprints'] and len(f['fingerprints'])==650
assert b['containerId']==a['containerId']==f['containerId']=='84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c'
assert all(x['volume']=='aos-qyh-history159-prepared-data-20261011' and x['native']['cluster']=='7695302940039200809' and x['native']['schema']=='a0v_161' and x['native']['enabledBindings']==0 for x in [b,a,f])
assert a['pgStartedAt']==f['pgStartedAt']==read(P/'pg-terminal.json')['startedAfter'] and b['pgStartedAt']!=f['pgStartedAt']
core=read(P/'native-core-read-deny-r1.json');assert core['who']=={'subject':'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657','orgId':'org-org','projectId':'dev-project','tokenKind':'oidc'}
assert core['drafts']=={'tenant':{'orgId':'org-org','projectId':'dev-project'},'count':0,'items':0} and core['unknownQuery']['status']==400 and core['anonymousStatus']==401
pages=read(P/'native-eight-menu-r1.json')['pages'];assert len(pages)==8 and len({x['route'] for x in pages})==8 and all(x['rootStatus']==200 and x['tenant']==core['drafts']['tenant'] for x in pages)
net=read(P/'native-network-final-r1.json');assert not net['nonGet'] and all(x['method']=='GET' for x in net['network'])
report={'head':cfg['head'],'apiPid':api['pid'],'webPid':web['pid'],'apiSourceGuard':True,'webManifestVerified':True,'hydrationSourceHashesExact':True,'sameVolumeCluster':True,'fingerprints650Equal':True,'genuineOidcReadback':True,'rootsEight200':True,'coreDraftsEmpty200Query400Anonymous401':True,'nonGetBusinessRequests':0,'auxiliary404Remaining':sorted({x['path'] for x in net['network'] if x['status']==404}),'allVisualPassed':False,'wholeGoalComplete':False,'scriptSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with (P/'live-verification-r2.json').open('x') as out:json.dump(report,out,indent=2)
print(json.dumps(report))
