"""Close only the bounded observed-outcome task, preserving full feature gates."""
from pathlib import Path
import json, subprocess, hashlib, importlib.util, sys
R=Path(__file__).resolve().parents[2]; B=Path(__file__).resolve().parent
a=json.loads((B/'independent-verification.json').read_text())
assert a['old_resources_unchanged'] and a['original_products_unchanged']
assert a['observations'][0]['original_source_committed'] and set(a['observations'][0]['occupation_counts'].values())=={0}
assert len(a['observations'][0]['denials'])==2 and all(x['sqlstate']=='22023' for x in a['observations'][0]['denials'])
files=[str(p.relative_to(R)) for p in sorted(B.iterdir()) if p.is_file()]
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).strip()
subprocess.run(['git','add','--',*files],cwd=R,check=True)
assert set(subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).splitlines())<=set(files)
subprocess.run(['git','commit','-m','test(aip): verify current consumer denial beyond original Source expiry'],cwd=R,check=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
sp=importlib.util.spec_from_file_location('m',R/'scripts/memory/memoryctl.py')
m=importlib.util.module_from_spec(sp);sys.modules['m']=m;sp.loader.exec_module(m)
auth=m.load_authority();assert auth['project_revision']=='AOS-001629'
d=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=auth['project_revision'],
 result='CURRENT_SOURCE_ORIGINAL_BODY_EXPIRY_DENIAL_OBSERVED',
 changed_files=['aos-platform/.evidence/'+B.name],commits=[head],
 verification=['Shared native signed Source; distinct current Owner/xid/pid positive consumer before unchanged original Source deadline; original DB clock crosses deadline with current signed consumer JWT still valid; Python and native SQL deny',
 'Independent original Source committed/hash/native C signature/provenance unchanged; six occupation tables zero; NOLOGIN/temporary interfaces absent/31 resources unchanged; products unchanged'],
 risks=['r1 diagnostic ImportError before publication retained; r2 diagnostic rollback lost transaction settings and produced boundary denial, not expiry proof; r3 expected expired-input fixture teardown refusal explicitly verified, no product fixture change',
 'Only shared current Source expiry diagnostic closed; Source/epoch/legacy feature Delivery, distinct layout and final COMMIT semantics unresolved; current consumer extra-key validation separately registered, no formal execution'],blockers=[])
rev=m.update_authority(expected_revision=auth['project_revision'],current_phase=auth['current_phase'],
 delivery_status=auth['delivery_status'],last_green_gate=auth['last_green_gate'],next_gate=auth['next_gate'],
 evidence=auth['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',
 summary='Shared current Owner real Source consumption positive before original Source valid_until; actual unchanged deadline crossed while current signed consumer JWT still valid; Python/native current consumer both deny with exact original expiry reason. Independent committed Source signature/hash/provenance unchanged, six occupation tables zero, NOLOGIN/interfaces restored,31resources unchanged. r1 diagnostic ImportError retained/no publication; r2 diagnostic transaction-boundary denial retained/not expiry proof; r3 expired-input fixture cleanup refusal explicitly verified. Bounded diagnostic only; final COMMIT semantics/distinct/current consumer extra-key/full Source feature Delivery remain pending. No product/currentDB/runtime/Provider/Goal changes.')])
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
 cp.update(authority_revision=rev['project_revision'],step='current-source-body-expiry-denied-current-command-validation-next')
 cp['evidence_files']=[ref if x==prior else x for x in cp['evidence_files']]
 cpfile.write_text(json.dumps(cp,indent=2));updates.extend([str(cpfile.relative_to(R)),ref])
assert m.validate_installation()['status']=='GREEN'
assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
(B/'context-delivery.json').write_text(json.dumps(dict(delivery=d,revision=rev['project_revision'],sync=sync,
 validation='GREEN',strong_projections='CURRENT',bounded_diagnostic_pass=True),ensure_ascii=False,indent=2))
updates.append(str((B/'context-delivery.json').relative_to(R)))
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).strip()
subprocess.run(['git','add','--',*updates],cwd=R,check=True)
assert set(subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).splitlines())<=set(updates)
subprocess.run(['git','commit','-m','docs(aos): register current Source body expiry denial evidence'],cwd=R,check=True)
print(rev['project_revision'],'BOUNDED_OBSERVATION_CLOSED')
