import hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent;O=R/'.evidence/gt-source-trusted-end-protocol-20261009'
s=importlib.util.spec_from_file_location('callback_finish_mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001650'
git=lambda *args:subprocess.check_output(['git',*args],cwd=R,text=True).strip()
assert git('rev-parse','HEAD').startswith('701f2d13e') and not git('diff','--cached','--name-only')
p=json.loads((B/'independent-verification.json').read_text());assert p['read_only'] and p['old_resources_unchanged'] and p['old_resource_count']==92 and p['strict_completion_candidate']=='RED'
assert p['xid_statuses']=={'check_then_wait':'committed','wait_then_check':'aborted'}
t=json.loads((O/'trust-audit.json').read_text());assert t['read_only'] and t['strict_completion_deadline']=='RED_UNPROVEN'
assert not (B/'quality-result-r1.json').exists() and json.loads((B/'quality-result-r1.transport.json').read_text())['returncode']==1
files=[str(x.relative_to(R)) for directory in (B,O) for x in sorted(directory.iterdir()) if x.is_file() and x.name!='finalize.log']
subprocess.run(['git','add','--',*files],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(files)
subprocess.run(['git','commit','-m','test(aip): prove native post-check callback can commit past deadline'],cwd=R,check=True);head=git('rev-parse','HEAD')
deliveries=[]
for directory,result,verification in ((B,'PRECOMMIT_SINGLE_CALLBACK_STRICT_COMPLETION_CANDIDATE_REJECTED_NATIVE_COUNTEREXAMPLE',['Compiled native C, known committed/aborted xids, one retained row, 92 old containers unchanged']), (O,'READONLY_TRUST_AUDIT_AND_PROTOCOL_DRAFT_COMPLETE_NOT_IMPLEMENTED',['Verifier/roles/ACL/preload native READ ONLY audit; trusted-end protocol and negative matrix drafted'])):
    deliveries.append(m.complete_task(m.DEFAULT_PATHS,task_id=directory.name,expected_revision=a['project_revision'],result=result,changed_files=[x for x in files if x.startswith(str(directory.relative_to(R))+'/')],commits=[head],verification=verification,risks=['Strict completion deadline and Source full delivery remain unproven','Independent model review unavailable: daemon ownership failure preserved, no resend or PASS','Prototype synthetic callback only; not installed in any old or formal database'],blockers=[]))
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/'+str((B/'review.md').relative_to(R)),summary='Native two-order callback counterexample independently committed/aborted; single PRE_COMMIT candidate insufficient for strict completion. Review daemon failure reconciled, no PASS/permission or full Source claim. Continue safe complete Model/input plan work.')])
orig=m.atomic_write_text;m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True);assert m.validate_installation()['status']=='GREEN'
paths=[];refs=[dict(path=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (B/'review.md',B/'independent-verification.json',B/'review-reconciliation.json',O/'protocol-contract.md')]
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
for tid in parents:
    f=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(f.read_text());prior=f'.evidence/{tid}/current-source-final-commit-boundary-reference-1650.json';new=f'.evidence/{tid}/current-source-native-callback-counterexample-reference-1651.json';assert prior in cp['evidence_files']
    (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2));cp.update(authority_revision=u['project_revision'],step='native-callback-candidate-rejected-continue-full-model-input-risk-protocol');cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];f.write_text(json.dumps(cp,indent=2));paths.extend([new,str(f.relative_to(R))])
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],evidence_head=head,deliveries=deliveries,sync=sync,goal_changed=False,model_review_available=False,source_full_delivery=False,formal_execution=False),indent=2));paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
subprocess.run(['git','add','--',*paths],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): retain native callback rejection and continue independent gates'],cwd=R,check=True)
print(u['project_revision'],'bounded candidate rejection delivered; full goal remains active')
