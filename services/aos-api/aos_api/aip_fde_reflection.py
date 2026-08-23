"""Versioned declarative Reflection rules for the six-step FDE chain."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Callable

RULE_SET_REF = "registry://aip/fde/reflection/1.0.0"


class ReflectionKind(StrEnum):
    HARD = "hard"
    SOFT = "soft"


@dataclass(frozen=True, slots=True)
class ReflectionRule:
    rule_key: str
    skill_key: str
    severity: str
    kind: ReflectionKind
    predicate: str
    fail_action: str
    checkpoint_target: str | None = None


def _r(
    rule_key: str,
    skill_key: str,
    predicate: str,
    *,
    kind: ReflectionKind = ReflectionKind.HARD,
    severity: str = "high",
    fail_action: str = "pause",
    checkpoint_target: str | None = None,
) -> ReflectionRule:
    return ReflectionRule(rule_key, skill_key, severity, kind, predicate, fail_action, checkpoint_target)


REFLECTION_RULES: tuple[ReflectionRule, ...] = (
    _r("s1.requirement_present", "fde.s1.requirement", "requirement_present"),
    _r("s1.platform_registered", "fde.s1.requirement", "platform_registered"),
    _r("s1.data_types_present", "fde.s1.requirement", "data_types_present"),
    _r("s1.inline_secret_absent", "fde.s1.requirement", "inline_secret_absent", severity="critical", fail_action="block"),
    _r("s2.secret_ref_opaque", "fde.s2.auth-draft", "secret_ref_opaque", severity="critical", fail_action="block"),
    _r("s2.auth_scheme_present", "fde.s2.auth-draft", "auth_scheme_present"),
    _r("s2.secret_payload_absent", "fde.s2.auth-draft", "secret_payload_absent", severity="critical", fail_action="block"),
    _r("s3.required_capabilities_present", "fde.s3.capability-probe", "required_capabilities_present"),
    _r("s3.schema_refs_exact", "fde.s3.capability-probe", "schema_refs_exact"),
    _r("s3.adapter_version_exact", "fde.s3.capability-probe", "adapter_version_exact"),
    _r("s3.online_limits_reviewed", "fde.s3.capability-probe", "soft_approval", kind=ReflectionKind.SOFT, severity="medium", fail_action="external_review"),
    _r("s4.coverage_check", "fde.s4.mapping-proposal", "coverage_threshold", checkpoint_target="CP3"),
    _r("s4.required_target_fields_check", "fde.s4.mapping-proposal", "required_target_fields"),
    _r("s4.no_conflicting_mappings", "fde.s4.mapping-proposal", "no_mapping_conflicts"),
    _r("s4.transform_allowlisted", "fde.s4.mapping-proposal", "transforms_allowlisted", severity="critical", fail_action="block"),
    _r("s4.confidence_review", "fde.s4.mapping-proposal", "soft_approval", kind=ReflectionKind.SOFT, severity="medium", fail_action="external_review"),
    _r("s4.episodic_difference_review", "fde.s4.mapping-proposal", "soft_approval", kind=ReflectionKind.SOFT, severity="low", fail_action="external_review"),
    _r("s5.sync_strategy_allowlisted", "fde.s5.controlled-sync", "sync_strategy_allowlisted", checkpoint_target="CP4"),
    _r("s5.side_effect_authorized", "fde.s5.controlled-sync", "side_effect_authorized", severity="critical", fail_action="block"),
    _r("s5.first_sync_evidenced", "fde.s5.controlled-sync", "first_sync_evidenced", checkpoint_target="CP4"),
    _r("s5.record_count_review", "fde.s5.controlled-sync", "soft_approval", kind=ReflectionKind.SOFT, severity="medium", fail_action="external_review"),
    _r("s6.freshness_pass", "fde.s6.validation", "freshness_pass", checkpoint_target="CP5"),
    _r("s6.schema_consistent", "fde.s6.validation", "schema_consistent", checkpoint_target="CP5"),
    _r("s6.quality_pass", "fde.s6.validation", "quality_pass", checkpoint_target="CP5"),
    _r("s6.primary_key_unique", "fde.s6.validation", "primary_key_unique", checkpoint_target="CP5"),
    _r("s6.reconciliation_review", "fde.s6.validation", "soft_approval", kind=ReflectionKind.SOFT, severity="medium", fail_action="external_review"),
)

RULE_SET_HASH = hashlib.sha256(
    json.dumps([asdict(rule) for rule in REFLECTION_RULES], ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
).hexdigest()

_OPAQUE_SECRET = re.compile(r"^(?:keychain|secret|vault)://")


def _non_blank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


_PREDICATES: dict[str, Callable[[dict[str, Any]], bool]] = {
    "requirement_present": lambda c: _non_blank(c.get("requirement")),
    "platform_registered": lambda c: c.get("platform") in {"niushop"},
    "data_types_present": lambda c: isinstance(c.get("dataTypes"), list) and bool(c["dataTypes"]),
    "inline_secret_absent": lambda c: c.get("inlineSecretDetected") is False,
    "secret_ref_opaque": lambda c: isinstance(c.get("secretRef"), str) and bool(_OPAQUE_SECRET.match(c["secretRef"])),
    "auth_scheme_present": lambda c: _non_blank(c.get("authScheme")),
    "secret_payload_absent": lambda c: c.get("secretPayloadRead") is False,
    "required_capabilities_present": lambda c: c.get("missingDataTypes") == [],
    "schema_refs_exact": lambda c: isinstance(c.get("schemaRefs"), list) and bool(c["schemaRefs"]) and all(_non_blank(row.get("contentHash")) for row in c["schemaRefs"]),
    "adapter_version_exact": lambda c: c.get("adapterPackRef") == "platform.ecommerce.niushop@1.0.0",
    "coverage_threshold": lambda c: isinstance(c.get("coverage"), (int, float)) and c["coverage"] >= 0.8,
    "required_target_fields": lambda c: c.get("requiredTargetsPresent") is True,
    "no_mapping_conflicts": lambda c: c.get("mappingConflicts") == [],
    "transforms_allowlisted": lambda c: c.get("unsupportedTypes") == [] and c.get("expressionExecution") is False,
    "sync_strategy_allowlisted": lambda c: c.get("syncStrategy") in {"watermark", "full", "snapshot", "cursor"},
    "side_effect_authorized": lambda c: c.get("sideEffectAuthorized") is True,
    "first_sync_evidenced": lambda c: c.get("firstSyncStatus") == "succeeded" and _non_blank(c.get("firstSyncReceiptRef")),
    "freshness_pass": lambda c: c.get("freshnessStatus") == "pass",
    "schema_consistent": lambda c: c.get("schemaStatus") == "pass",
    "quality_pass": lambda c: c.get("qualityStatus") == "pass",
    "primary_key_unique": lambda c: c.get("duplicateCount") == 0,
}


def evaluate_reflection(skill_key: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate hard rules explicitly; soft rules require an exact approval fact."""
    approvals = context.get("softApprovals") if isinstance(context.get("softApprovals"), dict) else {}
    results: list[dict[str, Any]] = []
    for rule in REFLECTION_RULES:
        if rule.skill_key != skill_key:
            continue
        if rule.kind is ReflectionKind.SOFT:
            passed = approvals.get(rule.rule_key) is True
            status = "passed" if passed else "external_required"
        else:
            predicate = _PREDICATES[rule.predicate]
            passed = bool(predicate(context))
            status = "passed" if passed else "failed"
        results.append(
            {
                "ruleKey": rule.rule_key,
                "kind": rule.kind.value,
                "status": status,
                "severity": rule.severity,
                "failAction": rule.fail_action,
                "checkpointTarget": rule.checkpoint_target,
            }
        )
    return results
