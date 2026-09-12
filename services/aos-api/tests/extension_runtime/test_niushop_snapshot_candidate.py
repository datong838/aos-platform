import importlib.util
import shutil
from pathlib import Path

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[4]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_prepare_never_overwrites_target(tmp_path,monkeypatch):
    prepare=load('prepare_niushop_snapshot_candidate')
    monkeypatch.setattr(prepare,'CANDIDATES',tmp_path)
    (tmp_path/prepare.TARGET).mkdir(parents=True)
    with pytest.raises(ValueError,match='exists'):prepare.prepare()


def test_old_hash_drift_is_rejected_before_copy(tmp_path,monkeypatch):
    prepare=load('prepare_niushop_snapshot_candidate')
    source=tmp_path/prepare.SOURCE;source.mkdir(parents=True);(source/'changed').write_text('changed')
    monkeypatch.setattr(prepare,'CANDIDATES',tmp_path)
    with pytest.raises(ValueError,match='baseline'):prepare.prepare()
    assert not (tmp_path/prepare.TARGET).exists()


def test_preparation_changes_only_declared_files_and_evaluates_new_mapping(tmp_path,monkeypatch):
    prepare=load('prepare_niushop_snapshot_candidate')
    shutil.copytree(prepare.CANDIDATES/prepare.SOURCE,tmp_path/prepare.SOURCE,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    monkeypatch.setattr(prepare,'CANDIDATES',tmp_path)
    result=prepare.prepare()
    assert result['outcome']=='NIUSHOP_SNAPSHOT_CANDIDATE_PREPARED'
    assert result['changedFiles']==['bundle.yaml','content/mappings/p01-shop.yaml','evidence/bundle-evals.json']
    assert result['sourceTreeHash']==prepare.BASE_HASH
    assert result['evaluation']['status']=='passed'
    assert result['evaluation']['scope']=='static-snapshot-mapping-only'
    value=yaml.safe_load((tmp_path/prepare.TARGET/'content/mappings/p01-shop.yaml').read_text())
    assert value['pii_exclusion']==['site_tel']
    assert value['snapshot_materialization']['property_defaults']['currency']=='CNY'


def test_profile_is_private_and_does_not_change_original_builder():
    profile=load('build_niushop_snapshot_candidates').load_builder()
    original=load('build_ecommerce_runtime_candidates')
    assert profile.RUNTIME_CASES[1][2]=='1.4.0'
    assert original.RUNTIME_CASES[1][2]=='1.3.0'
    assert profile.RUNTIME_CASES[0]==original.RUNTIME_CASES[0]
    assert profile.RUNTIME_CASES[2]==original.RUNTIME_CASES[2]


def test_actual_new_candidate_evidence_and_inventory_match():
    prepare=load('prepare_niushop_snapshot_candidate')
    import json
    target=prepare.CANDIDATES/prepare.TARGET
    assert json.loads((target/'evidence/bundle-evals.json').read_text())==prepare.evaluate(target)
    profile=load('build_niushop_snapshot_candidates').load_builder()
    result=profile.preflight()
    assert (result['bundleCount'],result['runtimeMemberCount'],result['moduleCount'],result['operationCount'])==(4,3,8,12)
    assert profile._tree_hash(prepare.CANDIDATES/prepare.SOURCE)==prepare.BASE_HASH
