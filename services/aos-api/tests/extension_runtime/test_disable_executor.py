from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

from aos_api.extension_runtime.disable_executor import RuntimeDisableExecutor


@pytest.mark.parametrize('status',[TransactionStatus.INTRANS,TransactionStatus.INERROR,TransactionStatus.ACTIVE,TransactionStatus.UNKNOWN])
def test_disable_rejects_non_idle_connection_without_touching_it(status):
    @contextmanager
    def connect():
        yield SimpleNamespace(info=SimpleNamespace(transaction_status=status))
    executor=RuntimeDisableExecutor(connect=connect,installation_store=None,
        check_current_permission=lambda **k:True,check_drained=lambda *a,**k:True)
    with pytest.raises(ValueError,match='independent idle'):
        executor.execute(org_id='org-org',project_id='dev-project',
            operation_id='00000000-0000-0000-0000-000000000001',expected_revision=1)
