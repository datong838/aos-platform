"""R18 read-only marketplace and deterministic import preview contracts."""
from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext
from aos_api.aip_skill_scan import ScanArtifact, SkillSourceFile


class MarketplaceAgentReadiness(AipContractModel):
    template_id: str
    display_name: str
    installed: bool
    runtime_readiness: str
    blockers: list[str] = Field(default_factory=list)
    repair_href: str
    repair_label: str


class MarketplacePackage(AipContractModel):
    package_id: str
    version: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    display_name: str
    publisher: str
    license: str
    source_ref: ResourceRef
    agent_count: int = Field(ge=0)
    skill_count: int = Field(ge=0)
    capability_count: int = Field(ge=0)
    installed_count: int = Field(ge=0)
    runnable_count: int = Field(ge=0)
    discoverable: bool = True
    install_authorized: bool = False
    agents: list[MarketplaceAgentReadiness] = Field(default_factory=list)


class MarketplaceCatalogResponse(AipContractModel):
    tenant: TenantContext
    items: list[MarketplacePackage]
    count: int = Field(ge=0)


class ImportPreviewKind(StrEnum):
    AGENT = "agent"
    CAPABILITY = "capability"


class ImportEvidenceStatus(StrEnum):
    UNKNOWN = "unknown"
    PASSED = "passed"
    BLOCKED = "blocked"
    EXTERNAL_REQUIRED = "external_required"


class ImportSourceInput(AipContractModel):
    source_ref: ResourceRef
    source_commit: str = Field(pattern=r"^[0-9a-f]{7,64}$")
    license_id: str = Field(min_length=1, max_length=120)
    sbom_ref: ResourceRef
    files: list[SkillSourceFile] = Field(min_length=1, max_length=256)


class ImportMappingInput(AipContractModel):
    target_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)
    tool_mappings: dict[str, str] = Field(default_factory=dict)
    permission_mappings: dict[str, str] = Field(default_factory=dict)
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)

    @field_validator("target_id", "display_name")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        return value.strip()


class ImportSecurityInput(AipContractModel):
    risk_level: str = Field(pattern=r"^(low|medium|high|critical)$")
    network_policy_ref: str | None = Field(default=None, min_length=1, max_length=200)
    secret_ref: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("secret_ref")
    @classmethod
    def _opaque_secret_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned.startswith(("vault://", "secret://", "keychain://")):
            raise ValueError("secretRef must be an opaque secret reference")
        return cleaned


class ImportPreviewRequest(AipContractModel):
    kind: ImportPreviewKind
    source: ImportSourceInput
    mapping: ImportMappingInput
    security: ImportSecurityInput


class ImportStepEvidence(AipContractModel):
    step: str
    status: ImportEvidenceStatus
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    blocker_codes: list[str] = Field(default_factory=list)
    summary: str


class ImportPreviewResponse(AipContractModel):
    tenant: TenantContext
    preview_id: str
    kind: ImportPreviewKind
    status: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    steps: list[ImportStepEvidence]
    scan_artifact: ScanArtifact
    import_job_authority: str = "not_created"
    approval_required: bool = True

    @model_validator(mode="after")
    def _truthful_status(self) -> "ImportPreviewResponse":
        if self.import_job_authority != "not_created":
            raise ValueError("R18 preview must not claim an ImportJob authority")
        blocked = any(step.status is ImportEvidenceStatus.BLOCKED for step in self.steps)
        expected = "blocked" if blocked else "external_required"
        if self.status != expected:
            raise ValueError("preview status does not match evidence")
        return self


__all__ = [
    "ImportEvidenceStatus",
    "ImportMappingInput",
    "ImportPreviewKind",
    "ImportPreviewRequest",
    "ImportPreviewResponse",
    "ImportSecurityInput",
    "ImportSourceInput",
    "ImportStepEvidence",
    "MarketplaceAgentReadiness",
    "MarketplaceCatalogResponse",
    "MarketplacePackage",
]
