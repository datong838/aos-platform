"""Durably contain the failed P Policy11 natural window without consuming its occurrences."""
import argparse
import json

import a0v_p_successor_business as current
from a0v_p_product_window import policy_profile
from a0v_qyh_current_product_event_first_chain import freeze, _approve

STATE = current.STATE.parent / "failed-natural-window-v5"
PREFIX = "a0v-qyh-p-policy11-failed-window-20260917-v1"
ACTIONS = ("approve-disable", "disable", "approve-fence", "fence")


def load(phase):
    path = STATE / f"{phase}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("private preceding containment result required")
    return json.loads(path.read_text())


def disable_payload(policy_receipt):
    if (policy_receipt.get("resourceType") != "SchedulePolicyRevision"
            or policy_receipt.get("resourceId") != policy_profile().POLICY
            or policy_receipt.get("revision") != 11):
        raise ValueError("exact P Policy11 receipt required")
    control = dict(
        schemaVersion="aos.ecommerce.product-event-control-command/v1",
        idempotencyKey=PREFIX + "-disable",
        policyRef=policy_receipt,
        expectedBindingRevision=1,
        intent="disable",
    )
    return dict(
        caseId=policy_profile().CASE,
        schedulePolicyId=policy_profile().POLICY,
        controlIntent=control,
    )


def current_fence_request():
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        runtime = conn.execute(
            "SELECT * FROM extension_runtime_binding WHERE org_id='org-org' AND "
            "project_id='dev-project' AND installation_id=%s AND generation=%s",
            (current.P_ID, current.P_GENERATION),
        ).fetchone()
        dispatch = conn.execute(
            "SELECT * FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND "
            "project_id='dev-project' AND operation_id='ecommerce_growth_event_control'"
        ).fetchone()
        enabled = conn.execute(
            "SELECT count(*) n FROM automation_schedule_binding WHERE org_id='org-org' AND "
            "project_id='dev-project' AND installation_id=%s AND generation=%s AND enabled",
            (current.P_ID, current.P_GENERATION),
        ).fetchone()["n"]
        source = conn.execute(
            "SELECT enabled FROM meta_schedule WHERE org_id='org-org' AND "
            "project_id='dev-project' AND id='sch-p02-qyh-controlled-20260913-v1'"
        ).fetchone()
    if (runtime is None or dispatch is None or runtime["revision"] != 6
            or runtime["execution_epoch"] != 3 or runtime["enabled"] is not True
            or runtime["operation_fence"] is not False or enabled != 0
            or source is None or source["enabled"] is not False
            or str(dispatch["installation_id"]) != current.P_ID
            or str(dispatch["generation"]) != current.P_GENERATION
            or dispatch["operation_fence"] is not False
            or str(dispatch["cutover_group_id"]) != current.GROUP
            or dispatch["cutover_group_revision"] != 49):
        raise ValueError("exact stopped P failed window required")
    return dict(
        schemaVersion="aos.ecommerce.event-control-dispatch/v1",
        phase="fence",
        installationRef=dict(
            installationId=current.P_ID,
            revision=5,
            lockHash=current.LOCK,
            overlayRevision="a0v-canonical-ecommerce-v1",
        ),
        generation=current.P_GENERATION,
        executionEpoch=3,
        runtimeRevision=6,
        cutoverGroupId=current.GROUP,
        expectedGroupRevision=49,
        caseId=policy_profile().CASE,
        schedulePolicyId=policy_profile().POLICY,
        idempotencyKey=PREFIX + "-fence",
    )


def run(phase):
    if phase not in ACTIONS:
        raise ValueError("unknown P containment phase")
    intent = STATE / f"{phase}-intent.json"
    if intent.exists():
        raise ValueError("existing containment intent requires read-only inspection")
    plane = current.setup()
    if phase == "approve-disable":
        payload = disable_payload(policy_profile().load("put")["receiptRef"])
        freeze(intent, payload)
        bundle, ref = _approve(
            "ecommerce_growth_event_control", payload, PREFIX + "-disable-approval"
        )
        result = dict(
            approvalRef=ref,
            control=payload["controlIntent"],
            proposalId=bundle.proposal.id,
        )
    elif phase == "disable":
        from aos_api.auth import Principal
        from aos_api.tenant_scope import TenantScope
        from aos_api.ecommerce_growth_canonical_router import (
            EcommerceGrowthCanonicalRouter,
            ExpectedRuntimeTarget,
        )
        from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
        approved = load("approve-disable")
        command = {**approved["control"], "approvalRef": approved["approvalRef"]}
        freeze(intent, command)
        scope = TenantScope("org-org", "dev-project")
        principal = Principal(
            subject=current.ACTOR,
            org_id=scope.org_id,
            project_id=scope.project_id,
            roles=["admin"],
        )
        router = EcommerceGrowthCanonicalRouter(
            build_scoped_ecommerce_growth_registry(principal, plane.pipeline_control_factory)
        )
        result = router.dispatch(
            scope=scope,
            operation_id="ecommerce_growth_event_control",
            command=command,
            expected_runtime=ExpectedRuntimeTarget(current.P_ID, current.P_GENERATION, 3),
        )
    elif phase == "approve-fence":
        load("disable")
        request = current_fence_request()
        payload = dict(
            caseId=policy_profile().CASE,
            schedulePolicyId=policy_profile().POLICY,
            dispatchIntent=request,
        )
        freeze(intent, payload)
        bundle, ref = _approve(
            "ecommerce_growth_event_dispatch", payload, PREFIX + "-fence-approval"
        )
        result = dict(request=request, approvalRef=ref, proposalId=bundle.proposal.id)
    else:
        from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
        from aos_api.tenant_scope import TenantScope
        approved = load("approve-fence")
        if current_fence_request() != approved["request"]:
            raise ValueError("P containment dispatch approval drifted")
        request = EventControlDispatchRequest.model_validate(
            {**approved["request"], "approvalRef": approved["approvalRef"]}
        )
        freeze(intent, request.wire())
        scope = TenantScope("org-org", "dev-project")
        result = plane.pipeline_control_factory.build_event_dispatch_lifecycle(scope).transition(
            scope=scope, request=request, actor=current.ACTOR
        )
    frozen = dict(result)
    freeze(STATE / f"{phase}-result.json", frozen)
    return frozen


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.phase), ensure_ascii=False, default=str, indent=2))
