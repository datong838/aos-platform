import ast,json,hashlib,importlib.util,sys,subprocess
from pathlib import Path
from datetime import datetime,timezone
import psycopg
from psycopg.rows import dict_row
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent;P=R/'.evidence/gt-source-full-suite-root-r4-20261009';head='654512f152cec1f342775f7273f947d6e781fe5d';sys.path.insert(0,str(R/'services/aos-api'))
s=importlib.util.spec_from_file_location('build_mem',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);assert m.load_authority()['project_revision']=='AOS-001643' and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==head
leases=m.load_leases(m.DEFAULT_PATHS)['leases'];tasks=[]
for tid in (B.name,'gt-capacity-source-publication-20261006'):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());ls=[x for x in leases if x['task_id']==tid];assert t['status']=='ACTIVE' and len(ls)==1 and t['owner']==ls[0]['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc);assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists();tasks.append(t)
(B/'task-lease-before-repair.json').write_text(json.dumps(dict(tasks=tasks,all_leases=leases),indent=2));r=json.loads((B/'native-whole-r1-result.json').read_text());calls=[x for x in r['results'] if x['phase']=='call'];failed=[x for x in calls if x['outcome']=='failed'];assert len(calls)==78 and len(failed)==1 and failed[0]['nodeid'].endswith('test_native_original_build_request_reads_actual_original_provenance')
for x in json.loads((B/'input-bindings-r1.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
lab=json.loads((B/'lab.json').read_text());from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions
with psycopg.connect(host='127.0.0.1',port=5437,user='aos_app',dbname=r['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster'];require_source_transaction_functions(c);counts={t:c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.'+t).fetchone()['n'] for t in ('source_pending','source_publication','source_provenance','global_account','global_provider')};assert all(v==0 for v in counts.values())
(B/'first-failure-independent.json').write_text(json.dumps(dict(failed_node=failed[0]['nodeid'],database=r['database'],whole_nodes=386,passed_nodes=77,unexecuted_nodes=308,exact_existing_function_acl_lock_audit=True,publication_counts=counts,root_cause='Original build provenance oracle repeats permanent157 profiles before model/native equality assertions',goal_completion_proven=False),indent=2))
pre=json.loads((B/'build-evidence-profile-preflight.json').read_text());selection_new=[x['function'] for x in pre['rows'] if x['direct_original_build_oracle'] or x['uses_helper']];names=[x['function'] for x in pre['rows'] if x['direct_original_build_oracle']]+['_install_original_evidence_profile','test_native_evidence_contract_rejects_coherently_rehashed_bad_metadata'];assert len(names)==5 and len(selection_new)==9
p=R/'.evidence/gt-capacity-source-publication-20261006/plan.md'
with p.open('a') as f:f.write('\n## Original build/evidence profile migration compatibility and full helper caller acceptance (AOS-001643)\nActual whole386nodes77PASS1FAIL259.24s308unexecuted; original Build provenance repeat permanentprofile CREATE. Independent retainedfailedDB exactfunction/body/ACL/lockaudit andzeroSource. OriginalSourceTask owns exact test+plan; currentr5Task evidence; active sameowner alloverlappingLease census. Exact changed definitions: '+', '.join(names)+'. Exact entire9 affected tests: '+', '.join(selection_new)+'.\nReplace two direct build profile setup loops and direct original_build_json installation with exact sameowner installed-function audit. Evidence helper formerly only sixprofile CREATE statements now audits full migrated foundation, no business control removal. Build request rollback count0→3+exactaudit; build_json absence→permanentpresence+audit; coherently badmetadata rollback count0→3+audit. Preserve original actual build provenance/Pydantic/canonical input/hash/ACL, binary64 JSONB decoded overflow/underflow/scientific/unicode/numeric equality, rawdecimal samples, all Evidence content/provenance/receipt faults and modelbadmetadata coherent hash positivecontrol, original genuine independent approvals/actualSCRAM, three distinct request/account/basis origins and original committed revoke/epoch triggers, numeric cutoff offsets/no Source issuance/canary. Full9tests12nodes plus previous15tests27nodes39expected; no paramfilters. Independent retainedsameoriginalsession fresh DB exact1963inputs/zeroSource/role/interface/occupationcleanup/nativecluster/durability/32oldresources/rootvolume reserve; protectedfixture6/1unstaged. Browserinapplicable. Full386Source/actualCOMMITexpiry and naturalchain/joint/continuousobservations remainpending; independent finalCOMMITprotocol candidate still depends complete endingchannel/latewait/WAL semantics. No currentDB/restart/Host/worker/Provider/mall/oldRun/push or unknownreplay.\n')
f=R/'services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py';text=f.read_text();changes=[]
class Control(ast.NodeTransformer):
 def visit_For(self,n):
  if isinstance(n.target,ast.Name) and n.target.id=='profile':return None
  return self.generic_visit(n)
 def visit_ImportFrom(self,n):
  if n.module=='aos_api.aip_provider_capacity_publication_transaction' and any(x.name=='require_source_transaction_functions' for x in n.names):return None
  return n
 def visit_Expr(self,n):
  if isinstance(n.value,ast.Call):
   c=n.value
   if isinstance(c.func,ast.Name) and c.func.id=='require_source_transaction_functions':return None
   if isinstance(c.func,ast.Attribute) and c.func.attr=='execute' and c.args and isinstance(c.args[0],ast.Name) and c.args[0].id=='CAPACITY_ORIGINAL_BUILD_JSON_SQL':return None
  return self.generic_visit(n)
 def visit_Assert(self,n):
  constants=[x.value for x in ast.walk(n) if isinstance(x,ast.Constant) and isinstance(x.value,str)]
  if any("to_regprocedure('aos_capacity_publication_private.original_build_json(jsonb)')" in x or 'SELECT count(*) AS count FROM pg_proc p JOIN pg_namespace' in x for x in constants):return None
  return self.generic_visit(n)
def controls(s):return ast.dump(Control().visit(ast.parse(s)),include_attributes=False)
for n in ast.parse(text).body:
 if not isinstance(n,ast.FunctionDef) or n.name not in names:continue
 old=ast.get_source_segment(text,n);new=old
 if n.name=='_install_original_evidence_profile':
  assert len(n.body)==2 and isinstance(n.body[0],ast.ImportFrom) and isinstance(n.body[1],ast.For)
  assert tuple(ast.literal_eval(n.body[1].iter))==('CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL','CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL','CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL','CAPACITY_ORIGINAL_BUILD_PROFILE_SQL','CAPACITY_ORIGINAL_BUILD_JSON_SQL','CAPACITY_ORIGINAL_EVIDENCE_PROFILE_SQL')
  new='def _install_original_evidence_profile(owner):\n    """Audit the complete migrated private foundation; keep old caller harness."""\n    from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions\n    require_source_transaction_functions(owner)'
 elif n.name=='test_native_evidence_contract_rejects_coherently_rehashed_bad_metadata':
  new=new.replace("(names,)).fetchone()['count']==0","(names,)).fetchone()['count']==3\n        from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions\n        require_source_transaction_functions(owner)")
 else:
  loops=[x for x in ast.walk(n) if isinstance(x,ast.For) and isinstance(x.target,ast.Name) and x.target.id=='profile']
  if loops:
   assert len(loops)==1;loop=loops[0];assert all(isinstance(x,ast.Name) and x.id.endswith('PROFILE_SQL') for x in loop.iter.elts)
   new=new.replace(ast.get_source_segment(text,loop),'from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions\n'+' '*loop.col_offset+'require_source_transaction_functions(owner)',1)
  else:new=new.replace('owner.execute(CAPACITY_ORIGINAL_BUILD_JSON_SQL)','from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions\n        require_source_transaction_functions(owner)',1)
  new=new.replace(".fetchone()['fn'] is None",".fetchone()['fn'] is not None\n        require_source_transaction_functions(owner)").replace("(names,)).fetchone()['count']==0","(names,)).fetchone()['count']==3\n        require_source_transaction_functions(owner)")
 if n.name!='_install_original_evidence_profile':assert controls(old)==controls(new)
 assert new!=old and sum(isinstance(x,ast.Assert) for x in ast.walk(ast.parse(old)))==sum(isinstance(x,ast.Assert) for x in ast.walk(ast.parse(new)))
 changes.append((n.name,old,new))
assert len(changes)==5
for name,old,new in changes:text=text.replace(old,new,1)
f.write_text(text);(B/'repaired-functions.json').write_text(json.dumps(names));(B/'affected-test-functions.json').write_text(json.dumps(selection_new));(B/'original-controls-ast-audit.json').write_text(json.dumps(dict(changed_definitions=names,all_noninstallation_test_controls_ast_equal=True,helper_original_contains_only_six_profile_installs=True,helper_all_six_calling_tests_preserved=True,all_assertion_counts_unchanged=True,production_changed=False),indent=2));(B/'repair.patch').write_text(subprocess.check_output(['git','diff','--',str(f.relative_to(R))],text=True));bs=json.loads((B/'input-bindings-r1.json').read_text())
for x in bs:x['sha256']=hashlib.sha256((R/x['path']).read_bytes()).hexdigest()
(B/'input-bindings-r2.json').write_text(json.dumps(bs,indent=2));selection=json.loads((P/'normalization-selection.json').read_text())+selection_new;(B/'normalization-selection.json').write_text(json.dumps(selection))
runner=(P/'run_normalization_r3.py').read_text().replace('2e670f9fe72f2a1ab929dab64ae9136c2437a29b',head).replace('AOS-001642','AOS-001643').replace('gt-source-full-suite-root-r4-20261009.json',B.name+'.json').replace('normalization-r3','normalization-r2').replace('input-bindings-r3','input-bindings-r2');a=runner.index('for n in (',runner.index('code=pytest.main'));z=runner.index("]+['-q'",a);runner=runner[:a]+'for n in '+repr(tuple(selection))+runner[z:];runner=runner.replace('Entire original15functions27nodes selected:5Provider functions9nodes plus10adjacentfunctions18nodes; not whole386node Source acceptance','Entire original24functions39nodes selected:9BuildEvidence functions12nodes plus15adjacentfunctions27nodes; not whole386node Source acceptance');(B/'run_normalization_r2.py').write_text(runner)
verifier=(P/'verify_normalization_r3.py').read_text().replace('2e670f9fe72f2a1ab929dab64ae9136c2437a29b',head).replace('AOS-001642','AOS-001643').replace('normalization-r3','normalization-r2').replace('input-bindings-r3','input-bindings-r2').replace('len(calls)==27 and len(bindings)==27','len(calls)==39 and len(bindings)==39').replace('aos-source-original-provider-real-lock-and-adjacent-twentyseven-nodes-verification/v1','aos-source-original-build-evidence-and-adjacent-thirtynine-nodes-verification/v1');(B/'verify_normalization_r2.py').write_text(verifier)
print('Actual77PASS1FAIL terminal diagnosed; plan before5minimaldefinition changes; all6helper callers entire tests selected,39expectednodes; businesscontrolsASTpreserved')
