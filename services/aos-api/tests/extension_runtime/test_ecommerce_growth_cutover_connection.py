from contextlib import contextmanager

import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.pq import TransactionStatus

from test_ecommerce_growth_registration_connection import credentials
from test_dispatch_first_registration_atomic_pg import registered_db, receipt_db, database, pytestmark as pg_required
from aos_api.ecommerce_growth_registration_connection import registration_connection
from aos_api.tenant_scope import TenantScope


def factory():
    from aos_api.ecommerce_growth_cutover_connection import scoped_cutover_connection
    return scoped_cutover_connection


def test_lazy_and_untrusted_scope_never_opens_connection():
    @contextmanager
    def forbidden():
        pytest.fail('unexpected connection')
        yield
    connect = factory()(forbidden)
    with pytest.raises(TypeError):
        with connect({'org_id': 'org-a', 'project_id': 'project-a'}):
            pass
    with pytest.raises(TypeError):
        factory()(None)


@pg_required
@pytest.mark.parametrize('finish', ['read', 'commit', 'raise'])
def test_actual_scoped_transaction(registered_db, tmp_path, monkeypatch, finish):
    case = registered_db
    case.db.owner.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(case.login)))
    path = credentials(tmp_path, dsn=make_conninfo(**{**case.db.pg, 'user': case.login}), role=case.login)
    monkeypatch.setenv('AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE', str(path))
    captured = []
    @contextmanager
    def identity():
        with registration_connection() as conn:
            previous = conn.isolation_level
            try:
                yield conn
            finally:
                captured.append((conn.info.transaction_status, conn.isolation_level == previous))
    connect = factory()(identity)
    def run():
        with connect(TenantScope('org-a', 'project-a')) as conn:
            row = conn.execute("SELECT current_user AS role,current_setting('transaction_isolation') AS isolation,current_setting('aos.org_id') AS org,current_setting('aos.project_id') AS project,current_setting('search_path') AS path").fetchone()
            assert row == dict(role='aos_extension_maintainer', isolation='serializable', org='org-a', project='project-a', path='pg_catalog, public')
            if finish == 'commit': conn.commit()
            if finish == 'raise': raise ValueError('caller failed')
    if finish == 'raise':
        with pytest.raises(ValueError, match='caller failed'): run()
    else: run()
    assert captured == [(TransactionStatus.IDLE, True)]


def test_busy_connection_is_rejected_before_changing_it():
    from types import SimpleNamespace
    @contextmanager
    def busy():
        yield SimpleNamespace(info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS))
    with pytest.raises(ValueError, match='idle'):
        with factory()(busy)(TenantScope('org-a', 'project-a')):
            pytest.fail('busy connection accepted')
