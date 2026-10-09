import json,ast,hashlib,sys,importlib.util,subprocess
from pathlib import Path
from datetime import datetime,timezone
import psycopg
from psycopg.rows import dict_row
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'services/aos-api'))
s=importlib.util.spec_from_file_location('audit_mem',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
assert m.load_authority()['project_revision']=='AOS-001640'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()=='8b238c737d266ae8cc11dac58ea2a554d39d6408'
all_leases=m.load_leases(m.DEFAULT_PATHS)['leases'];tasks=[]
for tid in (B.name,'gt-capacity-source-publication-20261006'):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());matches=[x for x in all_leases if x['task_id']==tid]
 assert t['status']=='ACTIVE' and len(matches)==1 and t['owner']==matches[0]['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
 assert datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
 tasks.append(t)
(B/'task-lease-before-repair.json').write_text(json.dumps(dict(tasks=tasks,all_leases=all_leases),indent=2))
r=json.loads((B/'native-whole-r1-result.json').read_text());calls=[x for x in r['results'] if x['phase']=='call'];failed=[x for x in calls if x['outcome']=='failed'];assert len(calls)==56 and len(failed)==1 and 'test_native_source_binding_rejects_coherent_wrong_hash' in failed[0]['nodeid']
for x in json.loads((B/'input-bindings-r1.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
lab=json.loads((B/'lab.json').read_text());db=r['database']
from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions
with psycopg.connect(host='127.0.0.1',port=5437,user='aos_app',dbname=db,passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster'];require_source_transaction_functions(c)
 counts={t:c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.'+t).fetchone()['n'] for t in ('source_pending','source_publication','source_provenance','global_account','global_provider')};assert all(v==0 for v in counts.values())
(B/'first-failure-independent.json').write_text(json.dumps(dict(failed_node=failed[0]['nodeid'],database=db,whole_nodes=386,passed_nodes=55,unexecuted_nodes=330,exact_existing_function_acl_lock_audit=True,publication_counts=counts,root_cause='Old explicit CREATE profile duplicates permanent a0v157 functions before native coherent wrong hash assertions',goal_completion_proven=False),indent=2))
p=R/'.evidence/gt-capacity-source-publication-20261006/plan.md'
with p.open('a') as f:f.write('\n## Original Source coherent wrong-hash oracle migration compatibility (AOS-001640)\nFull original386-node cumulative r2 actually terminates55PASS/1FAIL214.13s,330unexecuted. Exact first failure test_native_source_binding_rejects_coherent_wrong_hash repeats permanent157 CREATE before its positive/corruption/negative/restored assertions. Independent retained isolated DB full function/body/ACL/lock audit passes; five publication tables zero. Original SourceTask owns test and this plan; current full-suite-root-r2 Task owns evidence. All overlapping leases recorded, no second writer or takeover.\nMinimal test-only change in services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py: only this function replaces repeat source-profile CREATE with require_source_transaction_functions(owner), removes unused profile import and updates stale rollback comment. Preserve all original coherent stored-hash corruption, older SQL positive control, typed-native rejection, rollback restored positive, authentication and RLS assertions. No production SQL change. Run entire original function plus previous3normalization functions (6nodes), independently audit retained DB/zeroSource/1963inputhashes/32oldresources; selective commit preserves existing6additions1deletion fixture. Full386nodes and final actualCOMMIT expiry counterexample remain pending. Candidates: this original test repair is independent/authorized; finalCOMMIT hook design depends on complete protocol/clock contract and is not silently implemented. Browser inapplicable for test-only change.\n')
f=R/'services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py';text=f.read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='test_native_source_binding_rejects_coherent_wrong_hash');old=ast.get_source_segment(text,node)
new=old.replace('CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_APPROVAL_EVENT_PROJECTION_SQL)','CAPACITY_APPROVAL_EVENT_PROJECTION_SQL)').replace('owner.execute(CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)','from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions\n        require_source_transaction_functions(owner)').replace('owner.rollback()  # Never persist temporary private profile functions.','owner.rollback()  # Retain permanent profiles; discard isolated historical corruption.')
assert new!=old and old.count('owner.execute(CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)')==1
assert sum(isinstance(n,ast.Assert) for n in ast.walk(ast.parse(new)))==sum(isinstance(n,ast.Assert) for n in ast.walk(ast.parse(old)))
f.write_text(text.replace(old,new,1));(B/'repair.patch').write_text(subprocess.check_output(['git','diff','--',str(f.relative_to(R))],cwd=R,text=True))
bs=json.loads((B/'input-bindings-r1.json').read_text())
for x in bs:x['sha256']=hashlib.sha256((R/x['path']).read_bytes()).hexdigest()
(B/'input-bindings-r2.json').write_text(json.dumps(bs,indent=2))
selection=['test_native_source_binding_rejects_coherent_wrong_hash','test_original_source_binding_uses_typed_normalization_in_private_reader','test_original_source_time_profile_matches_original_datetime_oracle','test_original_source_candidate_profile_matches_original_shape_oracle'];(B/'normalization-selection.json').write_text(json.dumps(selection))
runner=(R/'.evidence/gt-source-full-suite-root-current-20261009/run_normalization_r2.py').read_text().replace('938c5209c90f7cacd9cffd08998aaff9a812979f','8b238c737d266ae8cc11dac58ea2a554d39d6408').replace('AOS-001639','AOS-001640').replace('gt-source-full-suite-root-current-20261009.json',B.name+'.json')
runner=runner.replace("for n in ('test_original_source_binding_uses_typed_normalization_in_private_reader', 'test_original_source_time_profile_matches_original_datetime_oracle', 'test_original_source_candidate_profile_matches_original_shape_oracle')","for n in "+repr(tuple(selection)))
(B/'run_normalization_r2.py').write_text(runner)
verifier=(R/'.evidence/gt-source-full-suite-root-current-20261009/verify_normalization_r2.py').read_text().replace('938c5209c90f7cacd9cffd08998aaff9a812979f','8b238c737d266ae8cc11dac58ea2a554d39d6408').replace('AOS-001639','AOS-001640').replace('len(calls)==5 and len(bindings)==5','len(calls)==6 and len(bindings)==6')
(B/'verify_normalization_r2.py').write_text(verifier)
print('Terminal RED55pass1fail;330unexecuted; retained DB zeroSource exact audit; plan before single-function test repair; original assertions retained')
