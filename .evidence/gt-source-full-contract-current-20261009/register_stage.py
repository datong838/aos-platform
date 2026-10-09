"""Close only the bounded core evidence Task and synchronize exact parent refs."""
import json, hashlib, subprocess, importlib.util, sys
from pathlib import Path
from datetime import datetime, timezone
R=Path(__file__).resolve().parents[2]; B=Path(__file__).resolve().parent
P=R/'.evidence/gt-capacity-source-publication-20261006/full-public-approval-current-1632'
def git(*args): return subprocess.check_output(['git',*args],cwd=R,text=True)
def module(name,path):
    sp=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
m=module('stage_memory',R/'scripts/memory/memoryctl.py')
assert git('rev-parse','HEAD').strip()=='0eba54befe62b6b625b0272ee9a82e98da22abf3'
assert not git('diff','--cached','--name-only').strip()
a=m.load_authority();assert a['project_revision']=='AOS-001632'
proof=json.loads((P/'independent-public-fault-verification.json').read_text())
assert proof['node_count']==24 and proof['single_full_green'] is False
assert proof['old_resources_unchanged'] and proof['product_hashes_unchanged']
for x in json.loads((B/'input-bindings.json').read_text()):
    assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
for tid in (B.name,'gt-capacity-source-publication-20261006',*parents):
    receipt=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text())
    assert receipt['status']=='ACTIVE' and datetime.fromisoformat(receipt['lease_expires_at'])>datetime.now(timezone.utc)
    assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
files=[str(p.relative_to(R)) for base in (B,P) for p in sorted(base.iterdir()) if p.is_file()]
subprocess.run(['git','add','--',*files],cwd=R,check=True)
assert set(git('diff','--cached','--name-only').splitlines())==set(files)
subprocess.run(['git','commit','-m','test(aip): verify original Source core and actual public field gates'],cwd=R,check=True)
head=git('rev-parse','HEAD').strip()
delivery=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],
 result='BOUNDED_ORIGINAL_CORE_NATIVE_VERIFIED_FULL_PARENT_SOURCE_PENDING',changed_files=[f for f in files if f.startswith(str(B.relative_to(R))+'/')],commits=[head],
 verification=['Original core 24 passed/369.99s/no hidden deselection; retained 24 databases/10 signed actual COMMIT Sources independently checked including after isolated PG recovery','Original public field follow-up 20 passed/4 setup environment errors plus four new-node passes; 24 independently reconciled, no single whole green claim'],
 risks=['Final actual COMMIT wall-clock counterexample unresolved','Full S01-S20/Source/profile/epoch/formalBoundary and model review remain incomplete','Isolated PG backend signal11 recovered; incident retained'],blockers=[])
summary='Original full core 24 native passes/24 retained DBs/10 signed actual COMMIT Sources; protected inputs/resources independently verified after recovery. Public original12 fields x2 layouts: r1 wrapper setup failure retained; r2 20passes/4setup errors from isolatedPG backend signal11; r3 four fresh-node passes/20deselected. Independent 24 actual public valid/refused/restored sequences, zero publication residue; no single complete public run green. Bounded evidence Task only delivered, original Source and business Tasks ACTIVE. Final COMMIT wall-clock/full S01-S20/formal installation/model-review/first-chain still pending; no product/currentDB/runtime/Goal changes.'
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary=summary)])
orig=m.atomic_write_text
m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
ref_files=[B/'review.md',B/'independent-core-verification.json',B/'full-contract-coverage-navigation.json',P/'review.md',P/'independent-public-fault-verification.json',P/'native-r2-diagnosis.json']
refs=[dict(path=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in ref_files]
paths=[]
for tid in parents:
    cpf=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(cpf.read_text())
    prior=f'.evidence/{tid}/current-source-exact-ref-fix-reference-1632.json';new=f'.evidence/{tid}/current-source-full-core-reference-1633.json'
    assert prior in cp['evidence_files']
    (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2))
    cp.update(authority_revision=u['project_revision'],step='original-source-core-native-verified-full-parent-and-commit-wallclock-pending')
    cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];cpf.write_text(json.dumps(cp,indent=2))
    paths.extend([new,str(cpf.relative_to(R))])
assert m.validate_installation()['status']=='GREEN'
assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
w=module('stage_wake',R/'scripts/long-task-watchdog/aos_wake_progress.py')
snapshots={tid:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2',f'.evidence/{tid}/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文') for tid in parents}
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],evidence_commit=head,delivery=delivery,sync=sync,checkpoints=snapshots,full_parent_source_delivery=False,goal_status_changed=False),indent=2))
paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
assert git('diff','--numstat','--','services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py').split()[:2]==['6','1']
subprocess.run(['git','add','--',*paths],cwd=R,check=True)
assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): record bounded Source core delivery and remaining gates'],cwd=R,check=True)
print(u['project_revision'],'BOUNDED_CORE_DELIVERED_ORIGINAL_SOURCE_ACTIVE')
