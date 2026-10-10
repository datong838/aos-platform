from pathlib import Path
import json,sys,hashlib
R=Path.cwd();B=R/'.evidence/gt-joint-operation-event-closure-20261010';sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_physical_capacity_joint_catalog import ForeignKey,Trigger,JointCatalogRejected
from aos_api.aip_physical_capacity_joint_events import EventCatalog,ForeignKeyAction,EventTrigger,EventEffect,TableEvent,joint_event_closure
raw=R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010/trigger-effects-current-r1-1685.json'
fns={**json.loads(raw.read_text())['functions'],**json.loads((B/'direct-function-bodies-r1.json').read_text())['functions']}
writes={
 'advance_identity_withdrawal':[('identity_epoch','UPDATE')],
 'advance_root_withdrawal_epoch':[('issuer_epoch','UPDATE'),('certificate_epoch','UPDATE')],
 'derive_certificate_identity':[('identity_epoch','INSERT'),('identity_epoch','UPDATE')],
 'derive_shared_parent_identity':[('identity_epoch','INSERT'),('identity_epoch','UPDATE')],
 'initialize_certificate_epoch':[('certificate_epoch','INSERT')],
}
contracts=[]
for name,v in sorted(fns.items()):
 if v['language']=='internal':continue
 assert v['language']=='plpgsql' and hashlib.sha256(v['body'].encode()).hexdigest()==v['body_sha256']
 op=name.split('.')[-1].split('(')[0];events=[dict(relation='aos_model_eval_issuer_private.'+r,operation=o) for r,o in writes.get(op,[])]
 contracts.append(dict(function=name,body_hash=v['body_sha256'],writes=events,review='manual visible PLpgSQL SQL write upper bound; branch union, NEW assignments stay original event; RAISE-only has no additional SQL writes'))
assert len(contracts)==15
base=json.loads((B/'current-events-negative-r1.json').read_text());cat=json.loads((R/'.evidence/gt-joint-constraint-dependency-closure-20261010/current-catalog-negative-r1.json').read_text())['catalog']
catalog=EventCatalog(frozenset(cat['relations']),tuple(ForeignKeyAction(ForeignKey(**f),*({'a':'NO ACTION','r':'RESTRICT','c':'CASCADE','n':'SET NULL','d':'SET DEFAULT'}[a] for a in base['actions'][f['key']])) for f in cat['foreign_keys']),tuple(EventTrigger(Trigger(**t),frozenset(o for bit,o in [(4,'INSERT'),(8,'DELETE'),(16,'UPDATE'),(32,'TRUNCATE')] if base['trigger_masks'][t['key']]&bit)) for t in cat['triggers']))
effects=tuple(EventEffect(x['function'],x['body_hash'],frozenset(TableEvent(**e) for e in x['writes'])) for x in contracts)
try:joint_event_closure(catalog,frozenset(TableEvent(**x) for x in base['seeds']),effects)
except JointCatalogRejected as e:rejection=str(e)
else:raise AssertionError('kernel without provenance accepted')
assert rejection=='TRIGGER_EFFECT_REQUIRED'
body=dict(contracts=contracts,application_sql_contract_count=15,internal_functions_omitted=sorted(k for k,v in fns.items() if v['language']=='internal'),real_catalog_rejection=rejection,kernel_empty_effect_approved=False,formal_installation_approved=False,recursive_effects_complete=False,execution_allowed=False,source_fetch_failure=dict(url='https://raw.githubusercontent.com/postgres/postgres/REL_16_14/src/backend/utils/adt/ri_triggers.c',curl_exit=35,message='Recv failure: Connection reset by peer',local_source_exists=False,following_assertion_failed_before_candidate_write=True),primary_source_reading_only=['https://raw.githubusercontent.com/postgres/postgres/REL_16_14/src/backend/utils/adt/ri_triggers.c','https://raw.githubusercontent.com/postgres/postgres/REL_16_14/src/include/catalog/pg_trigger.h'])
(B/'manual-effects-candidate-r1.json').open('x').write(json.dumps(body,indent=2)+'\n')
callbacks=json.loads((B/'fk-callbacks-r1.json').read_text());summary={k:v for k,v in callbacks.items() if k!='bindings'};summary['exact_callback_file_sha256']=hashlib.sha256((B/'fk-callbacks-r1.json').read_bytes()).hexdigest();(B/'fk-callbacks-summary-r1.json').open('x').write(json.dumps(summary,indent=2)+'\n')
print(json.dumps(dict(application_sql_contract_count=15,internal_functions_not_approved=len(body['internal_functions_omitted']),real_catalog_rejection=rejection,execution_allowed=False)))
