"""Current configuration-bound group read primitive, never an execution grant."""
from dataclasses import dataclass
from datetime import datetime,timezone
from time import monotonic

from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_owner import CurrentSnapshotGroup,PipelineSnapshotGroupOwner
from aos_api.pipeline_snapshot_group_read import SnapshotGroupResult,read_snapshot_group
from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
from aos_api.source_connection_config import SOURCE_CONNECTION_FIELDS,normalize_source_connection_config
from aos_api.tenant_scope import TenantScope


def _clock():return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SelectedSnapshotGroupResult:
    rows_by_table: dict[str,list[dict]]
    source_configuration_ref: PipelineExactRef
    started_at: datetime
    completed_at: datetime


def read_selected_snapshot_group(*,transaction,scope,group):
    """Trusted Host calls inside current group Owner, after confirmed claim commit.

    The supplied group is data, not permission. This primitive neither claims nor
    persists anything. Owner must retain and revalidate all current controls.
    Connection establishment and cleanup count toward the acceptance deadline;
    socket operations retain the existing driver's bounded timeout.
    """
    try:
        if (type(transaction) is not HostTransaction or type(scope) is not TenantScope
                or type(group) is not CurrentSnapshotGroup or type(group.members) is not tuple
                or not 1<=len(group.members)<=12):
            raise ValueError('exact bounded group required')
        if PipelineSnapshotGroupOwner._validate(transaction,scope,group.members)!=group:
            raise ValueError('group bounds differ from original members')
        started_at,started_tick=_clock(),monotonic()
        if not group.not_before<=started_at<group.expires_at:
            raise ValueError('group window expired')
        draft=group.members[0][1]
        row=transaction.execute('''SELECT id FROM public.meta_source
            WHERE org_id=%s AND project_id=%s AND id=%s FOR SHARE''',(*scope.key,draft.source_id)).fetchone()
        if row is None:raise ValueError('source unavailable')
        loaded=SourceConfigurationRevisionStore(transaction,scope).read_connection_input(draft.source_id)
        if (loaded is None or loaded.revision.source_id!=draft.source_id
                or loaded.revision.source_type!='jdbc-mysql-ssh'
                or loaded.revision.status not in {'registered','active','ready'}
                or loaded.props.get('runtimeMode')!='direct'
                or loaded.revision.ref.model_dump(mode='json',by_alias=True)!=draft.source_configuration_ref.model_dump(mode='json',by_alias=True)):
            raise ValueError('current source configuration differs')
        config=normalize_source_connection_config('jdbc-mysql-ssh',
            {key:value for key,value in loaded.props.items() if key in SOURCE_CONNECTION_FIELDS})
        with JdbcConnectorRuntime(config,reuse_cache=False) as runtime:
            result=read_snapshot_group(runtime,tuple(mapping.read_spec for _,_,mapping in group.members),
                row_limit=group.row_limit,timeout_seconds=group.timeout_seconds)
        completed_at,elapsed=_clock(),monotonic()-started_tick
        if (type(result) is not SnapshotGroupResult or elapsed<0 or elapsed>group.timeout_seconds
                or not started_at<=result.started_at<=result.completed_at<=completed_at
                or not group.not_before<=completed_at<group.expires_at):
            raise ValueError('group read deadline or source interval differs')
        return SelectedSnapshotGroupResult(result.rows_by_table,draft.source_configuration_ref,result.started_at,result.completed_at)
    except Exception:
        raise ValueError('SELECTED_SNAPSHOT_GROUP_READ_FAILED') from None
