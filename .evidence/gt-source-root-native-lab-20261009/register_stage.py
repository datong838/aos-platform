"""Exact test-only migration compatibility stage; preserve original fixture diff."""
import json, hashlib, subprocess, importlib.util, sys
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
m=mod('stage_memory',R/'scripts/memory/memoryctl.py');a=m.load_authority()
assert a['project_revision']=='AOS-001636' and git('rev-parse','HEAD').strip()=='455b74ea10487e5fa1be0392d14ef6ef4499cb9c'
assert not git('diff','--cached','--name-only').strip()
p=json.loads((B/'independent-final-verification.json').read_text());assert p['all_selected_passed'] and p['node_count']==2 and p['database_count']==2 and p['old_resources_unchanged']
for x in json.loads((B/'input-bindings-r1.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
for tid in (B.name,'gt-capacity-source-publication-20261006',*parents):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());assert t['status']=='ACTIVE' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
routing=R/'.evidence/gt-source-native-resource-routing-20261009'
files=[str(x.relative_to(R)) for folder in (B,routing) for x in sorted(folder.iterdir()) if x.is_file()]
subprocess.run(['git','add','--',*files],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(files)
subprocess.run(['git','commit','-m','test(aip): verify owned root native lab and both pending preparation layouts'],cwd=R,check=True);head=git('rev-parse','HEAD').strip()
delivery=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='ROOT_NATIVE_LAB_AND_ORIGINAL_PREPARATION_TWO_LAYOUTS_GREEN',changed_files=[x for x in files if x.startswith(str(B.relative_to(R))+'/')],commits=[head],verification=['New root ext4 local-bind owned named volume/exact native image/isolated cluster SCRAM verifier positive and tamper-negative','Original preparation two independent layouts2passed27.13s; exact inputs/native zero Source/fsync and protected32 old container identities unchanged'],risks=['Original full Source and actual final COMMIT clock pending','No independent model review result or formal first-chain acceptance'],blockers=[])
route_delivery=m.complete_task(m.DEFAULT_PATHS,task_id=routing.name,expected_revision=a['project_revision'],result='READONLY_CAPACITY_ROUTING_RESOLVED_BY_NEW_ROOT_NATIVE_LAB',changed_files=[str(x.relative_to(R)) for x in routing.iterdir() if x.is_file()],commits=[head],verification=['Current root ext4 capacity and owned distinct resource; all old profiles unchanged'],risks=['Full Source still pending'],blockers=[])
summary='Original retained data volume at reserve, no delete/restart/reuse. New sameVM rootext4 backed independent localbind named native PG16 lab, exact old image and C binary, SCRAM positive/tampered-negative, isolated cluster7694534063495901208/5437/768MiB. Initial privatepath and imagevolume ownership failures read-only reconciled and only new empty resource repaired, preserved. Original pending preparation bothlayouts2passed27.13s/2newDB, zero Source actualcommit, independent exact inputs/functionACLlock/fsync/rootvolume/protected32 old resources. OriginalSource ACTIVE; actualcommit triple/fullSource/final COMMIT wall-clock/firstchain remain pending; no Goal/private store/currentDB/Host change.'
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary=summary)])
orig=m.atomic_write_text;m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (B/'review.md',B/'independent-final-verification.json',B/'verifier-install.json')];paths=[]
for tid in parents:
 cpf=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(cpf.read_text());prior=f'.evidence/{tid}/current-source-original-preparation-reference-1636.json';new=f'.evidence/{tid}/current-source-root-native-reference-1637.json';assert prior in cp['evidence_files']
 (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2));cp.update(authority_revision=u['project_revision'],step='source-root-native-both-layouts-green-actual-commit-next-final-clock-pending');cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];cpf.write_text(json.dumps(cp,indent=2));paths.extend([new,str(cpf.relative_to(R))])
assert m.validate_installation()['status']=='GREEN';assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
w=mod('stage_wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');snapshots={tid:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2',f'.evidence/{tid}/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文') for tid in parents}
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],evidence_commit=head,delivery=delivery,sync=sync,checkpoints=snapshots,original_source_task='ACTIVE',full_source_delivery=False,goal_status_changed=False),indent=2));paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
subprocess.run(['git','add','--',*paths],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): record root native resource and both preparation layouts'],cwd=R,check=True)
print(u['project_revision'],'ROOT_NATIVE_RESOURCE_AND_BOTH_PREPARATION_LAYOUTS_GREEN')
