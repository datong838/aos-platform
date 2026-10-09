"""Close only the bounded observed-outcome task, preserving full feature gates."""
from pathlib import Path
import json, subprocess, hashlib, importlib.util, sys
R=Path(__file__).resolve().parents[2]; B=Path(__file__).resolve().parent
a=json.loads((B/'independent-red-verification.json').read_text())
assert a['old_resources_unchanged'] and a['original_products_unchanged']
assert a['observations'][0]['original_source_committed'] and all(v in (0,'ABSENT') for v in a['observations'][0]['occupation_counts'].values())
assert not a['named_expiry_gate_pass'] and len(a['observations'][0]['denials'])==2 and all(x['sqlstate']=='P0002' for x in a['observations'][0]['denials'])
files=[str(p.relative_to(R)) for p in sorted(B.iterdir()) if p.is_file()]
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).strip()
subprocess.run(['git','add','--',*files],cwd=R,check=True)
assert set(subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).splitlines())<=set(files)
subprocess.run(['git','commit','-m','test(aip): capture current Source expiry named-denial RED'],cwd=R,check=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
sp=importlib.util.spec_from_file_location('m',R/'scripts/memory/memoryctl.py')
m=importlib.util.module_from_spec(sp);sys.modules['m']=m;sp.loader.exec_module(m)
auth=m.load_authority();assert auth['project_revision']=='AOS-001629'
d=None  # RED diagnostic remains ACTIVE; no Delivery.
rev=m.update_authority(expected_revision=auth['project_revision'],current_phase=auth['current_phase'],
 delivery_status=auth['delivery_status'],last_green_gate=auth['last_green_gate'],next_gate=auth['next_gate'],
 evidence=auth['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',
 summary='Current Source original body expiry diagnostic RED. r1 import error/no publication retained; r2 lost local transaction settings/boundary denial retained; r3 fresh Source/current distinct Owner positive, unchanged Source expiry crossed with valid signed consumer JWT, Python/native P0002 query returned no rows instead of named22023 expiry gate. Trusted original current approval query filters expiries before STRICT lookup; exact refusal semantics require original contract review. Independent Source committed/hash/native C signature/provenance unchanged, occupation tables ABSENT in Source-only fixture, roles/interfaces restored,31resources unchanged. Original product bytes unchanged; Task remains ACTIVE/no Delivery, no full Source/Goal/formal execution claim.')])
orig=m.atomic_write_text
m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=f,sha256=hashlib.sha256((R/f).read_bytes()).hexdigest()) for f in files]
updates=[]
for task in ['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008']:
 cpfile=R/'.evidence'/task/'checkpoint.json';cp=json.loads(cpfile.read_text())
 prior='.evidence/'+task+'/source-body-expiry-commit-reference-1629.json'
 ref='.evidence/'+task+'/current-source-body-expiry-reference-1630.json'
 assert prior in cp['evidence_files']
 (R/ref).write_text(json.dumps(dict(authority_revision=rev['project_revision'],head=head,
 references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2))
 cp.update(authority_revision=rev['project_revision'],step='current-source-body-expiry-named-denial-red-original-contract-review-next')
 cp['evidence_files']=[ref if x==prior else x for x in cp['evidence_files']]
 cpfile.write_text(json.dumps(cp,indent=2));updates.extend([str(cpfile.relative_to(R)),ref])
assert m.validate_installation()['status']=='GREEN'
assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
(B/'context-delivery.json').write_text(json.dumps(dict(delivery=d,revision=rev['project_revision'],sync=sync,
 validation='GREEN',strong_projections='CURRENT',named_expiry_gate_pass=False,task_status="ACTIVE"),ensure_ascii=False,indent=2))
updates.append(str((B/'context-delivery.json').relative_to(R)))
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).strip()
subprocess.run(['git','add','--',*updates],cwd=R,check=True)
assert set(subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).splitlines())<=set(updates)
subprocess.run(['git','commit','-m','docs(aos): register current Source expiry diagnostic RED'],cwd=R,check=True)
print(rev['project_revision'],'CURRENT_SOURCE_EXPIRY_DIAGNOSTIC_RED_TASK_ACTIVE')
