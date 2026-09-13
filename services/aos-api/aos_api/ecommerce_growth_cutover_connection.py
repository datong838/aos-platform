"""Scoped cutover transactions over the existing protected registration identity."""
from contextlib import contextmanager

from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus

from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverStore
from aos_api.tenant_scope import TenantScope


def scoped_cutover_connection(identity_connect):
    """Build lazily; the control plane supplies its verified identity connector."""
    if not callable(identity_connect):
        raise TypeError('protected identity connector required')

    @contextmanager
    def connect(scope):
        if type(scope) is not TenantScope:
            raise TypeError('trusted TenantScope required')
        with identity_connect() as conn:
            if conn.info.transaction_status != TransactionStatus.IDLE:
                raise ValueError('cutover requires an independent idle connection')
            previous = conn.isolation_level
            conn.isolation_level = IsolationLevel.SERIALIZABLE
            try:
                conn.execute('SET LOCAL ROLE aos_extension_maintainer')
                conn.execute('SET LOCAL search_path TO pg_catalog, public')
                conn.execute("SELECT set_config('aos.org_id',%s,true), set_config('aos.project_id',%s,true)", scope.key)
                EcommerceGrowthCutoverStore._require_maintainer(conn)
                yield conn
            finally:
                # The Store explicitly commits successful phases; incomplete phases
                # and read-only replays must never be implicitly committed here.
                if conn.info.transaction_status != TransactionStatus.IDLE:
                    conn.rollback()
                conn.isolation_level = previous

    return connect
