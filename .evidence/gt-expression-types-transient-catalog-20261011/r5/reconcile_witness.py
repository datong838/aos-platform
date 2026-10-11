import json
from pathlib import Path
B=Path(__file__).resolve().parent
terminal=json.loads((B/'independent-readback.json').read_text())
types=json.loads((B/'type-binding-readback.json').read_text())
w=json.loads((B/'pre-rollback-catalog-witnesses.json').read_text());by={r['oid']:r for r in w}
missing=terminal['missing_post_rollback_oids'];bound=[by[x] for x in missing if x in by];unbound=sorted(set(missing)-set(by))
assert len(missing)==3 and not unbound
caller=json.loads((B/'cleanup-proof.json').read_text())['caller']
assert all(x['caller_pid']==int(caller['pid']) for x in bound)
assert all(len(x['source_sha256'])==64 and x['signature'] and x['owner'] for x in bound)
assert terminal['xid_aborted'] and len(terminal['table_counts'])==9 and not any(terminal['table_counts'].values())
assert types['records']==257 and set(types['missing_function_oids_after_rollback'])<=set(by)
x={'original_source_passed':True,'terminal_xid_aborted':True,'nine_tables_zero':True,'typed_records':types['records'],'observed_function_oids':terminal['observed_oid_count'],'terminal_function_identities':terminal['observed_function_count'],'pre_rollback_missing_function_witnesses':bound,'unbound_missing_function_oids':unbound,'same_caller_pre_call_catalog':True,'typed_function_oids':types['function_oids'],'typed_missing_function_witnesses_bound':True,'full_native_closure':False,'formal_root_or_business_authorized':False,'retained_witness_count':len(w),'limits':['Caller-visible pre-call catalog identity is not execution authority','No complete native event or unvisited-branch proof','No formal Root, natural COMMIT or QYH runtime acceptance']}
(B/'witness-reconciliation.json').open('x').write(json.dumps(x,indent=2)+'\n')
print(json.dumps({k:v for k,v in x.items() if k not in ['pre_rollback_missing_function_witnesses','limits']}))
