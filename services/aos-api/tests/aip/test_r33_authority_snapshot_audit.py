from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "aip" / "audit_r33_authority_snapshot.py"
    spec = importlib.util.spec_from_file_location("audit_r33_authority_snapshot", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tenant(*, ready: int, installed: int, runnable: int, bindings: int) -> dict:
    return {
        "sourceReadiness": {"sourceCount": 12, "statusCounts": {"ready": ready}},
        "agentRuntime": {
            "stats": {
                "definitionCount": 6,
                "installedCount": installed,
                "runnableCount": runnable,
            }
        },
        "authorityCounts": {
            "tableCounts": {
                "aip_agent_instance": installed,
                "aip_skill_binding": bindings,
                "aip_capability_binding": bindings,
            }
        },
    }


def test_classify_gates_requires_exact_positive_and_empty_canary() -> None:
    module = _load_module()
    gates = module.classify_gates(
        positive=_tenant(ready=12, installed=6, runnable=6, bindings=37),
        negative=_tenant(ready=0, installed=0, runnable=0, bindings=0),
    )

    assert gates == {
        "negativeCanaryIsolated": True,
        "sourceReadiness12of12": True,
        "sixAgentsRunnable": True,
    }


def test_classify_gates_fails_closed_for_partial_readiness_and_canary_binding() -> None:
    module = _load_module()
    gates = module.classify_gates(
        positive=_tenant(ready=10, installed=6, runnable=0, bindings=37),
        negative=_tenant(ready=0, installed=0, runnable=0, bindings=1),
    )

    assert gates == {
        "negativeCanaryIsolated": False,
        "sourceReadiness12of12": False,
        "sixAgentsRunnable": False,
    }


def test_classify_verdict_is_green_only_when_every_gate_is_true() -> None:
    module = _load_module()

    assert module.classify_verdict(
        {
            "negativeCanaryIsolated": True,
            "sourceReadiness12of12": True,
            "sixAgentsRunnable": True,
        }
    ) == "OPERATIONAL_GREEN"


def test_classify_verdict_fails_closed_when_any_gate_is_false() -> None:
    module = _load_module()

    for blocked_gate in (
        "negativeCanaryIsolated",
        "sourceReadiness12of12",
        "sixAgentsRunnable",
    ):
        gates = {
            "negativeCanaryIsolated": True,
            "sourceReadiness12of12": True,
            "sixAgentsRunnable": True,
        }
        gates[blocked_gate] = False
        assert (
            module.classify_verdict(gates)
            == "CODE_API_GREEN_OPERATIONAL_BLOCKED"
        )


def test_operational_gate_exit_code_keeps_default_audit_compatible() -> None:
    module = _load_module()

    assert module.operational_gate_exit_code(
        verdict="CODE_API_GREEN_OPERATIONAL_BLOCKED",
        require_operational_green=False,
    ) == 0


def test_operational_gate_exit_code_allows_exact_green_in_strict_mode() -> None:
    module = _load_module()

    assert module.operational_gate_exit_code(
        verdict="OPERATIONAL_GREEN",
        require_operational_green=True,
    ) == 0


def test_operational_gate_exit_code_blocks_non_green_in_strict_mode() -> None:
    module = _load_module()

    assert module.operational_gate_exit_code(
        verdict="CODE_API_GREEN_OPERATIONAL_BLOCKED",
        require_operational_green=True,
    ) == 3
