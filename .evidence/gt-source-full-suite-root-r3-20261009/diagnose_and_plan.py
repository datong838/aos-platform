import ast,json,hashlib,importlib.util,sys,subprocess
from pathlib import Path
from datetime import datetime,timezone
import psycopg
from psycopg.rows import dict_row
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent;P=R/'.evidence/gt-source-full-suite-root-r2-20261009'
sys.path.insert(0,str(R/'services/aos-api'))
s=importlib.util.spec_from_file_location('repair_memory',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();assert head=='35eb116cb0b0951dffc5a5a7c44986bb97df06f8' and m.load_authority()['project_revision']=='AOS-001641'
leases=m.load_leases(m.DEFAULT_PATHS)['leases'];tasks=[]
for tid in (B.name,'gt-capacity-source-publication-20261006'):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());ls=[x for x in leases if x['task_id']==tid];assert t['status']=='ACTIVE' and len(ls)==1 and t['owner']==ls[0]['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc);assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists();tasks.append(t)
(B/'task-lease-before-repair.json').write_text(json.dumps(dict(tasks=tasks,all_leases=leases),indent=2))
r=json.loads((B/'native-whole-r1-result.json').read_text());calls=[x for x in r['results'] if x['phase']=='call'];failed=[x for x in calls if x['outcome']=='failed'];assert len(calls)==57 and len(failed)==1 and failed[0]['nodeid'].endswith('test_native_original_capacity_application_profile_matches_original_model')
for x in json.loads((B/'input-bindings-r1.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
lab=json.loads((B/'lab.json').read_text());from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions
with psycopg.connect(host='127.0.0.1',port=5437,user='aos_app',dbname=r['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster'];require_source_transaction_functions(c)
 counts={t:c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.'+t).fetchone()['n'] for t in ('source_pending','source_publication','source_provenance','global_account','global_provider')};assert all(v==0 for v in counts.values())
(B/'first-failure-independent.json').write_text(json.dumps(dict(failed_node=failed[0]['nodeid'],database=r['database'],whole_nodes=386,passed_nodes=56,unexecuted_nodes=329,exact_existing_function_acl_lock_audit=True,publication_counts=counts,root_cause='Old test repeats permanent a0v157 source/application profiles before original model-equivalence assertions',goal_completion_proven=False),indent=2))
names=['test_native_original_capacity_application_profile_matches_original_model','test_native_original_capacity_request_rechecks_exact_row_expiry','test_native_original_candidate_profile_matches_original_model','test_native_original_candidate_rows_and_combination_keep_original_claims','test_native_candidate_combination_preserves_real_original_private_approval','test_native_candidate_combination_rejects_rehashed_original_row_term_faults']
p=R/'.evidence/gt-capacity-source-publication-20261006/plan.md'
with p.open('a') as f:f.write('\n## Original application/candidate oracle migrated installation compatibility (AOS-001641)\nCurrent whole386node cumulative56PASS1FAIL219.41s/329unexecuted; actual application duplicate sourceprofile CREATE. Independent full existingfunction/body/ACL/lock audit and zeroSource prove setup mismatch. Same original SourceTask owns exact test file and plan; current r3Task owns evidence; active sameowner/overlappingLease census frozen. Exact functions: '+', '.join(names)+'.\nOnly replace old repeat permanent profile CREATE or profile setup loop with require_source_transaction_functions(owner). Application rollback expected function absence becomes permanent presence plus exactaudit; candidate7functions expected0 becomes7 plus exactaudit. Keep complete original Pydantic/raw alias/unicode/date/integer/token-limit domains, catalog flags/ACLs, original row expiry Check corruption SAVEPOINT, real runtime candidate inserts and independent Maker/checker Source approvals/SCRAM reads, positive SQL and wrongMaker/canary denial, all four coherently rehashed cross-row faults and rollback restored positives. Do not alter assertions/domain loops or production SQL. Entire6functions12nodes plus previous4functions6nodes,18expected. Independent retained sameoriginalsessionDB exact1963inputs, zeroSource, role/interface/occupation cleanup/nativecluster/32oldresources/rootvolume/reserve. No currentDB/restart/Host/worker/Provider/mall/oldRun/push, browser inapplicable. Selective index preserves protectedfixture6/1. FullSource/currentfinalCOMMIT expiry and original naturalchain stillpending; no fullTaskDelivery. Candidate2 finalCOMMIT protocol requires complete ending-channel/latewait/WAL semantics, no silentrequirement reduction.\n')
f=R/'services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py';text=f.read_text();patch=[]
for n in ast.parse(text).body:
 if not isinstance(n,ast.FunctionDef) or n.name not in names:continue
 old=ast.get_source_segment(text,n);new=old
 if 'for profile in (' in old:
  loop=next(x for x in ast.walk(n) if isinstance(x,ast.For) and isinstance(x.target,ast.Name) and x.target.id=='profile');segment=ast.get_source_segment(text,loop)
  assert all(isinstance(x,ast.Name) and x.id.endswith('PROFILE_SQL') for x in loop.iter.elts)
  new=new.replace(segment,'from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions\n        require_source_transaction_functions(owner)')
 else:
  new=new.replace('owner.execute(CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)\n        owner.execute(CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL)','from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions\n        require_source_transaction_functions(owner)').replace('owner.execute(CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)\n        owner.execute(CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL)','from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions\n        require_source_transaction_functions(owner)')
 if n.name=='test_native_original_capacity_application_profile_matches_original_model':
  new=new.replace(".fetchone()['fn'] is None",".fetchone()['fn'] is not None\n        require_source_transaction_functions(owner)")
 if n.name=='test_native_original_candidate_profile_matches_original_model':
  new=new.replace("(names,)).fetchone()['n']==0","(names,)).fetchone()['n']==7\n        require_source_transaction_functions(owner)")
 assert new!=old
 assert sum(isinstance(x,ast.Assert) for x in ast.walk(ast.parse(new)))==sum(isinstance(x,ast.Assert) for x in ast.walk(ast.parse(old)))
 # All non-install domain loops and corruption bodies stay byte-identical.
 for x in ast.walk(n):
  if isinstance(x,(ast.For,ast.Try)) and not (isinstance(x,ast.For) and isinstance(x.target,ast.Name) and x.target.id=='profile'):
   assert ast.get_source_segment(text,x) in new
 patch.append((n.name,old,new))
assert len(patch)==6
for name,old,new in patch:text=text.replace(old,new,1)
f.write_text(text);(B/'repaired-functions.json').write_text(json.dumps(names));(B/'repair.patch').write_text(subprocess.check_output(['git','diff','--',str(f.relative_to(R))],cwd=R,text=True))
bs=json.loads((B/'input-bindings-r1.json').read_text())
for x in bs:x['sha256']=hashlib.sha256((R/x['path']).read_bytes()).hexdigest()
(B/'input-bindings-r2.json').write_text(json.dumps(bs,indent=2));selection=json.loads((P/'normalization-selection.json').read_text())+names;(B/'normalization-selection.json').write_text(json.dumps(selection))
runner=(P/'run_normalization_r2.py').read_text().replace('8b238c737d266ae8cc11dac58ea2a554d39d6408',head).replace('AOS-001640','AOS-001641').replace('gt-source-full-suite-root-r2-20261009.json',B.name+'.json')
a=runner.index('for n in (',runner.index('code=pytest.main'));z=runner.index("]+['-q'",a);runner=runner[:a]+'for n in '+repr(tuple(selection))+runner[z:];(B/'run_normalization_r2.py').write_text(runner)
verifier=(P/'verify_normalization_r2.py').read_text().replace('8b238c737d266ae8cc11dac58ea2a554d39d6408',head).replace('AOS-001640','AOS-001641').replace('len(calls)==6 and len(bindings)==6','len(calls)==18 and len(bindings)==18');(B/'verify_normalization_r2.py').write_text(verifier)
print('Actual terminal RED56pass1fail; six exact original application/candidate functions planned then minimally adapted; original loops/fault/assertions retained;18full nodes selected')
