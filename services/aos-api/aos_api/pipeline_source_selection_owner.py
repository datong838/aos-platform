"""Current-gated source selection approval; never reads the business source."""
import hashlib
import json
from uuid import UUID, uuid4

import yaml
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.manifest_loader import ManifestLoader, _UniqueKeySafeLoader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.aip_runtime_configuration_sources import build_current_configuration_authorization
from aos_api.ec_ingress_journal import IngressJournal
from aos_api.ec_source_adapter import _parse_site_filter
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.extension_runtime.configuration_authorization import CurrentConfigurationPermission
from aos_api.extension_runtime.configuration_store import read_configuration
from aos_api.extension_runtime.ipc import _pairs, _constant
from aos_api.extension_runtime.lifecycle_store import _require_transaction, _values, RuntimeConflict, RuntimeRevisionConflict
from aos_api.extension_runtime.runtime_gate import CurrentPolicy, run_guarded
from aos_api.extension_runtime.runtime_release_artifacts import CurrentRuntimeReleaseArtifacts
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef, PipelineSourceSelectionDraft
from aos_api.pipeline_source_selection import derive_mapping_read_spec
from aos_api.pipeline_source_selection_store import build_selection_payload, decode_selection_row, selection_request_hash
from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
from aos_api.tenant_scope import TenantScope


def verify_graph_read_spec(graph, mapping, spec, *, source_id):
    """Only the fixed snapshot graph is supported by this approval version."""
    try:
        nodes = graph['nodes']
        if graph['write_mode'] != 'SNAPSHOT' or type(nodes) is not list or len(nodes) != 3:
            raise ValueError('fixed snapshot graph required')
        indexed = {node['node_type']: node for node in nodes}
        if set(indexed) != {'source', 'transform', 'sink'}:
            raise ValueError('fixed snapshot nodes required')
        source_node, transform_node, sink_node = [indexed[k] for k in ('source','transform','sink')]
        ids = [node['id'] for node in nodes]
        if any(type(i) is not str or not i for i in ids) or len(set(ids)) != 3:
            raise ValueError('unique node identities required')
        if any(node.get('pipeline_id', graph['pipeline_id']) != graph['pipeline_id'] for node in nodes):
            raise ValueError('node pipeline differs')
        edges = graph['edges']
        expected = {(source_node['id'],transform_node['id']), (transform_node['id'],sink_node['id'])}
        if len(edges) != 2 or {(e['source_node_id'],e['target_node_id']) for e in edges} != expected:
            raise ValueError('fixed snapshot edges required')
        source, transform, sink = [n['config'] for n in (source_node,transform_node,sink_node)]
        if (source['source_id'] != source_id or (source.get('table') or source.get('source_table')) != spec.table
                or source.get('pk','id') != spec.primary_key
                or source.get('primary_key',spec.primary_key) != spec.primary_key
                or source.get('incremental_strategy') != 'snapshot' or source.get('cursor') is not None
                or ('initial' in source and type(source['initial']) is not bool)
                or tuple(sorted(_parse_site_filter(source.get('site_filter')).items())) != tuple(sorted(spec.filters))):
            raise ValueError('source graph differs from pinned specification')
        if (transform.get('expression') != 'row' or transform.get('field_mappings') != mapping['field_mappings']
                or transform.get('target_ot') != spec.object_type or sink.get('target_ot') != spec.object_type
                or sink.get('write_mode') != 'SNAPSHOT'):
            raise ValueError('transform or sink differs from pinned specification')
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('invalid fixed snapshot graph') from exc


def _wire(value):
    return value.model_dump(mode='json', by_alias=True)


def _now(conn):
    return _values(conn.execute('SELECT clock_timestamp() AS now').fetchone(), ('now',))[0]


class PipelineSourceSelectionOwner:
    def __init__(self, *, installation_store, artifacts, release_policy):
        if (type(installation_store) is not PostgresInstallationStore
                or type(artifacts) is not CurrentRuntimeReleaseArtifacts or type(release_policy) is not ReleasePolicy):
            raise TypeError('exact current source selection dependencies required')
        self._store, self._artifacts, self._release_policy = installation_store, artifacts, release_policy
        self._authorization = build_current_configuration_authorization(
            permission=CurrentConfigurationPermission(installation_store=installation_store))

    def append(self, conn, *, draft, actor, idempotency_key, previous_ref=None):
        draft = PipelineSourceSelectionDraft.model_validate(draft)
        idempotency_key = validate_idempotency_key(idempotency_key)
        _require_transaction(conn)
        identity = conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id").fetchone()
        if _values(identity, ('role','org_id','project_id')) != ('aos_runtime',draft.org_id,draft.project_id):
            raise PermissionError('current runtime identity and tenant required')
        selection_id, revision, previous_hash = str(uuid4()), 1, None
        if previous_ref is not None:
            previous_ref = PipelineExactRef.model_validate(previous_ref)
            if previous_ref.resource_type != 'SourceSelectionRevision' or type(previous_ref.revision) is not int:
                raise ValueError('exact selection predecessor required')
            selection_id = previous_ref.resource_id.removeprefix('source-selection-')
            if previous_ref.resource_id != 'source-selection-'+str(UUID(selection_id)):
                raise ValueError('canonical selection predecessor required')
            revision, previous_hash = previous_ref.revision+1, previous_ref.content_hash
        request_hash = selection_request_hash(draft=draft, actor=actor, selection_id=selection_id,
            revision=revision, previous_hash=previous_hash)
        target = (draft.org_id,draft.project_id,UUID(draft.installation_ref.installation_id),UUID(draft.generation))
        if conn.execute('SELECT installation_id FROM bundle_installation WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE',target[:3]).fetchone() is None:
            raise LookupError('selection installation unavailable')

        def persist(spec):
            with conn.cursor(row_factory=dict_row) as cursor:
                existing = cursor.execute('''SELECT * FROM pipeline_source_selection_revision
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND idempotency_key=%s''',(*target,idempotency_key)).fetchone()
                if existing is not None:
                    saved = decode_selection_row(existing)
                    if existing['request_hash'] != request_hash or saved.read_spec != spec:
                        raise RuntimeConflict('selection idempotency request differs')
                    return saved.ref
                latest = cursor.execute('''SELECT * FROM pipeline_source_selection_revision
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s
                    ORDER BY revision DESC LIMIT 1''',(*target,draft.pipeline_id)).fetchone()
                if (latest is None and previous_ref is not None) or (latest is not None and decode_selection_row(latest).ref != previous_ref):
                    raise RuntimeRevisionConflict('selection predecessor is not current')
                payload = build_selection_payload(draft=draft,read_spec=spec,selection_id=selection_id,
                    revision=revision,previous_hash=previous_hash,actor=actor)
                row = cursor.execute('''INSERT INTO pipeline_source_selection_revision
                    (org_id,project_id,installation_id,generation,pipeline_id,selection_id,revision,source_id,
                     source_configuration_revision,payload,content_hash,previous_revision,previous_hash,request_hash,idempotency_key,actor)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                    (*target,draft.pipeline_id,UUID(selection_id),revision,draft.source_id,
                     UUID(payload['sourceConfigurationRevision']),Jsonb(payload),canonical_sha256(payload),
                     None if revision == 1 else revision-1,previous_hash,request_hash,idempotency_key,actor)).fetchone()
                return decode_selection_row(row).ref
        return self._guarded(conn,draft,actor,persist)

    def _guarded(self, conn, draft, actor, callback):
        scope = TenantScope(draft.org_id,draft.project_id)
        if self._artifacts.scope != scope:
            raise PermissionError('artifact tenant differs')
        current = CurrentInstallationRef.model_validate(_wire(draft.installation_ref))
        baseline = self._store.load_active_baseline_in_transaction(conn, org_id=scope.org_id,
            project_id=scope.project_id, requested_ref=current)
        matches = [item for item in baseline.lock.payload.resolved if
            (item.publisher,item.id,item.version,item.content_hash) ==
            (draft.package_ref.publisher,draft.package_ref.id,draft.package_ref.version,draft.package_ref.content_hash)]
        if len(matches) != 1:
            raise PermissionError('selected package not uniquely installed')
        selected = matches[0]
        context = dict(org_id=scope.org_id,project_id=scope.project_id,
            installation_id=current.installation_id,generation=draft.generation,actor=actor)

        def check_policy(db, _baseline):
            row = db.execute('''SELECT config_ref FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR SHARE''',
                (scope.org_id,scope.project_id,UUID(current.installation_id),UUID(draft.generation))).fetchone()
            if row is None or _values(row,('config_ref',))[0] != _wire(draft.configuration_ref):
                raise PermissionError('current runtime configuration differs')
            read_configuration(db,**context,ref=draft.configuration_ref,authorize=self._authorization)
            return CurrentPolicy(permissions_valid=True,budget_valid=True,policy_valid=True)

        def execute():
            IngressJournal().verify_pipeline_source_binding(conn,scope,pipeline_id=draft.pipeline_id,
                source_id=draft.source_id,source_revision=draft.source_configuration_ref.resource_id.removeprefix('source-config-'),
                pipeline_hash=draft.graph_hash,graph_revision=draft.graph_revision)
            source = SourceConfigurationRevisionStore(HostTransaction(conn),scope).read_current(draft.source_id)
            if source is None or _wire(source.ref) != _wire(draft.source_configuration_ref):
                raise PermissionError('current source configuration differs')
            row = conn.execute('''SELECT payload FROM phase5_pipeline_graph
                WHERE org_id=%s AND project_id=%s AND pipeline_id=%s FOR SHARE''',(*scope.key,draft.pipeline_id)).fetchone()
            if row is None:
                raise LookupError('pipeline graph unavailable')
            graph = _values(row,('payload',))[0]
            record = self._artifacts.load_record(selected)
            self._release_policy.evaluate(record,checked_at=_now(conn),
                expected_signature_fingerprint=selected.signature_fingerprint,
                expected_evidence_revision=selected.release_evidence_revision)
            exports = record.manifest.exports
            documents = []
            for ref, paths in ((draft.mapping_ref,exports.mappings),(draft.schema_ref,exports.schemas),
                               (draft.masking_policy_ref,exports.policies+exports.mappings)):
                if ref.revision != selected.version or not ManifestLoader._is_exported_path(ref.resource_id,paths):
                    raise PermissionError('selected asset is not an exact exported version')
                raw = self._artifacts.read_artifact(selected,ref.resource_id,256*1024)
                if 'sha256:'+hashlib.sha256(raw).hexdigest() != ref.content_hash:
                    raise ValueError('selected asset digest differs')
                if ref.resource_id.endswith('.json'):
                    document = json.loads(raw,object_pairs_hook=_pairs,parse_constant=_constant)
                else:
                    document = yaml.load(raw,Loader=_UniqueKeySafeLoader)
                documents.append(document)
            spec = derive_mapping_read_spec(*documents)
            verify_graph_read_spec(graph,documents[0],spec,source_id=draft.source_id)
            check_policy(conn,baseline)
            if not draft.not_before <= _now(conn) < draft.expires_at:
                raise PermissionError('selection approval window is not current')
            return callback(spec)
        return run_guarded(conn,installation_store=self._store,org_id=scope.org_id,project_id=scope.project_id,
            current_ref=current,generation=draft.generation,request_epoch=draft.execution_epoch,selected=selected,
            check_current_policy=check_policy,execute=execute)
