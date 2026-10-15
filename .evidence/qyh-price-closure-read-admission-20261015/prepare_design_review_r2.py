from pathlib import Path
import hashlib
import json
import os
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
assert (E/'design-review-result-r1.transport.json').exists() and not (E/'design-review-result-r1.json').exists()
transport=E/'design-review-result-r1.transport.json'
assert json.loads(transport.read_text())['returncode']==0
request=json.loads((E/'design-review-request-r1.json').read_text())
old=next(iter(request['materials'].values()))
note={'priorRequestId':request['request_id'],'terminalOutcome':'RAW_JSON_EXTRA_DATA_STRICT_PARSE_REJECTED',
    'transportSha':hashlib.sha256(transport.read_bytes()).hexdigest(),'noLegalConsumption':True,
    'productCodeChanged':False,'rawNeverRepaired':True}
with (E/'design-review-terminal-r1.json').open('x') as stream:json.dump(note,stream,indent=2)
material=E/'design-review-material-r2.txt'
with material.open('x') as stream:
    stream.write('FRESH DESIGN R2. Prior model response terminated but strict raw JSON parser rejected extra data; not consumed and never repaired. No product changes. Return exactly one JSON object and no text before or after it.\n'+json.dumps(note)+'\n'+old)
relative=str(material.relative_to(R));request['request_id']=E.name+'-design-r2'
request['materials']={relative:material.read_text()};request['baseline']['files']={relative:hashlib.sha256(material.read_bytes()).hexdigest()}
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'design-review-request-r2.json').open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'freshRequest':request['request_id'],'priorRawNotConsumed':True,'productChanges':False}))
