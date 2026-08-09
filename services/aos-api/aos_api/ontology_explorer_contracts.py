"""O1-UX0 frozen DTOs for tenant-scoped ontology exploration.

These models freeze the public wire contract only. Tenant scope is always
derived from Principal and is deliberately absent from write DTOs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ONTOLOGY_EXPLORER_ERROR_CODES = (
    "TENANT_SCOPE_REQUIRED",
    "TENANT_SCOPE_FORBIDDEN",
    "EXPLORATION_SHARE_FORBIDDEN",
    "EXPLORATION_NOT_FOUND",
    "IDEMPOTENCY_CONFLICT",
    "OBJECT_REFERENCE_UNSTABLE",
    "REVISION_CONFLICT",
    "GRAPH_QUERY_TOO_LARGE",
    "GRAPH_QUERY_INVALID",
    "OBJECT_SET_TYPE_MISMATCH",
    "GRAPH_QUERY_RATE_LIMITED",
    "GRAPH_AUTHORITY_UNAVAILABLE",
    "EXPLORATION_ARCHIVE_REQUIRED",
)

GraphDomain = Literal["domain", "operational_lineage"]
EdgeAuthority = Literal["authoritative", "inferred", "compat_projection"]
SourceAuthority = Literal[
    "ecom_authoritative",
    "operational_authoritative",
    "knowledge_authoritative",
    "compat_projection",
]
KnowledgeSubjectType = Literal[
    "object_type",
    "object_instance",
    "action_type",
    "rule",
    "platform",
    "task_type",
]
ExplorationViewMode = Literal["table", "graph", "annotation"]
ExplorationVisibility = Literal["private", "workspace"]


class FrozenDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExplorationCreateDTO(FrozenDTO):
    name: str = Field(min_length=1, max_length=240)
    objectType: str = Field(min_length=1, max_length=128)
    viewMode: ExplorationViewMode = "table"
    visibility: ExplorationVisibility = "private"
    query: dict[str, object] = Field(default_factory=dict)
    columns: list[dict[str, object]] = Field(default_factory=list, max_length=256)
    graph: dict[str, object] = Field(default_factory=dict)


class ObjectRefDTO(FrozenDTO):
    objectType: str = Field(min_length=1, max_length=128)
    objectId: str = Field(min_length=1, max_length=512)


class LinkRefDTO(FrozenDTO):
    relationType: str = Field(min_length=1, max_length=128)
    source: ObjectRefDTO
    target: ObjectRefDTO


class KnowledgeSubjectRefDTO(FrozenDTO):
    subjectType: KnowledgeSubjectType
    subjectId: str = Field(min_length=1, max_length=512)
    objectRef: ObjectRefDTO | None = None

    @model_validator(mode="after")
    def require_object_ref_for_instance(self) -> "KnowledgeSubjectRefDTO":
        if self.subjectType == "object_instance" and self.objectRef is None:
            raise ValueError("object_instance knowledge subjects require objectRef")
        if self.subjectType != "object_instance" and self.objectRef is not None:
            raise ValueError("objectRef is only valid for object_instance knowledge subjects")
        return self


class TaskRefDTO(FrozenDTO):
    taskId: str = Field(min_length=1, max_length=512)
    revision: int | None = Field(default=None, ge=1)


class EvidenceRefDTO(FrozenDTO):
    evidenceId: str = Field(min_length=1, max_length=512)
    revision: int = Field(ge=1)


class ObjectSetCreateDTO(FrozenDTO):
    name: str = Field(min_length=1, max_length=240)
    objectType: str = Field(min_length=1, max_length=128)
    items: list[ObjectRefDTO] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_one_object_type(self) -> "ObjectSetCreateDTO":
        if any(item.objectType != self.objectType for item in self.items):
            raise ValueError("OBJECT_SET_TYPE_MISMATCH: v1 object sets require one Object Type")
        return self


class GraphSeedDTO(ObjectRefDTO):
    pass


class GraphQueryDTO(FrozenDTO):
    seeds: list[GraphSeedDTO] = Field(min_length=1, max_length=20)
    hops: int = Field(default=1, ge=1, le=5)
    maxNodes: int = Field(default=100, ge=1, le=500)
    direction: Literal["out", "in", "both"] = "both"
    objectTypes: list[str] = Field(default_factory=list, max_length=64)
    relationTypes: list[str] = Field(default_factory=list, max_length=128)
    graphDomains: list[GraphDomain] = Field(default_factory=lambda: ["domain"], min_length=1, max_length=2)
    cursor: str | None = Field(default=None, max_length=2048)


class GraphScopeDTO(FrozenDTO):
    orgId: str = Field(min_length=1)
    workspaceId: str = Field(min_length=1)


class GraphSnapshotMetaDTO(FrozenDTO):
    asOf: str = Field(min_length=1)
    watermark: str = Field(min_length=1)


class GraphNodeDTO(FrozenDTO):
    key: str = Field(min_length=1)
    objectType: str = Field(min_length=1)
    objectId: str = Field(min_length=1)
    label: str
    depth: int = Field(ge=0, le=5)
    masked: bool = True


class GraphValidityDTO(FrozenDTO):
    validFrom: str | None = Field(default=None, max_length=64)
    validUntil: str | None = Field(default=None, max_length=64)


class GraphEdgeDTO(FrozenDTO):
    key: str = Field(min_length=1)
    relationType: str = Field(min_length=1)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    direction: Literal["out", "in"]
    graphDomain: GraphDomain | None = None
    edgeAuthority: EdgeAuthority | None = None
    sourceRevision: str | None = Field(default=None, max_length=512)
    validity: GraphValidityDTO | None = None
    evidenceRefs: list[EvidenceRefDTO] = Field(default_factory=list, max_length=64)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    inferenceBasis: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def require_inference_metadata(self) -> "GraphEdgeDTO":
        if self.edgeAuthority == "inferred" and (
            self.confidence is None or self.inferenceBasis is None
        ):
            raise ValueError("inferred edges require confidence and inferenceBasis")
        return self
class GraphPageDTO(FrozenDTO):
    truncated: bool
    nextCursor: str | None = None


class GraphLimitsDTO(FrozenDTO):
    maxNodes: int = Field(ge=1, le=500)
    maxHops: int = Field(ge=1, le=5)


class GraphSnapshotDTO(FrozenDTO):
    scope: GraphScopeDTO
    sourceAuthority: SourceAuthority
    graphDomain: GraphDomain | None = None
    schemaEtag: str = Field(min_length=1)
    snapshot: GraphSnapshotMetaDTO
    nodes: list[GraphNodeDTO]
    edges: list[GraphEdgeDTO]
    page: GraphPageDTO
    limits: GraphLimitsDTO
