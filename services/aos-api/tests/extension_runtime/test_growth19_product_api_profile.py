import importlib
from pathlib import Path


def test_growth19_api_preserves_original_profile(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4]/'scripts'))
    current=importlib.import_module('a0v_growth19_product_controlled_api')
    original=importlib.import_module('a0v_product_controlled_api').load_launcher()
    launcher=current.load_launcher()
    assert launcher.BUNDLE_ROOT==current.BUNDLE_ROOT
    assert str(launcher.BUNDLE_ROOT).endswith('signed-bundles-growth-1.9-current')
    assert str(original.BUNDLE_ROOT).endswith('signed-bundles-niushop-1.23-current')
    assert launcher.API_FLAGS==original.API_FLAGS
    assert callable(launcher.configure_environment) and callable(launcher.preflight)
