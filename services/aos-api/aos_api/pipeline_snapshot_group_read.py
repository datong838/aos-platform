"""One bounded private InnoDB snapshot group, never an authorization or Receipt."""
from dataclasses import dataclass
from datetime import datetime,timezone
from time import monotonic

from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime
from aos_api.pipeline_source_selection import MappingReadSpec


@dataclass(frozen=True)
class SnapshotGroupResult:
    rows_by_table: dict[str,list[dict]]
    started_at: datetime
    completed_at: datetime


def read_snapshot_group(runtime,specs,*,row_limit,timeout_seconds):
    """Caller owns current scope/configuration authority and private runtime lifecycle.

    Never reuses a cached connection or retries a query. The result is a current
    consistent read, not historical source-modification evidence. All selected
    tables must use InnoDB; source limits are completeness guards, not pagination.
    """
    try:
        if (type(runtime) is not JdbcConnectorRuntime or runtime._reuse_cache is not False
                or runtime._conn is None or runtime._private_cleanup_pending
                or type(specs) is not tuple or not 1<=len(specs)<=12
                or type(row_limit) is not int or not 1<=row_limit<=1000
                or type(timeout_seconds) is not int or not 1<=timeout_seconds<=120):
            raise ValueError('bounded private snapshot group required')
        if any(type(spec) is not MappingReadSpec for spec in specs):raise ValueError('exact read specs required')
        for spec in specs:
            MappingReadSpec(spec.table,spec.object_type,spec.primary_key,spec.columns,spec.filters)
            if not set(dict(spec.filters))<=set(spec.columns):raise ValueError('scope fields must be selected')
        tables=tuple(spec.table for spec in specs)
        if len({name.casefold() for name in tables})!=len(tables):raise ValueError('unique source tables required')
        started_at=datetime.now(timezone.utc);started=monotonic()
        def check_time():
            elapsed=monotonic()-started
            if elapsed<0 or elapsed>timeout_seconds:raise ValueError('snapshot deadline elapsed')
        rows_by_table={}
        with runtime._standalone_lease:
            check_time()
            with runtime._conn.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            with runtime._read_only_transaction():
                with runtime._conn.cursor() as cursor:
                    placeholders=','.join('%s' for _ in tables)
                    cursor.execute('SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('+placeholders+')',tables)
                    engines=cursor.fetchall()
                    if (type(engines) not in (list,tuple) or len(engines)!=len(tables)
                            or {row['TABLE_NAME'] for row in engines}!=set(tables)
                            or any(row['ENGINE']!='InnoDB' for row in engines)):
                        raise ValueError('all snapshot tables must be InnoDB')
                    for spec in specs:
                        check_time()
                        selected=', '.join(f'`{column}`' for column in spec.columns)
                        filters=' AND '.join(f'`{column}` = %s' for column,_ in spec.filters)
                        query=f'SELECT {selected} FROM `{spec.table}` WHERE {filters} ORDER BY `{spec.primary_key}` LIMIT %s'
                        cursor.execute(query,tuple(value for _,value in spec.filters)+(row_limit,))
                        rows=list(cursor.fetchall());check_time()
                        if len(rows)>=row_limit:raise ValueError('snapshot may be truncated')
                        identities=set()
                        for row in rows:
                            if type(row) is not dict or set(row)!=set(spec.columns):raise ValueError('source columns differ')
                            identity=row[spec.primary_key]
                            if type(identity) not in (int,str) or not str(identity).strip() or str(identity) in identities:
                                raise ValueError('source identity differs')
                            identities.add(str(identity))
                            if any(type(row[name]) is bool or row[name]!=value for name,value in spec.filters):
                                raise ValueError('source scope differs')
                        rows_by_table[spec.table]=rows
        check_time()
        completed_at=datetime.now(timezone.utc)
        if completed_at<started_at:raise ValueError('source clock moved backwards')
        return SnapshotGroupResult(rows_by_table,started_at,completed_at)
    except Exception:
        raise ValueError('SNAPSHOT_GROUP_READ_FAILED') from None
