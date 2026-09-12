from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from a0v_firstchain_contract_materialize import require_target


@pytest.mark.parametrize('actual', ['postgres', 'aos_other', 'aos_text_renewal_20260912', None])
def test_wrong_database_rejected(actual):
    @contextmanager
    def connect(scope):
        yield SimpleNamespace(execute=lambda *a: SimpleNamespace(
            fetchone=lambda: None if actual is None else {'database': actual}))
    with pytest.raises(ValueError, match='DATABASE_MISMATCH'):
        require_target(connect, 'aos_meta_head')


def test_unlisted_target_does_not_connect():
    def forbidden(*args):
        pytest.fail('unlisted target must not connect')
    with pytest.raises(ValueError, match='DATABASE_REQUIRED'):
        require_target(forbidden, 'postgres')
