"""Missing mandatory current review must deny before Web intent/signals."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

E = Path(__file__).resolve().parent
R = E.parents[1]


def cmd(*args): return subprocess.check_output(args, cwd=R, text=True).strip()


def state():
    pg = json.loads(cmd('docker', '--context', 'colima-aos-extension', 'inspect', 'qyh-restored-pg-20261011'))[0]
    return dict(apiListener=cmd('lsof', '-t', '-nP', '-iTCP:18080', '-sTCP:LISTEN'), apiCommand=cmd('ps', '-p', '54057', '-o', 'command='), webListener=cmd('lsof', '-t', '-nP', '-iTCP:18434', '-sTCP:LISTEN'), webCommand=cmd('ps', '-p', '89803', '-o', 'command='), pgId=pg['Id'], pgStartedAt=pg['State']['StartedAt'], effectFiles={n: (E / n).exists() for n in ['pointer-web-switch-intent-r1.json', 'pointer-web-old-stop-r1.json', 'pointer-web-started-r1.json', 'customer-pointer-live-web-r1.log']})


def save(name, value):
    with (E / name).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


before = state()
assert before['apiListener'] == '54057' and before['webListener'] == '89803'
assert not any(before['effectFiles'].values()) and not (E / 'web-controller-review-request-r2.json').exists()
script = E / 'customer_pointer_web_switch_r1.py'
save('pre-effect-gate-deny-intent-r2.json', dict(before=before, controllerSha=hashlib.sha256(script.read_bytes()).hexdigest(), purpose='Actual missing-review negative probe, no gate edits or fabricated PASS.'))
result = subprocess.run([str(R / 'services/aos-api/.venv/bin/python'), str(script), '--phase', 'web'], cwd=R, capture_output=True, text=True)
with (E / 'pre-effect-gate-deny-raw-r2.log').open('x') as stream:
    stream.write(result.stdout + result.stderr)
after = state()
assert result.returncode != 0 and before == after
assert 'in quality' in result.stderr and 'FileNotFoundError' in result.stderr and 'web-controller-review-request-r2.json' in result.stderr
save('pre-effect-gate-deny-result-r2.json', dict(before=before, after=after, statesExactlyEqual=True, returncode=result.returncode, deniedBeforeIntentAndSignal=True, gateMissingReview=True, wholeGoalComplete=False))
print(json.dumps(dict(deniedBeforeIntentAndSignal=True, servicesExactlyUnchanged=True)))
