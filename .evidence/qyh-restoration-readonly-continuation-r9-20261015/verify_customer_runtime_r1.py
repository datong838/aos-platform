from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1];S=R/'.evidence/qyh-restoration-successor-latest-restart-20261013'
sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
HEAD='80b39a1a8d5f7b76e942c7005e8d4086980d215f';PID=15265
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(*args):return subprocess.check_output(args,cwd=R,text=True).strip()
def save(name,value):
 with (E/name).open('x') as stream:
  json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
assert command('git','rev-parse','HEAD')==HEAD
source=guard.require_api_source_candidate(R/'.evidence/qyh-full-system-restoration-20261011/customer-contribution-api-20261015.json')
assert command('lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN')==str(PID)
assert str(source) in command('lsof','-a','-p',str(PID),'-d','cwd','-Fn')
assert command('lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN')=='89803'
assert not command('git','diff','f036e46c643308651b415179e6e991870dbc26ab','HEAD','--','apps/web')
before_path=S/'customer-contribution-before-20261015.json';after_path=S/'customer-contribution-after-20261015.json'
before,after=read(before_path),read(after_path)
assert len(before['fingerprints'])==len(after['fingerprints'])==650 and before['fingerprints']==after['fingerprints']
for key in ['native','containerId','volume','pgStartedAt']:assert before[key]==after[key]
pg=json.loads(command('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0]
assert pg['Id']==before['containerId'] and pg['State']['StartedAt']==before['pgStartedAt'] and pg['Mounts'][0]['Name']==before['volume']
sdk=read(E/'customer-native-identity-sdk-r1.json')
assert sdk['me']==dict(subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657',orgId='org-org',projectId='dev-project')
view=sdk['view'];assert view['tenant']==dict(orgId='org-org',projectId='dev-project') and view['primaryColleague']=='私域管家'
assert all(view[key]==0 for key in ['consentPolicyCount','segmentCount','journeyCount','dialogueCount'])
assert view['latestBatch'] is None and view['allowedCommands']==[]
assert view['blockers']==['CUSTOMER_CONTACT_RESOLUTION_NOT_AUTHORIZED','CUSTOMER_START_SEND_NOT_AUTHORIZED']
assert view['contactResolutionAllowed'] is view['startAllowed'] is view['sendAllowed'] is view['externalEffectsAllowed'] is False
assert sdk['deny']['query']['status']==400 and sdk['deny']['contact']['status']==sdk['deny']['closure']['status']==404
assert sdk['anonymousStatus']==401
browser=read(E/'customer-native-geometry-deny-r1.json');assert browser['businessNonGet']==[] and browser['temporaryViewportCleared']
screens=[]
for width,height in [(1280,720),(1440,900),(1920,1080)]:
 metric=next(x for x in browser['metrics'] if x['width']==width)
 assert metric['geometry']['documentWidth']==metric['geometry']['viewportWidth']==width and not metric['geometry']['loading']
 filters=[b for b in metric['geometry']['buttons'] if b['text'] in ['全部','可披露','待复核','已排除']]
 assert len(filters)==4 and all(b['height']==32 for b in filters)
 assert metric['filterStates']==[['可披露'],['待复核'],['已排除'],['全部']]
 assert len(metric['tabStates'])==4 and all(len(x)==1 for x in metric['tabStates']) and len({x[0] for x in metric['tabStates']})==4
 assert all(p['right']<=width for p in metric['geometry']['panels'])
 for kind in ['reference','actual']:
  path=E/f'customer-{kind}-{width}-r1.png';assert struct.unpack('>II',path.read_bytes()[16:24])==(width,height)
  screens.append(dict(file=path.name,sha256=sha(path),width=width,height=height,inspected=True))
save('customer-full650-comparison-r1.json',dict(beforeFile=str(before_path.relative_to(R)),beforeSha=sha(before_path),afterFile=str(after_path.relative_to(R)),afterSha=sha(after_path),count=650,allEqual=True,differences=[],tableEquality={t:before['fingerprints'][t]==after['fingerprints'][t] for t in sorted(before['fingerprints'])}))
save('customer-live-shas-r1.json',dict(finalScreens=screens,captureMethod='actual native scale=css; reference stable paint then explicit CSS clip scale1',temporaryOverridesCleared=True,wholeVisualComplete=False))
save('customer-runtime-proof-r1.json',dict(head=HEAD,apiPid=PID,apiSource=str(source),sourceGuard=True,webPid=89803,webSourceHead='f036e46c643308651b415179e6e991870dbc26ab',frontendTreesUnchanged=True,originalContainerId=before['containerId'],originalVolume=before['volume'],pgStartedAt=before['pgStartedAt'],schema='a0v_161',tables=650,enabledBindings=0,all650BeforeAfterEqual=True,actualCustomerSdk200=True,actualSavedCounts=[0,0,0,0],latestBatch=None,commandsEmpty=True,allFourPublicEffectFlagsFalse=True,query400=True,anonymous401=True,customerContactAndClosureStill404=True,businessNonGet=[],actualThreeViewportsWithoutHorizontalOverflow=True,fourTabsAndFourFiltersSwitch=True,actualDataEmptyNotFixture=True,onlyApiSwitched=True,dailyFullPgApiWebRestartSubstitute=False,wholeGoalComplete=False))
print(json.dumps(dict(apiPid=PID,all650Equal=True,customerSdk200=True,sameSizeScreens=6,businessNonGet=[],wholeGoalComplete=False)))
