"""A bounded, private connection probe against a saved configuration version."""
from time import monotonic
from typing import Any

from aos_api import data_os_store
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime
from aos_api.source_connection_config import SOURCE_CONNECTION_FIELDS, normalize_source_connection_config
from aos_api.tenant_scope import TenantScope


def probe_source_tables(scope: TenantScope, source_id: str, expected_revision: str) -> dict[str, Any]:
    scope = data_os_store._require_scope(scope)
    started = monotonic()
    try:
        with data_os_store.connect(scope) as conn:
            row = conn.execute(
                """SELECT type,status,configuration_revision,props FROM meta_source
                   WHERE org_id=%s AND project_id=%s AND id=%s FOR SHARE""",
                (*scope.key, source_id),
            ).fetchone()
            if row is None:
                raise data_os_store.ApiError(code='SOURCE_NOT_FOUND',message='数据源不存在',status_code=404)
            if str(row['configuration_revision']) != expected_revision:
                raise data_os_store.ApiError(code='SOURCE_CONFIGURATION_CONFLICT',message='配置已变化，请重新读取后测试',status_code=409)
            if row['type'] != 'jdbc-mysql-ssh' or row['status'] not in {'registered','active','ready'}:
                raise data_os_store.ApiError(code='SOURCE_PROBE_NOT_ALLOWED',message='当前数据源不可测试',status_code=409)
            props = row['props']
            if type(props) is not dict:
                raise ValueError('invalid stored configuration')
            config = normalize_source_connection_config(row['type'], {
                key:value for key,value in props.items() if key in SOURCE_CONNECTION_FIELDS
            })
            with JdbcConnectorRuntime(config, reuse_cache=False) as runtime:
                discovery = runtime.list_configured_tables()
        return dict(ok=True,sourceId=source_id,configurationRevision=expected_revision,
                    latencyMs=round((monotonic()-started)*1000),**discovery)
    except data_os_store.ApiError:
        raise
    except Exception:
        raise data_os_store.ApiError(code='SOURCE_PROBE_FAILED',
            message='连接测试未成功，请检查配置或稍后重试',status_code=503) from None
