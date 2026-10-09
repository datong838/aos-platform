"""Close only the bounded observed-outcome task, preserving full feature gates."""
from pathlib import Path
import json, subprocess, hashlib, importlib.util, sys
R=Path(__file__).resolve().parents[2]; B=Path(__file__).resolve().parent
a=json.loads((B/'independent-verification.json').read_text())
assert a['old_resources_unchanged'] and a['original_products_unchanged']
assert a['observations'][0]['original_xact_state']=='committed'
assert a['teardown_assertion_failed'] and not a['complete_test_pass']
files=[str(p.relative_to(R)) for p in sorted(B.iterdir()) if p.is_file()]
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).strip()
subprocess.run(['git','add','--',*files],cwd=R,check=True)
assert set(subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).splitlines())<=set(files)
subprocess.run(['git','commit','-m','test(aip): observe actual Source commit beyond body expiry'],cwd=R,check=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
sp=importlib.util.spec_from_file_location('m',R/'scripts/memory/memoryctl.py')
m=importlib.util.module_from_spec(sp);sys.modules['m']=m;sp.loader.exec_module(m)
auth=m.load_authority();assert auth['project_revision']=='AOS-001628'
d=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=auth['project_revision'],
 result='SOURCE_BODY_EXPIRY_COMMIT_OBSERVATION_COMPLETE_WITH_TEARDOWN_ERROR',
 changed_files=['aos-platform/.evidence/'+B.name],commits=[head],
 verification=['Shared native SCRAM original xid13812/pid27985 finalized before expiry; actual Source body deadline crossed with JWT live; one actual COMMIT succeeded',
 'Independent committed xid/exact Source hash/native C signature/provenance/NOLOGIN/temporary interfaces absent/31 resources unchanged; products unchanged'],
 risks=['Pytest exit1: call passed, teardown error retained; complete test is NOT GREEN',
 'Only bounded observation closed; Source/epoch/legacy feature delivery and final COMMIT semantics unresolved; distinct layout and current consumer expiry pending; no formal execution'],blockers=[])
rev=m.update_authority(expected_revision=auth['project_revision'],current_phase=auth['current_phase'],
 delivery_status=auth['delivery_status'],last_green_gate=auth['last_green_gate'],next_gate=auth['next_gate'],
 evidence=auth['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',
 summary='Shared native Source body expiry actual COMMIT observation: xid13812/pid27985 commits after original valid_until with authentic JWT still live. Independent retained DB signature/hash/provenance/role/interface/31resource checks pass. Pytest call PASS but teardown ERROR (322.77s), not full GREEN. Bounded observation only; final temporal semantics, distinct layout, consumer expiry and full Source/epoch/legacy Delivery remain pending. No product/currentDB/runtime/Provider/Goal changes.')])
orig=m.atomic_write_text
m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=f,sha256=hashlib.sha256((R/f).read_bytes()).hexdigest()) for f in files]
updates=[]
for task in ['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008']:
 cpfile=R/'.evidence'/task/'checkpoint.json';cp=json.loads(cpfile.read_text())
 prior='.evidence/'+task+'/source-post-finalize-expiry-review-reference-1628.json'
 ref='.evidence/'+task+'/source-body-expiry-commit-reference-1629.json'
 assert prior in cp['evidence_files']
 (R/ref).write_text(json.dumps(dict(authority_revision=rev['project_revision'],head=head,
 references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2))
 cp.update(authority_revision=rev['project_revision'],step='source-body-expiry-commit-observed-current-consumer-expiry-next')
 cp['evidence_files']=[ref if x==prior else x for x in cp['evidence_files']]
 cpfile.write_text(json.dumps(cp,indent=2));updates.extend([str(cpfile.relative_to(R)),ref])
assert m.validate_installation()['status']=='GREEN'
assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
(B/'context-delivery.json').write_text(json.dumps(dict(delivery=d,revision=rev['project_revision'],sync=sync,
 validation='GREEN',strong_projections='CURRENT',complete_test_pass=False),ensure_ascii=False,indent=2))
updates.append(str((B/'context-delivery.json').relative_to(R)))
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).strip()
subprocess.run(['git','add','--',*updates],cwd=R,check=True)
assert set(subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).splitlines())<=set(updates)
subprocess.run(['git','commit','-m','docs(aos): record Source expiry observation and teardown limitation'],cwd=R,check=True)
print(rev['project_revision'],'BOUNDED_OBSERVATION_CLOSED')
