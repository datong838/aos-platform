import importlib.util,copy
from pathlib import Path
import pytest
p=Path(__file__).with_name('dependency_review.py');s=importlib.util.spec_from_file_location('dr159',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def pair():
 a=[];b=[]
 for table in m.TABLES:
  r={'schema':'public','table':table,'constraint':'fk_'+table+'_module_ti2','index':'uq_meta_module_scope_pk_ti2','primary':False,'target_schema':'public','target_table':'meta_module','index_method':'btree','key_columns':['org_id','project_id','module_pk'],'key_count':3,'total_count':3,'opclasses':['pg_catalog.text_ops']*3,'collations':['pg_catalog.default']*3,'options':[0,0,0],'predicate':None,'expressions':None,'nulls_not_distinct':False,'unique':True,'immediate':True,'valid':True,'ready':True,'live':True}
  a.append(r);r=copy.deepcopy(r);r.update(index='meta_module_pkey',primary=True);b.append(r)
 return a,b
@pytest.mark.parametrize('field,value',[('opclasses',['wrong']*3),('collations',['NONE']*3),('options',[1,0,0]),('key_columns',['project_id','org_id','module_pk']),('nulls_not_distinct',True),('predicate','true'),('expressions','lower(org_id)'),('valid',False),('immediate',False),('ready',False),('unique',False),('schema','dev-org'),('target_table','other')])
def test_native_candidate_key_drift_rejected(field,value):
 a,b=pair();b[0][field]=value
 with pytest.raises(ValueError):m.require_binding_pairs(a,b)
def test_exact_closed_pairs_only():
 a,b=pair();assert len(m.require_binding_pairs(a,b))==9
 with pytest.raises(ValueError):m.require_binding_pairs(a,b[:-1])
def test_dependency_requires_each_native_proof_once():
 a,b=pair();proof=m.require_binding_pairs(a,b)
 rows=[{'object_type':'table constraint','object_schema':'public','object_identity':name,'deptype':'n','referenced_type':'index','referenced_schema':'public','referenced_identity':indices[0],'referenced_name':indices[0].split('.')[1]} for name,indices in proof.items()]
 assert len(m.canonical_dependencies(rows,proof))==9
 with pytest.raises(ValueError):m.canonical_dependencies(rows[:-1],proof)
 with pytest.raises(ValueError):m.canonical_dependencies(rows+[copy.deepcopy(rows[0])],proof)
 changed=copy.deepcopy(rows);changed[0]['referenced_name']='other'
 with pytest.raises(ValueError):m.canonical_dependencies(changed,proof)
def test_toast_normalization_retains_parent_and_multiplicity():
 row={'object_type':'toast table','object_schema':'pg_toast','object_name':'pg_toast_123','object_identity':'pg_toast.pg_toast_123','referenced_type':'table','referenced_identity':'public.parent','deptype':'i'}
 r=m.canonical_dependencies([row,row],{});assert len(r)==2;assert r[0]['referenced_identity']=='public.parent';assert row['object_name']=='pg_toast_123'
 altered=copy.deepcopy(row);altered['deptype']='n';assert m.canonical_dependencies([altered],{})[0]['object_name']=='pg_toast_123'
