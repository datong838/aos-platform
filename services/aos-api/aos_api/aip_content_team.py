"""Canonical content-officer responsibility and draft-only production plan."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aos_api.aip_platform_harness import evaluate_harness, load_platform_harnesses

_EXACT_REF = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*:[^@#]+@[^#]+#[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ContentResponsibility:
    key: str
    name: str
    kind: str
    logic_ids: tuple[str, ...]
    executes_tools: bool
    forbidden_actions: tuple[str, ...]


RESPONSIBILITIES: tuple[ContentResponsibility, ...] = (
    ContentResponsibility("coordinator", "内容总监", "coordinator_profile", ("C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"), False, ("tts", "ffmpeg", "publish", "live_push")),
    ContentResponsibility("strategy", "策略", "shared", ("C01", "C02"), False, ("fabricate_fact",)),
    ContentResponsibility("copy_script", "脚本与文案", "shared", ("C03", "C04"), False, ("final_approval",)),
    ContentResponsibility("title", "标题", "shared_alias", ("C03",), False, ("medical_claim", "new_capability")),
    ContentResponsibility("voice", "配音", "specialist", (), True, ("platform_account",)),
    ContentResponsibility("composition", "合成", "specialist", (), True, ("unlicensed_asset",)),
    ContentResponsibility("audit", "审核", "specialist", ("C06",), False, ("relax_hard_gate",)),
    ContentResponsibility("live", "直播编排", "scene", (), False, ("unattended_live",)),
    ContentResponsibility("platform", "平台适配", "scene", ("C05", "C07"), False, ("publish", "boost", "private_message")),
    ContentResponsibility("review", "数据复盘", "scene", ("C08",), False, ("unsupported_attribution", "memory_promote")),
)

LOGIC_CROSSWALK: dict[str, tuple[str, str]] = {
    "C01": ("strategy", "ContentOpportunityPool.DRAFT"),
    "C02": ("strategy", "ContentStrategyDraft.DRAFT"),
    "C03": ("copy_script", "ContentVariantDraft.DRAFT"),
    "C04": ("copy_script", "VideoScriptDraft.DRAFT"),
    "C05": ("platform", "PlatformContentVariantDraft.DRAFT"),
    "C06": ("audit", "ContentApprovalPackage.DRAFT"),
    "C07": ("platform", "LeadSignalHandoffDraft.DRAFT"),
    "C08": ("review", "ContentEffectReviewDraft.DRAFT"),
}

STAGE_ORDER = ("strategy", "copy_script_title", "audit", "platform", "lead_handoff", "review")


class ContentTextPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    product_ref: str = Field(alias="productRef")
    fact_pack_ref: str = Field(alias="factPackRef")
    brief_ref: str = Field(alias="briefRef")
    evidence_bundle_ref: str = Field(alias="evidenceBundleRef")
    source_draft_ref: str | None = Field(default=None, alias="sourceDraftRef")
    eval_report_ref: str | None = Field(default=None, alias="evalReportRef")
    lineage_ref: str | None = Field(default=None, alias="lineageRef")
    harness_ids: tuple[str, ...] = Field(default=(), alias="harnessIds")
    harness_contexts: dict[str, dict[str, Any]] = Field(default_factory=dict, alias="harnessContexts")
    requested_action: Literal["create_draft", "publish"] = Field(default="create_draft", alias="requestedAction")
    c02_pilot_ref: str | None = Field(default=None, alias="c02PilotRef")

    @field_validator(
        "product_ref", "fact_pack_ref", "brief_ref", "evidence_bundle_ref",
        "source_draft_ref", "eval_report_ref", "lineage_ref", "c02_pilot_ref",
    )
    @classmethod
    def exact_refs(cls, value: str | None) -> str | None:
        if value is not None and not _EXACT_REF.fullmatch(value):
            raise ValueError("exact revision/hash ref required")
        return value


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def build_content_team_catalog() -> dict[str, Any]:
    payload = {
        "agentRole": "ecommerce.content_officer",
        "coordinatorIsProfile": True,
        "responsibilities": [asdict(item) for item in RESPONSIBILITIES],
        "logicCrosswalk": LOGIC_CROSSWALK,
        "stageOrder": STAGE_ORDER,
        "sharedCapabilityCountDelta": 0,
        "digitalCoworkerCountDelta": 0,
    }
    return {**payload, "contentHash": _hash(payload)}


def build_content_text_plan(request: ContentTextPlanRequest) -> dict[str, Any]:
    catalog = load_platform_harnesses()
    blockers: list[str] = []
    decisions = []
    if request.requested_action == "publish":
        blockers.append("CONTENT_PLATFORM_WRITE_DEFERRED_G5_G6")
    for harness_id in request.harness_ids:
        harness = catalog.get(harness_id)
        context = dict(request.harness_contexts.get(harness_id) or {})
        context.setdefault("requestedAction", request.requested_action)
        decision = evaluate_harness(harness, context)
        decisions.append(asdict(decision))
        blockers.extend(decision.blocker_codes)
    if request.source_draft_ref is None:
        blockers.append("CONTENT_SOURCE_DRAFT_REQUIRED")
    if request.eval_report_ref is None:
        blockers.append("CONTENT_EVAL_REPORT_REQUIRED")
    if request.lineage_ref is None:
        blockers.append("CONTENT_LINEAGE_REQUIRED")
    steps = [
        {"stage": "strategy", "logicIds": ["C01", "C02"], "sideEffect": False},
        {"stage": "copy_script_title", "logicIds": ["C03", "C04"], "sideEffect": False},
        {"stage": "audit", "logicIds": ["C06"], "sideEffect": False},
        {"stage": "platform", "logicIds": ["C05"], "sideEffect": False},
        {"stage": "lead_handoff", "logicIds": ["C07"], "sideEffect": False, "optional": True},
        {"stage": "review", "logicIds": ["C08"], "sideEffect": False, "deferredUntilOutcomeWindowClosed": True},
    ]
    unique_blockers = tuple(dict.fromkeys(blockers))
    status = "draft_ready" if not unique_blockers else (
        "deferred_g5_g6" if unique_blockers == ("CONTENT_PLATFORM_WRITE_DEFERRED_G5_G6",) else "blocked"
    )
    body = {
        "status": status,
        "productRef": request.product_ref,
        "factPackRef": request.fact_pack_ref,
        "briefRef": request.brief_ref,
        "evidenceBundleRef": request.evidence_bundle_ref,
        "sourceDraftRef": request.source_draft_ref,
        "evalReportRef": request.eval_report_ref,
        "lineageRef": request.lineage_ref,
        "c02PilotRef": request.c02_pilot_ref,
        "steps": steps,
        "harnessManifestRef": f"registry://aip/content/harness/{catalog.manifest_version}#{catalog.content_hash}",
        "harnessDecisions": decisions,
        "blockerCodes": unique_blockers,
        "providerCalls": 0,
        "platformWrites": 0,
        "mediaJobs": 0,
        "avatarSessions": 0,
        "memoryPromotions": 0,
    }
    return {**body, "planHash": _hash(body)}


__all__ = [
    "ContentTextPlanRequest", "LOGIC_CROSSWALK", "RESPONSIBILITIES", "STAGE_ORDER",
    "build_content_team_catalog", "build_content_text_plan",
]
