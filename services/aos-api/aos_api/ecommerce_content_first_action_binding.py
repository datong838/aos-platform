"""Current first-content approval composition. No HTTP route or Provider call.

The source envelope is produced and rechecked from the existing content Owner
in the Action transaction. It is not an alternative source of authority.
"""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json

from aos_api.aip_action_models import CreateActionProposalRequest, DecideActionProposalRequest
from aos_api.aip_action_policy import ACTION_APPROVAL_ROLES, classify_action_risk
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked, canonical_hash
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.auth import Principal, parse_bearer, resolve_principal
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_growth_runtime_connection import connect_serializable
from aos_api.openfga import openfga_api_url, user_key, marking_key
from aos_api.tenant_scope import TenantScope

ACTION = "ecommerce_growth_content_generate"
MARKERS = frozenset({"firstContentReviewKey", "firstContentSources"})
KEYS = MARKERS | {"budgetUpperBoundMinor"}
PURPOSE = "首次内容生成：审批当前来源与费用上限，不授权发布或发送"


def is_first_content(action_id, snapshot, payload):
    return (ACTION in {action_id, snapshot.get("id")}
            and type(payload) is dict and bool(MARKERS & payload.keys()))


def _deny(reason):
    raise AipActionTransitionBlocked("FIRST_CONTENT_" + reason)


def _identity(scope, authorization):
    from aos_api.aip_network_issuer_auth import _require_external_oidc_config
    if type(scope) is not TenantScope:
        _deny("SCOPE_REQUIRED")
    try:
        _require_external_oidc_config()
        principal = resolve_principal(token=parse_bearer(authorization),
            header_org=scope.org_id, header_project=scope.project_id)
    except Exception:
        _deny("EXTERNAL_IDENTITY_REQUIRED")
    if (type(principal) is not Principal or principal.token_kind != "oidc"
            or (principal.org_id, principal.project_id) != scope.key
            or not principal.subject or principal.subject == "unknown"
            or principal.subject != principal.subject.strip() or not principal.subject.isprintable()):
        _deny("EXTERNAL_IDENTITY_REQUIRED")
    return principal


def _metadata(conn):
    row = conn.execute("""SELECT id,name,object_type,parameters,required_markings,submission_criteria
        FROM meta_action_type WHERE id=%s FOR SHARE""", (ACTION,)).fetchone()
    if row is None or row["object_type"] != "Task":
        _deny("CURRENT_METADATA_REQUIRED")
    snapshot = dict(id=row["id"], name=row["name"], objectType=row["object_type"],
        parameters=row["parameters"], requiredMarkings=row["required_markings"],
        submissionCriteria=row["submission_criteria"])
    snapshot["revisionHash"] = canonical_hash(snapshot)
    return snapshot


def _actor(conn, scope, actor, snapshot, *, checker):
    if openfga_api_url():
        _deny("CURRENT_REMOTE_AUTHORITY_ADAPTER_REQUIRED")
    db = conn.execute("""SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,
        current_setting('aos.project_id',true) AS project_id""").fetchone()
    if db is None or (db["role"], db["org_id"], db["project_id"]) != ("aos_runtime", *scope.key):
        _deny("SCOPED_RUNTIME_TRANSACTION_REQUIRED")
    members = conn.execute("""SELECT role FROM meta_membership
        WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE""", (*scope.key, actor)).fetchall()
    if (len(members) != 1 or type(members[0]["role"]) is not str
            or not members[0]["role"].strip()):
        _deny("CURRENT_MEMBER_REQUIRED")
    role = members[0]["role"].lower()
    if checker and role not in ACTION_APPROVAL_ROLES:
        _deny("CURRENT_BUSINESS_APPROVER_REQUIRED")
    obj = conn.execute("""SELECT published,properties,required_markings FROM meta_object_type
        WHERE id=%s FOR SHARE""", (snapshot["objectType"],)).fetchone()
    if obj is None or obj["published"] is not True:
        _deny("CURRENT_OBJECT_REQUIRED")
    from aos_api.marking import field_marking_map
    # Require persisted bearer tuples even for admin. A JWT role does not fill
    # in missing current source markings. The content Owner uses internal facts.
    labels = {"internal", *(snapshot.get("requiredMarkings") or []),
              *(obj["required_markings"] or [])}
    for required in field_marking_map(obj["properties"]).values():
        labels.update(required)
    for label in sorted(labels):
        rows = conn.execute("""SELECT object_key FROM authz_tuple
            WHERE org_id=%s AND project_id=%s AND user_key=%s
              AND relation='bearer' AND object_key=%s FOR SHARE""",
            (*scope.key, user_key(actor), marking_key(label))).fetchall()
        if len(rows) != 1:
            _deny("CURRENT_MARKING_REQUIRED")
    return (role,)


def source_envelope(transaction, scope, review_key, sources):
    if sources is None or type(review_key) is not str:
        _deny("CURRENT_SOURCES_REQUIRED")
    context = sources.action_context
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    store = AipModelRuntimeStore(TransactionBoundConnectFactory(transaction, scope))
    resolution = context.resolution
    if resolution.selected_model is None or resolution.selected_provider is None:
        _deny("MODEL_PROVIDER_REQUIRED")
    model = store.get_model(scope, resolution.selected_model.asset_id, resolution.selected_model.revision)
    if (model.content_hash != resolution.selected_model.content_hash
            or model.provider != resolution.selected_provider
            or model.price_snapshot_ref != resolution.selected_price_snapshot):
        _deny("MODEL_PROVIDER_DRIFTED")
    plan_ref = context.request.run.plan_ref
    plan = transaction.execute("""SELECT content_hash FROM aip_plan_revision
        WHERE org_id=%s AND project_id=%s AND task_id=%s AND plan_revision_id=%s
          AND revision=%s AND approval_status='approved' FOR SHARE""",
        (*scope.key, sources.task_ref.resource_id, plan_ref.resource_id, int(plan_ref.revision))).fetchone()
    if plan is None:
        _deny("APPROVED_PLAN_REQUIRED")
    runtime = asdict(sources.snapshot)
    runtime.pop("checked_at")
    ref = lambda value: value.model_dump(mode="json", by_alias=True)
    value = dict(schemaVersion=2, tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
        reviewKey=review_key, reviewReceipt=context.response["receiptRef"],
        agentRunId=context.agent_run_id, agentRequest=ref(context.request), runtime=runtime,
        planRef=dict(resourceType="PlanRevision", resourceId=plan_ref.resource_id,
                     revision=int(plan_ref.revision), contentHash="sha256:" + plan["content_hash"].removeprefix("sha256:")),
        authorityRefs={key: value for key, value in sources.authorities.items()
                       if key != "capacity_reservation"}, sourceArtifactRefs=sources.source_artifact_refs,
        factSourceRefs=sources.fact_source_refs, modelRef=ref(resolution.selected_model),
        providerRef=ref(resolution.selected_provider), providerModelId=model.provider_model_id,
        runtimePolicyRef=ref(resolution.policy), quotaPolicyRef=ref(context.runtime_policy.quota_policy_ref),
        budgetPolicyRef=ref(context.runtime_policy.budget_policy_ref),
        maxInputTokens=sources.quota.max_input_tokens, maxOutputTokens=sources.quota.max_output_tokens,
        quotaExpiresAt=sources.quota.effective_until,
        budgetPolicyExpiresAt=context.budget_policy.effective_until)
    return json.loads(json.dumps(value, default=str))


def _request(transaction, scope, review_key, amount, expires_at, sources):
    if type(amount) is not int or not 1 <= amount <= 100_000_000:
        _deny("EXACT_AMOUNT_REQUIRED")
    now = sources.snapshot.checked_at
    context = sources.action_context
    if (type(expires_at) is not datetime or expires_at.utcoffset() is None
            or not now < expires_at <= min(now + timedelta(minutes=15),
                sources.quota.effective_until,
                context.budget_policy.effective_until)):
        _deny("CURRENT_EXPIRY_REQUIRED")
    return CreateActionProposalRequest(actionTypeId=ACTION,
        taskId=sources.task_ref.resource_id, runId=context.request.task_run_ref.resource_id,
        purpose=PURPOSE, expiresAt=expires_at.astimezone(timezone.utc), payload={
            "firstContentReviewKey": review_key,
            "firstContentSources": source_envelope(transaction, scope, review_key, sources),
            "budgetUpperBoundMinor": amount})


def _binding(scope, request, snapshot, risk):
    return canonical_hash(dict(domain="aos-first-content-action/v2", tenant=scope.key,
        request=request.model_dump(mode="json", by_alias=True), actionType=snapshot,
        policy={"floor": risk.floor.value, "reasons": list(risk.reasons), **risk.approval_policy}))


class FirstContentActionGuard:
    def __init__(self, principal):
        if type(principal) is not Principal or principal.token_kind != "oidc":
            _deny("EXTERNAL_IDENTITY_REQUIRED")
        self.principal = principal

    def _principal(self, scope, actor):
        if (scope.key != (self.principal.org_id, self.principal.project_id)
                or actor != self.principal.subject):
            _deny("IDENTITY_DRIFTED")

    def check_request(self, conn, scope, actor, body, snapshot, risk):
        self._principal(scope, actor)
        if type(body) is not CreateActionProposalRequest:
            _deny("DEDICATED_PROPOSAL_REQUIRED")
        if snapshot != _metadata(conn):
            _deny("METADATA_DRIFTED")
        _actor(conn, scope, actor, snapshot, checker=False)
        from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner
        payload = body.payload
        if set(payload) != KEYS:
            _deny("EXACT_PAYLOAD_REQUIRED")
        transaction = HostTransaction(conn)
        sources = ContentBudgetCommandOwner._prepare_approval_sources(transaction, scope, payload["firstContentReviewKey"])
        expected = _request(transaction, scope, payload["firstContentReviewKey"],
                            payload["budgetUpperBoundMinor"], body.expires_at, sources)
        expected_risk = classify_action_risk(ACTION, snapshot, expected.payload, None)
        if (canonical_hash(body.model_dump(mode="json", by_alias=True))
                != canonical_hash(expected.model_dump(mode="json", by_alias=True))
                or risk != expected_risk or risk.level is not ActionRiskLevel.R2):
            _deny("REQUEST_OR_RISK_DRIFTED")
        from aos_api.submission import evaluate_criteria
        if not evaluate_criteria(snapshot.get("submissionCriteria") or [], body.payload)["ok"]:
            _deny("SUBMISSION_CRITERIA_REQUIRED")
        ContentBudgetCommandOwner._approved_bound(sources.price, payload["budgetUpperBoundMinor"],
            max_input_tokens=sources.quota.max_input_tokens, max_output_tokens=sources.quota.max_output_tokens,
            **sources.cost_context)
        return _binding(scope, expected, snapshot, risk)

    def check_proposal(self, conn, scope, actor, row, *, checker):
        self._principal(scope, actor)
        if not checker and actor != row["created_by"]:
            _deny("MAKER_REQUIRED")
        if checker and actor == row["created_by"]:
            _deny("INDEPENDENT_CHECKER_REQUIRED")
        roles = _actor(conn, scope, actor, _metadata(conn), checker=checker)
        from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner
        sources = ContentBudgetCommandOwner._prepare_approval_sources(HostTransaction(conn), scope,
                                                             row["payload"]["firstContentReviewKey"])
        _verify_row(conn, scope, row, sources)
        return roles


def _verify_row(conn, scope, row, sources):
    transaction = HostTransaction(conn)
    snapshot = _metadata(conn)
    payload = row["payload"]
    if type(payload) is not dict or set(payload) != KEYS:
        _deny("EXACT_PAYLOAD_REQUIRED")
    request = _request(transaction, scope, payload["firstContentReviewKey"],
                       payload["budgetUpperBoundMinor"], row["expires_at"], sources)
    risk = classify_action_risk(ACTION, snapshot, request.payload, None)
    policy = {"floor": risk.floor.value, "reasons": list(risk.reasons), **risk.approval_policy}
    binding = _binding(scope, request, snapshot, risk)
    draft = conn.execute("""SELECT snapshot FROM aip_action_draft
        WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE""",
        (*scope.key, row["proposal_id"])).fetchone()
    stable = draft["snapshot"] if draft else None
    expected_stable = dict(tenantScope=dict(orgId=scope.org_id, projectId=scope.project_id),
        createdBy=row["created_by"], actionType=snapshot, taskId=request.task_id, runId=request.run_id,
        objectRef=None, purpose=PURPOSE, riskLevel=risk.level.value, policy=policy,
        approvalPolicyHash=canonical_hash(policy), payload=request.payload, diff={}, evidenceRefs=[],
        impactPreviewRef=None, actionBindingHash=binding, expiresAt=request.expires_at.isoformat())
    if (row["action_type_id"] != ACTION or row["action_type_snapshot"] != snapshot
            or row["action_type_revision_hash"] != snapshot["revisionHash"]
            or row["task_id"] != request.task_id or row["run_id"] != request.run_id
            or row["purpose"] != request.purpose or row["client_risk_hint"] is not None
            or canonical_hash(row["payload"]) != canonical_hash(request.payload) or row["policy_snapshot"] != policy
            or row["risk_level"] != risk.level.value or row["approval_policy_hash"] != canonical_hash(policy)
            or row["action_binding_hash"] != binding or row["impact_preview_id"] is not None
            or type(stable) is not dict or canonical_hash(stable) != row["proposal_hash"]
            or canonical_hash(stable) != canonical_hash(expected_stable)
            or stable.get("actionBindingHash") != binding or stable.get("actionType") != snapshot
            or stable.get("payload") != payload or stable.get("policy") != policy
            or stable.get("createdBy") != row["created_by"]
            or stable.get("taskId") != request.task_id or stable.get("runId") != request.run_id
            or stable.get("tenantScope") != dict(orgId=scope.org_id, projectId=scope.project_id)):
        _deny("PROPOSAL_BINDING_DRIFTED")
    _actor(conn, scope, row["created_by"], snapshot, checker=False)
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner
    ContentBudgetCommandOwner._approved_bound(sources.price, payload["budgetUpperBoundMinor"],
        max_input_tokens=sources.quota.max_input_tokens, max_output_tokens=sources.quota.max_output_tokens,
        **sources.cost_context)


def revalidate_first_content_approval(transaction, scope, event, sources, review_key):
    row = transaction.execute("""SELECT * FROM aip_action_proposal
        WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE""",
        (*scope.key, event["proposal_id"])).fetchone()
    if (row is None or sources is None or row["payload"].get("firstContentReviewKey") != review_key
            or event["actor_id"] == row["created_by"]):
        _deny("CURRENT_APPROVAL_SOURCES_REQUIRED")
    # HostTransaction preserves the same physical transaction and lock lifetime.
    _verify_row(transaction, scope, row, sources)
    _actor(transaction, scope, event["actor_id"], _metadata(transaction), checker=True)


def require_first_content_budget_source(conn, scope, event, payload, *, require_capacity=True):
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner
    if type(payload) is not dict or set(payload) != KEYS:
        _deny("EXACT_PAYLOAD_REQUIRED")
    key = payload["firstContentReviewKey"]
    transaction = HostTransaction(conn)
    if require_capacity:
        intent = transaction.execute("""SELECT state,claim_token FROM ecommerce_growth_content_budget_command_intent
            WHERE org_id=%s AND project_id=%s AND review_key=%s FOR SHARE""", (*scope.key, key)).fetchone()
        if intent is None or intent["state"] not in {"pending", "claimed"}:
            _deny("CURRENT_INTENT_REQUIRED")
        token = intent["claim_token"] if intent["state"] == "claimed" else None
        sources = ContentBudgetCommandOwner._prepare_sources(transaction, scope, key, claimed_token=token)
    else:
        sources = ContentBudgetCommandOwner._prepare_approval_sources(transaction, scope, key)
    revalidate_first_content_approval(transaction, scope, event, sources, key)
    return sources


def preview_first_content(scope, authorization, review_key, amount, expires_at):
    principal = _identity(scope, authorization)
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner
    with connect_serializable(scope) as conn:
        snapshot = _metadata(conn)
        _actor(conn, scope, principal.subject, snapshot, checker=False)
        transaction = HostTransaction(conn)
        sources = ContentBudgetCommandOwner._prepare_approval_sources(transaction, scope, review_key)
        request = _request(transaction, scope, review_key, amount, expires_at, sources)
        # No risk-fence update/claim/hold; transaction contains only reads/locks.
        conn.rollback()
        return request


def propose_first_content(scope, authorization, idempotency_key, request):
    if (type(request) is not CreateActionProposalRequest or request.action_type_id != ACTION
            or set(request.payload) != KEYS):
        _deny("EXACT_PROPOSAL_REQUIRED")
    _command_key(idempotency_key)
    principal = _identity(scope, authorization)
    with connect_serializable(scope) as conn:
        snapshot = _metadata(conn)
        guard = FirstContentActionGuard(principal)
        store = AipActionStore(TransactionBoundConnectFactory(HostTransaction(conn), scope),
                               first_content_guard=guard)
        result = store.create_proposal(scope, principal.subject, idempotency_key, request,
            snapshot, classify_action_risk(ACTION, snapshot, request.payload, None))
        conn.commit()
        return result


def decide_first_content(scope, authorization, proposal_id, idempotency_key, decision):
    principal = _identity(scope, authorization)
    if type(decision) is not DecideActionProposalRequest:
        _deny("DECISION_REQUIRED")
    _command_key(idempotency_key)
    with connect_serializable(scope) as conn:
        row = conn.execute("""SELECT action_type_id,action_type_snapshot,payload FROM aip_action_proposal
            WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE""",
            (*scope.key, proposal_id)).fetchone()
        if row is None or not is_first_content(row["action_type_id"], row["action_type_snapshot"], row["payload"]):
            _deny("EXACT_PROPOSAL_REQUIRED")
        store = AipActionStore(TransactionBoundConnectFactory(HostTransaction(conn), scope),
                               first_content_guard=FirstContentActionGuard(principal))
        result = store.decide(scope, principal.subject, proposal_id, idempotency_key, decision)
        conn.commit()
        return result


def _command_key(value):
    if (type(value) is not str or not 1 <= len(value) <= 120
            or value != value.strip() or not value.isprintable()):
        _deny("COMMAND_KEY_REQUIRED")
