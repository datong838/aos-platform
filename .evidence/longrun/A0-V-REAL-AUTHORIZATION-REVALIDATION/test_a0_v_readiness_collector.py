from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).with_name("a0-v-readiness-collector.py")
SPEC = importlib.util.spec_from_file_location("a0_v_readiness_collector", MODULE_PATH)
assert SPEC and SPEC.loader
COLLECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COLLECTOR)


def observation(body):
    return {"httpStatus": 200, "body": body}


def ready_source():
    return {"status": "ready", "sources": [{"status": "ready"} for _ in range(12)]}


def ready_stats():
    return {
        "definitionCount": 6,
        "installedCount": 6,
        "runnableCount": 6,
        "skillDefinitionCount": 37,
        "capabilityDefinitionCount": 10,
    }


def ready_positive():
    generated = datetime(2026, 9, 10, 10, tzinfo=timezone.utc)
    node = {"status": "ready", "blockerCode": None}
    return {
        "sourceReadiness": observation(ready_source()),
        "workshopSourceReadiness": observation(ready_source()),
        "agentRegistry": observation({"stats": ready_stats()}),
        "agentRuntimeReadiness": observation(
            {
                "catalog": {
                    "stats": ready_stats(),
                    "items": [
                        {"runtimeReadiness": "runnable", "blockers": []}
                        for _ in range(6)
                    ],
                }
            }
        ),
        "capabilityCatalog": observation({"count": 10, "availableCount": 10}),
        "modelRuntime": observation(
            {
                "generatedAt": generated.isoformat(),
                "resolutions": [{"readiness": "ready"}],
                "healthObservations": [
                    {
                        "status": "healthy",
                        "expiresAt": (generated + timedelta(minutes=5)).isoformat(),
                    }
                ],
            }
        ),
        "modelChain": observation(
            {
                "chains": [
                    {
                        "readiness": "ready",
                        "controlledTrialAllowed": True,
                        "nodes": [dict(node) for _ in range(6)],
                    }
                ]
            }
        ),
        "modelCost": observation(
            {
                "budgets": [
                    {
                        "status": "active",
                        "currency": "CNY",
                        "hardStop": True,
                        "dailyLimitMinor": 100,
                        "monthlyLimitMinor": 1000,
                    }
                ]
            }
        ),
    }


class SemanticReadinessTests(unittest.TestCase):
    def test_exact_ready_fixture_has_no_semantic_blockers(self):
        self.assertEqual(COLLECTOR._semantic_readiness_blockers(ready_positive()), [])

    def test_blocked_source_and_expired_health_fail_closed(self):
        positive = ready_positive()
        positive["sourceReadiness"] = observation(
            {"status": "blocked", "sources": [{"status": "blocked"} for _ in range(12)]}
        )
        positive["modelRuntime"]["body"]["healthObservations"][0]["expiresAt"] = (
            datetime(2026, 9, 10, 9, tzinfo=timezone.utc).isoformat()
        )
        blockers = COLLECTOR._semantic_readiness_blockers(positive)
        pairs = {(item["gate"], item["reason"]) for item in blockers}
        self.assertIn(("sourceReadiness.status", "STATUS_BLOCKED"), pairs)
        self.assertIn(("sourceReadiness.sources", "SOURCE_NOT_READY"), pairs)
        self.assertIn(
            ("modelRuntime.healthObservations", "NO_FRESH_HEALTHY_PROVIDER"), pairs
        )

    def test_malformed_and_partial_agent_catalog_fail_closed(self):
        positive = ready_positive()
        positive["workshopSourceReadiness"] = observation([])
        positive["agentRegistry"] = observation(
            {"stats": {**ready_stats(), "runnableCount": 5}}
        )
        positive["agentRuntimeReadiness"] = observation({})
        positive["capabilityCatalog"] = observation({"count": 10, "availableCount": 9})
        blockers = COLLECTOR._semantic_readiness_blockers(positive)
        gates = {item["gate"] for item in blockers}
        self.assertIn("workshopSourceReadiness.status", gates)
        self.assertIn("agentRegistry.stats.runnableCount", gates)
        self.assertIn("agentRuntimeReadiness.catalog", gates)
        self.assertIn("capabilityCatalog.availableCount", gates)


if __name__ == "__main__":
    unittest.main()
