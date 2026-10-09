import ast,json,hashlib,importlib.util,sys,subprocess
from pathlib import Path
from datetime import datetime,timezone
import psycopg
from psycopg.rows import dict_row
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent;P=R/'.evidence/gt-source-full-suite-root-r3-20261009';head='2e670f9fe72f2a1ab929dab64ae9136c2437a29b'
sys.path.insert(0,str(R/'services/aos-api'))
s=importlib.util.spec_from_file_location('provider_mem',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);assert m.load_authority()['project_revision']=='AOS-001642' and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==head
leases=m.load_leases(m.DEFAULT_PATHS)['leases'];tasks=[]
for tid in (B.name,'gt-capacity-source-publication-20261006'):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());ls=[x for x in leases if x['task_id']==tid];assert t['status']=='ACTIVE' and len(ls)==1 and t['owner']==ls[0]['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc);assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists();tasks.append(t)
(B/'task-lease-before-repair.json').write_text(json.dumps(dict(tasks=tasks,all_leases=leases),indent=2));r=json.loads((B/'native-whole-r1-result.json').read_text());calls=[x for x in r['results'] if x['phase']=='call'];failed=[x for x in calls if x['outcome']=='failed'];assert len(calls)==69 and len(failed)==1 and failed[0]['nodeid'].endswith('test_native_original_provider_profile_preserves_actual_business_hash')
for x in json.loads((B/'input-bindings-r1.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
lab=json.loads((B/'lab.json').read_text());from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions
with psycopg.connect(host='127.0.0.1',port=5437,user='aos_app',dbname=r['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster'];require_source_transaction_functions(c);counts={t:c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.'+t).fetchone()['n'] for t in ('source_pending','source_publication','source_provenance','global_account','global_provider')};assert all(v==0 for v in counts.values())
(B/'first-failure-independent.json').write_text(json.dumps(dict(failed_node=failed[0]['nodeid'],database=r['database'],whole_nodes=386,passed_nodes=68,unexecuted_nodes=317,exact_existing_function_acl_lock_audit=True,publication_counts=counts,root_cause='Original Provider oracle repeats permanent157 profile installation before actual business hash/native assertions',goal_completion_proven=False),indent=2))
names=[x['function'] for x in json.loads((B/'provider-profile-preflight.json').read_text())];p=R/'.evidence/gt-capacity-source-publication-20261006/plan.md'
with p.open('a') as f:f.write('\n## Original Provider profiles/current rows/full set/real lock migration compatibility (AOS-001642)\nActual whole386node cumulative68PASS1FAIL244.21s317unexecuted. Original Provider business-hash test repeats permanentprofile; independent retainedfailedDB exactfunction/body/ACL/lock and zeroSource auditpasses. OriginalSourceTask owns test/plan, currentr4Task evidence; sameowner alloverlappingLease snapshot; no parallelwriter/takeover. Exact functions: '+', '.join(names)+'.\nReplace only profile setup loops (including reader conn nestedloop) with strict require_source_transaction_functions(sameconnection). Rollback expectations: permanent read_original_provider remains, plus exactaudit; five provider profile functions stay5 plusaudit. Retain entire original Provider/Pydantic/canonical metadata exclusion, integer/JSON huge-decimal/unicode/naive datetime/ref/endpoint/SecretRef/lifecycle domains, coherent identity/hash/revision/tenant/lifecycle/business payload faults/savepoint rollback, full second actual Provider from original runtime/approval APIs, canary, exact pg_blocking_pids both reader-first/writer-first original SHARE fences and timeouts/joins/rollback. No Source/body SQL or business control changes. Entire5functions9nodes+previous10functions18nodes27expected, nofilterwithinfunction. Independent retainedDB exact1963inputs/zeroSource/role/interface/occupationcleanup/nativecluster/durability/32oldresources/rootvolume/reserve, protectedfixture6/1unstaged. Browserinapplicable. Full386Source/finalactualCOMMITexpiry/jointbusiness/firstchain remainpending; secondcandidate finalCOMMITprotocol needs completeauthority/endingchannels/latewait/WAL semantics, no silent narrowed requirement. No currentDB/restart/Provider/Host/worker/mall/oldRun/push.\n')
f=R/'services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py';text=f.read_text();changes=[]
class Control(ast.NodeTransformer):
 def visit_For(self,n):
  if isinstance(n.target,ast.Name) and n.target.id=='profile':return None
  return self.generic_visit(n)
 def visit_ImportFrom(self,n):
  if n.module=='aos_api.aip_provider_capacity_publication_transaction' and any(x.name=='require_source_transaction_functions' for x in n.names):return None
  return n
 def visit_Expr(self,n):
  if isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='require_source_transaction_functions':return None
  return self.generic_visit(n)
 def visit_Assert(self,n):
  constants=[x.value for x in ast.walk(n) if isinstance(x,ast.Constant) and isinstance(x.value,str)]
  if any("to_regprocedure('aos_capacity_publication_private.read_original_provider(jsonb)')" in x or 'SELECT count(*) AS n FROM pg_proc p JOIN pg_namespace' in x for x in constants):return None
  return self.generic_visit(n)
def controls(s):return ast.dump(Control().visit(ast.parse(s)),include_attributes=False)
for n in ast.parse(text).body:
 if not isinstance(n,ast.FunctionDef) or n.name not in names:continue
 old=ast.get_source_segment(text,n);loop=next(x for x in ast.walk(n) if isinstance(x,ast.For) and isinstance(x.target,ast.Name) and x.target.id=='profile');segment=ast.get_source_segment(text,loop);conn=ast.unparse(loop.body[0].value.func.value);assert conn in ('owner','conn') and all(isinstance(x,ast.Name) and x.id.endswith('PROFILE_SQL') for x in loop.iter.elts)
 new=old.replace(segment,'from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions\n'+' '*loop.col_offset+'require_source_transaction_functions('+conn+')',1)
 new=new.replace(".fetchone()['fn'] is None",".fetchone()['fn'] is not None\n        require_source_transaction_functions(owner)").replace("(names,)).fetchone()['n']==0","(names,)).fetchone()['n']==5\n        require_source_transaction_functions(owner)")
 assert new!=old and controls(old)==controls(new)
 assert sum(isinstance(x,ast.Assert) for x in ast.walk(ast.parse(old)))==sum(isinstance(x,ast.Assert) for x in ast.walk(ast.parse(new)))
 changes.append((n.name,old,new))
assert len(changes)==5
for name,old,new in changes:text=text.replace(old,new,1)
f.write_text(text);(B/'repaired-functions.json').write_text(json.dumps(names));(B/'original-controls-ast-audit.json').write_text(json.dumps(dict(functions=names,all_noninstallation_controls_ast_equal=True,all_assertion_counts_unchanged=True,changed_rollback_catalog_assertions=['permanent provider function presence with exactaudit','five permanent provider functions with exactaudit'],production_changed=False),indent=2));(B/'repair.patch').write_text(subprocess.check_output(['git','diff','--',str(f.relative_to(R))],text=True))
bs=json.loads((B/'input-bindings-r1.json').read_text())
for x in bs:x['sha256']=hashlib.sha256((R/x['path']).read_bytes()).hexdigest()
(B/'input-bindings-r2.json').write_text(json.dumps(bs,indent=2));selection=json.loads((P/'normalization-selection.json').read_text())+names;(B/'normalization-selection.json').write_text(json.dumps(selection))
runner=(P/'run_normalization_r2.py').read_text().replace('35eb116cb0b0951dffc5a5a7c44986bb97df06f8',head).replace('AOS-001641','AOS-001642').replace('gt-source-full-suite-root-r3-20261009.json',B.name+'.json');a=runner.index('for n in (',runner.index('code=pytest.main'));z=runner.index("]+['-q'",a);runner=runner[:a]+'for n in '+repr(tuple(selection))+runner[z:];runner=runner.replace('Entire original10functions18nodes selected:6application/candidate functions12nodes plus4adjacent functions6nodes; not whole386node Source acceptance','Entire original15functions27nodes selected:5Provider functions9nodes plus10adjacentfunctions18nodes; not whole386node Source acceptance');(B/'run_normalization_r2.py').write_text(runner)
verifier=(P/'verify_normalization_r2.py').read_text().replace('35eb116cb0b0951dffc5a5a7c44986bb97df06f8',head).replace('AOS-001641','AOS-001642').replace('len(calls)==18 and len(bindings)==18','len(calls)==27 and len(bindings)==27').replace('aos-source-original-application-candidate-and-adjacent-eighteen-nodes-verification/v1','aos-source-original-provider-real-lock-and-adjacent-twentyseven-nodes-verification/v1');(B/'verify_normalization_r2.py').write_text(verifier)
print('Terminal RED68pass1fail;5Provider functions plan then minimalsetupfix; all other controls ASTequal;27whole-functionnodes selected')
