"""Read-only process/source/data evidence after the single authorized API switch."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
S=R/'.evidence/qyh-restoration-successor-latest-restart-20261013'
sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
HEAD='4e038063368cc41fe17aec7b9f6148fa66bd7192'
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def cmd(*args):return subprocess.check_output(args,cwd=R,text=True).strip()
def save(name,value):
    with (E/name).open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
assert cmd('git','rev-parse','HEAD')==HEAD
source=guard.require_api_source_candidate(R/'.evidence/qyh-full-system-restoration-20261011/price-disposition-api-20261015.json')
assert cmd('lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN')=='95375'
assert str(source) in cmd('lsof','-a','-p','95375','-d','cwd','-Fn')
assert cmd('lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN')=='89803'
assert not cmd('git','diff','f036e46c643308651b415179e6e991870dbc26ab','HEAD','--','apps/web')
before=read(S/'price-disposition-before-20261015.json');after=read(S/'price-disposition-after-20261015.json')
assert len(before['fingerprints'])==len(after['fingerprints'])==650
assert before['fingerprints']==after['fingerprints']
for key in ['native','containerId','volume','pgStartedAt']:assert before[key]==after[key]
pg=json.loads(cmd('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0]
assert pg['Id']==before['containerId'] and pg['State']['StartedAt']==before['pgStartedAt'] and pg['Mounts'][0]['Name']==before['volume']
sdk=read(E/'disposition-native-identity-sdk-r1.json')
assert sdk['me']==dict(subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657',orgId='org-org',projectId='dev-project')
view=sdk['view'];assert view['caseCount']==0 and set(view['dispositionCounts'].values())=={0}
assert view['latestDisposition'] is view['latestObservation'] is None
assert view['allowedCommands']==[] and view['repricingEnabled'] is view['externalEffectsAllowed'] is False
browser=read(E/'disposition-native-geometry-deny-r1.json')
assert browser['deny']['anonymousStatus']==401 and not browser['businessNonGet']
assert any(x['path'].endswith('/price-governance/dispositions') and x['status']==200 for x in browser['trace'])
assert any(x['path'].endswith('/price-governance/dispositions') and x['status']==400 for x in browser['trace'])
assert any(x['status']==404 for x in browser['canonicalPriceClosure'])
screens=[]
for width,height in [(1280,720),(1440,900),(1920,1080)]:
    metric=next(x for x in browser['metrics'] if x['width']==width)
    assert all(x['height']==32 for x in metric['geometry']['buttons'])
    assert metric['geometry']['documentWidth']<=width and not metric['geometry']['loading']
    assert [x['pressed'] for x in metric['filters']]==[['可比'],['待复核'],['已排除'],['全部']]
    for kind,version in [('actual','r2'),('reference','r3')]:
        path=E/f'disposition-{kind}-{width}-{version}.png'
        assert struct.unpack('>II',path.read_bytes()[16:24])==(width,height)
        screens.append(dict(file=path.name,sha256=sha(path),width=width,height=height,inspected=True))
save('disposition-full650-comparison-r1.json',dict(
    beforeFile=str((S/'price-disposition-before-20261015.json').relative_to(R)),beforeSha=sha(S/'price-disposition-before-20261015.json'),
    afterFile=str((S/'price-disposition-after-20261015.json').relative_to(R)),afterSha=sha(S/'price-disposition-after-20261015.json'),
    count=650,allEqual=True,differences=[],
    tableEquality={table:before['fingerprints'][table]==after['fingerprints'][table] for table in sorted(before['fingerprints'])}))
save('disposition-live-shas-r1.json',dict(finalScreens=screens,
    finalPair='actual r2 native CSS-scale captures / reference r3 stable paint + explicit CSS clip(scale1)',
    preservedInvalidCaptures='actual r1 device-pixel dimensions; reference r1 native-view aspect ratio, r2 surface scale/crop, r4 experimental half-scale padding; never use as same-size acceptance.',
    reference1280r3Confirmed=True,postCaptureViewportOverridesCleared=True))
save('disposition-runtime-proof-r1.json',dict(head=HEAD,apiPid=95375,apiSource=str(source),sourceGuard=True,
    webPid=89803,webSourceHead='f036e46c643308651b415179e6e991870dbc26ab',frontendTreesUnchanged=True,
    originalContainerId=before['containerId'],originalVolume=before['volume'],pgStartedAt=before['pgStartedAt'],
    schema='a0v_161',tables=650,enabledBindings=0,all650BeforeAfterEqual=True,
    actualNativeDispositionSdk200=True,query400=True,anonymous401=True,commandsEmpty=True,externalEffectsAllowed=False,
    actualThreeViewportFilters32px=True,businessNonGet=[],actualDataEmptyNotFixture=True,
    canonicalPriceClosureStill404=True,manualInvalidPriceGovernanceClosurePath400NotCanonical=True,
    loginTimeoutReconciled='input[type=text] matched0 because original text input omitted type attribute. No auth/token resource and idle form; subsequent form input indexes completed one normal POST200. No unknown submit replay.',
    healthRoot404NotHealthRoute=True,actualApiV1Health200=True,
    onlyApiSwitched=True,dailyFullPgApiWebRestartSubstitute=False,wholeGoalComplete=False))
print(json.dumps(dict(apiPid=95375,all650Equal=True,actualSdk200=True,finalSameSizeScreens=6,businessNonGet=[],wholeGoalComplete=False)))
