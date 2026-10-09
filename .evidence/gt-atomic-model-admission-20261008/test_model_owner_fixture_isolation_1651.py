import importlib.util
from pathlib import Path
import sys
import tempfile
import pytest

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'services/aos-api'))
sys.path.insert(0,str(REPO/'services/aos-api/tests/extension_runtime'))
def load():
    spec=importlib.util.spec_from_file_location('owner_fixture_under_test',REPO/'services/aos-api/tests/aip/test_model_eval_execution_owner_pg.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_outside_directory_rejected_before_helper_loading(monkeypatch,tmp_path):
    monkeypatch.setenv('AOS_MODEL_OWNER_FIXTURE_EVIDENCE_ROOT',str(tmp_path))
    with pytest.raises(ValueError,match='isolated Model evidence'):
        load()._model_owner_fixture_base()

def test_original_directory_rejected_as_new_attempt(monkeypatch):
    monkeypatch.setenv('AOS_MODEL_OWNER_FIXTURE_EVIDENCE_ROOT',str(Path(__file__).parent))
    with pytest.raises(ValueError,match='isolated Model evidence'):
        load()._model_owner_fixture_base()

def test_default_original_fixture_path_preserved(monkeypatch):
    monkeypatch.delenv('AOS_MODEL_OWNER_FIXTURE_EVIDENCE_ROOT',raising=False)
    assert load()._model_owner_fixture_base()==Path(__file__).parent

def test_exact_helpers_accepted_then_existing_output_rejected(monkeypatch):
    original=Path(__file__).parent
    with tempfile.TemporaryDirectory(prefix='fixture-isolation-unit-',dir=original) as directory:
        selected=Path(directory)
        for name in ('legal_model_prefix_for_application_r4.py','legal_eval_application_fixture_r4.py'):
            (selected/name).write_bytes((original/name).read_bytes())
        monkeypatch.setenv('AOS_MODEL_OWNER_FIXTURE_EVIDENCE_ROOT',directory)
        assert load()._model_owner_fixture_base()==selected
        with pytest.raises(ValueError,match='exact registered helpers'):
            load()._model_owner_fixture_base(whole=True)
        extra='original_plan_certificate_fixture_r1.py'
        (selected/extra).write_bytes((original/extra).read_bytes())
        assert load()._model_owner_fixture_base(whole=True)==selected
        result=selected/'legal-eval-application-result-r4.json'
        result.write_text('retained known result')
        with pytest.raises(ValueError,match='earlier attempt'):
            load()._model_owner_fixture_base()
        assert result.read_text()=='retained known result'

def test_modified_helper_rejected_without_import(monkeypatch):
    original=Path(__file__).parent
    with tempfile.TemporaryDirectory(prefix='fixture-isolation-unit-',dir=original) as directory:
        selected=Path(directory)
        for name in ('legal_model_prefix_for_application_r4.py','legal_eval_application_fixture_r4.py'):
            (selected/name).write_bytes((original/name).read_bytes())
        (selected/'legal_model_prefix_for_application_r4.py').write_text('raise RuntimeError("must not execute")')
        monkeypatch.setenv('AOS_MODEL_OWNER_FIXTURE_EVIDENCE_ROOT',directory)
        with pytest.raises(ValueError,match='exact registered helpers'):
            load()._model_owner_fixture_base()
