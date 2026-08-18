from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from aos_api.aip_r1_bootstrap_probe import R1BootstrapProbeBlocked

SCRIPT = Path(__file__).resolve().parents[4] / "scripts/aip/refresh_r2_provider_health.py"
SPEC = importlib.util.spec_from_file_location("refresh_r2_provider_health", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

NOW = datetime(2026, 8, 17, 15, 0, tzinfo=UTC)


class RuntimeStore:
    def __init__(self) -> None:
        self.observations = []

    def get_provider(self, scope, asset_id, revision):
        assert scope.key == ("org-org", "dev-project")
        assert (asset_id, revision) == ("agnes-text-qyh-dev", 4)
        return SimpleNamespace(
            provider_instance_id=asset_id,
            revision=revision,
            content_hash="a" * 64,
        )

    def record_health(self, scope, actor, key, observation):
        self.observations.append((scope, actor, key, observation))
        return observation


class NetworkStore:
    def get(self, scope, asset_id, revision):
        assert (asset_id, revision) == ("network-qyh-text-dev", 1)
        return SimpleNamespace(policy_id=asset_id, revision=revision, content_hash="b" * 64)


class Probe:
    def __init__(self, *, fail_at: int | None = None) -> None:
        self.requests = []
        self.fail_at = fail_at

    def run(self, scope, request):
        self.requests.append(request)
        if self.fail_at == len(self.requests):
            raise R1BootstrapProbeBlocked("provider_transport_unknown")
        return SimpleNamespace(
            observed_at=NOW,
            latency_ms=len(self.requests) * 10,
            total_tokens=3,
        )


def test_plan_is_metadata_only_and_single_attempt() -> None:
    plan = MODULE.build_plan()
    assert plan["probeCount"] == 3
    assert plan["maxAttemptsPerProbe"] == 1
    assert plan["outputPolicy"] == "metadata-only"
    assert "prompt text" in plan["forbiddenOutputs"]


def test_three_successful_probes_write_one_short_lived_observation() -> None:
    runtime = RuntimeStore()
    probe = Probe()
    result = MODULE.refresh(
        probe=probe,
        runtime_store=runtime,
        network_store=NetworkStore(),
        clock=lambda: NOW,
    )
    assert result["providerCalls"] == 3
    assert result["promptOrAnswerBodiesReported"] == 0
    assert len(probe.requests) == 3
    assert len(runtime.observations) == 1
    observation = runtime.observations[0][3]
    assert int((observation.expires_at - observation.observed_at).total_seconds()) == 900


def test_unknown_second_call_stops_without_health_write_or_retry() -> None:
    runtime = RuntimeStore()
    probe = Probe(fail_at=2)
    with pytest.raises(MODULE.HealthRefreshBlocked) as exc:
        MODULE.refresh(
            probe=probe,
            runtime_store=runtime,
            network_store=NetworkStore(),
            clock=lambda: NOW,
        )
    assert exc.value.code == "provider_transport_unknown"
    assert exc.value.completed_calls == 1
    assert len(probe.requests) == 2
    assert runtime.observations == []
