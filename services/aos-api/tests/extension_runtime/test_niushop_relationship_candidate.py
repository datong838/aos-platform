from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import pytest


def module():
    root=Path(__file__).resolve().parents[4];sys.path.insert(0,str(root/'scripts'))
    spec=importlib.util.spec_from_file_location('relationship_candidate_test',root/'scripts/prepare_niushop_relationship_candidate.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def test_all_declared_relationships_match_current_output_and_core_direction():
    m=module();result=m.evaluate_relationships(m.relationship_policy(),m.CANDIDATES/m.SOURCE)
    assert result['candidateLinks']==14 and result['status']=='passed'


def test_historical_field_alias_cannot_enter_new_policy():
    m=module();p=m.relationship_policy()
    next(r for r in p['rules'] if r['linkType']=='OrderLine.ofProduct')['referenceProperty']='goodsId'
    with pytest.raises(ValueError,match='output'):m.evaluate_relationships(p,m.CANDIDATES/m.SOURCE)


def test_existing_candidate_is_immutable(tmp_path,monkeypatch):
    m=module();target=tmp_path/m.TARGET;target.mkdir(parents=True);marker=target/'keep';marker.write_text('protected')
    monkeypatch.setattr(m,'CANDIDATES',tmp_path)
    with pytest.raises(ValueError,match='already exists'):m.prepare()
    assert marker.read_text()=='protected'


def test_changed_predecessor_cannot_create_candidate(tmp_path,monkeypatch):
    m=module();(tmp_path/m.SOURCE).mkdir(parents=True);monkeypatch.setattr(m,'CANDIDATES',tmp_path)
    with pytest.raises(ValueError,match='baseline differs'):m.prepare()
    assert not (tmp_path/m.TARGET).exists()
