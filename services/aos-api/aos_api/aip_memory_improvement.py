"""Fail-closed AIP-5 E7 memory improvement evaluator and fact store."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_eval_contracts import EvidenceQuality
from aos_api.aip_memory_projection_contracts import (
    ImprovementConclusion,
    ImprovementMetric,
    ImprovementMetricName,
    ImprovementObservation,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]
MINIMUM_SAMPLE_SIZE = 30


class ImprovementEvaluationRequest(AipContractModel):
    observation_id: str = Field(min_length=1, max_length=200)
    agent_instance_ref: VersionedAssetRef
    metric_definition_ref: VersionedAssetRef
    eval_contract_ref: VersionedAssetRef
    cutoff_at: datetime
    observed_at: datetime

    @model_validator(mode="after")
    def _exact_refs(self):
        expected = (
            (self.agent_instance_ref, "AgentInstance"),
            (self.metric_definition_ref, "MetricDefinition"),
            (self.eval_contract_ref, "EvalContract"),
        )
        for ref, kind in expected:
            if ref.asset_type != kind:
                raise ValueError(f"reference must use assetType={kind}")
        if self.observed_at < self.cutoff_at:
            raise ValueError("observed_at must not precede cutoff_at")
        return self


class TrustedImprovementEvidence(AipContractModel):
    """Evidence resolved by server-side authorities, never accepted by the API."""

    eval_report_ref: VersionedAssetRef
    baseline_cohort_ref: VersionedAssetRef
    treatment_cohort_ref: VersionedAssetRef
    exposure_refs: list[VersionedAssetRef] = Field(min_length=1, max_length=10000)
    metrics: list[ImprovementMetric] = Field(min_length=1, max_length=3)
    quality: EvidenceQuality
    source_refs: list[VersionedAssetRef] = Field(min_length=1, max_length=128)
    revoked_exposure_refs: list[VersionedAssetRef] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def _governed_shape(self):
        if self.quality is EvidenceQuality.UNKNOWN:
            raise ValueError("trusted comparable evidence cannot have unknown quality")
        expected = (
            (self.eval_report_ref, "EvalReport"),
            (self.baseline_cohort_ref, "CohortSnapshot"),
            (self.treatment_cohort_ref, "CohortSnapshot"),
        )
        for ref, kind in expected:
            if ref.asset_type != kind:
                raise ValueError(f"reference must use assetType={kind}")
        if any(ref.asset_type != "MemoryExposure" for ref in self.exposure_refs):
            raise ValueError("exposure_refs must reference MemoryExposure")
        if any(ref.asset_type != "MemoryExposure" for ref in self.revoked_exposure_refs):
            raise ValueError("revoked_exposure_refs must reference MemoryExposure")
        if any(
            ref.asset_type not in {"EvalReport", "EvidenceSnapshot", "MetricSnapshot"}
            for ref in self.source_refs
        ):
            raise ValueError("source_refs must reference governed evidence assets")
        return self


class AipMemoryImprovementError(RuntimeError):
    code = "AIP_MEMORY_IMPROVEMENT_ERROR"


class AipMemoryImprovementNotFound(AipMemoryImprovementError):
    code = "AIP_MEMORY_IMPROVEMENT_NOT_FOUND"


class AipMemoryImprovementConflict(AipMemoryImprovementError):
    code = "AIP_MEMORY_IMPROVEMENT_CONFLICT"


class AipMemoryImprovementBlocked(AipMemoryImprovementError):
    code = "AIP_MEMORY_IMPROVEMENT_BLOCKED"


class AipMemoryImprovementPersistenceError(AipMemoryImprovementError):
    code = "AIP_MEMORY_IMPROVEMENT_PERSISTENCE_ERROR"


class AipMemoryImprovementService:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def evaluate(
        self,
        scope: TenantScope,
        request: ImprovementEvaluationRequest,
        *,
        evidence: TrustedImprovementEvidence | None = None,
    ) -> ImprovementObservation:
        self._require_scope(scope)
        try:
            with self._connect_factory(scope) as conn:
                self._require_authorities(conn, scope, request)
                observation = self._build(scope, request, evidence)
                existing = self._row(conn, scope, request.observation_id)
                if existing is not None:
                    replay = self._from_row(scope, existing)
                    if replay.observation_hash != observation.observation_hash:
                        raise AipMemoryImprovementConflict(
                            "observation id already has different evidence"
                        )
                    return replay
                self._insert(conn, scope, observation)
                conn.commit()
                return observation
        except AipMemoryImprovementError:
            raise
        except Exception as exc:
            raise AipMemoryImprovementPersistenceError(
                "memory improvement evaluation failed"
            ) from exc

    def get_observation(
        self, scope: TenantScope, observation_id: str
    ) -> ImprovementObservation:
        self._require_scope(scope)
        try:
            with self._connect_factory(scope) as conn:
                row = self._row(conn, scope, observation_id)
                if row is None:
                    raise AipMemoryImprovementNotFound("observation not found")
                return self._from_row(scope, row)
        except AipMemoryImprovementError:
            raise
        except Exception as exc:
            raise AipMemoryImprovementPersistenceError(
                "memory improvement observation read failed"
            ) from exc

    def list_observations(
        self, scope: TenantScope, *, instance_id: str | None = None, limit: int = 100
    ) -> list[ImprovementObservation]:
        self._require_scope(scope)
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        try:
            with self._connect_factory(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_memory_improvement_observation
                       WHERE org_id=%s AND project_id=%s
                         AND (%s::text IS NULL OR instance_id=%s)
                       ORDER BY observed_at DESC,observation_id LIMIT %s""",
                    (*scope.key, instance_id, instance_id, limit),
                ).fetchall()
                return [self._from_row(scope, row) for row in rows]
        except Exception as exc:
            raise AipMemoryImprovementPersistenceError(
                "memory improvement observation list failed"
            ) from exc

    def _build(self, scope, request, evidence):
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        limitations: list[str] = []
        if evidence is None:
            limitations = ["comparable_governed_evidence_unavailable"]
            payload = dict(
                tenant=tenant,
                observation_id=request.observation_id,
                agent_instance_ref=request.agent_instance_ref,
                metric_definition_ref=request.metric_definition_ref,
                eval_contract_ref=request.eval_contract_ref,
                quality=EvidenceQuality.UNKNOWN,
                cutoff_at=request.cutoff_at,
                observed_at=request.observed_at,
                conclusion=ImprovementConclusion.INSUFFICIENT_EVIDENCE,
                limitations=limitations,
            )
        else:
            limitations.extend(evidence.limitations)
            if evidence.revoked_exposure_refs:
                limitations.append("revoked_exposure_present")
            if any(
                metric.baseline_sample_size < MINIMUM_SAMPLE_SIZE
                or metric.treatment_sample_size < MINIMUM_SAMPLE_SIZE
                for metric in evidence.metrics
            ):
                limitations.append("minimum_sample_size_not_met")
            if limitations:
                payload = dict(
                    tenant=tenant,
                    observation_id=request.observation_id,
                    agent_instance_ref=request.agent_instance_ref,
                    metric_definition_ref=request.metric_definition_ref,
                    eval_contract_ref=request.eval_contract_ref,
                    quality=EvidenceQuality.UNKNOWN,
                    cutoff_at=request.cutoff_at,
                    observed_at=request.observed_at,
                    conclusion=ImprovementConclusion.INSUFFICIENT_EVIDENCE,
                    limitations=sorted(set(limitations)),
                )
            else:
                payload = dict(
                    tenant=tenant,
                    observation_id=request.observation_id,
                    agent_instance_ref=request.agent_instance_ref,
                    metric_definition_ref=request.metric_definition_ref,
                    eval_contract_ref=request.eval_contract_ref,
                    eval_report_ref=evidence.eval_report_ref,
                    baseline_cohort_ref=evidence.baseline_cohort_ref,
                    treatment_cohort_ref=evidence.treatment_cohort_ref,
                    exposure_refs=evidence.exposure_refs,
                    metrics=evidence.metrics,
                    quality=evidence.quality,
                    source_refs=evidence.source_refs,
                    cutoff_at=request.cutoff_at,
                    observed_at=request.observed_at,
                    conclusion=self._conclusion(evidence.metrics),
                )
        observation_hash = self._hash(payload)
        return ImprovementObservation(**payload, observation_hash=observation_hash)

    @staticmethod
    def _conclusion(metrics: list[ImprovementMetric]) -> ImprovementConclusion:
        outcomes: list[int] = []
        for metric in metrics:
            if (
                metric.confidence_interval_lower is not None
                and metric.confidence_interval_lower <= 0
                <= metric.confidence_interval_upper
            ):
                outcomes.append(0)
                continue
            delta = metric.treatment_value - metric.baseline_value
            if metric.metric_name is ImprovementMetricName.HUMAN_EDIT_RATE:
                delta = -delta
            outcomes.append(1 if delta > 0 else -1 if delta < 0 else 0)
        if any(value < 0 for value in outcomes):
            return ImprovementConclusion.REGRESSED
        if any(value > 0 for value in outcomes):
            return ImprovementConclusion.IMPROVED
        return ImprovementConclusion.UNCHANGED

    @staticmethod
    def _require_authorities(conn, scope, request) -> None:
        instance = conn.execute(
            """SELECT i.version,t.content_hash,i.status FROM aip_agent_instance i
               JOIN aip_agent_template_revision t ON t.template_id=i.template_id
                AND t.revision=i.template_revision
               WHERE i.org_id=%s AND i.project_id=%s AND i.instance_id=%s""",
            (*scope.key, request.agent_instance_ref.asset_id),
        ).fetchone()
        if instance is None:
            raise AipMemoryImprovementNotFound("agent instance not found")
        if (
            int(instance["version"]) != request.agent_instance_ref.revision
            or instance["content_hash"] != request.agent_instance_ref.content_hash
            or instance["status"] != "active"
        ):
            raise AipMemoryImprovementBlocked("agent instance exact revision is not active")
        metric = conn.execute(
            """SELECT content_hash FROM aip_metric_definition_revision
               WHERE org_id=%s AND project_id=%s AND metric_id=%s AND revision=%s""",
            (*scope.key, request.metric_definition_ref.asset_id, request.metric_definition_ref.revision),
        ).fetchone()
        if metric is None or metric["content_hash"] != request.metric_definition_ref.content_hash:
            raise AipMemoryImprovementBlocked("metric definition exact revision unavailable")
        contract = conn.execute(
            """SELECT content_hash,lifecycle FROM aip_eval_contract_revision
               WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=%s""",
            (*scope.key, request.eval_contract_ref.asset_id, request.eval_contract_ref.revision),
        ).fetchone()
        if (
            contract is None
            or contract["content_hash"] != request.eval_contract_ref.content_hash
            or contract["lifecycle"] != "frozen"
        ):
            raise AipMemoryImprovementBlocked("eval contract exact revision is not frozen")

    @staticmethod
    def _insert(conn, scope, observation) -> None:
        dump = observation.model_dump(mode="json", by_alias=True)
        conn.execute(
            """INSERT INTO aip_memory_improvement_observation (
               org_id,project_id,observation_id,instance_id,instance_version,instance_hash,
               metric_definition_ref,eval_contract_ref,eval_report_ref,baseline_cohort_ref,
               treatment_cohort_ref,exposure_refs,metrics,quality,source_refs,cutoff_at,
               observed_at,conclusion,limitations,observation_hash)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                 %s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s,%s,%s,%s::jsonb,%s)""",
            (
                *scope.key, observation.observation_id,
                observation.agent_instance_ref.asset_id,
                observation.agent_instance_ref.revision,
                observation.agent_instance_ref.content_hash,
                json.dumps(dump["metricDefinitionRef"]), json.dumps(dump["evalContractRef"]),
                AipMemoryImprovementService._optional_json(dump.get("evalReportRef")),
                AipMemoryImprovementService._optional_json(dump.get("baselineCohortRef")),
                AipMemoryImprovementService._optional_json(dump.get("treatmentCohortRef")),
                json.dumps(dump["exposureRefs"]),
                json.dumps(dump["metrics"]), observation.quality.value,
                json.dumps(dump["sourceRefs"]), observation.cutoff_at, observation.observed_at,
                observation.conclusion.value, json.dumps(observation.limitations),
                observation.observation_hash,
            ),
        )

    @staticmethod
    def _row(conn, scope, observation_id):
        return conn.execute(
            """SELECT * FROM aip_memory_improvement_observation
               WHERE org_id=%s AND project_id=%s AND observation_id=%s""",
            (*scope.key, observation_id),
        ).fetchone()

    @staticmethod
    def _from_row(scope, row):
        value = lambda name, default=None: row[name] if row[name] is not None else default
        parse = lambda item: json.loads(item) if isinstance(item, str) else item
        return ImprovementObservation(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            observation_id=row["observation_id"],
            agent_instance_ref=VersionedAssetRef(
                asset_type="AgentInstance", asset_id=row["instance_id"],
                revision=int(row["instance_version"]), content_hash=row["instance_hash"],
            ),
            metric_definition_ref=parse(row["metric_definition_ref"]),
            eval_contract_ref=parse(row["eval_contract_ref"]),
            eval_report_ref=parse(value("eval_report_ref")),
            baseline_cohort_ref=parse(value("baseline_cohort_ref")),
            treatment_cohort_ref=parse(value("treatment_cohort_ref")),
            exposure_refs=parse(row["exposure_refs"]), metrics=parse(row["metrics"]),
            quality=row["quality"], source_refs=parse(row["source_refs"]),
            cutoff_at=row["cutoff_at"], observed_at=row["observed_at"],
            conclusion=row["conclusion"], limitations=parse(row["limitations"]),
            observation_hash=row["observation_hash"],
        )

    @staticmethod
    def _hash(value) -> str:
        encoded = json.dumps(
            AipMemoryImprovementService._canonical(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode()).hexdigest()

    @staticmethod
    def _canonical(value):
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json", by_alias=True)
        if isinstance(value, dict):
            return {key: AipMemoryImprovementService._canonical(item) for key, item in value.items()}
        if isinstance(value, list):
            return [AipMemoryImprovementService._canonical(item) for item in value]
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        return value

    @staticmethod
    def _optional_json(value):
        return None if value is None else json.dumps(value)

    @staticmethod
    def _require_scope(scope):
        if not scope.org_id.strip() or not scope.project_id.strip():
            raise ValueError("tenant scope is required")
