import importlib.util
from pathlib import Path
import pytest
P=Path(__file__).with_name('snapshot_all.py')
s=importlib.util.spec_from_file_location('snapshot_all159',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def test_duplicate_table_names_remain_distinct():
 assert m.qualified('public','risk').as_string()=='"public"."risk"'
 assert m.qualified('aos_capacity_publication_private','risk').as_string()=='"aos_capacity_publication_private"."risk"'

def test_identifier_does_not_execute_sql():
 assert m.qualified('public','x";DROP DATABASE y;--').as_string()=='"public"."x"";DROP DATABASE y;--"'

@pytest.mark.parametrize('schemas',[['public'],['public','unknown'],[]])
def test_missing_or_unknown_schema_rejected(schemas):
 with pytest.raises(ValueError):m.require_schema_set(schemas)

@pytest.mark.parametrize('key',['tables','functions','policies','role_memberships','column_acl','sequences'])
def test_any_restore_omission_rejected(key):
 before={key:[{'evidence':'original'}]};after={key:[]}
 with pytest.raises(ValueError):m.compare_exact(before,after)

def test_exact_comparison_preserves_input():
 a={'tables':{'public.x':{'rows':0,'sha256':'x'}}};assert m.compare_exact(a,a)==True
@pytest.mark.parametrize('version',['a0v_158','a0v_159'])
def test_explicit_original_migrated_schema_set_only(version):
 schemas=['public','aos_capacity_publication_private','aos_model_eval_execution_private','aos_model_eval_issuer_private']
 assert m.require_schema_set(schemas,version=version) is None
 with pytest.raises(ValueError):m.require_schema_set(schemas,version='a0v_157')
 with pytest.raises(ValueError):m.require_schema_set(schemas+['unregistered'],version=version)
@pytest.mark.parametrize('version',['a0v_160',None,True,'a0v_159;COMMIT'])
def test_schema_version_selector_closed(version):
 with pytest.raises(ValueError):m.require_schema_set(list(m.SCHEMAS),version=version)
