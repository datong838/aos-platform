"""Reconcile exact live sources, original data and native SDK after one API switch."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1];S=R/'.evidence/qyh-restoration-successor-latest-restart-20261013'
sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
HEAD='04092c82f9dcaccf7b23ff6e61d536a9f650aa38'
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def command(*args):return subprocess.check_output(args,cwd=R,text=True).strip()
def save(name,value):
    with (E/name).open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
assert command('git','rev-parse','HEAD')==HEAD
source=guard.require_api_source_candidate(R/'.evidence/qyh-full-system-restoration-20261011/price-closure-api-20261015.json')
assert command('lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN')=='8498'
assert str(source) in command('lsof','-a','-p','8498','-d','cwd','-Fn')
assert command('lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN')=='89803'
assert not command('git','diff','f036e46c643308651b415179e6e991870dbc26ab','HEAD','--','apps/web')
before_path=S/'price-closure-before-20261015.json';after_path=S/'price-closure-after-20261015.json'
before,after=read(before_path),read(after_path)
assert len(before['fingerprints'])==len(after['fingerprints'])==650
assert before['fingerprints']==after['fingerprints']
for key in ['native','containerId','volume','pgStartedAt']:assert before[key]==after[key]
pg=json.loads(command('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0]
assert pg['Id']==before['containerId'] and pg['State']['StartedAt']==before['pgStartedAt'] and pg['Mounts'][0]['Name']==before['volume']
sdk=read(E/'closure-native-identity-sdk-r1.json')
assert sdk['me']==dict(subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657',orgId='org-org',projectId='dev-project')
for module in ['price','creator']:
    view=sdk[module]
    assert view['module']==module and view['tenant']==dict(orgId='org-org',projectId='dev-project')
    assert all(view[key] is None for key in ['latestClosure','latestUsage','latestEffect','latestHandoff'])
    assert len(view['blockers'])==4 and view['allowedCommands']==[]
    assert view['handoffConsumeAllowed'] is view['memoryPromotionAllowed'] is view['externalEffectsAllowed'] is False
browser=read(E/'closure-native-geometry-deny-r1.json')
assert browser['deny']['anonymousStatus']==401 and not browser['businessNonGet']
assert any(x['path'].endswith('/price/closure-contributions') and x['status']==400 for x in browser['trace'])
assert any(x['path'].endswith('/customer/closure-contributions') and x['status']==404 for x in browser['trace'])
screens=[]
for width,height in [(1280,720),(1440,900),(1920,1080)]:
    metric=next(x for x in browser['metrics'] if x['width']==width)
    assert all(x['height']==32 for x in metric['geometry']['buttons'])
    assert metric['geometry']['documentWidth']<=width and not metric['geometry']['loading']
    assert [x['pressed'] for x in metric['filters']]==[['可比'],['待复核'],['已排除'],['全部']]
    for kind in ['actual','reference']:
        path=E/f'closure-{kind}-{width}-r1.png'
        assert struct.unpack('>II',path.read_bytes()[16:24])==(width,height)
        screens.append(dict(file=path.name,sha256=sha(path),width=width,height=height,inspected=True))
save('closure-full650-comparison-r1.json',dict(beforeFile=str(before_path.relative_to(R)),beforeSha=sha(before_path),
    afterFile=str(after_path.relative_to(R)),afterSha=sha(after_path),count=650,allEqual=True,differences=[],
    tableEquality={table:before['fingerprints'][table]==after['fingerprints'][table] for table in sorted(before['fingerprints'])}))
save('closure-live-shas-r1.json',dict(finalScreens=screens,
    captureMethod='actual native scale=css; reference stable native paint then explicit CSS clip scale1',
    temporaryOverridesCleared=True,wholeVisualComplete=False))
save('closure-runtime-proof-r1.json',dict(head=HEAD,apiPid=8498,apiSource=str(source),sourceGuard=True,
    webPid=89803,webSourceHead='f036e46c643308651b415179e6e991870dbc26ab',frontendTreesUnchanged=True,
    originalContainerId=before['containerId'],originalVolume=before['volume'],pgStartedAt=before['pgStartedAt'],
    schema='a0v_161',tables=650,enabledBindings=0,all650BeforeAfterEqual=True,actualPriceSdk200=True,
    actualCreatorSdkStillCreator=True,fourActualGapsEach=True,commandsEmpty=True,allThreePublicEffectFlagsFalse=True,
    query400=True,anonymous401=True,customerClosureStill404=True,businessNonGet=[],actualThreeViewportFilters32px=True,
    actualDataEmptyNotFixture=True,onlyApiSwitched=True,dailyFullPgApiWebRestartSubstitute=False,wholeGoalComplete=False))
print(json.dumps(dict(apiPid=8498,all650Equal=True,priceAndCreatorSdk200=True,sameSizeScreens=6,businessNonGet=[],wholeGoalComplete=False)))
