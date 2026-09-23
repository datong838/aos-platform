"""W6-A: activate BG-02 event chain for DS authority (c6812824/b59582cc).

Phases (all freeze intent first, then execute, receipt-first):
  facts           - read-only: DS authority refs (config/lock/generation/binding), case, schedules
  prepare         - compose new event policy draft for DS (generation-h 20260924)
  approve         - approval proposal for the policy put
  put             - canonical router dispatch ecommerce_growth_schedule_put
  action          - register meta_action_type ecommerce_growth_event_dispatch
  approve-dispatch- approval proposal for the event dispatch expansion
  expand          - extend the cutover group with the event-control operation
  approve-control - approval proposal for the event control command
  enable          - canonical router dispatch ecommerce_growth_event_control
  verify          - read-only: policy head / binding rows / discovery candidate count

Run AFTER W5 final automations are both GREEN (definition 8b1d0f7e enabled + first dispatch 12/12).

Two facts verified on 2026-09-24 that the W6 checklist states differently:
  * `ecommerce_growth_event_control` is NOT among the 9 `ECOMMERCE_GROWTH_OPERATIONS`.
    It is `EVENT_CONTROL_OPERATION`, the 10th, and enters the cutover group only via
    this module's `expand` phase. The target set after enable is
    `(*ECOMMERCE_GROWTH_OPERATIONS, EVENT_CONTROL_OPERATION)` -- see
    `ecommerce_growth_host_composition.py:122`.
  * The dispatch-plane epoch is 3, which is what `ExpectedRuntimeTarget` takes; the
    `extension_runtime_binding.execution_epoch` of 4 is a different semantic plane.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"
STATE = BASE / "replacement-dq/w6-bg02-activation"
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
DS_ID = "c6812824-a0c3-4adc-9ebc-d56178ae135c"
DS_GENERATION = "b59582cc-2abf-472d-8f59-bfc8be1138c8"
DS_LOCK = "sha256:1b8468b86496b277a0ecd3a802379b3640e5ed1ec76e9ec420b9d15089013938"
CASE = "case-qyh-full-store-baseline-20260915"
# A1 must CONTINUE the existing policy chain, not open a new policy id.
# `prepare_event_case_binding` accepts exactly two shapes: a first policy on an
# unbound Case, or a successor of the policy the Case already binds -- and
# `validate_successor` demands `self.policy_id == previous.policy_id`. Case rev14
# binds generation-f rev12 (sha256:c86bdb6c...), so revision 13 on that same id is
# the only legal move. The W6 checklist's `...-generation-h-20260924` id satisfies
# neither branch (verified 2026-09-24 against the live Case bindings).
POLICY = "product-event-qyh-full-store-generation-f-20260916"
PREFIX = "a0v-w6-bg02-ds-event-v1"
GROWTH_BACKEND = BASE / "bn-canonical-alias-registry/signed-bundles/solution.ecommerce.growth/1.10.2/backend"
SDK_ROOT = ROOT / "packages/aos-extension-sdk/python"

# DS adaptation values measured 2026-09-24 (see W6 checklist "侦察定案").
DS_EPOCH = 3                       # dispatch plane, NOT the binding plane's 4
DS_INSTALL_REVISION = 5
DS_OVERLAY = "a0v-canonical-ecommerce-v1"
DS_GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
EXPECTED_GROUP_REVISION = 363
P02_SELECTION = "e3582d30-62c7-4ff8-903a-20932cfb4a0f"
P02_SELECTION_REVISION = 1
P02_SELECTION_HASH = "sha256:6b3be8324cf80c330a6b5d1faba1c4295a07b3c5f4b25685166cc92eb371d1c7"
PIPELINE = "P02-product-qyh"
API_BASE = os.environ.get("A0V_W6_API", "http://127.0.0.1:8080")
ACTION = dict(id="ecommerce_growth_event_dispatch", name="配置电商商品事件受控入口",
              objectType="Case", parameters=[], requiredMarkings=[], submissionCriteria=[])
# ProductEventSchedulePolicy.__post_init__ asserts
# `effective_until - effective_from <= timedelta(days=1)`, so the policy window is
# one day, not the 30 days the W6 checklist mentions. Discovery only needs the
# window to cover "now", so a rolling day is both sufficient and contract-legal.
POLICY_WINDOW = timedelta(days=1)
DEFINITION = "8b1d0f7e-3a6c-4b58-9d27-6f0e2a91c001"

ENV = {
    "AOS_DOTENV_DISABLED": "1",
    "AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE": str(BASE / "bm-runtime-credentials/runtime-host-identities.json"),
    "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
    "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
    "AOS_BUNDLE_ROOT": str(BASE / "bn-canonical-alias-registry/signed-bundles"),
    "AOS_BUNDLE_TRUST_ROOTS_FILE": str(BASE / "bm-trust-root-rotation/signing/trust-roots.json"),
    "AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE": str(BASE / "bn-registration-credentials/registration-main-identity.json"),
}


def freeze(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        raise ValueError(f"immutable intent already frozen: {path.name}")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, ensure_ascii=False, default=str, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def load(name: str) -> dict:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f"private {name} result required")
    return json.loads(path.read_text())


def _resolve_dsn() -> None:
    """``aos_api.db.connect`` needs ``AOS_DATABASE_URL``; this repo ships no ``.env``.

    The launchd agent's plist is the authoritative source in the recovery
    environment, and it has to be the same database the 8080 service uses --
    rehearsing the put against a different database would be worse than not
    rehearsing at all. ``connect(scope)`` is also what the shared ``_approve``
    helper uses, so the whole approval chain depends on this.
    """
    if os.environ.get("AOS_DATABASE_URL"):
        return
    import plistlib
    plist = Path(os.environ.get("A0V_W6_PLIST",
                                Path.home() / "Library/LaunchAgents/com.aos.a0v-api-8080.plist"))
    if not plist.is_file():
        raise ValueError(f"AOS_DATABASE_URL unset and no plist at {plist}")
    value = plistlib.loads(plist.read_bytes()).get("EnvironmentVariables", {}).get("AOS_DATABASE_URL")
    if not value:
        raise ValueError(f"AOS_DATABASE_URL missing from {plist}")
    os.environ["AOS_DATABASE_URL"] = value


def setup():
    os.environ.update(ENV)
    _resolve_dsn()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(SDK_ROOT))
    if GROWTH_BACKEND.is_dir():
        sys.path.insert(0, str(GROWTH_BACKEND))
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    plane = build_runtime_control_plane(registration_connect=registration_connection)
    return plane


@contextmanager
def _conn():
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    with consumer_connection(runtime_worker_connection, SCOPE) as conn:
        yield conn


@contextmanager
def _web_connection(scope):
    from aos_api.db import connect
    with connect(scope) as conn:
        yield conn


def facts(plane) -> dict:
    """Read-only: collect DS authority references needed by later phases."""
    with _conn() as conn:
        head = conn.execute("""SELECT i.current_revision, r.state, r.lock_hash, r.overlay_revision,
            (SELECT count(*) FROM bundle_composition c
              WHERE c.composition_pk=r.composition_pk) AS pkgs
            FROM bundle_installation i JOIN bundle_installation_revision r
            ON (i.org_id,i.project_id,i.installation_pk,i.current_revision)=
               (r.org_id,r.project_id,r.installation_pk,r.revision)
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s LIMIT 1""",
            (*SCOPE.values(), DS_ID)).fetchone()
        group = conn.execute("""SELECT cutover_group_id, max(revision) AS max_rev,
            min(cutover_group_revision) AS grp_rev, max(execution_epoch) AS epoch,
            count(*) AS ops
            FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s
            GROUP BY cutover_group_id""",
            (*SCOPE.values(), DS_ID)).fetchone()
        binding = conn.execute("""SELECT generation, revision, execution_epoch, enabled,
            observed_state, operation_fence, config_ref
            FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s
            ORDER BY revision DESC LIMIT 1""", (*SCOPE.values(), DS_ID)).fetchone()
        case = conn.execute("""SELECT case_id, current_revision, version, lifecycle
            FROM ecommerce_investigation_case_head
            WHERE org_id=%s AND project_id=%s AND case_id=%s""",
            (*SCOPE.values(), CASE)).fetchone()
        definition = conn.execute("""SELECT definition_id, state
            FROM pipeline_snapshot_schedule_definition_head
            WHERE org_id=%s AND project_id=%s AND definition_id=%s""",
            (*SCOPE.values(), DEFINITION)).fetchone()
        selection = conn.execute("""SELECT selection_id, revision, pipeline_id, content_hash
            FROM pipeline_source_selection_revision
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
            AND selection_id=%s AND revision=%s""",
            (*SCOPE.values(), DS_ID, DS_GENERATION, P02_SELECTION, P02_SELECTION_REVISION)).fetchone()
    result = dict(dsHead=dict(head) if head else None,
                  dsBinding=dict(binding) if binding else None,
                  dsGroup=dict(group) if group else None,
                  case=dict(case) if case else None,
                  definition=dict(definition) if definition else None,
                  p02Selection=dict(selection) if selection else None,
                  outcome="W6_FACTS_GREEN" if head and binding and case and selection else "W6_FACTS_INCOMPLETE")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return result


def _selection_ref() -> dict:
    """The A1 sourceSelectionRef must point exactly at the DS P02 selection."""
    with _conn() as conn:
        row = conn.execute("""SELECT selection_id, revision, content_hash
            FROM pipeline_source_selection_revision
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
            AND selection_id=%s AND revision=%s""",
            (*SCOPE.values(), DS_ID, DS_GENERATION, P02_SELECTION, P02_SELECTION_REVISION)).fetchone()
    if row is None:
        raise ValueError("DS P02 source selection required")
    if row["content_hash"] != P02_SELECTION_HASH:
        raise ValueError(f"DS P02 selection hash drifted: {row['content_hash']}")
    # `SourceSelectionRevision` exactly -- ProductEventSchedulePolicy.__post_init__
    # rejects anything else, and the "Pipeline" spelling is not in its vocabulary.
    return dict(resourceType="SourceSelectionRevision",
                resourceId="source-selection-" + str(row["selection_id"]),
                revision=row["revision"], contentHash=row["content_hash"], receiptId=None)


def _policy_window() -> tuple[datetime, datetime]:
    """[now floored to the hour, +1d) -- the closed interval the contract allows."""
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return start, start + POLICY_WINDOW


def _runtime_revision() -> int:
    """`runtimeRevision` semantics for the expand request are still open (checklist §7).

    Read the live binding revision and let an operator override it, so the first
    real run can disprove the assumption without editing code.
    """
    override = os.environ.get("A0V_W6_RUNTIME_REVISION")
    if override:
        return int(override)
    with _conn() as conn:
        row = conn.execute("""SELECT max(revision) AS n FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
            (*SCOPE.values(), DS_ID)).fetchone()
    return int(row["n"]) if row and row["n"] else DS_INSTALL_REVISION


def _previous_policy():
    """The policy revision the Case currently binds; A1 becomes its successor."""
    from ecommerce_growth.ecommerce_product_event_schedule import ProductEventSchedulePolicy
    with _conn() as conn:
        row = conn.execute("""SELECT current_revision, content_hash, authority_data
            FROM ecommerce_investigation_schedule_policy_head
            WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s""",
            (*SCOPE.values(), POLICY)).fetchone()
    if row is None:
        raise ValueError(f"preceding event policy chain required: {POLICY}")
    data = row["authority_data"]
    if isinstance(data, str):
        data = json.loads(data)
    previous = ProductEventSchedulePolicy.from_authority(data)
    if previous.revision != row["current_revision"]:
        raise ValueError("policy head revision and authority payload disagree")
    return previous


def _case_policy_ref() -> dict:
    """The Case must bind exactly the preceding policy revision, or the put is illegal."""
    with _conn() as conn:
        row = conn.execute("""SELECT authority_data FROM ecommerce_investigation_case_revision
            WHERE org_id=%s AND project_id=%s AND case_id=%s
            ORDER BY revision DESC LIMIT 1""", (*SCOPE.values(), CASE)).fetchone()
    if row is None:
        raise ValueError("current Case revision required")
    data = row["authority_data"]
    if isinstance(data, str):
        data = json.loads(data)
    return data.get("schedulePolicyRef") or {}


def prepare(plane) -> dict:
    """Compose the successor policy against the DS authority and freeze the put command."""
    from aos_api.aip_budget_reservation_store import canonical_hash as approval_hash
    from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
    from aos_api.tenant_scope import TenantScope
    from ecommerce_growth.ecommerce_business_investigation_case import (
        BusinessInvestigationCase, canonical_hash)
    from ecommerce_growth.ecommerce_product_event_binding import prepare_event_case_binding
    from ecommerce_growth.ecommerce_product_event_schedule import ProductEventSchedulePolicy

    scope = TenantScope(**SCOPE)
    case = BusinessInvestigationCaseStore(_web_connection).get(scope, CASE)
    original = case.model_dump(mode="json", by_alias=True)
    authority = BusinessInvestigationCase.from_authority(original)
    previous = _previous_policy()
    bound = _case_policy_ref()
    if (bound.get("resourceId") != previous.policy_id
            or bound.get("revision") != previous.revision
            or bound.get("contentHash") != previous.content_hash):
        raise ValueError(f"Case does not bind the preceding policy revision: {bound}")
    start, end = _policy_window()
    revision = previous.revision + 1
    raw = dict(schemaVersion="aos.ecommerce.product-event-schedule-policy/v1",
               tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
               schedulePolicyId=POLICY, revision=revision,
               priorRef=dict(resourceType="SchedulePolicyRevision", resourceId=previous.policy_id,
                             revision=previous.revision, contentHash=previous.content_hash,
                             receiptId=None),
               caseRef=dict(resourceType="BusinessInvestigationCaseRevision", resourceId=case.case_id,
                            revision=case.revision, contentHash=case.content_hash, receiptId=None),
               sourceSelectionRef=_selection_ref(), methodRef=original["investigationProfileRef"],
               platform="niushop", shopId="1", objectTypes=["Product"],
               effectiveFrom=start.isoformat(), effectiveUntil=end.isoformat(),
               maxSourceAgeSeconds=3600, recoveryWindowSeconds=900,
               createdBy=ACTOR, createdAt=start.isoformat())
    raw["contentHash"] = canonical_hash(raw)
    pair = prepare_event_case_binding(authority, ProductEventSchedulePolicy.from_authority(raw),
                                      previous_policy=previous)
    policy = pair.policy.authority_payload()
    payload = dict(caseId=CASE, schedulePolicyId=POLICY, expectedPolicyRevision=previous.revision,
                   expectedCaseVersion=case.version,
                   policyHash=approval_hash(policy, prefixed=True))
    command = dict(idempotencyKey=PREFIX + "-policy-put", expectedPolicyRevision=previous.revision,
                   expectedCaseVersion=case.version,
                   policy={k: v for k, v in policy.items() if k != "tenant"},
                   caseAuthority={k: v for k, v in pair.case.authority_payload().items() if k != "tenant"})
    freeze(STATE / "prepare-intent.json", dict(caseId=CASE, schedulePolicyId=POLICY,
                                               policyRevision=revision,
                                               window=[start.isoformat(), end.isoformat()]))
    return dict(outcome="CURRENT_POLICY_SUCCESSOR_PREPARED", payload=payload, command=command,
                policyRevision=revision, previousRevision=previous.revision,
                policyHash=payload["policyHash"],
                window=dict(from_=start.isoformat(), until=end.isoformat()))


def run(phase: str, plane) -> dict:
    from a0v_qyh_current_product_event_first_chain import _approve
    scope_label = dict(SCOPE)
    if phase == "prepare":
        return prepare(plane)
    if phase == "approve":
        prepared = load("prepare")
        bundle, ref = _approve("ecommerce_growth_schedule_put", prepared["payload"], PREFIX + "-schedule-approval")
        return dict(outcome="CURRENT_H_SCHEDULE_APPROVED", proposalId=bundle.proposal.id, approvalRef=ref)
    if phase == "put":
        from aos_api.auth import Principal
        from aos_api.ecommerce_growth_canonical_router import (
            EcommerceGrowthCanonicalRouter, ExpectedRuntimeTarget)
        from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
        from aos_api.tenant_scope import TenantScope
        prepared = load("prepare")
        command = {**prepared["command"], "approvalRef": load("approve")["approvalRef"]}
        freeze(STATE / "put-intent.json", command)
        scope = TenantScope(**scope_label)
        principal = Principal(subject=ACTOR, org_id=scope.org_id, project_id=scope.project_id,
                              roles=["admin"])
        router = EcommerceGrowthCanonicalRouter(
            build_scoped_ecommerce_growth_registry(principal, plane.pipeline_control_factory))
        result = router.dispatch(scope=scope, operation_id="ecommerce_growth_schedule_put",
                                 command=command,
                                 expected_runtime=ExpectedRuntimeTarget(DS_ID, DS_GENERATION, DS_EPOCH))
        return dict(outcome="CURRENT_H_POLICY_SAVED", **result)
    if phase == "action":
        import a0v_qyh_current_product_event_first_chain as qyh
        qyh.API = API_BASE
        with _web_connection(scope_label) as conn:
            row = conn.execute("""SELECT id,name,object_type,parameters,required_markings,submission_criteria
                FROM meta_action_type WHERE id=%s""", (ACTION["id"],)).fetchone()
        expected = None if row is None else dict(id=row["id"], name=row["name"], objectType=row["object_type"],
                                                 parameters=row["parameters"], requiredMarkings=row["required_markings"],
                                                 submissionCriteria=row["submission_criteria"])
        if expected is not None and expected != ACTION:
            raise ValueError("current event dispatch action differs")
        freeze(STATE / "action-intent.json", ACTION)
        if expected is None:
            _, expected = qyh.api("POST", "/v1/actions/types", ACTION)
        return dict(outcome="CURRENT_H_EVENT_DISPATCH_ACTION", action=expected)
    if phase == "approve-dispatch":
        # A plain dict, not EventControlDispatchRequest: `approvalRef` does not exist
        # until the approval below is granted, and the model requires it. The `expand`
        # phase validates the assembled request once the ref is available -- the same
        # two-step shape the generation-g template uses.
        request = dict(schemaVersion="aos.ecommerce.event-control-dispatch/v1", phase="expand",
                       installationRef=dict(installationId=DS_ID, revision=DS_INSTALL_REVISION,
                                            lockHash=DS_LOCK, overlayRevision=DS_OVERLAY),
                       generation=DS_GENERATION, executionEpoch=DS_EPOCH,
                       runtimeRevision=_runtime_revision(),
                       cutoverGroupId=DS_GROUP, expectedGroupRevision=EXPECTED_GROUP_REVISION,
                       caseId=CASE, schedulePolicyId=POLICY, idempotencyKey=PREFIX + "-expand")
        payload = dict(caseId=CASE, schedulePolicyId=POLICY, dispatchIntent=request)
        bundle, ref = _approve(ACTION["id"], payload, PREFIX + "-dispatch-approval")
        freeze(STATE / "approve-dispatch-intent.json", payload)
        return dict(outcome="EVENT_DISPATCH_APPROVED", proposalId=bundle.proposal.id,
                    approvalRef=ref, request=request)
    if phase in ("expand", "expand-recovered"):
        from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
        from aos_api.tenant_scope import TenantScope
        approved = load("approve-dispatch")
        request = EventControlDispatchRequest.model_validate(
            {**approved["request"], "approvalRef": approved["approvalRef"]})
        freeze(STATE / "expand-intent.json", request.wire())
        scope = TenantScope(**scope_label)
        lifecycle = plane.pipeline_control_factory.build_event_dispatch_lifecycle(scope)
        result = lifecycle.transition(scope=scope, request=request, actor=ACTOR)
        return dict(outcome="CURRENT_H_EVENT_DISPATCH_EXPANDED", **result)
    if phase == "approve-control":
        policy_ref = load("put")["receiptRef"]
        control = dict(schemaVersion="aos.ecommerce.product-event-control-command/v1",
                       idempotencyKey=PREFIX + "-control", policyRef=policy_ref,
                       expectedBindingRevision=0, intent="enable")
        payload = dict(caseId=CASE, schedulePolicyId=POLICY, controlIntent=control)
        bundle, ref = _approve("ecommerce_growth_event_control", payload, PREFIX + "-control-approval")
        freeze(STATE / "approve-control-intent.json", payload)
        return dict(outcome="CURRENT_H_EVENT_CONTROL_APPROVED", proposalId=bundle.proposal.id,
                    approvalRef=ref, control=control)
    if phase == "enable":
        from aos_api.auth import Principal
        from aos_api.ecommerce_growth_canonical_router import (
            EcommerceGrowthCanonicalRouter, ExpectedRuntimeTarget)
        from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
        from aos_api.tenant_scope import TenantScope
        approved = load("approve-control")
        command = {**approved["control"], "approvalRef": approved["approvalRef"]}
        freeze(STATE / "enable-intent.json", command)
        scope = TenantScope(**scope_label)
        principal = Principal(subject=ACTOR, org_id=scope.org_id, project_id=scope.project_id,
                              roles=["admin"])
        router = EcommerceGrowthCanonicalRouter(
            build_scoped_ecommerce_growth_registry(principal, plane.pipeline_control_factory))
        result = router.dispatch(scope=scope, operation_id="ecommerce_growth_event_control",
                                 command=command,
                                 expected_runtime=ExpectedRuntimeTarget(DS_ID, DS_GENERATION, DS_EPOCH))
        return dict(outcome="CURRENT_H_EVENT_ENABLED", **result)
    if phase == "verify":
        return verify(plane)
    raise ValueError(f"unknown W6 BG-02 phase: {phase}")


def verify(plane) -> dict:
    """Read-only: policy head state, DS binding rows, and the discovery candidate count.

    A4 cannot be satisfied before the new definition produces its first natural run
    (04:00Z); a zero candidate count before then is expected, not a failure.
    """
    with _conn() as conn:
        head = conn.execute("""SELECT schedule_policy_id, current_revision, enabled, lifecycle
            FROM ecommerce_investigation_schedule_policy_head
            WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s""",
            (*SCOPE.values(), POLICY)).fetchone()
        bindings = conn.execute("""SELECT count(*) AS n,
            count(*) FILTER (WHERE enabled AND approved) AS live,
            min(effective_from) AS first_from, max(effective_until) AS last_until
            FROM automation_schedule_binding
            WHERE org_id=%s AND project_id=%s AND policy_id=%s""",
            (*SCOPE.values(), POLICY)).fetchone()
        ops = conn.execute("""SELECT count(*) AS n FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s
            AND operation_id='ecommerce_growth_event_control'""",
            (*SCOPE.values(), DS_ID)).fetchone()
        runs = conn.execute("""SELECT count(*) AS n FROM meta_schedule_run
            WHERE org_id=%s AND project_id=%s AND status='succeeded'
            AND started_at > now() - interval '24 hours'""", tuple(SCOPE.values())).fetchone()
        outbox = conn.execute("""SELECT count(*) AS n FROM projection_outbox
            WHERE org_id=%s AND project_id=%s AND event_source='authoritative_store'
            AND created_at > now() - interval '24 hours'""", tuple(SCOPE.values())).fetchone()
    result = dict(policyHead=dict(head) if head else None,
                  bindings=dict(bindings) if bindings else None,
                  eventControlOps=ops["n"] if ops else 0,
                  recentSuccessfulRuns=runs["n"] if runs else 0,
                  recentAuthoritativeOutbox=outbox["n"] if outbox else 0)
    result["outcome"] = ("W6_H_VERIFY_ENABLED" if head and head["enabled"]
                         and result["eventControlOps"] >= 1 else "W6_H_VERIFY_INCOMPLETE")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return result


PHASES = ["facts", "prepare", "approve", "put", "action", "approve-dispatch", "expand",
          "approve-control", "enable", "verify"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=PHASES)
    parser.add_argument("--state-dir", default=None,
                        help="override STATE (used for dry-run rehearsal into a temp dir)")
    args = parser.parse_args()
    if args.state_dir:
        globals()["STATE"] = Path(args.state_dir)
    plane = setup()
    if args.phase == "facts":
        facts(plane)
        return
    result = run(args.phase, plane)
    if args.phase not in ("verify",):
        freeze(globals()["STATE"] / f"{args.phase}-result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
