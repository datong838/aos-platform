import importlib.util,copy
from pathlib import Path
import pytest
p=Path(__file__).with_name('restore_comparison.py');s=importlib.util.spec_from_file_location('rc159',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def trigger(number):
 n='RI_ConstraintTrigger_a_'+str(number)
 return {'tgname':n,'tgisinternal':True,'tgenabled':'O','nspname':'public','relname':'parent','definition':f'CREATE CONSTRAINT TRIGGER "{n}" AFTER DELETE ON public.parent FROM public.child NOT DEFERRABLE INITIALLY IMMEDIATE FOR EACH ROW EXECUTE FUNCTION "RI_FKey_noaction_del"()'}
def test_only_generated_oid_changes():
 assert m.require_equivalent({'triggers':[trigger(1)]},{'triggers':[trigger(9999)]})
@pytest.mark.parametrize('change',['disabled','function','relation','delete','duplicate','user_trigger'])
def test_ri_effect_or_multiplicity_drift_rejected(change):
 a={'triggers':[trigger(1)]};b=copy.deepcopy(a)
 if change=='disabled':b['triggers'][0]['tgenabled']='D'
 if change=='function':b['triggers'][0]['definition']=b['triggers'][0]['definition'].replace('noaction_del','cascade_del')
 if change=='relation':b['triggers'][0]['definition']=b['triggers'][0]['definition'].replace('public.child','public.other')
 if change=='delete':b['triggers']=[]
 if change=='duplicate':b['triggers'].append(trigger(999))
 if change=='user_trigger':b['triggers'][0]['tgisinternal']=False;b['triggers'][0]['tgname']='RI_ConstraintTrigger_a_99'
 with pytest.raises(ValueError):m.require_equivalent(a,b)
def test_arbitrary_check_not_normalized():
 a={'constraints':[{'contype':'c','definition':'CHECK (allowed = true)'}]};b=copy.deepcopy(a);b['constraints'][0]['definition']='CHECK (true)'
 with pytest.raises(ValueError):m.require_equivalent(a,b)
@pytest.mark.parametrize('key',['tables','function_acl','functions','role_memberships'])
def test_non_check_non_name_evidence_must_be_exact(key):
 with pytest.raises(ValueError):m.require_equivalent({key:['original']},{key:[]})

@pytest.mark.parametrize('column',['publisher_subject','signer_key_id','signer_publisher'])
def test_exact_private_anchor_three_conjunction_pairs(column):
 r={'nspname':'aos_capacity_publication_private','relname':'deployment_anchor','conname':'deployment_anchor_'+column+'_check','contype':'c','definition':f'CHECK ((((length({column}) >= 1) AND (length({column}) <= 200)) AND ({column} = btrim({column}))))'}
 a={'constraints':[r]};b=copy.deepcopy(a);b['constraints'][0]['definition']=f'CHECK (((length({column}) >= 1) AND (length({column}) <= 200) AND ({column} = btrim({column}))))'
 assert m.require_equivalent(a,b)
 for key,value in [('nspname','public'),('definition',b['constraints'][0]['definition'].replace('200','201')),('definition',b['constraints'][0]['definition'].replace(' = btrim',' <> btrim'))]:
  mutated=copy.deepcopy(b);mutated['constraints'][0][key]=value
  with pytest.raises(ValueError):m.require_equivalent(a,mutated)
