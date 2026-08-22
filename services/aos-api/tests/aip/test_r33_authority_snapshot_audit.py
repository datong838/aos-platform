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
