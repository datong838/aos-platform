from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import pytest
import yaml
import json


def module():
    root=Path(__file__).resolve().parents[4];sys.path.insert(0,str(root/'scripts'))
    spec=importlib.util.spec_from_file_location('extended_candidate_test',root/'scripts/prepare_niushop_extended_candidate.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def test_extended_source_policy_and_three_canonical_snapshots():
    m=module();root=m.CANDIDATES/m.SOURCE
    schema=json.loads((root/m.SCHEMA).read_text());mask=yaml.safe_load((root/m.MASKING).read_text())
    before=deepcopy((schema,mask))
    new_schema,new_mask=m.extended_policy(schema,mask)
    assert (schema,mask)==before
    assert len(new_schema['tables'])==12
    assert new_schema['tables'][:8]==schema['tables']
    for filename in m.MAPPINGS:
        old=yaml.safe_load((root/filename).read_text());old_copy=deepcopy(old)
        new=m.extended_mapping(old)
        assert old==old_copy
        assert m.evaluate_extended(new,new_schema,new_mask)['status']=='passed'


def test_original_sensitive_mappings_remain_rejected_by_new_policy():
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    m=module();root=m.CANDIDATES/m.SOURCE
    schema,mask=m.extended_policy(json.loads((root/m.SCHEMA).read_text()),yaml.safe_load((root/m.MASKING).read_text()))
    for filename in ('content/mappings/p10-system-config.yaml','content/mappings/p11-product-review.yaml','content/mappings/p12-payment.yaml'):
        original=yaml.safe_load((root/filename).read_text());original['incremental_strategy']='snapshot'
        with pytest.raises(ValueError):derive_mapping_read_spec(original,schema,mask)


def test_existing_extended_candidate_is_never_overwritten(tmp_path,monkeypatch):
    m=module();target=tmp_path/m.TARGET;target.mkdir(parents=True)
    monkeypatch.setattr(m,'CANDIDATES',tmp_path)
    with pytest.raises(ValueError,match='already exists'):m.prepare()


def test_changed_source_evidence_rejected(monkeypatch,tmp_path):
    m=module();p=tmp_path/'changed.json';p.write_text('{}');monkeypatch.setattr(m,'OBSERVATION',p)
    with pytest.raises(ValueError,match='observation'):m.extended_policy({}, {})
