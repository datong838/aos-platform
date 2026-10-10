"""Only established CHECK reassociation and generated native RI names."""
import copy,json,re,importlib.util
from pathlib import Path
R=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('restore150_reviewed',R/'scripts/a0v_current_150_restore_gate.py');legacy=importlib.util.module_from_spec(s);s.loader.exec_module(legacy)
ANCHOR_COLUMNS=frozenset(('publisher_subject','signer_key_id','signer_publisher'))
RI=frozenset('RI_FKey_'+x for x in ('check_ins','check_upd','noaction_del','noaction_upd','restrict_del','restrict_upd','cascade_del','cascade_upd','setnull_del','setnull_upd','setdefault_del','setdefault_upd'))
def normalize(value):
 result=copy.deepcopy(value)
 for r in result.get('constraints',[]):
  if r['contype']=='c':
   r['definition']=legacy.length_and_candidate(r['definition'])
   for column in ANCHOR_COLUMNS:
    if (r.get('nspname'),r.get('relname'),r.get('conname'))!=('aos_capacity_publication_private','deployment_anchor','deployment_anchor_'+column+'_check'):continue
    original=f'CHECK ((((length({column}) >= 1) AND (length({column}) <= 200)) AND ({column} = btrim({column}))))'
    restored=f'CHECK (((length({column}) >= 1) AND (length({column}) <= 200) AND ({column} = btrim({column}))))'
    if r['definition']==original:r['definition']=restored
 for r in result.get('triggers',[]):
  name=r['tgname']
  if not r['tgisinternal'] or re.fullmatch(r'RI_ConstraintTrigger_[ac]_[0-9]+',name) is None:continue
  prefix='CREATE CONSTRAINT TRIGGER "'+name+'" '
  function=re.search(r'EXECUTE FUNCTION "(RI_FKey_[a-z_]+)"\(\)$',r['definition'])
  if not r['definition'].startswith(prefix) or function is None or function[1] not in RI:
   raise ValueError('UNKNOWN_INTERNAL_TRIGGER_DEFINITION')
  canonical=re.sub(r'_[0-9]+$','_GENERATED_OID',name)
  r['tgname']=canonical;r['definition']='CREATE CONSTRAINT TRIGGER "'+canonical+'" '+r['definition'][len(prefix):]
 for k in ('constraints','triggers'):
  if k in result:result[k].sort(key=lambda r:json.dumps(r,sort_keys=True))
 return result

def require_equivalent(before,after):
 if normalize(before)!=normalize(after):raise ValueError('UNREVIEWED_RESTORE_DIFFERENCE')
 return True
