"""Versioned, draft-only platform Harness definitions for ecommerce content.

This module loads declarative manifests and evaluates only local governance
facts. It never calls a platform, browser, Provider, Action or secret backend.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MANIFEST_PATH = (
    Path(__file__).resolve().parents[3]
    / "bundles/solutions/ecommerce-growth/content/harness/platform-harnesses.v1.json"
)
EXPECTED_IDS = (
    "DY-01", "DY-02", "DY-03", "DY-04", "DY-05",
    "KS-01", "KS-02", "KS-03",
    "SPH-01", "SPH-02", "SPH-03",
    "XHS-01", "XHS-02", "XHS-03",
)
ALLOWED_MODES = frozenset({"read_only", "draft_only", "proposal_only"})
WRITE_ACTIONS = frozenset(
    {
        "publish", "boost", "comment", "reply_comment", "private_message",
        "live_push", "invite_creator", "set_commission", "mini_program_write",
        "enterprise_wechat_write", "export_pii", "fabricate_experience",
    }
)
_EXACT_REF = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*:[^@#]+@[^#]+#[0-9a-f]{64}$")
_INJECTION = re.compile(
    r"(?:ignore\s+(?:all\s+)?previous|reveal\s+(?:the\s+)?system\s+prompt|"
    r"jailbreak|忽略(?:以上|之前)|泄露系统提示词)", re.IGNORECASE
)


class HarnessManifestError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RuleAuthority:
    source_status: str
    source_ref: str | None
    effective_at: datetime | None
    review_at: datetime | None
    content_hash: str | None


@dataclass(frozen=True, slots=True)
class PlatformHarness:
    harness_id: str
    platform_id: str
    name: str
    version: str
    logic_id: str
    output_contract: str
    risk_level: str
    required_inputs: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    allowed_modes: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    rule_authority: RuleAuthority
    eval_cases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HarnessCatalog:
    manifest_version: str
    schema_version: str
    content_hash: str
    harnesses: tuple[PlatformHarness, ...]

    def get(self, harness_id: str) -> PlatformHarness:
        for item in self.harnesses:
            if item.harness_id == harness_id:
                return item
        raise HarnessManifestError(f"unknown harness: {harness_id}")


@dataclass(frozen=True, slots=True)
class HarnessDecision:
    harness_id: str
    status: str
    blocker_codes: tuple[str, ...]
    output_contract: str
    external_side_effect: bool = False


def _parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HarnessManifestError("rule authority timestamp must be an ISO string")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise HarnessManifestError("rule authority timestamp must include timezone")
    return result


def _strict_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise HarnessManifestError(
            f"{label} keys drifted: missing={sorted(expected - set(value))}, "
            f"extra={sorted(set(value) - expected)}"
        )


def load_platform_harnesses(path: Path = MANIFEST_PATH) -> HarnessCatalog:
    raw = json.loads(path.read_text(encoding="utf-8"))
    _strict_keys(raw, {"manifestVersion", "schemaVersion", "harnesses"}, "manifest")
    if raw["schemaVersion"] != "aos.content.platform-harness/v1":
        raise HarnessManifestError("unsupported platform Harness schema")
    definitions: list[PlatformHarness] = []
    item_keys = {
        "harnessId", "platformId", "name", "version", "logicId",
        "outputContract", "riskLevel", "requiredInputs", "requiredCapabilities",
        "allowedModes", "forbiddenActions", "ruleAuthority", "evalCases",
    }
    authority_keys = {"sourceStatus", "sourceRef", "effectiveAt", "reviewAt", "contentHash"}
    for index, item in enumerate(raw["harnesses"]):
        _strict_keys(item, item_keys, f"harness[{index}]")
        authority = item["ruleAuthority"]
        _strict_keys(authority, authority_keys, f"harness[{index}].ruleAuthority")
        modes = tuple(item["allowedModes"])
        forbidden = tuple(item["forbiddenActions"])
        if not modes or not set(modes) <= ALLOWED_MODES:
            raise HarnessManifestError(f"{item['harnessId']} has unsafe mode")
        if not {"publish", "private_message", "live_push"} <= set(forbidden):
            raise HarnessManifestError(f"{item['harnessId']} write boundary is incomplete")
        if len(set(item["evalCases"])) < 5 or "prompt_injection" not in item["evalCases"]:
            raise HarnessManifestError(f"{item['harnessId']} Eval coverage is incomplete")
        definitions.append(
            PlatformHarness(
                harness_id=item["harnessId"], platform_id=item["platformId"],
                name=item["name"], version=item["version"], logic_id=item["logicId"],
                output_contract=item["outputContract"], risk_level=item["riskLevel"],
                required_inputs=tuple(item["requiredInputs"]),
                required_capabilities=tuple(item["requiredCapabilities"]),
                allowed_modes=modes, forbidden_actions=forbidden,
                rule_authority=RuleAuthority(
                    source_status=authority["sourceStatus"],
                    source_ref=authority["sourceRef"],
                    effective_at=_parse_time(authority["effectiveAt"]),
                    review_at=_parse_time(authority["reviewAt"]),
                    content_hash=authority["contentHash"],
                ),
                eval_cases=tuple(item["evalCases"]),
            )
        )
    ids = tuple(item.harness_id for item in definitions)
    if ids != EXPECTED_IDS:
        raise HarnessManifestError(f"Harness ids/order drifted: {ids}")
    payload = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return HarnessCatalog(
        manifest_version=raw["manifestVersion"], schema_version=raw["schemaVersion"],
        content_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        harnesses=tuple(definitions),
    )


def evaluate_harness(
    harness: PlatformHarness,
    context: dict[str, Any],
    *,
    now: datetime | None = None,
) -> HarnessDecision:
    blockers: list[str] = []
    requested_action = str(context.get("requestedAction") or "create_draft")
    if requested_action in WRITE_ACTIONS or requested_action in harness.forbidden_actions:
        return HarnessDecision(
            harness.harness_id, "deferred_g5_g6", ("HARNESS_WRITE_ACTION_DEFERRED",),
            harness.output_contract,
        )
    summary = str(context.get("summary") or "")
    if _INJECTION.search(summary):
        blockers.append("HARNESS_PROMPT_INJECTION_BLOCKED")
    for key in harness.required_inputs:
        value = context.get(key)
        if not isinstance(value, str) or not _EXACT_REF.fullmatch(value):
            blockers.append(f"HARNESS_REQUIRED_EXACT_REF_MISSING:{key}")
    if blockers:
        return HarnessDecision(harness.harness_id, "blocked", tuple(blockers), harness.output_contract)
    authority = harness.rule_authority
    if (
        authority.source_status != "verified"
        or not authority.source_ref
        or not authority.content_hash
        or authority.effective_at is None
        or authority.review_at is None
    ):
        blockers.append("HARNESS_RULE_AUTHORITY_UNVERIFIED")
    else:
        checked_at = now or datetime.now(UTC)
        if checked_at < authority.effective_at or checked_at >= authority.review_at:
            blockers.append("HARNESS_RULE_AUTHORITY_STALE")
    capability_states = context.get("capabilityStates")
    if not isinstance(capability_states, dict) or any(
        capability_states.get(key) != "available" for key in harness.required_capabilities
    ):
        blockers.append("HARNESS_CAPABILITY_UNKNOWN")
    if blockers:
        status = "blocked" if "HARNESS_RULE_AUTHORITY_STALE" in blockers else "unknown"
        return HarnessDecision(harness.harness_id, status, tuple(blockers), harness.output_contract)
    return HarnessDecision(harness.harness_id, "draft_ready", (), harness.output_contract)


__all__ = [
    "EXPECTED_IDS", "HarnessCatalog", "HarnessDecision", "HarnessManifestError",
    "PlatformHarness", "RuleAuthority", "evaluate_harness", "load_platform_harnesses",
]
