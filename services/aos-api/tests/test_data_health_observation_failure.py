from contextlib import contextmanager
from unittest.mock import MagicMock
import pytest
from aos_api.errors import ApiError
from aos_api.routers import wave_ext
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('failure',[PermissionError('private-details'),ConnectionError('private-details')])
def test_failed_observation_is_not_reported_as_zero(monkeypatch,failure):
    @contextmanager
    def unavailable(scope):
        raise failure
        yield
    monkeypatch.setattr('aos_api.db.connect',unavailable)
    with pytest.raises(ApiError) as caught:
        wave_ext._pg_ot_row_count(TenantScope('org-org','dev-project'),'Order')
    assert caught.value.status_code==503
    assert caught.value.code=='DATA_OBSERVATION_UNAVAILABLE'
    assert 'private-details' not in str(caught.value)


@pytest.mark.parametrize('count',[0,42])
def test_verified_count_preserves_zero_and_tenant_scope(monkeypatch,count):
    conn=MagicMock();conn.execute.return_value.fetchone.return_value={'c':count}
    scope=TenantScope('org-org','dev-project')
    @contextmanager
    def available(actual_scope):
        assert actual_scope==scope
        yield conn
    monkeypatch.setattr('aos_api.db.connect',available)
    assert wave_ext._pg_ot_row_count(scope,'Order')==count
    assert conn.execute.call_args.args[1]==('org-org','dev-project','Order')
