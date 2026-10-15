"""Prove the existing NEED_EVIDENCE gate denies before signals; no PASS fabrication."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
E=Path(__file__).resolve().parent;R=E.parents[1]
def command(*args):return subprocess.check_output(args,cwd=R,text=True).strip()
def state():
    pg=json.loads(command('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0]
    return {'apiListener':command('lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN'),
        'apiCommand':command('ps','-p','80779','-o','command='),
        'webListener':command('lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN'),
        'webCommand':command('ps','-p','89803','-o','command='),
        'pgId':pg['Id'],'pgStartedAt':pg['State']['StartedAt'],
        'apiEffectsArtifacts':{name:(E/name).exists() for name in [
            'api-switch-intent-r1.json','api-old-stop-r1.json','api-started-r1.json','price-disposition-live-api-r1.log']}}
def save(name,value):
    with (E/name).open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
before=state()
assert before['apiListener']=='80779' and before['webListener']=='89803'
assert not any(before['apiEffectsArtifacts'].values())
assert json.loads((E/'api-controller-review-result-r3.json').read_text())['result']['verdict']=='NEED_EVIDENCE'
script=E/'price_disposition_api_switch_r3.py'
save('pre-effect-gate-deny-intent-r4.json',dict(before=before,controllerSha=hashlib.sha256(script.read_bytes()).hexdigest(),
    purpose='Negative gate probe only: existing NEED_EVIDENCE must throw inside quality/legal before any intent or signal. No change to gate or review.'))
result=subprocess.run([str(R/'services/aos-api/.venv/bin/python'),str(script),'--phase','api'],cwd=R,capture_output=True,text=True)
with (E/'pre-effect-gate-deny-raw-r4.log').open('x') as stream:stream.write(result.stdout+result.stderr)
after=state()
assert result.returncode!=0 and before==after
assert 'in legal' in result.stderr and result.stderr.rstrip().endswith('AssertionError')
save('pre-effect-gate-deny-result-r4.json',dict(before=before,after=after,statesExactlyEqual=True,
    returncode=result.returncode,deniedBeforeIntentAndSignal=True,gateStillNeedEvidence=True,
    rawLogSha=hashlib.sha256((E/'pre-effect-gate-deny-raw-r4.log').read_bytes()).hexdigest(),
    notPostEffectProof=True,wholeGoalComplete=False))
print(json.dumps(dict(deniedBeforeIntentAndSignal=True,api80779StillRunning=True,statesExactlyEqual=True)))
