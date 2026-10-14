"""Synthetic authority rows are not genuine customer/human approvals."""
import copy
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from psycopg import IsolationLevel

from aos_api.aip_production_contract_store import canonical_hash
from aos_api.ecommerce_creator_internal_workflow import EcommerceCreatorInternalWorkflow
from aos_api.ecommerce_creator_internal_workflow_readonly import (
    CreatorInternalWorkflowReadonlyReader, CreatorWorkflowReadonlyError,
    MAX_ROWS, MAX_ITEM_BYTES, MAX_TOTAL_BYTES,
)
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('org-org', 'dev-project')
NOW = datetime(2026, 10, 14, tzinfo=timezone.utc)


def row(*, purpose='outreach_batch', brief='brief-fixture', revision=1, version=1):
    spec = dict(purpose=purpose, title='内部准备', summary='整理内部合作条件',
                status='draft', details={'channel': '站内邀约'}, externalEffectsAllowed=False)
    schema = EcommerceCreatorInternalWorkflow._schema_ref().model_dump(mode='json', by_alias=True)
    value = dict(head_org=SCOPE.org_id, head_project=SCOPE.project_id, head_brief=brief,
                 head_task='creator-task-fixture', current_revision=revision, version=version,
                 head_updated=NOW, org_id=SCOPE.org_id, project_id=SCOPE.project_id,
                 brief_id=brief, task_id='creator-task-fixture', revision=revision,
                 brief_type='creator_internal_workflow', lifecycle='draft', created_by='fixture',
                 created_at=NOW, task_org=SCOPE.org_id, task_project=SCOPE.project_id,
                 linked_task='creator-task-fixture', task_type='ecommerce.workshop.creator_internal_task',
                 spec=spec, schema_ref=schema)
    return reseal(value)


def reseal(value):
    value['content_hash'] = canonical_hash({
        'briefType': value['brief_type'], 'schemaRef': value['schema_ref'], 'spec': value['spec']})
    value['payload_bytes'] = len(json.dumps(value['spec'], ensure_ascii=False).encode()) + len(json.dumps(value['schema_ref']).encode())
    return value


def snapshot(rows=(), *, readonly=True, isolation=IsolationLevel.REPEATABLE_READ, cutoff=NOW, fail=False, auto=False):
    calls, connections = [], []
    class Result:
        def __init__(self, data): self.data = data
        def fetchone(self): return self.data[0]
        def fetchall(self): return self.data
    class Connection:
        read_only = readonly
        autocommit = auto
        isolation_level = isolation
        def execute(self, sql, params=()):
            calls.append((sql, params))
            assert sql.startswith('SELECT ')
            if fail: raise psycopg.OperationalError('fixture connection failure')
            if 'transaction_timestamp' in sql: return Result([{'cutoff': cutoff}])
            assert 'LEFT JOIN aip_task_brief_revision' in sql and 'LEFT JOIN aip_task t' in sql
            assert 'r.brief_type=%s OR r.brief_id IS NULL' in sql
            assert 'CASE WHEN octet_length' in sql and 'LIMIT %s' in sql
            assert params == (*SCOPE.key, 'creator_internal_workflow', MAX_ROWS + 1)
            return Result(rows)
        def commit(self): pytest.fail('reader cannot mutate')
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        connections.append(scope)
        yield Connection()
    return CreatorInternalWorkflowReadonlyReader(connect_factory=connect), calls, connections


def denied(rows, code, **options):
    reader, _, _ = snapshot(rows, **options)
    with pytest.raises(CreatorWorkflowReadonlyError) as error:
        reader.list(SCOPE)
    assert error.value.code == 'CREATOR_WORKFLOW_READ_' + code
    assert str(error.value) == error.value.code


def test_empty_is_true_one_readonly_snapshot():
    reader, calls, connections = snapshot()
    result = reader.list(SCOPE)
    assert result.items == [] and result.count == 0
    assert len(calls) == 2 and connections == [SCOPE]
    assert result.tenant.org_id == SCOPE.org_id


def test_all_six_purposes_and_latest_per_purpose_preserve_typed_exact_ref():
    purposes = ['candidate_import', 'outreach_batch', 'outreach_message',
                'collaboration', 'delivery_check', 'relationship_plan']
    rows = [row(purpose=p, brief='brief-' + p) for p in purposes]
    rows.append(row(brief='brief-older'))
    reader, _, _ = snapshot(rows)
    result = reader.list(SCOPE)
    assert result.count == 6
    assert [v.purpose for v in result.items] == purposes
    assert result.items[1].resource_id == 'brief-outreach_batch'
    assert result.items[1].content_hash == rows[1]['content_hash']


@pytest.mark.parametrize('field,value', [
    ('head_org', 'other'), ('head_project', 'other'), ('org_id', 'other'),
    ('project_id', 'other'), ('task_org', 'other'), ('task_project', 'other'),
    ('brief_id', 'other'), ('head_brief', 'other'), ('head_task', 'other'), ('task_id', 'other'), ('linked_task', None),
    ('task_type', 'other'), ('current_revision', 2), ('revision', True),
    ('version', 0), ('version', True), ('created_at', NOW + timedelta(seconds=1)),
    ('head_updated', NOW - timedelta(seconds=1)), ('created_at', NOW.replace(tzinfo=None)),
    ('lifecycle', 'unknown'), ('content_hash', 'a' * 64), ('spec', None),
])
def test_authority_drift_fails_before_any_success(field, value):
    item = row(); item[field] = value
    denied([item], 'AUTHORITY_DRIFT')


def test_missing_current_revision_is_not_empty_success():
    item = row(); item.update(brief_id=None, payload_bytes=None, spec=None)
    denied([item], 'AUTHORITY_DRIFT')


def test_bad_older_duplicate_is_not_hidden_by_latest_purpose():
    broken = row(brief='older'); broken['content_hash'] = 'b' * 64
    denied([row(), broken], 'AUTHORITY_DRIFT')


@pytest.mark.parametrize('change', [
    {'schema_ref': {'resourceType': 'Other', 'resourceId': 'other', 'revision': '1'}},
    {'spec': {'externalEffectsAllowed': True}}, {'spec': {'purpose': 'unknown'}},
    {'spec': {'status': 'unknown'}}, {'spec': {'restoredFromRevision': 1}},
])
def test_rehashed_bad_contract_is_still_rejected(change):
    item = row()
    for key, value in change.items():
        if key == 'spec': item['spec'].update(value)
        else: item[key] = value
    reseal(item)
    denied([item], 'AUTHORITY_DRIFT')


@pytest.mark.parametrize('details', [{'password': 'fixture'}, {'channel': {'nested': 'fixture'}},
    {'owner': None}, {'channel': 'x' * 2001}])
def test_unknown_or_nested_details_are_explicit_unavailable(details):
    item = row(); item['spec']['details'] = details; reseal(item)
    denied([item], 'CONTENT_UNSUPPORTED')


@pytest.mark.parametrize('text', ['Bearer fixture-token-123', 'fixture@example.test', '13800138000', 'sk-fixture123'])
def test_known_sensitive_text_never_reaches_response(text):
    item = row(); item['spec']['details']['channel'] = text; reseal(item)
    denied([item], 'PRIVACY_UNAVAILABLE')


@pytest.mark.parametrize('options,code', [({'readonly': False}, 'UNAVAILABLE'), ({'auto': True}, 'UNAVAILABLE'),
    ({'isolation': IsolationLevel.READ_COMMITTED}, 'UNAVAILABLE'),
    ({'fail': True}, 'UNAVAILABLE'), ({'cutoff': NOW.replace(tzinfo=None)}, 'AUTHORITY_DRIFT')])
def test_connection_or_clock_unknown_is_not_empty(options, code):
    denied([], code, **options)


def test_row_bound_checks_all_rows_before_purpose_reduction():
    reader, _, _ = snapshot([row()] * MAX_ROWS)
    assert reader.list(SCOPE).count == 1
    denied([row()] * (MAX_ROWS + 1), 'LIMIT_EXCEEDED')


def test_single_oversize_sql_null_guard_and_total_size_limit():
    item = row(); item.update(payload_bytes=MAX_ITEM_BYTES + 1, spec=None, schema_ref=None)
    denied([item], 'LIMIT_EXCEEDED')
    item = row(); item['payload_bytes'] = MAX_ITEM_BYTES
    denied([item] * (MAX_TOTAL_BYTES // MAX_ITEM_BYTES + 1), 'LIMIT_EXCEEDED')


def test_valid_restore_and_freeze_version_are_readable_saved_facts_only():
    item = row(revision=3, version=4); item['spec'].update(status='approved', restoredFromRevision=1)
    item['lifecycle'] = 'frozen'; reseal(item)
    reader, _, _ = snapshot([item]); result = reader.list(SCOPE)
    assert result.items[0].revision == 3 and result.items[0].version == 4
    assert result.items[0].status == 'approved'
    assert 'allowedCommands' not in result.model_dump(by_alias=True)
