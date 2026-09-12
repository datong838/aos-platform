from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import pytest
import yaml


def module():
    root=Path(__file__).resolve().parents[4]
    sys.path.insert(0,str(root/'scripts'))
    spec=importlib.util.spec_from_file_location('product_candidate_test',root/'scripts/prepare_niushop_product_candidate.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def test_product_candidate_preserves_constraints_and_does_not_mutate_predecessor():
    m=module();root=m.CANDIDATES/m.SOURCE
    original=yaml.safe_load((root/m.MAPPING).read_text());before=deepcopy(original)
    new=m.product_mapping(original)
    assert original==before
    assert new['site_filter']=='site_id=1'
    assert new['validation']['non_negative']==before['validation']['non_negative']
    assert new['incremental_strategy']=='snapshot'
    assert 'soft_delete' not in new and 'incremental_cursor' not in new
    assert m.evaluate_product(new,root)['status']=='passed'


def test_existing_candidate_is_never_overwritten(tmp_path,monkeypatch):
    m=module();target=tmp_path/m.TARGET;target.mkdir(parents=True)
    marker=target/'keep';marker.write_text('protected')
    monkeypatch.setattr(m,'CANDIDATES',tmp_path)
    with pytest.raises(ValueError,match='already exists'):m.prepare()
    assert marker.read_text()=='protected'


def test_changed_predecessor_cannot_create_candidate(tmp_path,monkeypatch):
    m=module();source=tmp_path/m.SOURCE;source.mkdir(parents=True)
    monkeypatch.setattr(m,'CANDIDATES',tmp_path)
    with pytest.raises(ValueError,match='baseline differs'):m.prepare()
    assert not (tmp_path/m.TARGET).exists()
