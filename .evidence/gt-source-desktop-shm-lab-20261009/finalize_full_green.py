import json,hashlib,subprocess,importlib.util,sys
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('fullgreen_mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001648'
git=lambda *args:subprocess.check_output(['git',*args],cwd=R,text=True)
assert git('rev-parse','HEAD').strip()=='007902dbf4159a9efb46199ce85f490a82bd64bf' and not git('diff','--cached','--name-only').strip()
p=json.loads((B/'independent-whole-final-verification.json').read_text());assert p['all_selected_passed'] and p['node_count']==386 and p['old_resources_unchanged'] and p['root_available_bytes']>2580000000
r=json.loads((B/'native-whole-r4-result.json').read_text());assert r['pytest_exit']==0 and len([x for x in r['results'] if x['phase']=='call'])==386
for x in json.loads((B/'input-bindings-r1.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
for tid in (B.name,'gt-capacity-source-publication-20261006',*parents):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());assert t['status']=='ACTIVE' and t['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
(B/'review.md').write_text('原101函数386节点完整单次累计终态通过，独立保留数据库回读签名/hash/provenance/xid/权限/清理/耐久/1963输入及77既有资源；本波仅证据运行器，业务代码不变。原r2收集路径失败无fixture效果，保留。真实COMMIT截止反例、联合准入、自然首链、八工作台和长期Goal未通过；不得以累计绿授执行权限。用户明确恢复已撤回暂停，产品Goalactive已回读，后续继续已登记截止门。\n'+p['summary']+'\n')
old=R/'.evidence/gt-source-full-suite-desktop-r2-20261009'
files=[str(x.relative_to(R)) for directory in (B,old) for x in sorted(directory.iterdir()) if x.is_file()]
assert all(x.startswith('.evidence/') for x in files)
subprocess.run(['git','add','--',*files],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(files)
subprocess.run(['git','commit','-m','test(aip): verify entire Source cumulative on large native Desktop lab'],cwd=R,check=True);head=git('rev-parse','HEAD').strip()
d=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='ENTIRE386_NATIVE_SOURCE_CUMULATIVE_GREEN_FINAL_COMMIT_DEADLINE_PENDING',changed_files=files,commits=[head],verification=[p['summary'],'Independent retained native signedSource/xid/provenance/fullfoundation/ACL/roles/cleanup/durability/1963inputs/77priorresources readback'],risks=['Original actualCOMMITexpirycounterexample unresolved; fullSourceDelivery andformalfirstchain unproven'],blockers=[])
failed=json.loads((old/'independent-failure-verification.json').read_text())
assert failed['database_count']==127 and failed['sources']==7 and failed['old_resources_unchanged'] and failed['exact_inputs_unchanged']
dfailed=m.complete_task(m.DEFAULT_PATHS,task_id=old.name,expected_revision=a['project_revision'],result='WHOLE_R3_341PASS_SETUP_SHM_ERROR_TERMINAL_READONLY_RECONCILED',changed_files=[x for x in files if x.startswith(str(old.relative_to(R))+'/')],commits=[head],verification=[failed['summary'],'127 retained databases / 7 committed signed Sources; SIG11 and WAL recovery preserved; no replay'],risks=['64MiB shared memory exhaustion and backend SIG11; r3 is FAILED, not cumulative green'],blockers=[])
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary=(B/'review.md').read_text())])
orig=m.atomic_write_text;m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True);refs=[dict(path=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (B/'review.md',B/'independent-whole-final-verification.json',old/'next-final-commit-investigation.md')];paths=[]
for tid in parents:
 cpf=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(cpf.read_text());prior=f'.evidence/{tid}/current-source-desktop-native-lab-reference-1648.json';new=f'.evidence/{tid}/current-source-entire386-reference-1649.json';assert prior in cp['evidence_files']
 (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2));cp.update(authority_revision=u['project_revision'],step='entire386-native-source-cumulative-green-final-commit-deadline-counterexample-pending');cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];cpf.write_text(json.dumps(cp,indent=2));paths.extend([new,str(cpf.relative_to(R))])
assert m.validate_installation()['status']=='GREEN'
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],evidence_commit=head,delivery=d,prior_failed_delivery=dfailed,sync=sync,full_source_delivery=False,formal_execution=False,user_resume_explicit=True,goal_status_changed=False),indent=2));paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
subprocess.run(['git','add','--',*paths],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): record complete Source cumulative and next deadline gate'],cwd=R,check=True)
print(u['project_revision'],p['summary'])
