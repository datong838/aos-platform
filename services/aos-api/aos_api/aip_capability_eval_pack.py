"""Pure helpers for W-D1 EvalPack attachment (no DB)."""

from aos_api.aip_agent_registry_contracts import CapabilityReadiness


def strip_eval_pack_unavailable(reasons: list[str]) -> list[str]:
    return [code for code in reasons if code != "eval_pack_unavailable"]


def definition_readiness(reasons: list[str]) -> CapabilityReadiness:
    return CapabilityReadiness.BLOCKED if reasons else CapabilityReadiness.AVAILABLE
