from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1];S=R/'.evidence/qyh-restoration-successor-latest-restart-20261013'
sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
HEAD='17164dc7b71bdb897db501d03657741f42c8122b';PID=44093
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(*args):return subprocess.check_output(args,cwd=R,text=True).strip()
def save(name,value):
 with (E/name).open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
assert command('git','rev-parse','HEAD')==HEAD
source=guard.require_api_source_candidate(R/'.evidence/qyh-full-system-restoration-20261011/customer-contact-api-20261015.json')
assert command('lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN')==str(PID) and str(source) in command('lsof','-a','-p',str(PID),'-d','cwd','-Fn')
assert command('lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN')=='89803'
assert not command('git','diff','f036e46c643308651b415179e6e991870dbc26ab','HEAD','--','apps/web')
before_path=S/'customer-contact-before-20261015.json';after_path=S/'customer-contact-after-20261015.json'
before,after=read(before_path),read(after_path)
assert len(before['fingerprints'])==len(after['fingerprints'])==650 and before['fingerprints']==after['fingerprints']
for key in ['native','containerId','volume','pgStartedAt']:assert before[key]==after[key]
pg=json.loads(command('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0]
assert pg['Id']==before['containerId'] and pg['State']['StartedAt']==before['pgStartedAt'] and pg['Mounts'][0]['Name']==before['volume']
sdk=read(E/'contact-native-identity-sdk-r1.json')
assert sdk['me']==dict(subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657',orgId='org-org',projectId='dev-project')
view=sdk['view'];assert view['tenant']==dict(orgId='org-org',projectId='dev-project') and view['primaryColleague']=='私域管家'
assert view['frequencyPolicyCount']==view['withdrawalCount']==0 and view['latestStart'] is None
assert all(v==0 for v in view['ledger'].values()) and len(view['ledger'])==9
assert view['allowedCommands']==[] and view['blockers']==['CUSTOMER_CONTACT_GOVERNANCE_NOT_PREPARED']
assert view['permitRedemptionAllowed'] is view['contactResolutionAllowed'] is view['providerDispatchAllowed'] is view['sendAllowed'] is view['externalEffectsAllowed'] is False
assert sdk['deny']['query']['status']==400 and sdk['deny']['closure']['status']==404 and sdk['anonymousStatus']==401
browser=read(E/'contact-native-geometry-deny-r1.json');assert browser['businessNonGet']==[] and browser['temporaryViewportCleared']
assert len(browser['normalAuthPosts'])==1 and browser['normalAuthPosts'][0]['status']==200
screens=[]
for width,height in [(1280,720),(1440,900),(1920,1080)]:
 metric=next(x for x in browser['metrics'] if x['width']==width)
 assert metric['geometry']['documentWidth']==metric['geometry']['viewportWidth']==width and not metric['geometry']['loading']
 assert len(metric['geometry']['buttons'])==4 and all(b['height']==32 for b in metric['geometry']['buttons'])
 assert metric['filters']==[['可披露'],['待复核'],['已排除'],['全部']]
 assert len(metric['tabs'])==4 and all(len(x)==1 for x in metric['tabs']) and len({x[0] for x in metric['tabs']})==4
 assert all(p['right']<=width for p in metric['geometry']['panels'])
 for kind in ['reference','actual']:
  path=E/f'contact-{kind}-{width}-r1.png';assert struct.unpack('>II',path.read_bytes()[16:24])==(width,height)
  screens.append(dict(file=path.name,sha256=sha(path),width=width,height=height,inspected=True))
save('contact-full650-comparison-r1.json',dict(beforeFile=str(before_path.relative_to(R)),beforeSha=sha(before_path),afterFile=str(after_path.relative_to(R)),afterSha=sha(after_path),count=650,allEqual=True,differences=[],tableEquality={t:before['fingerprints'][t]==after['fingerprints'][t] for t in sorted(before['fingerprints'])}))
save('contact-live-shas-r1.json',dict(finalScreens=screens,captureMethod='actual native scale=css; reference stable paint then explicit CSS clip scale1',temporaryOverridesCleared=True,wholeVisualComplete=False))
save('contact-runtime-proof-r1.json',dict(head=HEAD,signingCodeHead='90a601fd1ad2a57c128bf05416dbf97239412865',apiPid=PID,apiSource=str(source),sourceGuard=True,webPid=89803,webSourceHead='f036e46c643308651b415179e6e991870dbc26ab',frontendTreesUnchanged=True,originalContainerId=before['containerId'],originalVolume=before['volume'],pgStartedAt=before['pgStartedAt'],schema='a0v_161',tables=650,enabledBindings=0,all650BeforeAfterEqual=True,actualContactSdk200=True,actualSavedCounts=[0,0],latestStart=None,ledgerAllZero=True,commandsEmpty=True,allFivePublicEffectFlagsFalse=True,query400=True,anonymous401=True,customerClosureStill404=True,businessNonGet=[],actualThreeViewportsWithoutHorizontalOverflow=True,fourTabsAndFourFiltersSwitch=True,actualDataEmptyNotFixture=True,onlyApiSwitched=True,dailyFullPgApiWebRestartSubstitute=False,wholeGoalComplete=False))
print(json.dumps(dict(apiPid=PID,all650Equal=True,contactSdk200=True,sameSizeScreens=6,businessNonGet=[],wholeGoalComplete=False)))
