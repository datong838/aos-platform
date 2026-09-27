"""Exact candidate preparation never authorizes current execution."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest
import yaml

from aos_api.ec_ingress_journal import _digest
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_source_selection_candidate import (
    ExportedAssetCandidate, compile_source_selection_candidate,
)
from aos_api.tenant_scope import TenantScope
from tests.test_pipeline_runtime_control_contracts import payload
from tests.test_pipeline_source_selection import assets
from tests.test_pipeline_source_selection_owner import graph_case


def case():
    body = payload()
    body.pop('sourceSelectionRef')
    body.pop('mappingRef')
    body.pop('schemaRef')
    body.pop('maskingPolicyRef')
    body['packageRef']['version'] = '1.0.0'
    graph, _, _ = graph_case()
    graph['pipeline_id'] = body['pipelineId']
    graph['nodes'][0]['config']['source_id'] = body['sourceId']
    graph['nodes'][1]['config']['field_mappings'] = assets()[0]['field_mappings']
    body['graphHash'] = _digest(graph)
    documents = assets()
    paths = ('content/mappings/p01-shop.yaml', 'content/schemas/niushop-schema-fingerprint.json',
             'content/mappings/_pii-exclusion.yaml')
    kinds = ('Mapping', 'SchemaFingerprint', 'MaskingPolicy')
    candidates = []
    for path, kind, document in zip(paths, kinds, documents):
        raw = json.dumps(document).encode() if path.endswith('.json') else yaml.safe_dump(document).encode()
        ref = PipelineExactRef.model_validate({'resourceType': kind, 'resourceId': path,
            'revision': '1.0.0', 'contentHash': 'sha256:' + sha256(raw).hexdigest()})
        candidates.append(ExportedAssetCandidate(ref, raw))
    kwargs = dict(scope=TenantScope(body['orgId'], body['projectId']), base=body,
        graph=graph, graph_revision=1, mappings=(candidates[0],), schemas=(candidates[1],),
        masking_policies=(candidates[2],), exports={'mappings': ('content/mappings/',),
            'schemas': ('content/schemas/',), 'policies': ('content/policies/',)})
    return kwargs


def test_unique_candidate_is_prepared_without_execution_grant():
    draft = compile_source_selection_candidate(**case())
    assert draft.state == 'prepared' and draft.read_only is True
    assert draft.mapping_ref.resource_type == 'Mapping'
    assert draft.graph_hash == _digest(case()['graph'])


@pytest.mark.parametrize('fault', ['zero', 'ambiguous', 'graph', 'revision', 'source', 'tenant',
    'digest', 'export', 'version', 'unbounded', 'invalid_schema', 'missing_package'])
def test_candidate_fails_closed(fault):
    kwargs = case()
    if fault == 'zero': kwargs['mappings'] = ()
    elif fault == 'ambiguous': kwargs['mappings'] *= 2
    elif fault == 'graph': kwargs['graph']['nodes'][0]['config']['pk'] = 'different'
    elif fault == 'revision': kwargs['graph_revision'] = 2
    elif fault == 'source': kwargs['base']['sourceId'] = 'other'
    elif fault == 'tenant': kwargs['scope'] = TenantScope('dev-org', 'dev-project')
    elif fault == 'digest':
        item = kwargs['mappings'][0]
        kwargs['mappings'] = (ExportedAssetCandidate(item.ref, item.raw + b' '),)
    elif fault == 'export': kwargs['exports']['mappings'] = ('private/',)
    elif fault == 'version': kwargs['base']['packageRef']['version'] = '2.0.0'
    elif fault == 'unbounded': kwargs['mappings'] *= 17
    elif fault == 'invalid_schema':
        item = kwargs['schemas'][0]
        raw = b'{"version":1,"tables":[]}'
        ref = item.ref.model_copy(update={'content_hash': 'sha256:' + sha256(raw).hexdigest()})
        kwargs['schemas'] = (ExportedAssetCandidate(ref, raw),)
    else: kwargs['base'].pop('packageRef')
    with pytest.raises((ValueError, PermissionError)):
        compile_source_selection_candidate(**kwargs)


def test_caller_inputs_are_not_mutated():
    kwargs = case()
    before = deepcopy(kwargs)
    compile_source_selection_candidate(**kwargs)
    assert kwargs == before
