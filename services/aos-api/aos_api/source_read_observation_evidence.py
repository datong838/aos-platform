"""Immutable storage for read observations, never upstream freshness authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.source_read_observation import SourceReadObservation
from aos_api.tenant_scope import TenantScope


_TYPE = "source-read-observation"
_PREFIX = "evidence-source-read-"


def canonical_observation_evidence(
    scope: TenantScope, observation: SourceReadObservation, *, actor: str,
) -> tuple[dict[str, Any], str]:
    item = SourceReadObservation.model_validate(observation.model_dump())
    if (item.tenant.org_id, item.tenant.project_id) != scope.key:
        raise ValueError("observation evidence scope drifted")
    if type(actor) is not str or not actor or actor.strip() != actor or len(actor) > 200:
        raise ValueError("canonical observation actor required")
    body = {
        "schemaVersion": "aos.source-read-observation-evidence/v1",
        "observation": item.model_dump(mode="json", by_alias=True),
        "actor": actor, "purpose": "observation-only", "upstreamFreshness": "unknown", "factIds": [],
    }
    return body, canonical_hash(body)


def _subject(item: SourceReadObservation) -> dict[str, str]:
    return {"resourceType": "DataSource", "resourceId": item.source_id, "authority": "postgres:meta_source"}


@dataclass(frozen=True, slots=True)
class PersistedSourceObservation:
    observation: SourceReadObservation
    actor: str
    recorded_at: datetime


class SourceObservationEvidenceStore:
    def __init__(self, transaction: HostTransaction, scope: TenantScope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("observation evidence requires HostTransaction and TenantScope")
        self._transaction, self._scope = transaction, scope

    def put(
        self, observation: SourceReadObservation, rows: list[dict[str, Any]], *, actor: str,
    ) -> InvestigationExactRef:
        body, digest = canonical_observation_evidence(self._scope, observation, actor=actor)
        item = SourceReadObservation.model_validate(body["observation"])
        item.verify_rows(rows)
        ref = InvestigationExactRef(resource_type="Evidence", resource_id=_PREFIX + digest,
                                    revision=1, content_hash="sha256:" + digest)
        self._transaction.execute("""INSERT INTO public.aip_evidence
            (org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,source_type,source_ref,
             observed_at,freshness_at,content_hash,redaction,payload,created_by,created_at)
            VALUES(%s,%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,'{}'::jsonb,%s,%s,clock_timestamp())
            ON CONFLICT (org_id,project_id,evidence_id) DO NOTHING""",
            (*self._scope.key, ref.resource_id, _TYPE, Jsonb(_subject(item)), _TYPE, item.source_id,
             item.read_finished_at, item.read_started_at, digest, Jsonb(body), actor))
        restored = self.read_exact(ref)
        if restored is None or canonical_observation_evidence(
            self._scope, restored.observation, actor=restored.actor
        ) != (body, digest):
            raise ValueError("observation evidence persistence drifted")
        return ref

    def read_exact(self, ref: InvestigationExactRef) -> PersistedSourceObservation | None:
        ref = InvestigationExactRef.model_validate(ref.model_dump())
        if (ref.resource_type != "Evidence" or type(ref.revision) is not int or ref.revision != 1
            or ref.receipt_id is not None or ref.resource_id != _PREFIX + ref.content_hash[7:]):
            raise ValueError("exact source observation evidence reference required")
        row = self._transaction.execute("""SELECT e.*, EXISTS(
            SELECT 1 FROM public.aip_evidence_revoke_event r WHERE r.org_id=e.org_id
            AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
            AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked
            FROM public.aip_evidence e WHERE e.org_id=%s AND e.project_id=%s AND e.evidence_id=%s""",
            (*self._scope.key, ref.resource_id)).fetchone()
        if row is None:
            return None
        if row["revoked"]:
            raise ValueError("observation evidence revoked")
        raw = row["payload"]
        if type(raw) is not dict or type(raw.get("observation")) is not dict:
            raise ValueError("invalid observation evidence body")
        item = SourceReadObservation.model_validate(raw["observation"])
        actor = raw.get("actor")
        body, digest = canonical_observation_evidence(self._scope, item, actor=actor)
        recorded_at = row.get("created_at")
        if (not isinstance(recorded_at, datetime) or recorded_at.utcoffset() is None
            or recorded_at < item.read_finished_at):
            raise ValueError("observation evidence recorded time is invalid")
        expected = dict(org_id=self._scope.org_id, project_id=self._scope.project_id,
            evidence_id=ref.resource_id, run_id=None, evidence_type=_TYPE, subject_ref=_subject(item),
            source_type=_TYPE, source_ref=item.source_id, observed_at=item.read_finished_at,
            freshness_at=item.read_started_at, content_hash=digest, redaction={}, created_by=actor)
        if (body != raw or canonical_hash(raw) != digest or ref.content_hash != "sha256:" + digest
            or any(row.get(key) != value for key, value in expected.items())):
            raise ValueError("observation evidence authority drifted")
        return PersistedSourceObservation(item, actor, recorded_at)
