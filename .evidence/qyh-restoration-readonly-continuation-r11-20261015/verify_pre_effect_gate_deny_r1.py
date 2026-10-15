"""Prove the missing mandatory independent review gate denies before signals; no PASS fabrication."""
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
        'apiCommand':command('ps','-p','44093','-o','command='),
        'webListener':command('lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN'),
        'webCommand':command('ps','-p','89803','-o','command='),
        'pgId':pg['Id'],'pgStartedAt':pg['State']['StartedAt'],
        'apiEffectsArtifacts':{name:(E/name).exists() for name in [
            'api-switch-intent-r1.json','api-old-stop-r1.json','api-started-r1.json','customer-closure-live-api-r1.log']}}
def save(name,value):
    with (E/name).open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
before=state()
assert before['apiListener']=='44093' and before['webListener']=='89803'
assert not any(before['apiEffectsArtifacts'].values())
assert not (E/'api-controller-review-request-r1.json').exists() and not (E/'api-controller-review-result-r1.json').exists()
script=E/'customer_closure_api_switch_r1.py'
save('pre-effect-gate-deny-intent-r1.json',dict(before=before,controllerSha=hashlib.sha256(script.read_bytes()).hexdigest(),
    purpose='Negative gate probe only: missing mandatory independent review must throw inside quality/legal before any intent or signal. No change to gate or review.'))
result=subprocess.run([str(R/'services/aos-api/.venv/bin/python'),str(script),'--phase','api'],cwd=R,capture_output=True,text=True)
with (E/'pre-effect-gate-deny-raw-r1.log').open('x') as stream:stream.write(result.stdout+result.stderr)
after=state()
assert result.returncode!=0 and before==after
assert 'in quality' in result.stderr and 'FileNotFoundError' in result.stderr and 'api-controller-review-request-r1.json' in result.stderr
save('pre-effect-gate-deny-result-r1.json',dict(before=before,after=after,statesExactlyEqual=True,
    returncode=result.returncode,deniedBeforeIntentAndSignal=True,gateMissingReview=True,
    rawLogSha=hashlib.sha256((E/'pre-effect-gate-deny-raw-r1.log').read_bytes()).hexdigest(),
    notPostEffectProof=True,wholeGoalComplete=False))
print(json.dumps(dict(deniedBeforeIntentAndSignal=True,api44093StillRunning=True,statesExactlyEqual=True)))
