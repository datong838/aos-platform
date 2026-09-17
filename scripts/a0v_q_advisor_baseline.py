"""Configure and observe one natural QYH advisor baseline on recovered S."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import importlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/runtime"
PRODUCT_EVENT_STATE = (
    ROOT.parent
    / ".aos-recovery-20260915/state/niushop-1.23-current-package/business/p02-e-first-chain-r2"
)
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
CASE_ID = "case-qyh-advisor-baseline-20260917"
POLICY_ID = "schedule-qyh-advisor-baseline-once-20260917"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
MAKER = "user:dev"
CHECKER = "a0v-ecommerce-growth-1.4-approval-checker"


def freeze(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as handle:
        json.dump(value, handle, ensure_ascii=False, default=str, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def freeze_or_match(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError(f"immutable intent differs: {path.name}")
        return
    freeze(path, value)


def load_result(name: str) -> dict[str, Any]:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f"private {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def setup():
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.dont_write_bytecode = True
    bundle_root = (
        ROOT.parent
        / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
    )
    growth_backend = bundle_root / "solution.ecommerce.growth/1.10.0/backend"
    sdk_root = ROOT / "packages/aos-extension-sdk/python"
    if not growth_backend.is_dir() or not (sdk_root / "aos_extension_sdk").is_dir():
        raise ValueError("current signed S ecommerce growth backend required")
    sys.path.insert(0, str(sdk_root))
    sys.path.insert(0, str(growth_backend))
    previous = importlib.import_module("a0v_qyh_current_product_event_first_chain")
    plane = importlib.import_module("a0v_s_successor_business").setup()
    preflight = importlib.import_module("a0v_s_product_preflight").load_profile()
    return previous, preflight, plane


def _router(previous, preflight, plane, *, subject: str, roles: list[str]):
    from aos_api.auth import Principal
    from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter
    from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope(**SCOPE)
    principal = Principal(
        subject=subject,
        org_id=scope.org_id,
        project_id=scope.project_id,
        roles=roles,
    )
    router = EcommerceGrowthCanonicalRouter(
        build_scoped_ecommerce_growth_registry(principal, plane.pipeline_control_factory)
    )
    with previous._scope_and_connection()[1] as conn:
        target = previous._runtime_target(preflight, conn)
    return scope, router, target


def prepare(previous, preflight, _plane) -> dict[str, Any]:
    result = preflight.run("preflight")
    if result.get("outcome") != "PRODUCT_CURRENT_PREFLIGHT_GREEN":
        raise ValueError("current Product preflight required")
    brief_path = PRODUCT_EVENT_STATE / "brief-result.json"
    if not brief_path.is_file() or brief_path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("current frozen baseline TaskBrief required")
    brief = json.loads(brief_path.read_text(encoding="utf-8"))["brief"]
    with previous._scope_and_connection()[1] as conn:
        head = conn.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall()
        action = conn.execute(
            "SELECT id FROM meta_action_type WHERE id='ecommerce_growth_schedule_put'"
        ).fetchone()
        reviewer = conn.execute(
            "SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",
            (*SCOPE.values(), CHECKER),
        ).fetchone()
        canary = conn.execute(
            "SELECT count(*) AS n FROM ecommerce_investigation_case_head "
            "WHERE org_id='dev-org' AND project_id='dev-project' AND case_id=%s",
            (CASE_ID,),
        ).fetchone()["n"]
    if {row["version_num"] for row in head} != {"a0v_078"}:
        raise ValueError("a0v_078 single migration head required")
    if action is None or reviewer is None or reviewer["role"] != "admin" or canary:
        raise ValueError("current schedule approval prerequisites differ")
    return {
        "outcome": "S_ADVISOR_BASELINE_PREPARED",
        "installationRef": result["currentInstallationRef"],
        "runtimeBinding": result["runtimeBinding"],
        "taskBriefRef": {
            "resourceType": "TaskBriefRevision",
            "resourceId": brief["briefId"],
            "revision": brief["revision"],
            "contentHash": (
                brief["contentHash"]
                if brief["contentHash"].startswith("sha256:")
                else "sha256:" + brief["contentHash"]
            ),
            "receiptId": None,
        },
        "canaryCaseCount": canary,
    }


def configure_case(previous, preflight, plane) -> dict[str, Any]:
    from aos_api.ecommerce_business_investigation_case import (
        BusinessInvestigationCaseLifecycle,
        BusinessInvestigationCaseStore,
    )
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from aos_api.ecommerce_business_investigation_case_selection import (
        CatalogCanonicalProfileSelectionSource,
        PostgresCanonicalShopSelectionSource,
    )
    from aos_api.ecommerce_business_investigation_aip_composition import (
        PostgresAipProductionCompositionSource,
    )

    scope, router, target = _router(
        previous, preflight, plane, subject=MAKER, roles=["owner"]
    )
    with previous._scope_and_connection()[1] as conn:
        factory = TransactionBoundConnectFactory(HostTransaction(conn), scope)
        shop = PostgresCanonicalShopSelectionSource(factory).read(scope)
        profile = CatalogCanonicalProfileSelectionSource(
            composition_source=PostgresAipProductionCompositionSource(factory)
        ).read(scope, "initial_store_analysis")
    if shop is None or profile is None:
        raise ValueError("current canonical baseline Case selection required")
    request = {
        "caseId": CASE_ID,
        "analysisType": "initial_store_analysis",
        "title": "栖月汇经营参谋首次全店基线分析",
        "purposeCode": "initial_store_analysis",
        "channelRef": shop.channel_ref.model_dump(by_alias=True, mode="json"),
        "businessEntityRef": shop.business_entity_ref.model_dump(by_alias=True, mode="json"),
        "entityChannelBindingRef": shop.entity_channel_binding_ref.model_dump(
            by_alias=True, mode="json"
        ),
        "investigationProfileRef": profile.investigation_profile_ref.model_dump(
            by_alias=True, mode="json"
        ),
        "scopeRef": profile.scope_ref.model_dump(by_alias=True, mode="json"),
        "schedulePolicyRef": None,
    }
    command = {
        "idempotencyKey": "a0v-s-advisor-baseline-case-create-20260917-v1",
        "taskBriefRef": load_result("prepare")["taskBriefRef"],
        "case": request,
    }
    freeze_or_match(STATE / "case-intent.json", command)
    created = router.dispatch(
        scope=scope,
        operation_id="ecommerce_growth_case_put",
        command=command,
        expected_runtime=target,
    )
    authority = created["authority"]
    if authority["lifecycle"] == "DRAFT":
        changed = BusinessInvestigationCaseStore(previous._web_connection).transition(
            scope,
            CASE_ID,
            BusinessInvestigationCaseLifecycle.ACTIVE,
            expected_version=authority["version"],
            idempotency_key="a0v-s-advisor-baseline-case-activate-20260917-v1",
            actor=MAKER,
            occurred_at=datetime.now(timezone.utc),
        )
        authority = changed.authority.model_dump(by_alias=True, mode="json")
    if authority["lifecycle"] != "ACTIVE":
        raise ValueError("active advisor baseline Case required")
    return {
        "outcome": "S_ADVISOR_BASELINE_CASE_ACTIVE",
        "authority": authority,
        "createReplayed": created["replayed"],
    }


def _approval_ref(bundle) -> dict[str, Any]:
    from aos_api.aip_budget_reservation_store import canonical_hash

    approved = [item for item in bundle.approvals if item.decision.value == "approved"]
    if len(approved) != 1:
        raise ValueError("one exact independent schedule approval required")
    event = approved[0]
    row = {
        "approval_event_id": event.id,
        "proposal_id": event.proposal_id,
        "proposal_version": event.proposal_version,
        "proposal_hash": event.proposal_hash,
        "decision": event.decision.value,
        "actor_id": event.actor.actor_id,
        "reason": event.reason,
        "expires_at": event.expires_at,
        "created_at": event.created_at,
        "action_binding_hash": event.action_binding_hash,
    }
    return {
        "resourceType": "ActionApprovalEvent",
        "resourceId": event.id,
        "revision": event.proposal_version,
        "contentHash": canonical_hash(row, prefixed=True),
        "receiptId": None,
    }


def _approve_schedule(previous, payload: dict[str, Any]):
    from aos_api.aip_action_models import CreateActionProposalRequest, DecideActionProposalRequest
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_action_store import AipActionStore
    from aos_api.aip_contracts import ApprovalDecision
    from aos_api.tenant_scope import TenantScope

    key = "a0v-s-advisor-baseline-schedule-approval-20260917-v1"
    scope = TenantScope(**SCOPE)
    store = AipActionStore(previous._web_connection)
    snapshot = store.action_type_snapshot(scope, "ecommerce_growth_schedule_put")
    with previous._web_connection(scope) as conn:
        existing = conn.execute(
            "SELECT proposal_id FROM aip_action_proposal WHERE org_id=%s AND project_id=%s "
            "AND idempotency_key=%s",
            (*scope.key, key + ":proposal"),
        ).fetchone()
    if existing is None:
        body = CreateActionProposalRequest(
            actionTypeId="ecommerce_growth_schedule_put",
            purpose="栖月汇经营参谋首次全店基线计划内部配置",
            payload=payload,
            expiresAt=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        risk = classify_action_risk(
            "ecommerce_growth_schedule_put", snapshot, payload, body.risk_hint
        )
        reviewed = store.create_proposal(scope, MAKER, key + ":proposal", body, snapshot, risk)
    else:
        reviewed = store.get_proposal(scope, existing["proposal_id"])
    approved = {item.actor.actor_id for item in reviewed.approvals if item.decision.value == "approved"}
    if CHECKER not in approved:
        reviewed = store.decide(
            scope,
            CHECKER,
            reviewed.proposal.id,
            key + ":approval:1",
            DecideActionProposalRequest(
                expectedProposalVersion=reviewed.proposal.version,
                expectedProposalHash=reviewed.proposal.proposal_hash,
                decision=ApprovalDecision.APPROVED,
                reason="当前租户首次经营基线计划独立复核",
                approvalExpiresAt=reviewed.proposal.expires_at - timedelta(minutes=5),
            ),
            ("admin",),
        )
    if reviewed.proposal.status.value != "approved":
        raise ValueError("approved advisor baseline schedule proposal required")
    return reviewed, _approval_ref(reviewed)


def approve_schedule(previous, _preflight, _plane) -> dict[str, Any]:
    from aos_api.aip_budget_reservation_store import canonical_hash

    case = load_result("case")["authority"]
    policy = {
        "schedulePolicyId": POLICY_ID,
        "caseRef": {
            "resourceType": "BusinessInvestigationCaseRevision",
            "resourceId": CASE_ID,
            "revision": case["revision"],
            "contentHash": case["contentHash"],
            "receiptId": None,
        },
        "analysisType": "initial_store_analysis",
        "policyKind": "initial_checkup",
        "cadence": "once",
        "enabled": True,
        "overlapPolicy": "skip",
        "timezone": "Asia/Shanghai",
        "weeklyDay": None,
        "localTime": None,
    }
    payload = {
        "caseId": CASE_ID,
        "schedulePolicyId": POLICY_ID,
        "expectedPolicyRevision": 0,
        "expectedCaseVersion": case["version"],
        "policyHash": canonical_hash(policy, prefixed=True),
    }
    freeze_or_match(
        STATE / "schedule-approval-intent.json",
        {"maker": MAKER, "checker": CHECKER, "payload": payload},
    )
    bundle, ref = _approve_schedule(previous, payload)
    return {
        "outcome": "S_ADVISOR_BASELINE_SCHEDULE_APPROVED",
        "proposalId": bundle.proposal.id,
        "approvalRef": ref,
        "policy": policy,
    }


def put_policy(previous, preflight, plane) -> dict[str, Any]:
    scope, router, target = _router(
        previous, preflight, plane, subject=ACTOR, roles=["admin"]
    )
    case = load_result("case")["authority"]
    approved = load_result("schedule-approval")
    command = {
        "idempotencyKey": "a0v-s-advisor-baseline-policy-put-20260917-v1",
        "caseId": CASE_ID,
        "expectedPolicyRevision": 0,
        "expectedCaseVersion": case["version"],
        "policy": approved["policy"],
        "approvalRef": approved["approvalRef"],
    }
    freeze_or_match(STATE / "policy-intent.json", command)
    result = router.dispatch(
        scope=scope,
        operation_id="ecommerce_growth_schedule_put",
        command=command,
        expected_runtime=target,
    )
    return {"outcome": "S_ADVISOR_BASELINE_POLICY_SAVED", **result}


def observe(previous, _preflight, _plane) -> dict[str, Any]:
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope(**SCOPE)
    with previous._scope_and_connection()[1] as conn:
        policy = conn.execute(
            "SELECT authority_data FROM ecommerce_investigation_schedule_policy_head "
            "WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s",
            (*scope.key, POLICY_ID),
        ).fetchone()
        control = conn.execute(
            "SELECT authority FROM ecommerce_schedule_policy_control_receipt "
            "WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s ORDER BY created_at DESC LIMIT 1",
            (*scope.key, POLICY_ID),
        ).fetchone()
        bindings = conn.execute(
            "SELECT count(*) AS n FROM automation_schedule_binding WHERE org_id=%s AND project_id=%s "
            "AND policy_id=%s AND enabled=true",
            (*scope.key, POLICY_ID),
        ).fetchone()["n"]
        occurrences = conn.execute(
            "SELECT occurrence_id,status,scheduled_at,receipt_ref FROM automation_occurrence "
            "WHERE org_id=%s AND project_id=%s AND policy_id=%s ORDER BY created_at",
            (*scope.key, POLICY_ID),
        ).fetchall()
        runs = conn.execute(
            "SELECT authority_data FROM ecommerce_investigation_run_head WHERE org_id=%s AND project_id=%s "
            "AND authority_data->'caseRef'->>'resourceId'=%s ORDER BY updated_at",
            (*scope.key, CASE_ID),
        ).fetchall()
        canary = conn.execute(
            "SELECT count(*) AS n FROM automation_occurrence WHERE org_id='dev-org' "
            "AND project_id='dev-project' AND policy_id=%s",
            (POLICY_ID,),
        ).fetchone()["n"]
    return {
        "outcome": "S_ADVISOR_BASELINE_OBSERVED",
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "policy": None if policy is None else policy["authority_data"],
        "control": None if control is None else control["authority"],
        "activeBindings": bindings,
        "occurrences": [dict(row) for row in occurrences],
        "runs": [row["authority_data"] for row in runs],
        "canaryOccurrences": canary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "case", "schedule-approval", "policy", "observe"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("immutable output exists; inspect before retry")
    previous, preflight, plane = setup()
    functions = {
        "prepare": prepare,
        "case": configure_case,
        "schedule-approval": approve_schedule,
        "policy": put_policy,
        "observe": observe,
    }
    result = functions[args.action](previous, preflight, plane)
    freeze(args.output, result)
    canonical = STATE / f"{args.action}-result.json"
    if canonical.resolve() != args.output.resolve():
        freeze(canonical, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    main()
