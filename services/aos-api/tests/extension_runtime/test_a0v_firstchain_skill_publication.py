from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import a0v_firstchain_skill_publication as preparation


@pytest.mark.parametrize('database', ['aos_meta_head', 'postgres', 'other_clone', None])
def test_non_owned_clone_is_rejected_before_constructing_stores(monkeypatch, database):
    calls = []
    def execute(query):
        calls.append(query)
        return SimpleNamespace(fetchone=lambda: None if database is None else {'database': database})
    @contextmanager
    def connect(scope):
        assert scope == preparation.SCOPE
        yield SimpleNamespace(execute=execute)
    monkeypatch.setattr(preparation, 'AipModelRuntimeStore', lambda *a: pytest.fail('must reject before stores'))
    with pytest.raises(ValueError, match='FIRSTCHAIN_CONTRACT_CLONE_ONLY'):
        preparation.prepare_contracts(connect)
    assert calls == ['SELECT current_database() AS database']


def test_no_implicit_database_fallback():
    with pytest.raises(ValueError, match='EXPLICIT_CLONE_CONNECTION_REQUIRED'):
        preparation.prepare_contracts(None)
