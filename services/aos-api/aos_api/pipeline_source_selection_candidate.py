"""Pure preparation of one exact SourceSelection draft; never an approval."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import yaml

from aos_api.asset_registry.manifest_loader import ManifestLoader, _UniqueKeySafeLoader
from aos_api.ec_ingress_journal import _digest
from aos_api.extension_runtime.ipc import _pairs, _constant
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef, PipelineSourceSelectionDraft
from aos_api.pipeline_source_selection import derive_mapping_read_spec
from aos_api.pipeline_source_selection_owner import verify_graph_read_spec
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class ExportedAssetCandidate:
    """Caller-supplied bytes; the caller must independently verify current release."""
    ref: PipelineExactRef
    raw: bytes


def _document(candidate: ExportedAssetCandidate, kind: str, version: str,
              exported: tuple[str, ...]) -> dict:
    if type(candidate) is not ExportedAssetCandidate:
        raise ValueError('exact asset candidate required')
    ref = PipelineExactRef.model_validate(candidate.ref)
    if (ref.resource_type != kind or ref.revision != version
            or not ManifestLoader._is_exported_path(ref.resource_id, exported)
            or type(candidate.raw) is not bytes or not 0 < len(candidate.raw) <= 256 * 1024
            or 'sha256:' + hashlib.sha256(candidate.raw).hexdigest() != ref.content_hash):
        raise ValueError('candidate asset reference differs')
    try:
        document = (json.loads(candidate.raw, object_pairs_hook=_pairs, parse_constant=_constant)
                    if ref.resource_id.endswith('.json') else yaml.load(candidate.raw, Loader=_UniqueKeySafeLoader))
    except (ValueError, yaml.YAMLError, UnicodeError) as exc:
        raise ValueError('candidate asset document invalid') from exc
    if type(document) is not dict:
        raise ValueError('candidate asset document invalid')
    return document


def compile_source_selection_candidate(*, scope: TenantScope, base: dict, graph: dict,
                                       graph_revision: int, mappings: tuple[ExportedAssetCandidate, ...],
                                       schemas: tuple[ExportedAssetCandidate, ...],
                                       masking_policies: tuple[ExportedAssetCandidate, ...],
                                       exports) -> PipelineSourceSelectionDraft:
    """Return a prepared draft only for a unique fixed-snapshot asset tuple.

    This does not prove the caller's installation, binding, source or release is
    current. The original Owner must revalidate all of them in its transaction.
    """
    if (type(scope) is not TenantScope or type(base) is not dict or type(graph) is not dict
            or type(graph_revision) is not int or graph_revision < 1
            or type(exports) is not dict or set(exports) != {'mappings', 'schemas', 'policies'}
            or any(type(items) is not tuple or len(items) > 16 for items in
                   (mappings, schemas, masking_policies))
            or any(type(paths) is not tuple or any(type(path) is not str for path in paths)
                   for paths in exports.values())):
        raise ValueError('bounded exact candidate inputs required')
    if (base.get('orgId'), base.get('projectId')) != scope.key:
        raise PermissionError('candidate tenant differs')
    if (base.get('pipelineId') != graph.get('pipeline_id')
            or base.get('graphRevision') != graph_revision
            or base.get('graphHash') != _digest(graph)):
        raise ValueError('candidate graph revision differs')
    package = base.get('packageRef')
    if type(package) is not dict or type(package.get('version')) is not str:
        raise ValueError('candidate package reference required')
    version = package['version']
    mapping_docs = [(item.ref, _document(item, 'Mapping', version, exports['mappings'])) for item in mappings]
    schema_docs = [(item.ref, _document(item, 'SchemaFingerprint', version, exports['schemas'])) for item in schemas]
    masking_exports = exports['policies'] + exports['mappings']
    masking_docs = [(item.ref, _document(item, 'MaskingPolicy', version, masking_exports))
                    for item in masking_policies]
    matches = []
    for mapping_ref, mapping in mapping_docs:
        for schema_ref, schema in schema_docs:
            for masking_ref, masking in masking_docs:
                try:
                    spec = derive_mapping_read_spec(mapping, schema, masking)
                    verify_graph_read_spec(graph, mapping, spec, source_id=base.get('sourceId'))
                except ValueError:
                    continue
                matches.append((mapping_ref, schema_ref, masking_ref))
                if len(matches) > 1:
                    raise ValueError('source selection candidate is ambiguous')
    if len(matches) != 1:
        raise ValueError('source selection candidate unavailable')
    mapping_ref, schema_ref, masking_ref = matches[0]
    return PipelineSourceSelectionDraft.model_validate(base | {
        'mappingRef': mapping_ref.model_dump(mode='json', by_alias=True),
        'schemaRef': schema_ref.model_dump(mode='json', by_alias=True),
        'maskingPolicyRef': masking_ref.model_dump(mode='json', by_alias=True),
    })
