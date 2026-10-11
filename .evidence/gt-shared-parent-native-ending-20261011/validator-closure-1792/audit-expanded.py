"""Bound current generated SQL lexical graph: investigation, never authorization."""
import hashlib,inspect,json,re,subprocess
from pathlib import Path
from aos_api import aip_shared_parent_atomic_admission as a
from aos_api import aip_physical_capacity_occupation_authority as physical
from aos_api import aip_provider_capacity_occupation_source as source
functions={}
generators=[(name,g) for name,g in vars(a).items() if name.startswith('shared_parent_') and name.endswith('_statements') and inspect.isfunction(g)]
generators += [(g.__name__,g) for g in (physical.occupation_account_guard_statements,physical.occupation_case_binding_statements,physical.occupation_eval_fact_statements,physical.occupation_judge_fact_statements,physical.occupation_plan_risk_statements,source.occupation_source_statements)]
for name,generator in generators:
 if inspect.signature(generator).parameters:continue
 for sql in generator():
  match=re.match(r'CREATE FUNCTION ([a-z_]+\.[a-z_]+)\(',sql)
  if not match:continue
  key=match[1]
  if key in functions:assert functions[key]['sha256']==hashlib.sha256(sql.encode()).hexdigest(),key
  calls=sorted(set(re.findall(r'\b[a-z_]+\.[a-z_]+(?=\()',sql))-{key})
  functions[key]={'sha256':hashlib.sha256(sql.encode()).hexdigest(),'qualified_candidates':calls,'direct_dml_tokens':re.findall(r'\b(?:INSERT INTO|UPDATE|DELETE FROM|MERGE INTO|TRUNCATE)\b',sql),'unqualified_candidates':sorted(set(re.findall(r'(?<![.\w])([a-z_][a-z_0-9]*)\s*\(',sql))),'generator':name}
root=a.COMPLETE_END_FACTS.split('(')[0];todo=[root];seen=set();unresolved=set()
while todo:
 key=todo.pop()
 if key in seen:continue
 if key not in functions:unresolved.add(key);continue
 seen.add(key);todo.extend(functions[key]['qualified_candidates'])
result={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_sha256':hashlib.sha256(Path(a.__file__).read_bytes()).hexdigest(),'root':root,'reachable':{k:functions[k] for k in sorted(seen)},'unresolved_qualified_candidates':sorted(unresolved),'dependency_source_hashes':{str(Path(mod.__file__)):hashlib.sha256(Path(mod.__file__).read_bytes()).hexdigest() for mod in (physical,source)},'semantic_closure_proven':False,'execution_authorized':False,'limits':['lexical candidates include possible relation/type syntax','unqualified overloads/operators/casts/dynamic SQL and native callbacks are not resolved','no runtime installation/Owner/ACL verification']}
Path(__file__).with_name('expanded-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'reachable_count':len(seen),'unresolved':sorted(unresolved),'direct_dml_nodes':[k for k in seen if functions[k]['direct_dml_tokens']],'semantic_closure_proven':False}))
