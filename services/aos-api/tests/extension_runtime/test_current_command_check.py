from contextlib import contextmanager
from unittest.mock import MagicMock,patch

import pytest

from aos_api.asset_registry.installation_store import PostgresInstallationStore


@pytest.mark.parametrize('result',[True,False,None,1,'allowed'])
def test_current_check_precedes_cached_receipt(result):
    conn=MagicMock()
    conn.execute.return_value.fetchone.return_value={
        'subject':'actor','request_hash':'sha256:'+'a'*64,'status_code':202,
        'response_json':{'operationId':'test-operation'},'response_etag':'"1"'}
    @contextmanager
    def connect():yield conn
    check=MagicMock(return_value=result);handler=MagicMock()
    with patch('aos_api.asset_registry.installation_store.apply_asset_transaction_scope'):
        args=dict(org_id='org-org',project_id='dev-project',operation='test-current-replay',
                  idempotency_key='request',subject='actor',request_hash='sha256:'+'a'*64,
                  handler=handler,current_check=check)
        if result is True:
            receipt=PostgresInstallationStore(connect).execute_idempotent(**args)
            assert receipt.replayed
        else:
            with pytest.raises(PermissionError):PostgresInstallationStore(connect).execute_idempotent(**args)
        check.assert_called_once_with(conn)
        handler.assert_not_called()
        # Advisory lock is allowed, receipt SELECT must wait for permission.
        if result is not True:assert conn.execute.call_count==1


def test_async_current_check_cannot_return_cached_receipt():
    conn=MagicMock()
    @contextmanager
    def connect():yield conn
    async def check(conn):return True
    with patch('aos_api.asset_registry.installation_store.apply_asset_transaction_scope'):
        with pytest.raises(ValueError):PostgresInstallationStore(connect).execute_idempotent(
            org_id='org-org',project_id='dev-project',operation='test',idempotency_key='request',
            subject='actor',request_hash='sha256:'+'a'*64,handler=MagicMock(),current_check=check)
