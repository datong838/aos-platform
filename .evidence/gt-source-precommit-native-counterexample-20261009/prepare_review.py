import hashlib,json,subprocess
from pathlib import Path
B=Path(__file__).resolve().parent;R=B.parents[1]
files=[B/x for x in ('plan.md','probe.c','run_probe.py','verify_probe.py','results.json','independent-verification.json','review.md','task.json')]
materials={str(x.relative_to(R)):x.read_text() for x in files}
request=dict(schema='aos-material-review/v1',kind='quality',request_id='precommit-native-candidate-quality-r1',task_id=B.name,owner='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2',baseline=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-001650',files={str(x.relative_to(R)):hashlib.sha256(x.read_bytes()).hexdigest() for x in files}),materials=materials,claims=['The test C establishes opposite PRE_COMMIT callback orders without a signed Source or production authorization.', 'The two single native commit attempts have known outcomes: check-before-wait committed after the deadline and wait-before-check rejected with 23514.', 'Independent read-only evidence contains exactly one retained test row, committed/aborted xid statuses, durable settings, and comparison of 92 existing containers.', 'The conclusion rejects the single-callback strict completion candidate and does not claim the complete Source or business goal is green.'])
(B/'quality-request-r1.json').write_text(json.dumps(request,indent=2))
print('Frozen quality review prepared')
