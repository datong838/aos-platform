import importlib
import pytest
from test_growth19_successor_business import profile


def test_existing_source_intent_never_reopens_or_resubmits(profile,monkeypatch,tmp_path):
    module=importlib.import_module('a0v_growth19_product_source_once')
    monkeypatch.setattr(module,'STATE',tmp_path)
    (tmp_path/'execute-intent.json').write_text('{}')
    calls=[]
    monkeypatch.setattr(module.f,'setup',lambda:calls.append('setup'))
    monkeypatch.setattr(module,'api',lambda *args:calls.append(args))
    with pytest.raises(ValueError,match='read-only'):module.run()
    assert calls==[]
