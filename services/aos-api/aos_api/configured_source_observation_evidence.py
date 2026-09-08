"""Persist configuration/observation lineage without asserting business freshness."""
from dataclasses import dataclass
from datetime import datetime

from psycopg.types.json import Jsonb

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.configured_source_observation import ConfiguredSourceObservation
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
from aos_api.source_read_observation_evidence import SourceObservationEvidenceStore
from aos_api.tenant_scope import TenantScope

_TYPE = "configured-source-observation"
_PREFIX = "evidence-configured-source-"


def _body(observation_ref, configuration_ref, actor):
    if type(actor) is not str or not actor or actor.strip() != actor or len(actor) > 200:
        raise ValueError("canonical observation actor required")
    return {"schemaVersion": "aos.configured-source-observation-evidence/v1",
        "observationEvidenceRef": observation_ref.model_dump(mode="json", by_alias=True),
        "configurationRef": configuration_ref.model_dump(mode="json", by_alias=True),
        "actor": actor, "purpose": "configuration-observation-lineage-only", "factIds": [],
        "secretMaterialVersionKnown": False, "connectionIdentityVerified": False,
        "upstreamFreshness": "unknown"}


@dataclass(frozen=True, slots=True)
class PersistedConfiguredObservation:
    observation: ConfiguredSourceObservation
    observation_evidence_ref: InvestigationExactRef
    actor: str
    recorded_at: datetime


class ConfiguredObservationEvidenceStore:
    def __init__(self, transaction: HostTransaction, scope: TenantScope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("configured evidence requires HostTransaction and TenantScope")
        self._transaction, self._scope = transaction, scope
        self._configurations = SourceConfigurationRevisionStore(transaction, scope)
        self._observations = SourceObservationEvidenceStore(transaction, scope)

    def _verify_configuration(self, item):
        observation = item.observation
        revision = self._configurations.read_exact(item.source_configuration_ref)
        if (revision is None or revision.source_id != observation.source_id
            or (observation.tenant.org_id, observation.tenant.project_id) != self._scope.key
            or revision.recorded_at > observation.read_started_at):
            raise ValueError("observation configuration lineage drifted")

    def put(self, item: ConfiguredSourceObservation, rows, *, actor: str) -> InvestigationExactRef:
        item = ConfiguredSourceObservation.model_validate(item.model_dump())
        item.verify_rows(rows)
        self._verify_configuration(item)
        child = self._observations.put(item.observation, rows, actor=actor)
        body = _body(child, item.source_configuration_ref, actor)
        digest = canonical_hash(body)
        ref = InvestigationExactRef(resource_type="Evidence", resource_id=_PREFIX + digest,
            revision=1, content_hash="sha256:" + digest)
        observation = item.observation
        self._transaction.execute("""INSERT INTO public.aip_evidence
            (org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,source_type,source_ref,
             observed_at,freshness_at,content_hash,redaction,payload,created_by,created_at)
            VALUES(%s,%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,'{}'::jsonb,%s,%s,clock_timestamp())
            ON CONFLICT(org_id,project_id,evidence_id) DO NOTHING""",
            (*self._scope.key, ref.resource_id, _TYPE, Jsonb(body["configurationRef"]), _TYPE,
             observation.source_id, observation.read_finished_at, observation.read_started_at,
             digest, Jsonb(body), actor))
        restored = self.read_exact(ref)
        if restored is None or restored.observation != item or restored.actor != actor:
            raise ValueError("configured observation persistence drifted")
        return ref

    def read_exact(self, ref: InvestigationExactRef) -> PersistedConfiguredObservation | None:
        ref = InvestigationExactRef.model_validate(ref.model_dump())
        if (ref.resource_type != "Evidence" or type(ref.revision) is not int or ref.revision != 1
            or ref.receipt_id is not None or ref.resource_id != _PREFIX + ref.content_hash[7:]):
            raise ValueError("exact configured observation evidence reference required")
        row = self._transaction.execute("""SELECT e.*,EXISTS(
            SELECT 1 FROM public.aip_evidence_revoke_event r WHERE r.org_id=e.org_id
            AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
            AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked
            FROM public.aip_evidence e WHERE e.org_id=%s AND e.project_id=%s AND e.evidence_id=%s""",
            (*self._scope.key, ref.resource_id)).fetchone()
        if row is None:
            return None
        if row["revoked"]:
            raise ValueError("configured observation evidence revoked")
        raw = row["payload"]
        if type(raw) is not dict:
            raise ValueError("invalid configured evidence body")
        child_ref = InvestigationExactRef.model_validate(raw.get("observationEvidenceRef"))
        config_ref = InvestigationExactRef.model_validate(raw.get("configurationRef"))
        actor = raw.get("actor")
        body = _body(child_ref, config_ref, actor)
        digest = canonical_hash(body)
        if raw != body or canonical_hash(raw) != digest or ref.content_hash != "sha256:" + digest:
            raise ValueError("configured observation content drifted")
        child = self._observations.read_exact(child_ref)
        if child is None or child.actor != actor:
            raise ValueError("configured observation owner unavailable")
        item = ConfiguredSourceObservation(observation=child.observation.model_dump(),
            sourceConfigurationRef=config_ref.model_dump())
        self._verify_configuration(item)
        observed = item.observation
        recorded = row.get("created_at")
        if (not isinstance(recorded, datetime) or recorded.utcoffset() is None
            or recorded < child.recorded_at):
            raise ValueError("configured observation recorded time drifted")
        expected = dict(org_id=self._scope.org_id, project_id=self._scope.project_id,
            evidence_id=ref.resource_id, run_id=None, evidence_type=_TYPE,
            subject_ref=body["configurationRef"], source_type=_TYPE, source_ref=observed.source_id,
            observed_at=observed.read_finished_at, freshness_at=observed.read_started_at,
            content_hash=digest, redaction={}, created_by=actor)
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError("configured observation authority drifted")
        return PersistedConfiguredObservation(item, child_ref, actor, recorded)
