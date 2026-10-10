from pathlib import Path
import sys,json,os,hashlib,psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-joint-operation-event-closure-20261010';sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_physical_capacity_joint_catalog import ForeignKey,Trigger,JointCatalogRejected
from aos_api.aip_physical_capacity_joint_events import EventCatalog,ForeignKeyAction,EventTrigger,TableEvent,joint_event_closure
orig=json.loads((R/'.evidence/gt-joint-constraint-dependency-closure-20261010/current-catalog-negative-r1.json').read_text());cat=orig['catalog'];lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());relations=frozenset(cat['relations']);actions={};masks={}
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=orig['identity']['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('server_version') AS version,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity['readonly']=='on' and identity['cluster']==lab['cluster']
 for x in c.execute("SELECT n.nspname||'.'||r.relname||'.'||k.conname AS key,k.confupdtype,k.confdeltype FROM pg_constraint k JOIN pg_class r ON r.oid=k.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace WHERE k.contype='f' AND (n.nspname='public' OR n.nspname LIKE 'aos_%')").fetchall():actions[x['key']]=(x['confupdtype'],x['confdeltype'])
 for x in c.execute("SELECT n.nspname||'.'||r.relname||'.'||t.tgname AS key,t.tgtype,encode(sha256(convert_to(p.prosrc,'UTF8')),'hex') AS hash FROM pg_trigger t JOIN pg_class r ON r.oid=t.tgrelid JOIN pg_namespace n ON n.oid=r.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname='public' OR n.nspname LIKE 'aos_%'").fetchall():masks[x['key']]=(x['tgtype'],x['hash'])
 assert set(actions)=={f['key'] for f in cat['foreign_keys']} and set(masks)=={t['key'] for t in cat['triggers']};assert all(masks[t['key']][1]==t['body_hash'] for t in cat['triggers'])
 decoded={'a':'NO ACTION','r':'RESTRICT','c':'CASCADE','n':'SET NULL','d':'SET DEFAULT'}
 fks=tuple(ForeignKeyAction(ForeignKey(**f),*[decoded[a] for a in actions[f['key']]]) for f in cat['foreign_keys'])
 triggers=tuple(EventTrigger(Trigger(**t),frozenset(op for bit,op in [(4,'INSERT'),(8,'DELETE'),(16,'UPDATE'),(32,'TRUNCATE')] if masks[t['key']][0]&bit)) for t in cat['triggers']);catalog=EventCatalog(relations,fks,triggers)
 seeds=frozenset([*[TableEvent('aos_physical_capacity_occupation_private.'+x,'INSERT') for x in ['prepared_parent_debit','prepared_execution_intent','prepared_plan_risk','prepared_shared_risk_description']],TableEvent('aos_model_eval_execution_private.manifest','INSERT'),TableEvent('aos_model_eval_issuer_private.executor_certificate','INSERT'),TableEvent('aos_model_eval_issuer_private.shared_parent_certificate_identity_binding','INSERT'),*[TableEvent('public.'+x,'INSERT') for x in ['aip_model_eval_budget_reservation','aip_model_eval_budget_reservation_bucket','aip_model_judge_budget_reservation','aip_model_judge_budget_reservation_bucket']],TableEvent('public.aip_budget_bucket','INSERT'),TableEvent('public.aip_budget_bucket','UPDATE'),TableEvent('public.aip_budget_cost_runtime_fence','UPDATE'),TableEvent('aos_physical_capacity_occupation_private.parent_debit_guard','UPDATE')])
 direct=[x for x in triggers if any(x.trigger.relation==e.relation and e.operation in x.operations for e in seeds)]
 try:joint_event_closure(catalog,seeds,())
 except JointCatalogRejected as exc:rejection=str(exc)
 else:raise AssertionError('unreviewed real effects accepted')
 assert rejection=='TRIGGER_EFFECT_REQUIRED'
 body=dict(identity=identity,seeds=[dict(relation=x.relation,operation=x.operation) for x in sorted(seeds)],seed_source_status='original-source candidate write set, not observed production/event queue',exact_mask_actions_current=True,source_catalog_sha256=orig['catalog_sha256'],actions=actions,trigger_masks={k:v[0] for k,v in masks.items()},direct_matching_trigger_count=len(direct),direct_matching_functions=sorted({x.trigger.function for x in direct}),real_catalog_negative=rejection,execution_allowed=False,full_finalizer_implemented=False,actual_event_queue_proven=False)
 (B/'current-events-negative-r1.json').open('x').write(json.dumps(body,indent=2)+'\n');print(json.dumps({k:v for k,v in body.items() if k not in ['actions','trigger_masks','seeds','direct_matching_functions']},indent=2))
