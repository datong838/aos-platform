"""Saved creator preparation projection; never grants workflow execution."""
from datetime import datetime

import psycopg
from psycopg import IsolationLevel

from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.aip_production_contracts import TaskBriefRevision
from aos_api.db import connect_read_only
from aos_api.ecommerce_creator_internal_workflow import (
    EcommerceCreatorInternalWorkflow, CreatorInternalWorkflowError,
)
from aos_api.ecommerce_creator_internal_workflow_contracts import CreatorInternalWorkflowListResponse
from aos_api.public_contracts import redact_sensitive
from aos_api.tenant_scope import TenantScope

MAX_ROWS = 1000
MAX_ITEM_BYTES = 64 * 1024
MAX_TOTAL_BYTES = 1024 * 1024
_DETAIL_KEYS = frozenset({
    'owner', 'productRef', 'productName', 'candidateSource', 'contentCategory',
    'audienceScale', 'channel', 'budget', 'commission', 'benefits',
    'deliverables', 'evidence', 'schedule',
})
_SPEC_KEYS = frozenset({'purpose', 'title', 'summary', 'details', 'status',
                        'externalEffectsAllowed', 'restoredFromRevision'})


class CreatorWorkflowReadonlyError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _deny(suffix):
    raise CreatorWorkflowReadonlyError('CREATOR_WORKFLOW_READ_' + suffix)


def _integer(value):
    return type(value) is int and value >= 1


def _time(value, cutoff):
    return isinstance(value, datetime) and value.utcoffset() is not None and value <= cutoff


class CreatorInternalWorkflowReadonlyReader:
    def __init__(self, *, connect_factory=None):
        self._connect = connect_factory or connect_read_only

    @staticmethod
    def _rows(conn, scope):
        return conn.execute(
            f'''SELECT h.org_id AS head_org,h.project_id AS head_project,
                h.brief_id AS head_brief,h.task_id AS head_task,h.current_revision,
                h.version,h.updated_at AS head_updated,
                r.org_id,r.project_id,r.brief_id,r.task_id,r.revision,r.brief_type,
                r.content_hash,r.lifecycle,r.created_by,r.created_at,
                t.org_id AS task_org,t.project_id AS task_project,
                t.task_id AS linked_task,t.task_type,
                octet_length(r.spec::text)+octet_length(r.schema_ref::text) AS payload_bytes,
                CASE WHEN octet_length(r.spec::text)+octet_length(r.schema_ref::text)<={MAX_ITEM_BYTES}
                     THEN r.spec ELSE NULL END AS spec,
                CASE WHEN octet_length(r.spec::text)+octet_length(r.schema_ref::text)<={MAX_ITEM_BYTES}
                     THEN r.schema_ref ELSE NULL END AS schema_ref
                FROM aip_task_brief_head h
                LEFT JOIN aip_task_brief_revision r
                  ON r.org_id=h.org_id AND r.project_id=h.project_id
                 AND r.brief_id=h.brief_id AND r.revision=h.current_revision
                LEFT JOIN aip_task t
                  ON t.org_id=h.org_id AND t.project_id=h.project_id AND t.task_id=h.task_id
                WHERE h.org_id=%s AND h.project_id=%s
                  AND (r.brief_type=%s OR r.brief_id IS NULL)
                ORDER BY r.created_at DESC,h.brief_id LIMIT %s''',
            (*scope.key, 'creator_internal_workflow', MAX_ROWS + 1),
        ).fetchall()

    @staticmethod
    def _draft(row, scope, cutoff):
        for org, project in [('head_org', 'head_project'), ('org_id', 'project_id'),
                             ('task_org', 'task_project')]:
            if (row[org], row[project]) != scope.key:
                _deny('AUTHORITY_DRIFT')
        if (row['head_brief'] != row['brief_id']
                or row['head_task'] != row['task_id']
                or row['linked_task'] != row['task_id']
                or row['task_type'] != 'ecommerce.workshop.creator_internal_task'
                or not all(_integer(row[k]) for k in ['revision', 'current_revision', 'version'])
                or row['current_revision'] != row['revision'] or row['version'] < row['revision']
                or not _time(row['created_at'], cutoff) or not _time(row['head_updated'], cutoff)
                or row['created_at'] > row['head_updated']):
            _deny('AUTHORITY_DRIFT')
        spec, schema = row['spec'], row['schema_ref']
        if type(spec) is not dict or type(schema) is not dict:
            _deny('AUTHORITY_DRIFT')
        if ResourceRef.model_validate(schema) != EcommerceCreatorInternalWorkflow._schema_ref():
            _deny('AUTHORITY_DRIFT')
        if row['content_hash'] != canonical_hash({
                'briefType': row['brief_type'], 'schemaRef': schema, 'spec': spec}):
            _deny('AUTHORITY_DRIFT')
        value = TaskBriefRevision(
            tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
            brief_id=row['brief_id'], task_id=row['task_id'], revision=row['revision'],
            version=row['version'], brief_type=row['brief_type'], schema_ref=schema,
            spec=spec, content_hash=row['content_hash'], lifecycle=row['lifecycle'],
            created_by=row['created_by'], created_at=row['created_at'],
        )
        EcommerceCreatorInternalWorkflow._require_creator_brief(value)
        if set(spec) - _SPEC_KEYS:
            _deny('CONTENT_UNSUPPORTED')
        if not 2 <= len(spec['title']) <= 160 or not 2 <= len(spec['summary']) <= 2000:
            _deny('CONTENT_UNSUPPORTED')
        restore = spec.get('restoredFromRevision')
        if 'restoredFromRevision' in spec and (not _integer(restore) or restore >= row['revision']):
            _deny('AUTHORITY_DRIFT')
        details = spec.get('details', {})
        if (set(details) - _DETAIL_KEYS
                or any(type(v) is not str or len(v) > 2000 for v in details.values())):
            _deny('CONTENT_UNSUPPORTED')
        visible = {'title': spec['title'], 'summary': spec['summary'], 'details': details}
        if redact_sensitive(visible) != visible:
            _deny('PRIVACY_UNAVAILABLE')
        return EcommerceCreatorInternalWorkflow._draft(value)

    def list(self, scope: TenantScope) -> CreatorInternalWorkflowListResponse:
        try:
            with self._connect(scope) as conn:
                if (conn.read_only is not True or conn.autocommit is not False
                        or conn.isolation_level != IsolationLevel.REPEATABLE_READ):
                    _deny('UNAVAILABLE')
                cutoff = conn.execute('SELECT transaction_timestamp() AS cutoff').fetchone()['cutoff']
                if not isinstance(cutoff, datetime) or cutoff.utcoffset() is None:
                    _deny('AUTHORITY_DRIFT')
                rows = self._rows(conn, scope)
                if len(rows) > MAX_ROWS:
                    _deny('LIMIT_EXCEEDED')
                total, items, seen = 0, [], set()
                for row in rows:
                    size = row['payload_bytes']
                    if type(size) is not int or size < 1:
                        _deny('AUTHORITY_DRIFT')
                    total += size
                    if size > MAX_ITEM_BYTES or total > MAX_TOTAL_BYTES:
                        _deny('LIMIT_EXCEEDED')
                    draft = self._draft(row, scope, cutoff)
                    if draft.purpose not in seen:
                        seen.add(draft.purpose)
                        items.append(draft)
                result = CreatorInternalWorkflowListResponse(
                    tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
                    items=items, count=len(items),
                )
                if len(result.model_dump_json(by_alias=True).encode()) > MAX_TOTAL_BYTES:
                    _deny('LIMIT_EXCEEDED')
                return result
        except CreatorWorkflowReadonlyError:
            raise
        except psycopg.Error:
            _deny('UNAVAILABLE')
        except (ValueError, KeyError, TypeError, AttributeError, CreatorInternalWorkflowError):
            _deny('AUTHORITY_DRIFT')
