"""Verify captured native writes without treating counters as queued events."""
import hashlib,json,subprocess
from pathlib import Path
R=Path.cwd();B=R/'.evidence/gt-shared-parent-atomic-admission-finalizer-20261010';N=B/'write-closure-native-1743-r1'
rows=[json.loads(l) for l in (N/'native-write-capture.jsonl').read_text().splitlines()]
commit=[r for r in rows if r['point']=='before_actual_commit'];assert len(commit)==1
c=commit[0];proof=json.loads((N/'component-native-proof.json').read_text());rb=json.loads((N/'independent-readback.json').read_text());result=json.loads((N/'result-r1.json').read_text())
assert c['identity']['xid']==proof['rollback_xid']
assert all(r['identity']=={**c['identity'],'observed_at':r['identity']['observed_at']} for r in rows)
assert all(r['counters_include_rolled_back_savepoints'] and not r['pending_event_queue_proven'] for r in rows)
assert proof['actual_commit_rejected'] and rb['native_caller_aborted'] and rb['temporary_permissions_restored']
assert not rb['whole_fixture_pass'] and result['old_files_unchanged']
tables={r['relid']:r['schemaname']+'.'+r['relname'] for r in c['write_counters']}
shared={i:n for i,n in tables.items() if n.startswith('aos_shared_parent')};original={i:n for i,n in tables.items() if i not in shared}
assert len(tables)==17 and len(shared)==8 and len(original)==9
assert {'public.aip_budget_bucket','public.aip_budget_cost_runtime_fence','public.aip_model_eval_budget_reservation','public.aip_model_judge_budget_reservation'}<=set(original.values())
assert all(r['tgrelid'] in tables for r in c['triggers'])
assert all(r['conrelid'] in tables or r['confrelid'] in tables for r in c['constraints'])
assert all(r['tgenabled']=='O' for r in c['triggers'])
defusers=[r for r in c['triggers'] if r['tgdeferrable'] and not r['tgisinternal']]
assert len(defusers)==9 and all(r['tginitdeferred'] for r in defusers)
incoming=[r for r in c['constraints'] if r['conrelid'] not in tables and r['confrelid'] in tables]
foreign=[r for r in c['constraints'] if r['contype']=='f']
assert all(not r['condeferrable'] for r in foreign)
files=['native-write-capture.jsonl','result-r1.json','profiler-restoration.json','independent-readback.json','run-native-r1.py','source_newjudge_native_trial_1606.py']
output=dict(status='ACTUAL_NATIVE_WRITE_OVERAPPROXIMATION_VERIFIED',authority='AOS-001743',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),task=B.name,database=result['databases'][0],caller=c['identity'],stage_captures=len(rows),actual_write_counter_relations=list(tables.values()),original_relation_count=len(original),shared_relation_count=len(shared),catalog_counts={k:len(c[k]) for k in ['constraints','triggers','indexes','columns']},foreign_constraints=len(foreign),incoming_foreign_constraints=len(incoming),deferred_user_triggers=[dict(table=tables[r['tgrelid']],name=r['tgname'],function=r['function'],body_hash=r['body_hash']) for r in defusers],exact_capture_hashes={f:hashlib.sha256((N/f).read_bytes()).hexdigest() for f in files},actual_missing_end_commit_rejected=True,native_caller_aborted=True,temporary_permissions_restored=True,whole_fixture_pass=False,pending_event_queue_proven=False,counters_include_rolled_back_savepoints=True,transitive_event_closure_proven=False,full_admission_commit=False,execution_allowed=False,full_task_delivered=False,limitations=['Write statistics include rolled-back savepoints and do not enumerate pending events.','Incoming constraints on untouched relations do not prove absence of cascade-triggered effects.','Immediate FK catalog flags alone do not prove future deferred trigger execution has no waits.','Original whole fixture call and cleanup remain Source-currentness RED.'],next_step='Read exact native deferred bodies and transitive trigger dependencies; freeze an event-drain protocol before implementing the complete ending.')
(B/'write-closure-verification-1743.json').open('x').write(json.dumps(output,indent=2)+'\n')
print(json.dumps({k:output[k] for k in ['status','stage_captures','original_relation_count','shared_relation_count','foreign_constraints','incoming_foreign_constraints','pending_event_queue_proven']}))
