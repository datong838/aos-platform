from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts/aip/bootstrap_r2_d03_skill_authority.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_r2_d03_skill_authority", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@dataclass(frozen=True)
class Model:
    registered_model_id: str = "model-qyh-text-dev"
    revision: int = 1
    content_hash: str = "a" * 64


def test_plan_is_d03_only_and_has_no_runtime_side_effects() -> None:
    plan = MODULE.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["approvalRef"] == MODULE.APPROVAL_REF
    assert "Provider call" in plan["forbiddenSideEffects"]
    assert "CapabilityBinding" in plan["forbiddenSideEffects"]
    assert "AgentRun" in plan["forbiddenSideEffects"]


def test_model_alias_contains_the_full_immutable_identity() -> None:
    alias = MODULE._model_alias(Model())
    assert alias == f"RegisteredModelRevision:model-qyh-text-dev@1#{'a' * 64}"


def test_isolated_registry_uses_no_secret_or_provider() -> None:
    alias = MODULE._model_alias(Model())
    registry = MODULE._isolated_registry(alias)
    adapter_name, result = registry.invoke_llm(
        alias, "safe D03 contract input", timeout_seconds=1
    )
    assert adapter_name == "d03-isolated-skill-contract-eval"
    assert result.usage.model == alias
    assert MODULE.SCOPE.key == ("org-org", "dev-project")
    assert MODULE.CANARY_SCOPE.key == ("dev-org", "dev-project")
