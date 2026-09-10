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


INSTALLATION_ID = "11111111-1111-4111-8111-111111111111"


def ready_installation_collection():
    return {
        "items": [
            {
                "installationId": INSTALLATION_ID,
                "state": "active",
                "currentRevision": 7,
                "activeRevision": 7,
                "etagVersion": 7,
            }
        ],
        "total": 1,
        "limit": 100,
        "offset": 0,
    }


def ready_runtime_installation():
    return {
        "installationId": INSTALLATION_ID,
        "installationRevision": 7,
        "installationEtag": 7,
        "installationState": "active",
        "effectiveState": "ready",
        "binding": {
            "generation": "generation-7",
            "installationRevision": 7,
            "profileRef": "internal-python-v1",
            "configRef": {"configurationId": "approved-config"},
            "executionEpoch": 2,
            "desiredState": "enabled",
            "observedState": "ready",
            "enabled": True,
            "operationFence": False,
            "revision": 4,
        },
        "currentOperation": None,
        "reasons": [],
    }


def ready_workshop_modules():
    items = [
        {"moduleId": module_id, "readiness": "available", "blockers": []}
        for module_id in sorted(COLLECTOR.EXPECTED_WORKSHOP_MODULE_IDS)
    ]
    return {"items": items, "count": len(items)}


def ready_positive():
    generated = datetime(2026, 9, 10, 10, tzinfo=timezone.utc)
    node = {"status": "ready", "blockerCode": None}
    stage = {
        "profile": "ecommerce.business-investigation",
        "lifecycle": "frozen",
        "readiness": "ready",
        "blockers": [],
        "sealedBy": "reviewer",
        "sealedAt": generated.isoformat(),
        "sealHash": "a" * 64,
        "stages": [
            {"stageId": value}
            for value in ("portrait", "diagnosis", "solution-design")
        ],
    }
    plan = {
        "profile": "ecommerce.business-investigation.readonly",
        "lifecycle": "frozen",
        "readiness": "ready",
        "coverage": "complete",
        "blockers": [],
        "uncoveredSlots": [],
        "slots": [
            {"slotId": value}
            for value in (
                "investigation-owner",
                "data-steward",
                "content-research",
                "customer-research",
                "channel-research",
                "business-reviewer",
            )
        ],
    }
    result = {
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
        "agentInstances": observation({"items": [], "count": 0}),
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
    for name in ("productionContexts", "productionStartDecisions", "taskBriefs"):
        result[name] = observation({"items": [], "count": 0})
    result["stageTemplates"] = observation({"items": [stage], "count": 1})
    result["responsibilityPlans"] = observation({"items": [plan], "count": 1})
    return result


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

    def test_dynamic_outputs_may_be_empty_before_first_chain(self):
        blockers = COLLECTOR._semantic_readiness_blockers(ready_positive())
        gates = {item["gate"] for item in blockers}
        self.assertTrue(
            {"productionContexts", "productionStartDecisions", "taskBriefs"}.isdisjoint(gates)
        )

    def test_static_investigation_authorities_fail_closed(self):
        positive = ready_positive()
        stage = positive["stageTemplates"]["body"]["items"][0]
        stage["stages"][1]["stageId"] = "wrong-stage"
        plan = positive["responsibilityPlans"]["body"]["items"][0]
        plan["slots"] = plan["slots"][:-1]
        blockers = COLLECTOR._semantic_readiness_blockers(positive)
        pairs = {(item["gate"], item["reason"]) for item in blockers}
        self.assertIn(
            ("stageTemplates.authority", "INVESTIGATION_TEMPLATE_NOT_READY"), pairs
        )
        self.assertIn(
            ("responsibilityPlans.authority", "INVESTIGATION_PLAN_NOT_READY"), pairs
        )

    def test_contract_collection_count_mismatch_fails_closed(self):
        positive = ready_positive()
        positive["taskBriefs"] = observation({"items": [], "count": 1})
        blockers = COLLECTOR._semantic_readiness_blockers(positive)
        self.assertIn(
            {"gate": "taskBriefs.collection", "reason": "COLLECTION_COUNT_MISMATCH"},
            blockers,
        )

    def test_stage_authority_missing_draft_and_ambiguous_fail_closed(self):
        scenarios = (
            ("wrong-profile", {"profile": "wrong"}, "INVESTIGATION_TEMPLATE_MISSING"),
            ("draft", {"lifecycle": "draft"}, "INVESTIGATION_TEMPLATE_NOT_FROZEN"),
            ("blocked", {"readiness": "blocked"}, "INVESTIGATION_TEMPLATE_NOT_READY"),
        )
        for label, changes, reason in scenarios:
            with self.subTest(label=label):
                positive = ready_positive()
                positive["stageTemplates"]["body"]["items"][0].update(changes)
                blockers = COLLECTOR._semantic_readiness_blockers(positive)
                self.assertIn(
                    {"gate": "stageTemplates.authority", "reason": reason}, blockers
                )

        positive = ready_positive()
        items = positive["stageTemplates"]["body"]["items"]
        items.append(dict(items[0]))
        positive["stageTemplates"]["body"]["count"] = 2
        blockers = COLLECTOR._semantic_readiness_blockers(positive)
        self.assertIn(
            {
                "gate": "stageTemplates.authority",
                "reason": "INVESTIGATION_TEMPLATE_AMBIGUOUS",
            },
            blockers,
        )

    def test_global_catalog_does_not_prove_tenant_isolation(self):
        blockers, unverified = COLLECTOR._exact_isolation_outcome(None, None, None)
        self.assertEqual(blockers, [])
        self.assertEqual(
            unverified,
            [
                {
                    "gate": "crossTenantResourceIsolation",
                    "reason": "NO_POSITIVE_RESOURCE_AVAILABLE_FOR_CANARY_COMPARISON",
                }
            ],
        )

    def test_exact_agent_instance_proves_or_blocks_isolation(self):
        exact_id = COLLECTOR._first_agent_instance_id(
            {"items": [{"instanceId": "z"}, {"instanceId": "a"}], "count": 2}
        )
        self.assertEqual(exact_id, "a")
        blockers, unverified = COLLECTOR._exact_isolation_outcome(
            exact_id, {"httpStatus": 200}, {"httpStatus": 404}
        )
        self.assertEqual((blockers, unverified), ([], []))
        blockers, unverified = COLLECTOR._exact_isolation_outcome(
            exact_id, {"httpStatus": 200}, {"httpStatus": 200}
        )
        self.assertEqual(unverified, [])
        self.assertIn(
            {"gate": "crossTenantResourceIsolation.canary", "reason": "EXPECTED_404"},
            blockers,
        )

    def test_exact_active_installation_is_selected(self):
        installation_id, revision, blockers = COLLECTOR._active_installation_readiness(
            ready_installation_collection()
        )
        self.assertEqual((installation_id, revision, blockers), (INSTALLATION_ID, 7, []))

    def test_missing_ambiguous_and_stale_active_installations_fail_closed(self):
        missing = ready_installation_collection()
        missing["items"][0]["state"] = "uninstalled"
        self.assertEqual(
            COLLECTOR._active_installation_readiness(missing)[2][0]["reason"],
            "ACTIVE_INSTALLATION_MISSING",
        )

        ambiguous = ready_installation_collection()
        second = dict(ambiguous["items"][0])
        second["installationId"] = "22222222-2222-4222-8222-222222222222"
        ambiguous["items"].append(second)
        ambiguous["total"] = 2
        self.assertEqual(
            COLLECTOR._active_installation_readiness(ambiguous)[2][0]["reason"],
            "ACTIVE_INSTALLATION_AMBIGUOUS",
        )

        stale = ready_installation_collection()
        stale["items"][0]["activeRevision"] = 6
        self.assertEqual(
            COLLECTOR._active_installation_readiness(stale)[2][0]["reason"],
            "ACTIVE_INSTALLATION_POINTER_MISMATCH",
        )

    def test_incomplete_installation_page_fails_closed(self):
        body = ready_installation_collection()
        body["total"] = 2
        self.assertEqual(
            COLLECTOR._active_installation_readiness(body)[2][0]["reason"],
            "INCOMPLETE_OR_MALFORMED_COLLECTION",
        )

    def test_runtime_requires_exact_ready_unfenced_binding(self):
        self.assertEqual(
            COLLECTOR._runtime_installation_readiness(
                ready_runtime_installation(),
                installation_id=INSTALLATION_ID,
                installation_revision=7,
            ),
            [],
        )
        terminal = ready_runtime_installation()
        terminal["currentOperation"] = {"status": "succeeded"}
        self.assertEqual(
            COLLECTOR._runtime_installation_readiness(
                terminal,
                installation_id=INSTALLATION_ID,
                installation_revision=7,
            ),
            [],
        )
        for label, changes in (
            ("fenced", {"operationFence": True}),
            ("disabled", {"enabled": False}),
            ("stale", {"installationRevision": 6}),
            ("unconfigured", {"configRef": None}),
        ):
            with self.subTest(label=label):
                body = ready_runtime_installation()
                body["binding"].update(changes)
                self.assertEqual(
                    COLLECTOR._runtime_installation_readiness(
                        body,
                        installation_id=INSTALLATION_ID,
                        installation_revision=7,
                    )[0]["reason"],
                    "RUNTIME_NOT_READY",
                )
        running = ready_runtime_installation()
        running["currentOperation"] = {"status": "running"}
        self.assertEqual(
            COLLECTOR._runtime_installation_readiness(
                running,
                installation_id=INSTALLATION_ID,
                installation_revision=7,
            )[0]["reason"],
            "RUNTIME_NOT_READY",
        )

    def test_runtime_exact_id_requires_positive_200_and_canary_404(self):
        self.assertEqual(
            COLLECTOR._runtime_installation_outcome(
                installation_id=INSTALLATION_ID,
                installation_revision=7,
                positive_exact=observation(ready_runtime_installation()),
                canary_exact={"httpStatus": 404, "body": {"code": "RUNTIME_NOT_FOUND"}},
            ),
            [],
        )
        blockers = COLLECTOR._runtime_installation_outcome(
            installation_id=INSTALLATION_ID,
            installation_revision=7,
            positive_exact=observation(ready_runtime_installation()),
            canary_exact=observation(ready_runtime_installation()),
        )
        self.assertIn(
            {
                "gate": "bundleRuntimeInstallation.canary",
                "reason": "EXPECTED_404",
                "httpStatus": 200,
            },
            blockers,
        )

    def test_workshop_requires_exact_eight_available_modules(self):
        self.assertEqual(COLLECTOR._workshop_module_readiness(ready_workshop_modules()), [])

        missing = ready_workshop_modules()
        missing["items"].pop()
        missing["count"] -= 1
        self.assertEqual(
            COLLECTOR._workshop_module_readiness(missing)[0]["reason"],
            "EXPECTED_EXACT_EIGHT_MODULES",
        )

        degraded = ready_workshop_modules()
        degraded["items"][0].update(
            {"readiness": "degraded", "blockers": [{"reasonCode": "MISSING"}]}
        )
        self.assertEqual(
            COLLECTOR._workshop_module_readiness(degraded)[0]["reason"],
            "MODULE_NOT_AVAILABLE",
        )
        duplicate = ready_workshop_modules()
        duplicate["items"][0]["moduleId"] = duplicate["items"][1]["moduleId"]
        self.assertEqual(
            COLLECTOR._workshop_module_readiness(duplicate)[0]["reason"],
            "EXPECTED_EXACT_EIGHT_MODULES",
        )


if __name__ == "__main__":
    unittest.main()
