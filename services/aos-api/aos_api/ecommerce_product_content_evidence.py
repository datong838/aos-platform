"""Immutable internal product preparation evidence; no business readiness grant."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
import json

from psycopg.types.json import Jsonb
from aos_api.aip_evidence_dependencies import POLICY, require_evidence_dependencies
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_product_content_snapshot import ProductContentSnapshotReader, build_product_content_snapshot
from aos_api.ecommerce_product_joint_quality import ProductJointQualityCounts, _RULE, _counts
from aos_api.source_observation_rows_codec import encode_observed_rows, decode_observed_rows
from aos_api.source_read_observation import OBSERVATION_PUBLIC_FIELDS
from aos_api.tenant_scope import TenantScope

_PREFIX = 'evidence-product-content-'
_TYPE = 'product-content-snapshot'


def _json(value):
    return json.loads(json.dumps(value, default=lambda item: item.isoformat() if isinstance(item, datetime) else item, allow_nan=False))


def _plain(ref):
    return ExactRevisionRef(resource_type='Evidence', resource_id=ref.resource_id, revision=1,
        content_hash=ref.content_hash.removeprefix('sha256:')).model_dump(mode='json', by_alias=True)


@dataclass(frozen=True, slots=True)
class PersistedProductContent:
    rows: list
    snapshot: object


class ProductContentEvidenceStore:
    def __init__(self, transaction, scope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError('product evidence requires HostTransaction and TenantScope')
        self._tx, self._scope = transaction, scope
        self._observations = ConfiguredObservationEvidenceStore(transaction, scope)

    def put(self, *, evidence_ref, rows, channel_ref, entity_ref, binding_ref, actor, run_id=None):
        if type(actor) is not str or not actor or actor.strip() != actor or len(actor)>200:
            raise ValueError('canonical product evidence actor required')
        rows=deepcopy(rows)
        encoded=encode_observed_rows(rows)
        if any(not set(row).issubset(OBSERVATION_PUBLIC_FIELDS['niushop.product-quality-observation/v1']) for row in rows):
            raise ValueError('unsupported product fields')
        args=dict(evidence_ref=evidence_ref,rows=rows,channel_ref=channel_ref,entity_ref=entity_ref,binding_ref=binding_ref)
        snapshot=ProductContentSnapshotReader(self._tx,self._scope).read(**args)
        saved=self._observations.read_exact(evidence_ref)
        if run_id is not None and (type(run_id) is not str or not self._tx.execute(
            'SELECT 1 FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s',(*self._scope.key,run_id)).fetchone()):
            raise ValueError('product evidence run unavailable')
        identity=dict(schemaVersion='aos.product-content-source/v1',tenant=list(self._scope.key),actor=actor,runId=run_id,
            observationRef=evidence_ref.model_dump(mode='json',by_alias=True),
            selectionRefs=[r.model_dump(mode='json',by_alias=True) for r in (channel_ref,entity_ref,binding_ref)],
            selectionPolicy=snapshot.selection_policy)
        body=dict(identity,encodedRows=encoded,snapshot=_json(asdict(snapshot)),evidencePolicyVersion=POLICY,
            upstreamEvidenceRefs=[_plain(evidence_ref),_plain(saved.observation_evidence_ref)],marking=['internal'],factIds=[])
        if len(json.dumps(body,ensure_ascii=False).encode())>2_000_000:
            raise ValueError('complete product evidence exceeds supported size')
        key=_PREFIX+canonical_hash(identity)
        observation=saved.observation.observation
        self._tx.execute('''INSERT INTO aip_evidence
            (org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,source_type,source_ref,
             observed_at,freshness_at,content_hash,redaction,payload,created_by,created_at)
            VALUES(%s,%s,%s,%s,%s,%s,'database',%s,%s,%s,%s,'{}'::jsonb,%s,%s,clock_timestamp())
            ON CONFLICT(org_id,project_id,evidence_id) DO NOTHING''',
            (*self._scope.key,key,run_id,_TYPE,Jsonb(identity['observationRef']),observation.source_id,
             observation.read_finished_at,observation.read_started_at,canonical_hash(body),Jsonb(body),actor))
        row=self._tx.execute('SELECT content_hash,payload FROM aip_evidence WHERE org_id=%s AND project_id=%s AND evidence_id=%s',(*self._scope.key,key)).fetchone()
        if any(row['payload'].get(k)!=v for k,v in identity.items()) or row['payload'].get('encodedRows')!=encoded:
            raise ValueError('product evidence replay drifted')
        ref=ExactRevisionRef(resource_type='Evidence',resource_id=key,revision=1,content_hash=row['content_hash'])
        self.read_exact(ref)
        return ref

    def read_exact(self, ref):
        ref=ExactRevisionRef.model_validate(ref.model_dump())
        if ref.resource_type!='Evidence' or ref.revision!=1:
            raise ValueError('exact product evidence required')
        row=self._tx.execute('''SELECT e.*,EXISTS(SELECT 1 FROM aip_evidence_revoke_event r
            WHERE r.org_id=e.org_id AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
            AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked FROM aip_evidence e
            WHERE org_id=%s AND project_id=%s AND evidence_id=%s''',(*self._scope.key,ref.resource_id)).fetchone()
        if row is None or row['revoked'] or row['content_hash']!=ref.content_hash:
            raise ValueError('product evidence unavailable')
        body=row['payload']
        if type(body) is not dict or canonical_hash(body)!=ref.content_hash or len(json.dumps(body).encode())>2_000_000:
            raise ValueError('product evidence content drifted')
        require_evidence_dependencies(self._tx,self._scope,body)
        identity={k:body.get(k) for k in ('schemaVersion','tenant','actor','runId','observationRef','selectionRefs','selectionPolicy')}
        if identity['schemaVersion']!='aos.product-content-source/v1' or identity['tenant']!=list(self._scope.key) or ref.resource_id!=_PREFIX+canonical_hash(identity):
            raise ValueError('product evidence identity drifted')
        original=InvestigationExactRef.model_validate(body['observationRef'])
        saved=self._observations.read_exact(original)
        if saved is None:
            raise ValueError('product observation unavailable')
        observation=saved.observation.observation
        rows=decode_observed_rows(body['encodedRows'])
        saved.observation.verify_rows(rows)
        if any(not set(item).issubset(OBSERVATION_PUBLIC_FIELDS['niushop.product-quality-observation/v1']) for item in rows):
            raise ValueError('unsupported product fields')
        measured=datetime.fromisoformat(body['snapshot']['quality']['measured_at'])
        if measured.utcoffset() is None or not observation.read_finished_at<=measured<=row['created_at']:
            raise ValueError('product measurement time drifted')
        quality=ProductJointQualityCounts(self._scope.key,(original.resource_type,original.resource_id,original.revision,original.content_hash),
            _RULE,measured,len(rows),*_counts(rows,observation.read_finished_at))
        snapshot=build_product_content_snapshot(rows,quality,observation.read_finished_at)
        expected=dict(identity,encodedRows=body['encodedRows'],snapshot=_json(asdict(snapshot)),evidencePolicyVersion=POLICY,
            upstreamEvidenceRefs=[_plain(original),_plain(saved.observation_evidence_ref)],marking=['internal'],factIds=[])
        headers=dict(evidence_type=_TYPE,source_type='database',source_ref=observation.source_id,subject_ref=body['observationRef'],
            run_id=body['runId'],created_by=body['actor'],redaction={},observed_at=observation.read_finished_at,freshness_at=observation.read_started_at)
        if canonical_hash(expected)!=ref.content_hash or any(row[k]!=v for k,v in headers.items()):
            raise ValueError('product snapshot authority drifted')
        return PersistedProductContent(rows,snapshot)
