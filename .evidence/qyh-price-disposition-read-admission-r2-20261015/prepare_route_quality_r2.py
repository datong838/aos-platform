from pathlib import Path
import hashlib
import json
import os
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
proof=json.loads((R/'.evidence/qyh-price-disposition-bounded-reader-20261015/source-verification-r1.json').read_text())
current={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in proof['sourceAfter']}
assert current==proof['sourceAfter'] and proof['returncode']==0
ledger={'stageExplanation':'http-red-r1.log is deliberately retained PRE-IMPLEMENTATION RED (10 failed,4 passed). It is not current candidate evidence. The unmodified six-file candidate passed frozen267 and now all17 targeted current route tests. R1 REWORK is preserved/legally consumed; no code changed to conceal RED or bypass review.',
    'frozen267SourceEqualsCurrent':current,'currentTargetedLog':'http-stage-green-r2.log',
    'currentTargetedLogSha':hashlib.sha256((E/'http-stage-green-r2.log').read_bytes()).hexdigest(),
    'priorReworkResultSha':hashlib.sha256((E/'route-quality-result-r1.json').read_bytes()).hexdigest(),
    'priorReworkConsumption':json.loads((E/'route-quality-consumption-r1.json').read_text())}
with (E/'route-stage-ledger-r2.json').open('x') as stream:json.dump(ledger,stream,ensure_ascii=False,indent=2)
material=E/'route-quality-material-r2.txt'
with material.open('x') as stream:
    stream.write('REVIEW R2: separate preserved historical pre-code RED from current post-code GREEN. Check current source and all17 full targeted results below; r1 suggested fixing code based on RED, so fresh independent validation was gathered without altering code.\n')
    stream.write(json.dumps(ledger,ensure_ascii=False,indent=2)+'\nCURRENT TARGETED FULL RAW LOG\n'+(E/'http-stage-green-r2.log').read_text())
    stream.write('\nUNCHANGED R1 FROZEN CODE MATERIAL (its http-red excerpt is HISTORICAL PRE-CODE)\n'+(E/'route-quality-material-r1.txt').read_text())
relative=str(material.relative_to(R));materials={relative:material.read_text()}
assert len(json.dumps(materials).encode())<=65536,len(json.dumps(materials).encode())
request=json.loads((E/'route-quality-request-r1.json').read_text())
request['request_id']=E.name+'-route-quality-r2';request['materials']=materials
request['baseline']['files']={relative:hashlib.sha256(material.read_bytes()).hexdigest()}
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'route-quality-request-r2.json').open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'materialBytes':len(json.dumps(materials).encode()),'codeChangedSinceFrozen267':False}))
