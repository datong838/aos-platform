import importlib.util
from pathlib import Path

import pytest


def isolated_loader():
    path = Path(__file__).resolve().parents[1] / 'aos_api/env_load.py'
    spec = importlib.util.spec_from_file_location('isolated_env_load', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('force', [False, True])
def test_disabled_loader_never_discovers_files(monkeypatch, force):
    loader = isolated_loader()
    monkeypatch.setenv('AOS_DOTENV_DISABLED', '1')
    def forbidden():
        pytest.fail('disabled loader must not enumerate credential files')
    monkeypatch.setattr(loader, '_candidate_paths', forbidden)
    assert loader.load_dotenv(force=force) is None
    assert loader._LOADED is False


def test_default_loader_still_loads_fixture(monkeypatch, tmp_path):
    loader = isolated_loader()
    monkeypatch.delenv('AOS_DOTENV_DISABLED', raising=False)
    monkeypatch.delenv('AOS_TEST_SYNTHETIC_DOTENV', raising=False)
    path = tmp_path / '.env'
    path.write_text('AOS_TEST_SYNTHETIC_DOTENV=fixture\n')
    monkeypatch.setattr(loader, '_candidate_paths', lambda: [path])
    assert loader.load_dotenv() == path
    import os
    assert os.environ.pop('AOS_TEST_SYNTHETIC_DOTENV') == 'fixture'
