import hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('boundary_finish_mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001649'
git=lambda *args:subprocess.check_output(['git',*args],cwd=R,text=True).strip()
assert git('rev-parse','HEAD').startswith('5861fd9fd') and not git('diff','--cached','--name-only')
p=json.loads((B/'boundary-audit.json').read_text());assert p['read_only'] and p['inputs_unchanged'] and p['strict_completion_deadline']=='RED_UNPROVEN'
for x in json.loads((B/'inputs.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
files=[str(x.relative_to(R)) for x in sorted(B.iterdir()) if x.is_file()]
subprocess.run(['git','add','--',*files],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(files)
subprocess.run(['git','commit','-m','docs(aip): audit final Source commit callback and durability boundaries'],cwd=R,check=True);head=git('rev-parse','HEAD')
d=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='READONLY_COMMIT_PIPELINE_AUDIT_GREEN_STRICT_COMPLETION_DEADLINE_RED',changed_files=files,commits=[head],verification=['Frozen PG16.14 callback LIFO/commit/WAL/PREPARE sequence','Retained exact native signed Source/hash/provenance/committed xid READ ONLY'],risks=['Strict actual completion deadline unresolved; no native callback installed or business permission'],blockers=[])
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/'+str((B/'boundary-contract.md').relative_to(R)),summary='Native READ ONLY and upstream commit pipeline audit complete; callback LIFO and post-check durability waits prevent strict completion proof. Continue trusted-end protocol and typed Model safe work.')])
orig=m.atomic_write_text;m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
assert m.validate_installation()['status']=='GREEN'
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
paths=[]
refs=[dict(path=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (B/'boundary-audit.json',B/'boundary-contract.md')]
for tid in parents:
    f=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(f.read_text());prior=f'.evidence/{tid}/current-source-entire386-reference-1649.json';new=f'.evidence/{tid}/current-source-final-commit-boundary-reference-1650.json';assert prior in cp['evidence_files']
    (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2))
    cp.update(authority_revision=u['project_revision'],step='commit-boundary-audit-complete-strict-deadline-pending-continue-safe-protocol');cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];f.write_text(json.dumps(cp,indent=2));paths.extend([new,str(f.relative_to(R))])
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,delivery=d,sync=sync,goal_changed=False,formal_execution=False),indent=2));paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
subprocess.run(['git','add','--',*paths],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): synchronize commit boundary audit and continuing safe gates'],cwd=R,check=True)
print(u['project_revision'],'bounded audit delivered; safe protocol work continues')
