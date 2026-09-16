"""Bounded twelve-source preview. No configuration writes or source execution."""
from copy import deepcopy
import hashlib
import json
import yaml

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import ResolvedBundle
from aos_api.asset_registry.manifest_loader import _UniqueKeySafeLoader
from aos_api.extension_runtime.runtime_release_artifacts import CurrentRuntimeReleaseArtifacts
from aos_api.pipeline_source_selection import derive_mapping_read_spec
from aos_api.pipeline_source_selection_owner import verify_graph_read_spec
from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES, CANONICAL_QYH_OBJECT_TYPE_DISPLAY_NAMES


def _graph(source, mapping, source_id):
    pipeline = source.pipeline_id
    configs = (
        dict(source_id=source_id, table=mapping['source_table'], source_table=mapping['source_table'],
             pk=mapping['primary_key'], primary_key=mapping['primary_key'],
             site_filter=mapping['site_filter'], incremental_strategy='snapshot', initial=False,
             unique_key_pattern=mapping['unique_key_pattern']),
        dict(expression='row', field_mappings=deepcopy(mapping['field_mappings']), target_ot=mapping['target_ot']),
        dict(target_ot=mapping['target_ot'], write_mode='SNAPSHOT', unique_key_pattern=mapping['unique_key_pattern']),
    )
    nodes = [dict(id=pipeline+'-'+kind, name=kind, node_type=kind,
                  position_x=60+260*i, position_y=60, config=config)
             for i, (kind, config) in enumerate(zip(('source', 'transform', 'sink'), configs))]
    return dict(pipeline_id=pipeline, pipeline_type='ETL', write_mode='SNAPSHOT',
                name='栖月汇-'+CANONICAL_QYH_OBJECT_TYPE_DISPLAY_NAMES[source.object_type], nodes=nodes,
                edges=[dict(id=pipeline+'-edge-'+str(i), source_node_id=nodes[i]['id'],
                            target_node_id=nodes[i+1]['id']) for i in range(2)])


def build_preview(artifacts, selected, source_id):
    """Caller obtains selected from current installation; preview grants no authority."""
    if type(artifacts) is not CurrentRuntimeReleaseArtifacts or type(selected) is not ResolvedBundle:
        raise TypeError('original release artifact reader and resolved bundle required')
    if selected.id != 'platform.ecommerce.niushop':
        raise ValueError('canonical Niushop package required')
    if type(source_id) is not str or not source_id or source_id.strip() != source_id:
        raise ValueError('canonical source identity required')

    def read(path, kind):
        raw = artifacts.read_artifact(selected, path, 256*1024)
        document = json.loads(raw) if path.endswith('.json') else yaml.load(raw, Loader=_UniqueKeySafeLoader)
        ref = dict(resourceType=kind, resourceId=path, revision=selected.version,
                   contentHash='sha256:'+hashlib.sha256(raw).hexdigest())
        return document, ref

    schema, schema_ref = read('content/schemas/niushop-schema-fingerprint.json', 'SchemaFingerprint')
    masking, masking_ref = read('content/mappings/_pii-exclusion.yaml', 'MaskingPolicy')
    members, tables = [], set()
    for source in CANONICAL_QYH_SOURCES:
        mapping, mapping_ref = read('content/mappings/'+source.mapping_file, 'Mapping')
        spec = derive_mapping_read_spec(mapping, schema, masking)
        compile_snapshot_mapping(mapping, spec)
        if spec.object_type != source.object_type or spec.table in tables:
            raise ValueError('canonical source object or unique table mismatch')
        tables.add(spec.table)
        graph = _graph(source, mapping, source_id)
        verify_graph_read_spec(graph, mapping, spec, source_id=source_id)
        members.append(dict(pipelineId=source.pipeline_id, objectType=spec.object_type, table=spec.table,
                            graph=graph, graphPreviewHash=canonical_sha256(graph),
                            schedule=dict(pipelineId=source.pipeline_id, name=graph['name'],
                                          enabled=False, cron='0 * * * *', ingest=None),
                            artifactRefs=dict(mappingRef=mapping_ref, schemaRef=schema_ref,
                                              maskingPolicyRef=masking_ref)))
    body = dict(schemaVersion='aos.snapshot-configuration-preview/v1', executionAuthorized=False,
                sourceId=source_id, packageRef=dict(publisher=selected.publisher, id=selected.id,
                                                  version=selected.version, contentHash=selected.content_hash),
                members=members)
    return dict(**body, previewHash=canonical_sha256(body))
