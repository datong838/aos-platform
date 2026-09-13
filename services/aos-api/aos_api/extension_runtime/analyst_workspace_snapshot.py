"""Host-owned canonical snapshot input for the installed analyst projection."""
from copy import deepcopy

from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.extension_runtime.ui_current_principal import read_current_ui_principal
from aos_api.extension_runtime.ui_read_api_database import read_host_ui_principal

_QUERY = '''WITH selected_cases AS (
    SELECT h.org_id,h.project_id,h.case_id,h.updated_at,r.authority_data AS case_authority
    FROM ecommerce_investigation_case_head h
    LEFT JOIN ecommerce_investigation_case_revision r
      ON r.org_id=h.org_id AND r.project_id=h.project_id
      AND r.case_id=h.case_id AND r.revision=h.current_revision
    WHERE h.org_id=%s AND h.project_id=%s
    ORDER BY h.updated_at DESC,h.case_id ASC LIMIT %s
)
SELECT c.case_id,c.case_authority,r.run_id,r.authority_data AS run_authority,s.authority_data AS state_authority
FROM selected_cases c
LEFT JOIN LATERAL (
    SELECT run_id,authority_data,created_at FROM ecommerce_investigation_run
    WHERE org_id=c.org_id AND project_id=c.project_id AND case_id=c.case_id
    ORDER BY created_at DESC,run_id ASC LIMIT %s
) r ON true
LEFT JOIN ecommerce_investigation_run_state_head s
  ON s.org_id=c.org_id AND s.project_id=c.project_id AND s.run_id=r.run_id
ORDER BY c.updated_at DESC,c.case_id ASC,r.created_at DESC,r.run_id ASC'''


def _validate_snapshot_read(conn,case_limit,run_limit):
    _require_transaction(conn)
    if type(case_limit) is not int or not 1 <= case_limit <= 50 or type(run_limit) is not int or not 1 <= run_limit <= 10:
        raise ValueError('bounded workspace page required')
    isolation=conn.execute('SHOW transaction_isolation').fetchone()
    if isolation is None or isolation['transaction_isolation'] not in {'repeatable read','serializable'}:
        raise ValueError('workspace snapshot requires repeatable transaction')


def read_analyst_workspace_snapshot(*,conn,scope:TenantScope,subject:str,
                                    required_markings:tuple[str,...],case_limit=20,run_limit=5):
    _validate_snapshot_read(conn,case_limit,run_limit)
    read_current_ui_principal(conn=conn,scope=scope,subject=subject,required_markings=required_markings)
    return _read_snapshot_rows(conn,scope,case_limit,run_limit)


def read_host_analyst_workspace_snapshot(*,conn,scope:TenantScope,subject:str,
                                         required_markings:tuple[str,...],case_limit=20,run_limit=5):
    _validate_snapshot_read(conn,case_limit,run_limit)
    read_host_ui_principal(conn=conn,scope=scope,subject=subject,required_markings=required_markings)
    return _read_snapshot_rows(conn,scope,case_limit,run_limit)


def _read_snapshot_rows(conn,scope,case_limit,run_limit):
    clock=conn.execute('SELECT clock_timestamp() AS cutoff_at').fetchone()
    if clock is None:
        raise ValueError('workspace snapshot clock unavailable')
    rows=conn.execute(_QUERY,(*scope.key,case_limit+1,run_limit+1)).fetchall()
    groups={}; seen_runs=set(); truncated=False
    for row in rows:
        case_id=row['case_id']
        if case_id not in groups:
            if len(groups)==case_limit:
                truncated=True; continue
            if not isinstance(row['case_authority'],dict) or row['case_authority'].get('caseId') != case_id:
                raise ValueError('workspace Case authority differs')
            groups[case_id]=dict(case=deepcopy(row['case_authority']),runs=[])
        group=groups[case_id]
        if group['case'] != row['case_authority']:
            raise ValueError('workspace Case head differs')
        run_id=row['run_id']
        if run_id is None:
            if row['run_authority'] is not None or row['state_authority'] is not None:
                raise ValueError('workspace Run sources differ')
            continue
        if run_id in seen_runs or not isinstance(row['state_authority'],dict) or not isinstance(row['run_authority'],dict):
            raise ValueError('workspace Run state missing or duplicated')
        if row['state_authority'].get('runId') != run_id or row['run_authority'].get('runId') != run_id:
            raise ValueError('workspace Run source identity differs')
        seen_runs.add(run_id)
        if len(group['runs'])==run_limit:
            truncated=True; continue
        group['runs'].append(dict(authority=deepcopy(row['run_authority']),state=deepcopy(row['state_authority'])))
    return dict(schemaVersion='aos.analyst-workspace-snapshot/v1',tenant=dict(orgId=scope.org_id,projectId=scope.project_id),
                cutoffAt=clock['cutoff_at'].isoformat(),cases=list(groups.values()),truncated=truncated)
