"""Bounded selected read primitive. The execution Owner retains authorization."""
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic

from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef, PipelineSourceSelectionDraft
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
from aos_api.source_connection_config import SOURCE_CONNECTION_FIELDS, normalize_source_connection_config
from aos_api.tenant_scope import TenantScope


def _clock():
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SelectedSnapshotResult:
    rows: list[dict]
    source_configuration_ref: PipelineExactRef
    started_at: datetime
    completed_at: datetime


def read_selected_snapshot(*, transaction, scope, draft, read_spec):
    """One private source SELECT, no retries, persistence or execution grant.

    A limit-sized result is deliberately rejected even when it might be complete.
    The shorter requested deadline controls result acceptance; the existing driver
    retains its 30-second socket timeout and is not forcibly interrupted here.
    """
    try:
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope or type(read_spec) is not MappingReadSpec:
            raise TypeError('exact selected read dependencies required')
        draft = PipelineSourceSelectionDraft.model_validate(draft)
        spec = MappingReadSpec(read_spec.table,read_spec.object_type,read_spec.primary_key,
                               read_spec.columns,read_spec.filters)
        started_at, started_tick = _clock(), monotonic()
        if scope.key != (draft.org_id,draft.project_id) or not draft.not_before <= started_at < draft.expires_at:
            raise ValueError('selected read scope or window differs')
        row = transaction.execute('''SELECT id FROM public.meta_source
            WHERE org_id=%s AND project_id=%s AND id=%s FOR SHARE''',(*scope.key,draft.source_id)).fetchone()
        if row is None:
            raise ValueError('selected source unavailable')
        loaded = SourceConfigurationRevisionStore(transaction,scope).read_connection_input(draft.source_id)
        if (loaded is None or loaded.revision.source_id != draft.source_id
                or loaded.revision.source_type != 'jdbc-mysql-ssh'
                or loaded.revision.status not in {'registered','active','ready'}
                or loaded.props.get('runtimeMode') != 'direct'
                or loaded.revision.ref.model_dump(mode='json',by_alias=True) != draft.source_configuration_ref.model_dump(mode='json',by_alias=True)):
            raise ValueError('selected source revision differs')
        config = normalize_source_connection_config('jdbc-mysql-ssh',
            {key:value for key,value in loaded.props.items() if key in SOURCE_CONNECTION_FIELDS})
        with JdbcConnectorRuntime(config,reuse_cache=False) as runtime:
            rows = runtime.read_rows(spec.table,columns=spec.columns,where_equals=dict(spec.filters),limit=draft.row_limit)
        completed_at, elapsed = _clock(), monotonic()-started_tick
        if (elapsed < 0 or elapsed > draft.timeout_seconds or completed_at < started_at
                or not draft.not_before <= completed_at < draft.expires_at):
            raise ValueError('selected read deadline elapsed')
        if type(rows) is not list or len(rows) >= draft.row_limit:
            raise ValueError('selected snapshot may be truncated')
        identities = set()
        for row in rows:
            if type(row) is not dict or set(row) != set(spec.columns):
                raise ValueError('selected snapshot columns differ')
            identity = row[spec.primary_key]
            if type(identity) not in (str,int) or identity == '' or identity in identities:
                raise ValueError('selected snapshot primary key differs')
            identities.add(identity)
            if any(column in row and row[column] != value for column,value in spec.filters):
                raise ValueError('selected snapshot scope differs')
        return SelectedSnapshotResult(rows,draft.source_configuration_ref,started_at,completed_at)
    except Exception:
        # Neither connector errors nor rejected source values may escape.
        raise ValueError('SELECTED_SNAPSHOT_READ_FAILED') from None
