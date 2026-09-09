"""Host-only, transaction-bound quality evidence using the existing AIP owner.

Persistence proves the immutable measurement, not the authenticity of a source
or the successful execution of a business task. No public routing is installed.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from typing import Any

from pydantic import Field, field_validator
from psycopg.types.json import Jsonb

from aos_api.aip_contracts import AipContractModel
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.data_requirement_quality import QualityMeasurementRecord, ResolvedPopulationPolicy, evaluate_quality
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope

SCHEMA = "aos.data-requirement-quality-evidence/v1"
TYPE = "data-requirement-quality"


class QualityEvidenceInput(AipContractModel):
    requirement: DataRequirementRevisionRecord
    measurement: QualityMeasurementRecord
    population_policy: ResolvedPopulationPolicy
    evaluated_at: datetime
    actor: str = Field(min_length=1, max_length=200)
    run_id: str | None = Field(min_length=1, max_length=200)

    @field_validator("actor", "run_id")
    @classmethod
    def _identity(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("evidence identity must be canonical")
        return value


def _utc(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError("quality evidence timestamps require timezone")
        return value.astimezone(UTC).isoformat(timespec="microseconds")
    if isinstance(value, dict):
        return {key: _utc(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_utc(item) for item in value]
    return value


def canonical_quality_evidence(scope: TenantScope, value: QualityEvidenceInput) -> tuple[dict[str, Any], str]:
    item = QualityEvidenceInput.model_validate(value.model_dump())
    result = evaluate_quality(scope, item.requirement, item.measurement,
        evaluated_at=item.evaluated_at, population_policy=item.population_policy)
    serialized = _utc(item.model_dump(by_alias=True))
    # Requirement is an existing authority: its hash includes original offset
    # representations. Preserve that body; normalize only our own timestamps.
    serialized["requirement"] = json.loads(json.dumps(
        item.requirement.model_dump(by_alias=True), default=str, ensure_ascii=False, allow_nan=False))
    body = {"schemaVersion": SCHEMA, "input": serialized,
            "assessment": _utc(asdict(result)), "factIds": []}
    if len(json.dumps(body, ensure_ascii=False, allow_nan=False).encode()) > 2_000_000:
        raise ValueError("quality evidence exceeds size limit")
    return body, canonical_hash(body)


def _subject(item: QualityEvidenceInput) -> dict[str, Any]:
    return {**item.measurement.requirement_ref.model_dump(by_alias=True),
            "authority": "postgres:data_requirement_revision"}


class QualityEvidenceStore:
    def __init__(self, transaction: HostTransaction, scope: TenantScope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("quality evidence requires HostTransaction and TenantScope")
        self._transaction, self._scope = transaction, scope

    def put(self, value: QualityEvidenceInput) -> InvestigationExactRef:
        body, digest = canonical_quality_evidence(self._scope, value)
        item = QualityEvidenceInput.model_validate(body["input"])
        ref = InvestigationExactRef(resource_type="Evidence", resource_id="evidence-quality-" + digest,
                                    revision=1, content_hash="sha256:" + digest)
        self._transaction.execute("""INSERT INTO public.aip_evidence
            (org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,source_type,source_ref,
             observed_at,freshness_at,content_hash,redaction,payload,created_by,created_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'{}'::jsonb,%s,%s,%s)
            ON CONFLICT (org_id,project_id,evidence_id) DO NOTHING""",
            (*self._scope.key, ref.resource_id, item.run_id, TYPE, Jsonb(_subject(item)), TYPE,
             item.requirement.requirement_id, item.measurement.measured_at,
             item.measurement.source_observed_at, digest, Jsonb(body), item.actor, item.evaluated_at))
        saved = self.read_exact(ref)
        if saved is None or canonical_quality_evidence(self._scope, saved) != (body, digest):
            raise ValueError("quality evidence persistence drifted")
        return ref

    def read_exact(self, ref: InvestigationExactRef) -> QualityEvidenceInput | None:
        ref = InvestigationExactRef.model_validate(ref.model_dump())
        if (ref.resource_type != "Evidence" or type(ref.revision) is not int or ref.revision != 1
            or ref.receipt_id is not None or ref.resource_id != "evidence-quality-" + ref.content_hash[7:]):
            raise ValueError("exact quality evidence reference required")
        row = self._transaction.execute("""SELECT e.*, EXISTS(
            SELECT 1 FROM public.aip_evidence_revoke_event r WHERE r.org_id=e.org_id
            AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
            AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked
            FROM public.aip_evidence e WHERE e.org_id=%s AND e.project_id=%s AND e.evidence_id=%s""",
            (*self._scope.key, ref.resource_id)).fetchone()
        if row is None:
            return None
        if row["revoked"]:
            raise ValueError("quality evidence revoked")
        raw = row["payload"]
        if not isinstance(raw, dict) or not isinstance(raw.get("input"), dict):
            raise ValueError("invalid quality evidence body")
        item = QualityEvidenceInput.model_validate(raw["input"])
        body, digest = canonical_quality_evidence(self._scope, item)
        expected = dict(org_id=self._scope.org_id, project_id=self._scope.project_id,
            evidence_id=ref.resource_id, run_id=item.run_id, evidence_type=TYPE,
            subject_ref=_subject(item), source_type=TYPE, source_ref=item.requirement.requirement_id,
            observed_at=item.measurement.measured_at, freshness_at=item.measurement.source_observed_at,
            content_hash=digest, redaction={}, created_by=item.actor, created_at=item.evaluated_at)
        if (canonical_hash(raw) != digest or body != raw or ref.content_hash != "sha256:" + digest
            or any(row.get(key) != value for key, value in expected.items())):
            raise ValueError("quality evidence authority drifted")
        return item
