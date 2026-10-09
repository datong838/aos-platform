from pathlib import Path
import json,hashlib,subprocess,importlib.util,sys
R=Path.cwd();B=R/'.evidence/gt-occupation-preparation-types-20261009';product='services/aos-api/aos_api/aip_physical_capacity_occupation_contracts.py';old=(B/'original-contract.py.txt').read_bytes();assert (R/product).read_bytes().startswith(old);assert json.loads((R/'.evidence/gt-atomic-model-admission-20261008/physical-guard-static.json').read_text())['files'][product]==hashlib.sha256(old).hexdigest()
assert '31 failed' in (B/'red-r1.log').read_text() and '31 passed' in (B/'green-r1.log').read_text() and '349 passed' in (B/'adjacent-r1.log').read_text()
(B/'static-review.json').write_text(json.dumps(dict(original_prefix_unchanged=True,original_guard_registered_baseline_match=True,original_preexisting_untracked=True,source_sha256=hashlib.sha256((R/product).read_bytes()).hexdigest(),runtime_entry_added=False,database_operations=False),indent=2)+'\n')
(B/'review.md').write_text('''# 非执行占用响应类型契约复审

仅追加根、首事件及完整响应DTO。原PhysicalAccountGuardPreparation字节前缀完全保留，hash与atomic已登记physical-guard-static基线一致；原未跟踪文件在现有授权范围纳入版本。复用原_ModelExecutionContract未知字段拒绝/实例重新验证及canonical_hash，不复制算法。

真实封存原生响应SHA绑定；RED31FAIL0.28秒为缺类，最小追加后31PASS0.23秒，相邻349PASS0.72秒，7项既有警告。重算哈希后bool/int混淆、状态/首事件/租户/身份/xid/pid/call/hash等篡改仍拒绝。顶层root/event身份及哈希精确一致；这仅描述prepare事实，不接受客户端对象作为authority。

证据生成首次JSON路径KeyError发生在静态断言，没有提交/authority/DB效果；修正为原files键再对账，不修改产品。未增加SQL包装/运行入口/迁移/DB操作，因此不重复已封存数据库回归和浏览器。SQL包装真实连接的租户/login/xid/pid核对另实施。

实际准入、unknown占用、费用/Usage、Judge输入结果、transport/finalizer/最终COMMIT及首链仍待真实证据。五父Task ACTIVE，长期Goal未修改。
''')
# Preserve exact finalization source as reviewable evidence.
(B/'finalize_wave.py').write_text(Path(__file__).read_text())
files=[product]+[str(p.relative_to(R)) for p in sorted(B.iterdir()) if p.is_file() and p.name not in ('delivery.json','context-sync-1617.json','evidence-commit.json','stage-files.json')];files=sorted(set(files));(B/'stage-files.json').write_text(json.dumps(files,indent=2)+'\n');files.append(str((B/'stage-files.json').relative_to(R)))
assert not subprocess.check_output(['git','diff','--cached','--name-only'],text=True).strip();subprocess.run(['git','add','--',*files],check=True);assert set(subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines())<=set(files);subprocess.run(['git','commit','-m','feat(aip): validate nonexecuting occupation root and event contracts'],check=True);head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();(B/'evidence-commit.json').write_text(json.dumps(dict(head=head,product_changed=True),indent=2)+'\n')
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);a=m.load_authority();assert a['project_revision']=='AOS-001616'
d=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='NONEXECUTING_OCCUPATION_TYPES_GREEN_SQL_WRAPPER_PENDING',changed_files=['aos-platform/'+product,'aos-platform/.evidence/'+B.name],commits=[head],verification=['Native fixture exact hash/reference; missing classRED31 then31PASS0.23s, adjacent349PASS0.72s','Original guard prefix/hash exact registered baseline; reused original canonical/revalidation semantics'],risks=['DTO descriptive only; no SQL wrapper/runtime authority/admission/Judge results/fees/transport/finalizer','Preexisting untracked guard file incorporated under original Task scope; original preserved'],blockers=[]);(B/'delivery.json').write_text(json.dumps(d,indent=2)+'\n')
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary='Strict descriptive nonexecuting root/initial event/response DTOs reuse original canonical_hash and instance revalidation. Actual native frozen response SHA-bound; RED31 missing-class failures then31PASS0.23s and adjacent349PASS0.72s. Re-signed invalid bool/int/state/tenant/origin/call/sequence/hash still denied. Original preexisting untracked guard prefix/hash exact registered baseline, incorporated under existing authorized Task. No SQL wrapper/runtime authority/DB/migration/actual admission/unknown/fees/Judge result/transport/finalizer/Goal change; five parentTasks ACTIVE. Next original narrow SQL wrapper same connection authority and real native validation.')])
orig=m.atomic_write_text
def safe(path,text,**kw):
 if str(path).startswith('/Users/ddt/.codex/memories/'):return
 return orig(path,text,**kw)
m.atomic_write_text=safe;sync=m.sync_projections(apply=True,include_prime=True)
ts=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008']
for t in ts:
 old=f'.evidence/{t}/occupation-type-investigation-reference-1616.json';new=f'.evidence/{t}/occupation-preparation-types-reference-1617.json';(R/new).write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,execution_allowed=False,references=[dict(path=x,sha256=hashlib.sha256((R/x).read_bytes()).hexdigest()) for x in [old]+files]),indent=2)+'\n');p=R/'.evidence'/t/'checkpoint.json';c=json.loads(p.read_text());c['evidence_files']=[new if x==old else x for x in c['evidence_files']];c.update(authority_revision=r['project_revision'],step='occupation-preparation-types-green-original-sql-wrapper-pending');p.write_text(json.dumps(c,indent=2)+'\n')
v=m.validate_installation();status=m.memory_status();assert v['status']=='GREEN';assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong')
s=importlib.util.spec_from_file_location('wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');w=importlib.util.module_from_spec(s);sys.modules[s.name]=w;s.loader.exec_module(w)
for t in ts:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2',f'.evidence/{t}/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文')
(B/'context-sync-1617.json').write_text(json.dumps(dict(revision=r['project_revision'],head=head,sync=sync,validation=v,status=status,all_five_checkpoint_bindings='PASS'),ensure_ascii=False,indent=2)+'\n');print('AOS-001617 GREEN; five checkpoints PASS')
