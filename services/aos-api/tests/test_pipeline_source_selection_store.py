"""Selection record integrity only; no database grant or business approval."""
from copy import deepcopy
from uuid import UUID

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.pipeline_source_selection_store import build_selection_payload, decode_selection_row, selection_request_hash
from test_pipeline_runtime_control_contracts import payload


def selection_row(revision=1):
    body = payload()
    body.pop('sourceSelectionRef')
    draft = PipelineSourceSelectionDraft.model_validate(body)
    spec = MappingReadSpec('ns_site', 'Shop', 'site_id', ('site_id', 'site_name'), (('site_id', 1),))
    identity = '55555555-5555-4555-8555-555555555555'
    previous_hash = None if revision == 1 else 'sha256:'+'f'*64
    document = build_selection_payload(draft=draft, read_spec=spec, selection_id=identity,
        revision=revision, previous_hash=previous_hash, actor='test-actor')
    return dict(org_id=draft.org_id, project_id=draft.project_id,
        installation_id=UUID(draft.installation_ref.installation_id), generation=UUID(draft.generation),
        pipeline_id=draft.pipeline_id, source_id=draft.source_id,
        source_configuration_revision=UUID(draft.source_configuration_ref.resource_id.removeprefix('source-config-')),
        selection_id=UUID(identity), revision=revision, previous_revision=None if revision==1 else revision-1,
        previous_hash=previous_hash, actor='test-actor', payload=document,
        content_hash=canonical_sha256(document),
        request_hash=selection_request_hash(draft=draft, actor='test-actor', selection_id=identity,
            revision=revision, previous_hash=previous_hash))


@pytest.mark.parametrize('revision', [1, 2])
def test_record_roundtrip_detaches_mutable_database_payload(revision):
    row = selection_row(revision)
    record = decode_selection_row(row)
    assert record.ref.resource_type == 'SourceSelectionRevision'
    assert record.ref.revision == revision
    assert record.read_spec.columns == ('site_id', 'site_name')
    assert record.draft.state == 'prepared'
    row['payload']['readSpec']['columns'].append('site_tel')
    assert record.read_spec.columns == ('site_id', 'site_name')


@pytest.mark.parametrize('field,value', [
    ('org_id','another-org'), ('generation',UUID('66666666-6666-4666-8666-666666666666')),
    ('revision',2), ('actor','another-actor'), ('content_hash','sha256:'+'0'*64),
    ('request_hash','sha256:'+'0'*64), ('previous_revision',1), ('source_id','another-source'),
])
def test_database_column_drift_is_rejected(field, value):
    row = selection_row()
    row[field] = value
    with pytest.raises(ValueError):
        decode_selection_row(row)


@pytest.mark.parametrize('case', ['extra', 'bad_budget', 'bad_column', 'bad_filter', 'list_spec'])
def test_rehashed_malformed_payload_is_rejected(case):
    row = deepcopy(selection_row())
    if case == 'extra': row['payload']['executionGranted'] = True
    elif case == 'bad_budget': row['payload']['draft']['rowLimit'] = True
    elif case == 'bad_column': row['payload']['readSpec']['columns'] = ['site_id', '*']
    elif case == 'bad_filter': row['payload']['readSpec']['filters'] = [['site_id', True]]
    else: row['payload']['readSpec'] = []
    row['content_hash'] = canonical_sha256(row['payload'])
    with pytest.raises(ValueError):
        decode_selection_row(row)


def test_first_request_hash_does_not_depend_on_new_server_identity():
    row = selection_row()
    record = decode_selection_row(row)
    other = selection_request_hash(draft=record.draft, actor=record.actor,
        selection_id='66666666-6666-4666-8666-666666666666', revision=1, previous_hash=None)
    assert other == row['request_hash']


def test_boolean_previous_revision_is_not_a_database_revision():
    row = selection_row(2)
    row['previous_revision'] = True
    with pytest.raises(ValueError):
        decode_selection_row(row)


def test_boolean_header_cannot_equal_integer_revision():
    row=selection_row()
    row['payload']['revision']=True
    with pytest.raises(ValueError):decode_selection_row(row)
