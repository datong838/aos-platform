"""Fixed nine legacy FK alternate equivalent unique-index binding review."""
import copy,json,re
TABLES=frozenset(('module_canvas_config','module_deployment','module_events','module_instance_overlay','module_interface','module_query','module_user_view_preference','module_variable','module_widget_instance'))
SEMANTICS=('target_schema','target_table','index_method','key_columns','key_count','total_count','opclasses','collations','options','predicate','expressions','nulls_not_distinct')
def require_binding_pairs(source,restored):
 left={x['table']:x for x in source};right={x['table']:x for x in restored}
 if set(left)!=TABLES or set(right)!=TABLES or len(source)!=9 or len(restored)!=9:raise ValueError('NINE_BINDING_COVERAGE_REQUIRED')
 proof={}
 for table in TABLES:
  a,b=left[table],right[table]
  for r in (a,b):
   if r['schema']!='public' or r['constraint']!='fk_'+table+'_module_ti2':raise ValueError('FIXED_FK_SCOPE_REQUIRED')
   if not all(r[k] is True for k in ('unique','immediate','valid','ready','live')):raise ValueError('CANDIDATE_KEY_NOT_USABLE')
  if a['index']!='uq_meta_module_scope_pk_ti2' or b['index']!='meta_module_pkey' or a['primary'] is not False or b['primary'] is not True:raise ValueError('FIXED_ALTERNATE_BINDING_REQUIRED')
  if any(a[k]!=b[k] for k in SEMANTICS):raise ValueError('FK_KEY_SEMANTICS_CHANGED')
  if a['target_schema']!='public' or a['target_table']!='meta_module' or a['key_columns']!=['org_id','project_id','module_pk'] or a['key_count']!=3 or a['total_count']!=3 or a['predicate'] is not None or a['expressions'] is not None:raise ValueError('FIXED_PLAIN_THREE_COLUMN_KEY_REQUIRED')
  proof['fk_'+table+'_module_ti2 on public.'+table]=('public.uq_meta_module_scope_pk_ti2','public.meta_module_pkey')
 return proof

def canonical_dependencies(rows,proof):
 result=copy.deepcopy(rows)
 seen=[]
 for r in result:
  if r['object_type']=='toast table' and r['deptype']=='i' and r['referenced_type']=='table':
   name=r.get('object_name');schema=r.get('object_schema')
   if schema=='pg_toast' and isinstance(name,str) and re.fullmatch(r'pg_toast_[0-9]+',name) and r['object_identity']=='pg_toast.'+name:
    r['object_name']='pg_toast_GENERATED_FOR_PARENT';r['object_identity']='pg_toast.pg_toast_GENERATED_FOR_PARENT'
  identity=r.get('object_identity')
  if identity in proof and r['object_type']=='table constraint' and r['object_schema']=='public' and r['deptype']=='n' and r['referenced_type']=='index':
   expected=proof[identity]
   if r['referenced_identity'] not in expected or r['referenced_name']!=r['referenced_identity'].split('.')[1] or r['referenced_schema']!='public':raise ValueError('UNPROVEN_DEPENDENCY_INDEX')
   seen.append(identity);r['referenced_identity']='public.PROVEN_EQUIVALENT_META_MODULE_KEY';r['referenced_name']='PROVEN_EQUIVALENT_META_MODULE_KEY'
 if sorted(seen)!=sorted(proof):raise ValueError('EXACTLY_ONE_DEPENDENCY_PER_FK_REQUIRED')
 result.sort(key=lambda r:json.dumps(r,sort_keys=True));return result
