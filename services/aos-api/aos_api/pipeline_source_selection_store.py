"""Strict selection record encoding. No approval, database write or execution."""
from dataclasses import asdict, dataclass
import json
from uuid import UUID

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef, PipelineSourceSelectionDraft
from aos_api.pipeline_source_selection import MappingReadSpec

_SCHEMA = 'aos.pipeline-source-selection-revision/v1'
_METHOD = 'aos.mapping-snapshot-read/v1'


def _identity(selection_id, revision, previous_hash, actor):
    if type(selection_id) is not str or str(UUID(selection_id)) != selection_id:
        raise ValueError('canonical selection identity required')
    if type(revision) is not int or not 1 <= revision < 2**63:
        raise ValueError('positive selection revision required')
    if type(actor) is not str or not 1 <= len(actor) <= 240 or actor != actor.strip() or not actor.isprintable():
        raise ValueError('canonical selection actor required')
    if revision == 1:
        if previous_hash is not None:
            raise ValueError('first selection cannot have a previous hash')
        return None
    return PipelineExactRef(resource_type='SourceSelectionRevision',
        resource_id='source-selection-'+selection_id, revision=revision-1, content_hash=previous_hash)


def selection_request_hash(*, draft, actor, selection_id, revision, previous_hash):
    draft = PipelineSourceSelectionDraft.model_validate(draft)
    previous = _identity(selection_id, revision, previous_hash, actor)
    # A newly generated first identity is not part of the caller's request.
    return canonical_sha256(dict(actor=actor, draft=draft.model_dump(mode='json', by_alias=True),
        previousRef=previous.model_dump(mode='json', by_alias=True) if previous else None))


def build_selection_payload(*, draft, read_spec, selection_id, revision, previous_hash, actor):
    draft = PipelineSourceSelectionDraft.model_validate(draft)
    _identity(selection_id, revision, previous_hash, actor)
    if type(read_spec) is not MappingReadSpec:
        raise ValueError('exact immutable mapping read specification required')
    checked = MappingReadSpec(read_spec.table, read_spec.object_type, read_spec.primary_key,
                              read_spec.columns, read_spec.filters)
    return dict(schemaVersion=_SCHEMA, methodVersion=_METHOD,
        orgId=draft.org_id, projectId=draft.project_id,
        installationId=draft.installation_ref.installation_id, generation=draft.generation,
        pipelineId=draft.pipeline_id, sourceId=draft.source_id,
        sourceConfigurationRevision=draft.source_configuration_ref.resource_id.removeprefix('source-config-'),
        selectionId=selection_id, revision=revision, actor=actor, previousHash=previous_hash,
        draft=draft.model_dump(mode='json', by_alias=True),
        readSpec=json.loads(json.dumps(asdict(checked), allow_nan=False)))


@dataclass(frozen=True)
class SourceSelectionRecord:
    ref: PipelineExactRef
    draft: PipelineSourceSelectionDraft
    read_spec: MappingReadSpec
    actor: str
    previous_hash: str | None


def decode_selection_row(row) -> SourceSelectionRecord:
    """Decode audit data, including expired records; current permission is separate."""
    try:
        payload = row['payload']
        if type(payload) is not dict:
            raise ValueError('selection payload must be an object')
        draft = PipelineSourceSelectionDraft.model_validate_json(json.dumps(payload['draft'], allow_nan=False))
        raw_spec = payload['readSpec']
        if type(raw_spec) is not dict or set(raw_spec) != {'table','object_type','primary_key','columns','filters'}:
            raise ValueError('selection read spec shape differs')
        if type(raw_spec['columns']) is not list or type(raw_spec['filters']) is not list:
            raise ValueError('selection read spec arrays required')
        if any(type(term) is not list or len(term) != 2 for term in raw_spec['filters']):
            raise ValueError('selection scope pair differs')
        spec = MappingReadSpec(raw_spec['table'], raw_spec['object_type'], raw_spec['primary_key'],
            tuple(raw_spec['columns']), tuple(tuple(term) for term in raw_spec['filters']))
        identity, revision, previous_hash, actor = str(row['selection_id']), row['revision'], row['previous_hash'], row['actor']
        expected = build_selection_payload(draft=draft, read_spec=spec, selection_id=identity,
            revision=revision, previous_hash=previous_hash, actor=actor)
        if payload != expected or canonical_sha256(expected) != row['content_hash']:
            raise ValueError('selection payload or content hash differs')
        columns = {'org_id':'orgId','project_id':'projectId','installation_id':'installationId',
            'generation':'generation','pipeline_id':'pipelineId','source_id':'sourceId',
            'source_configuration_revision':'sourceConfigurationRevision'}
        if any(str(row[column]) != expected[name] for column,name in columns.items()):
            raise ValueError('selection identity columns differ')
        if (row['previous_revision'] != (None if revision == 1 else revision-1)
                or (revision > 1 and type(row['previous_revision']) is not int)):
            raise ValueError('selection predecessor differs')
        if row['request_hash'] != selection_request_hash(draft=draft, actor=actor,
                selection_id=identity, revision=revision, previous_hash=previous_hash):
            raise ValueError('selection request hash differs')
        ref = PipelineExactRef(resource_type='SourceSelectionRevision', resource_id='source-selection-'+identity,
            revision=revision, content_hash=row['content_hash'])
        return SourceSelectionRecord(ref, draft, spec, actor, previous_hash)
    except (KeyError, TypeError, ValueError):
        raise ValueError('invalid source selection record') from None
