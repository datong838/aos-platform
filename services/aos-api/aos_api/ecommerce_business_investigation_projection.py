"""BI-W4-08 rebuildable read model for one business investigation Run."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol, Self

import psycopg
from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.ecommerce_business_investigation_artifact import (
    BusinessInvestigationArtifactBinding,
    BusinessInvestigationArtifactType,
)
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunControl,
    BusinessInvestigationRunLifecycle,
    BusinessInvestigationRunRecord,
    BusinessInvestigationRunStateRevision,
    BusinessInvestigationUncertainCommand,
)
from aos_api.tenant_scope import TenantScope


PROJECTION_SCHEMA = "aos.ecommerce.business-investigation-workbench-view/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


class BusinessInvestigationArtifactSlot(AipContractModel):
    artifact_type: BusinessInvestigationArtifactType
    status: Literal["bound", "missing"]
    artifact_ref: InvestigationExactRef | None = None
    binding_id: str | None = Field(default=None, min_length=1, max_length=200)
    binding_hash: str | None = Field(default=None, pattern=SHA256)
    selection_revision: int | None = Field(default=None, ge=1)
    data_cutoff: datetime | None = None
    lineage_ref: InvestigationExactRef | None = None

    @field_validator("data_cutoff")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("artifact slot dataCutoff must include timezone")
        return value

    @model_validator(mode="after")
    def _honest_status(self) -> Self:
        values = (
            self.artifact_ref,
            self.binding_id,
            self.binding_hash,
            self.selection_revision,
            self.data_cutoff,
            self.lineage_ref,
        )
        if self.status == "missing" and any(item is not None for item in values):
            raise ValueError("missing artifact slot cannot expose stale binding data")
        if self.status == "bound":
            if any(item is None for item in values):
                raise ValueError("bound artifact slot requires exact binding data")
            if self.artifact_ref is None or self.artifact_ref.resource_type != self.artifact_type.value:
                raise ValueError("artifact slot type must match artifactRef")
        return self


class BusinessInvestigationSourceWatermark(AipContractModel):
    case_revision: int = Field(ge=1)
    run_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    binding_hashes: list[str] = Field(default_factory=list, max_length=4)
    content_hash: str = Field(pattern=SHA256)

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        if self.binding_hashes != sorted(set(self.binding_hashes)):
            raise ValueError("source watermark binding hashes must be unique and sorted")
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("contentHash")
        if self.content_hash != _canonical_hash(value):
            raise ValueError("source watermark contentHash drifted")
        return self


class BusinessInvestigationWorkbenchView(AipContractModel):
    schema_version: Literal[PROJECTION_SCHEMA] = PROJECTION_SCHEMA
    tenant: TenantContext
    projection_hash: str = Field(pattern=SHA256)
    source_watermark: BusinessInvestigationSourceWatermark
    observed_at: datetime
    case_ref: InvestigationExactRef
    run_ref: InvestigationExactRef
    state_ref: InvestigationExactRef
    lifecycle: BusinessInvestigationRunLifecycle
    control: BusinessInvestigationRunControl
    pending_requirement_ref: InvestigationExactRef | None = None
    uncertain_command: BusinessInvestigationUncertainCommand | None = None
    artifacts: list[BusinessInvestigationArtifactSlot] = Field(min_length=4, max_length=4)

    @field_validator("observed_at")
    @classmethod
    def _observed_at(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("observedAt must include timezone")
        return value

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if [item.artifact_type for item in self.artifacts] != list(BusinessInvestigationArtifactType):
            raise ValueError("artifact slots require canonical order")
        expected = (
            (self.case_ref, "BusinessInvestigationCaseRevision"),
            (self.run_ref, "BusinessInvestigationRun"),
            (self.state_ref, "BusinessInvestigationRunStateRevision"),
        )
        if any(ref.resource_type != resource_type for ref, resource_type in expected):
            raise ValueError("workbench view exact ref type drifted")
        if self.run_ref.resource_id != self.state_ref.resource_id:
            raise ValueError("Run and state refs must retain identity")
        if self.source_watermark.case_revision != self.case_ref.revision:
            raise ValueError("case watermark drifted")
        if self.source_watermark.run_version != self.run_ref.revision:
            raise ValueError("Run watermark drifted")
        if self.source_watermark.state_version != self.state_ref.revision:
            raise ValueError("state watermark drifted")
        if self.projection_hash != self.calculated_projection_hash():
            raise ValueError("projectionHash drifted")
        return self

    def calculated_projection_hash(self) -> str:
        payload = self.model_dump(by_alias=True, mode="json")
        payload.pop("projectionHash")
        payload.pop("observedAt")
        return _canonical_hash(payload)


@dataclass(frozen=True, slots=True)
class BusinessInvestigationProjectionSource:
    case: BusinessInvestigationCaseRevision
    run: BusinessInvestigationRunRecord
    state: BusinessInvestigationRunStateRevision
    bindings: tuple[BusinessInvestigationArtifactBinding, ...] = ()


class BusinessInvestigationProjectionReader(Protocol):
    def read(self, scope: TenantScope, run_id: str) -> BusinessInvestigationProjectionSource: ...


class BusinessInvestigationProjectionError(RuntimeError):
    pass


class BusinessInvestigationProjectionNotFound(BusinessInvestigationProjectionError):
    pass


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class CanonicalBusinessInvestigationProjectionReader:
    """Read canonical heads and bindings without persisting a projection."""

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def read(self, scope: TenantScope, run_id: str) -> BusinessInvestigationProjectionSource:
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT c.authority_data AS case_authority,
                              r.authority_data AS run_authority,
                              s.authority_data AS state_authority
                       FROM ecommerce_investigation_run r
                       JOIN ecommerce_investigation_run_state_head s
                         ON s.org_id=r.org_id AND s.project_id=r.project_id AND s.run_id=r.run_id
                       JOIN ecommerce_investigation_case_head h
                         ON h.org_id=r.org_id AND h.project_id=r.project_id AND h.case_id=r.case_id
                       JOIN ecommerce_investigation_case_revision c
                         ON c.org_id=h.org_id AND c.project_id=h.project_id
                        AND c.case_id=h.case_id AND c.revision=h.current_revision
                       WHERE r.org_id=%s AND r.project_id=%s AND r.run_id=%s""",
                    (*scope.key, run_id),
                ).fetchone()
                if row is None:
                    raise BusinessInvestigationProjectionNotFound(
                        "BusinessInvestigationRun projection source is not visible"
                    )
                binding_rows = conn.execute(
                    """SELECT DISTINCT ON (artifact_type) binding_data
                       FROM ecommerce_investigation_artifact_binding
                       WHERE org_id=%s AND project_id=%s AND run_id=%s
                       ORDER BY artifact_type,selection_revision DESC,
                                artifact_revision DESC,bound_at DESC,binding_id DESC""",
                    (*scope.key, run_id),
                ).fetchall()
        except BusinessInvestigationProjectionNotFound:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise BusinessInvestigationProjectionError(
                "canonical Workbench projection read failed closed"
            ) from exc
        try:
            return BusinessInvestigationProjectionSource(
                case=BusinessInvestigationCaseRevision.model_validate(row["case_authority"]),
                run=BusinessInvestigationRunRecord.model_validate(row["run_authority"]),
                state=BusinessInvestigationRunStateRevision.model_validate(row["state_authority"]),
                bindings=tuple(
                    BusinessInvestigationArtifactBinding.model_validate(item["binding_data"])
                    for item in binding_rows
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BusinessInvestigationProjectionError(
                "canonical Workbench projection contract failed closed"
            ) from exc


class BusinessInvestigationProjectionBuilder:
    def __init__(self, reader: BusinessInvestigationProjectionReader) -> None:
        self._reader = reader

    def build(
        self, scope: TenantScope, run_id: str, *, observed_at: datetime
    ) -> BusinessInvestigationWorkbenchView:
        source = self._reader.read(scope, run_id)
        self._validate_source(source, scope=scope, run_id=run_id)
        bindings = {item.artifact_ref.resource_type: item for item in source.bindings}
        artifacts = [self._slot(kind, bindings.get(kind.value)) for kind in BusinessInvestigationArtifactType]
        binding_hashes = sorted(item.binding_hash for item in source.bindings)
        watermark_value = {
            "caseRevision": source.case.revision,
            "runVersion": source.run.version,
            "stateVersion": source.state.version,
            "bindingHashes": binding_hashes,
        }
        watermark = BusinessInvestigationSourceWatermark.model_validate(
            {**watermark_value, "contentHash": _canonical_hash(watermark_value)}
        )
        draft = BusinessInvestigationWorkbenchView.model_construct(
            schema_version=PROJECTION_SCHEMA,
            tenant=source.case.tenant,
            projection_hash="sha256:" + "0" * 64,
            source_watermark=watermark,
            observed_at=observed_at,
            case_ref=InvestigationExactRef.model_validate(
                self._ref(
                    "BusinessInvestigationCaseRevision",
                    source.case.case_id,
                    source.case.revision,
                    source.case.content_hash,
                )
            ),
            run_ref=InvestigationExactRef.model_validate(
                self._ref(
                    "BusinessInvestigationRun",
                    source.run.run_id,
                    source.run.version,
                    source.run.content_hash,
                )
            ),
            state_ref=InvestigationExactRef.model_validate(
                self._ref(
                    "BusinessInvestigationRunStateRevision",
                    source.state.run_id,
                    source.state.version,
                    source.state.content_hash,
                )
            ),
            lifecycle=source.state.lifecycle,
            control=source.state.control,
            pending_requirement_ref=source.state.pending_requirement_ref,
            uncertain_command=source.state.uncertain_command,
            artifacts=artifacts,
        )
        payload = draft.model_dump(by_alias=True, mode="json")
        payload["projectionHash"] = draft.calculated_projection_hash()
        return BusinessInvestigationWorkbenchView.model_validate(payload)

    @staticmethod
    def _ref(resource_type: str, resource_id: str, revision: int, content_hash: str) -> dict[str, Any]:
        return {
            "resourceType": resource_type,
            "resourceId": resource_id,
            "revision": revision,
            "contentHash": content_hash,
        }

    @staticmethod
    def _slot(
        kind: BusinessInvestigationArtifactType,
        binding: BusinessInvestigationArtifactBinding | None,
    ) -> BusinessInvestigationArtifactSlot:
        if binding is None:
            return BusinessInvestigationArtifactSlot(artifact_type=kind, status="missing")
        return BusinessInvestigationArtifactSlot(
            artifact_type=kind,
            status="bound",
            artifact_ref=binding.artifact_ref,
            binding_id=binding.binding_id,
            binding_hash=binding.binding_hash,
            selection_revision=binding.selection_revision,
            data_cutoff=binding.data_cutoff,
            lineage_ref=binding.lineage_ref,
        )

    @staticmethod
    def _validate_source(
        source: BusinessInvestigationProjectionSource, *, scope: TenantScope, run_id: str
    ) -> None:
        tenant = (source.case.tenant.org_id, source.case.tenant.project_id)
        if tenant != scope.key or any(
            (item.tenant.org_id, item.tenant.project_id) != scope.key
            for item in (source.run, source.state, *source.bindings)
        ):
            raise BusinessInvestigationProjectionError("projection source tenant drifted")
        if source.run.run_id != run_id or source.state.run_id != run_id:
            raise BusinessInvestigationProjectionError("projection source Run identity drifted")
        if source.run.case_ref.resource_id != source.case.case_id:
            raise BusinessInvestigationProjectionError("projection source Case identity drifted")
        types = [item.artifact_ref.resource_type for item in source.bindings]
        if len(types) != len(set(types)) or any(
            item.run_ref.resource_id != run_id
            or item.case_ref.resource_id != source.case.case_id
            for item in source.bindings
        ):
            raise BusinessInvestigationProjectionError("projection artifact binding drifted")


__all__ = [
    "BusinessInvestigationArtifactSlot",
    "BusinessInvestigationProjectionBuilder",
    "BusinessInvestigationProjectionError",
    "BusinessInvestigationProjectionNotFound",
    "BusinessInvestigationProjectionReader",
    "BusinessInvestigationProjectionSource",
    "BusinessInvestigationSourceWatermark",
    "BusinessInvestigationWorkbenchView",
    "CanonicalBusinessInvestigationProjectionReader",
    "PROJECTION_SCHEMA",
]
