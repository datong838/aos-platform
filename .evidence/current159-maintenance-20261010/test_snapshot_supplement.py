import importlib.util,copy
from pathlib import Path
import pytest
p=Path(__file__).with_name('snapshot_supplement.py');s=importlib.util.spec_from_file_location('ss159',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
@pytest.mark.parametrize('kind',['a','w','?',None])
def test_unknown_routine_kind_rejected(kind):
 with pytest.raises(ValueError):m.require_routine_kinds(['f',kind])
def test_function_only_supported():assert m.require_routine_kinds(['f']) is None
@pytest.mark.parametrize('version',['a0v_158','a0v_159'])
@pytest.mark.parametrize('namespace',['aos_model_eval_execution_private','aos_model_eval_issuer_private'])
def test_new_private_schema_unsupported_routine_rejected(version,namespace,monkeypatch):
 def reject_followup(*args):raise AssertionError('Supplement queries must not follow unsupported routine')
 monkeypatch.setattr(m,'rows',reject_followup)
 class Result:
  def __init__(self,values):self.values=values
  def __iter__(self):return iter(self.values)
  def fetchall(self):return self.values
 class Connection:
  read_only=True
  def execute(self,sql):
   if 'SELECT nspname FROM pg_namespace' in sql:return Result([(x,) for x in ['public','aos_capacity_publication_private','aos_model_eval_execution_private','aos_model_eval_issuer_private']])
   if 'SELECT version_num' in sql:return Result([(version,)])
   if 'SELECT DISTINCT prokind' in sql:return Result([('a',)] if "'"+namespace+"'" in sql else [('f',)])
   raise AssertionError('Supplement queries must not follow unsupported routine')
 with pytest.raises(ValueError,match='UNREVIEWED_ROUTINE_KIND'):m.supplement(Connection(),version)
@pytest.mark.parametrize('field',['database_acl','sequence_definitions','type_acl','domain_constraints','dependencies','shared_dependencies','comments','collations'])
def test_supplement_omission_cannot_pass(field):
 a={k:[] for k in m.FIELDS};b=copy.deepcopy(a);del b[field]
 with pytest.raises(ValueError):m.require_supplement_equivalent(a,b)
@pytest.mark.parametrize('field',['database_acl','sequence_definitions','type_acl','dependencies'])
def test_changed_supplement_cannot_pass(field):
 a={k:[] for k in m.FIELDS};b=copy.deepcopy(a);b[field]=[{'changed':True}]
 with pytest.raises(ValueError):m.require_supplement_equivalent(a,b)
def test_missing_all_supplement_rejected():
 with pytest.raises(ValueError):m.require_supplement_equivalent({}, {})
def test_exact_full_supplement_preserved():
 a={k:[] for k in m.FIELDS};b=copy.deepcopy(a);assert m.require_supplement_equivalent(a,b);assert a==b

def test_internal_name_token_boundaries_and_comment_text_preserved():
 a={k:[] for k in m.FIELDS}
 a['dependencies']=[{'object_type':'trigger','object_identity':'trigger RI_ConstraintTrigger_a_101 on public.x'}]
 a['comments']=[{'object_type':'trigger','object_identity':'trigger RI_ConstraintTrigger_a_10 on public.x','description':'RI_ConstraintTrigger_a_10 is historical text'}]
 triggers=[{'tgname':'RI_ConstraintTrigger_a_10','tgisinternal':True},{'tgname':'RI_ConstraintTrigger_a_101','tgisinternal':True}]
 r=m.canonical(a,triggers)
 assert r['dependencies'][0]['object_identity']=='trigger RI_ConstraintTrigger_a_GENERATED_OID on public.x'
 assert r['comments'][0]['description']==a['comments'][0]['description']
 assert a['dependencies'][0]['object_identity'].endswith('a_101 on public.x')
def test_user_trigger_name_is_not_normalized():
 a={k:[] for k in m.FIELDS};a['dependencies']=[{'object_type':'trigger','object_identity':'trigger RI_ConstraintTrigger_a_10 on public.x'}]
 assert m.canonical(a,[{'tgname':'RI_ConstraintTrigger_a_10','tgisinternal':False}])==a

def test_dependency_normalization_is_linear_in_rows(monkeypatch):
 calls=[]
 class CountPattern:
  def sub(self,callback,value):
   calls.append(value);return __import__('re').sub(r'(?<![A-Za-z0-9_])RI_ConstraintTrigger_[ac]_[0-9]+(?![A-Za-z0-9_])',callback,value)
 monkeypatch.setattr(m,'OBJECT_NAME',CountPattern())
 a={k:[] for k in m.FIELDS};a['dependencies']=[{'object_type':'trigger','object_identity':f'trigger RI_ConstraintTrigger_a_{i%200} on public.x'} for i in range(1000)]
 triggers=[{'tgname':f'RI_ConstraintTrigger_a_{i}','tgisinternal':True} for i in range(200)]
 r=m.canonical(a,triggers);assert len(calls)==1000;assert len(r['dependencies'])==1000
 assert all(x['object_identity']=='trigger RI_ConstraintTrigger_a_GENERATED_OID on public.x' for x in r['dependencies'])
