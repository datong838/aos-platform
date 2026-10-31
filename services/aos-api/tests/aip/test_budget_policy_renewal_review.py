"""C source HTTP/DTO unit contracts, never real identity or budget consent.

The positive HTTP unit uses an explicit unit-fixture principal and reader.
Genuine signed identity, PostgreSQL and publication remain separate native gates.
"""
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import aip_model_governance_policies as router


PATH = "/v1/aip/model-governance-policies/budgets/fixture-policy/renewal-source"


def snapshot():
    tenant = {"orgId": "org-org", "projectId": "dev-project"}
    budget = {
        "tenant": tenant, "budgetId": "fixture-budget", "revision": 1,
        "contentHash": "b" * 64, "createdBy": "unit-fixture",
        "createdAt": "2026-09-01T00:00:00Z", "environment": "development",
        "currency": "CNY", "dailyLimitMinor": 1000, "monthlyLimitMinor": 20000,
        "alertThresholdPct": 80, "hardStop": True, "unknownUsageBehavior": "block",
        "effectiveFrom": "2026-09-01T00:00:00Z",
        "effectiveUntil": "2027-01-01T00:00:00Z", "owner": "unit-fixture",
        "overBudgetApprover": "unit-fixture-checker", "lifecycle": "active",
    }
    policy = {
        "tenant": tenant, "policyId": "fixture-policy", "revision": 13,
        "contentHash": "c" * 64, "createdBy": "unit-fixture",
        "createdAt": "2026-09-01T00:00:00Z", "environment": "development",
        "effectiveFrom": "2026-09-01T00:00:00Z",
        "effectiveUntil": "2026-09-25T00:00:00Z", "owner": "unit-fixture",
        "approvalRef": "unit-fixture-old-approval", "lifecycle": "active",
        "budgetRevisionRef": {"assetType": "BudgetRevision", "assetId": "fixture-budget",
                              "revision": 1, "contentHash": "b" * 64},
        "currency": "CNY", "hardStop": True, "unknownUsageBehavior": "block",
        "unknownPriceBehavior": "block", "allowZeroPrice": False,
        "zeroPriceApprovalRef": None,
    }
    return {
        "schemaVersion": "aos.budget-policy-renewal.review-source/v1",
        "tenant": tenant, "evaluatedAt": "2026-10-16T00:00:00Z",
        "sourcePolicy": policy, "sourceHeadVersion": 13,
        "sourceBudget": budget, "currentBudget": deepcopy(budget),
        "sourceProvider": None, "currentProvider": None,
        "sourceWindow": "expired", "budgetWindow": "effective",
        "state": "blocked", "blockers": ["RENEWAL_SOURCE_COST_AUTHORIZATION_MISSING"],
        "approvalVerified": False, "activationEligible": False,
    }


def app():
    instance = FastAPI()
    register_exception_handlers(instance)
    instance.include_router(router.router)
    return instance


def unit_reader_client(org="org-org", project="dev-project"):
    instance = app()
    calls = []

    class UnitReader:
        def read(self, scope, policy_id):
            calls.append((scope.key, policy_id))
            return snapshot()

    instance.dependency_overrides[require_principal] = lambda: Principal(
        subject="unit-reader-not-a-real-person", org_id=org, project_id=project,
        token_kind="unit-fixture",
    )
    instance.dependency_overrides[router.get_budget_renewal_review_reader] = lambda: UnitReader()
    return TestClient(instance), calls


def test_source_endpoint_requires_original_auth_before_reader():
    # No authenticated principal override: this is a real missing-token refusal.
    with TestClient(app()) as client:
        response = client.get(PATH)
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_source_projects_exact_head_and_keeps_budget_and_policy_windows_separate():
    client, calls = unit_reader_client()
    with client:
        response = client.get(PATH)
    assert response.status_code == 200, response.text
    value = response.json()
    assert calls == [(("org-org", "dev-project"), "fixture-policy")]
    assert value["sourceHeadVersion"] == value["sourcePolicy"]["revision"] == 13
    assert value["sourcePolicy"]["lifecycle"] == "active"
    assert value["sourceWindow"] == "expired"
    assert value["budgetWindow"] == "effective"
    assert value["sourceBudget"]["revision"] == 1
    assert value["sourceBudget"]["dailyLimitMinor"] == 1000
    assert value["approvalVerified"] is value["activationEligible"] is False
    assert value["state"] == "blocked"  # Missing cost authorization is not invented.


@pytest.mark.parametrize("org,project", [("dev-org", "dev-project"), ("org-org", "other")])
def test_source_rejects_cross_scope_before_reader(org, project):
    client, calls = unit_reader_client(org, project)
    with client:
        response = client.get(PATH)
    assert response.status_code == 403
    assert calls == []


def test_source_rejects_unknown_query_instead_of_ignoring_revision():
    client, calls = unit_reader_client()
    with client:
        response = client.get(PATH + "?revision=1")
    assert response.status_code == 400
    assert calls == []


def test_source_has_no_write_method():
    with TestClient(app()) as client:
        response = client.post(PATH, json={"activationEligible": True})
    assert response.status_code == 405


@pytest.mark.parametrize("field,value", [
    ("sourceHeadVersion", True), ("sourceHeadVersion", 0),
    ("approvalVerified", True), ("approvalVerified", 0),
    ("activationEligible", True), ("activationEligible", 0),
])
def test_source_dto_cannot_promote_or_coerce_observation(field, value):
    from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalReviewSource
    body = snapshot()
    body[field] = value
    with pytest.raises(ValidationError):
        BudgetPolicyRenewalReviewSource.model_validate(body)


@pytest.mark.parametrize("change", ["cross-tenant", "missing-budget", "drift", "wrong-window", "false-ready"])
def test_source_dto_rejects_inconsistent_observations(change):
    from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalReviewSource
    body = snapshot()
    if change == "cross-tenant":
        body["currentBudget"]["tenant"]["projectId"] = "other"
    elif change == "missing-budget":
        body["sourceBudget"] = None  # Missing facts cannot retain an effective window.
    elif change == "drift":
        body["currentBudget"]["revision"] = 2  # Requires an explicit changed blocker.
    elif change == "wrong-window":
        body["sourceWindow"] = "effective"
    else:
        body["state"], body["blockers"] = "ready", []
    with pytest.raises(ValidationError):
        BudgetPolicyRenewalReviewSource.model_validate(body)


class UnitSnapshotConnection:
    """Explicit SQL unit fixture, not native PostgreSQL or RLS evidence."""
    def __init__(self, *, read_only=True, missing=None):
        from psycopg import IsolationLevel
        self.read_only = read_only
        self.isolation_level = IsolationLevel.REPEATABLE_READ
        self.missing = missing
        self.queries = []
        self.owner = snapshot()

    def execute(self, query, params=()):
        from datetime import datetime
        assert self.read_only is True
        assert query.startswith("SELECT ")
        self.queries.append((query, params))
        if "clock_timestamp()" in query:
            value = {"now": datetime.fromisoformat("2026-10-16T00:00:00+00:00")}
        elif "aip_model_governance_policy_head" in query:
            value = None if self.missing == "policy" else {"current_revision": 13, "version": 17}
        elif "aip_model_governance_policy_revision" in query:
            value = {"payload": self.owner["sourcePolicy"]}
        elif "aip_budget_head" in query:
            value = None if self.missing == "budget-head" else {"current_revision": 1}
        elif "aip_budget_revision" in query:
            value = None if self.missing == "budget" else {"payload": self.owner["sourceBudget"]}
        else:
            raise AssertionError("unexpected SQL in source reader unit fixture")

        class Row:
            def fetchone(self):
                return value
        return Row()


def reader_fixture(connection):
    from contextlib import contextmanager
    from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalReviewReader
    scopes = []

    @contextmanager
    def connect(scope):
        scopes.append(scope.key)
        yield connection

    return BudgetPolicyRenewalReviewReader(connect), scopes


def test_reader_uses_one_readonly_snapshot_original_owner_reads_and_database_clock():
    from aos_api.tenant_scope import TenantScope
    connection = UnitSnapshotConnection()
    reader, scopes = reader_fixture(connection)
    result = reader.read(TenantScope("org-org", "dev-project"), "fixture-policy")
    assert scopes == [("org-org", "dev-project")]
    assert result.source_head_version == 17  # CAS head version need not equal revision 13.
    assert result.source_policy.revision == 13
    assert result.source_window == "expired" and result.budget_window == "effective"
    assert result.evaluated_at.isoformat() == "2026-10-16T00:00:00+00:00"
    assert result.source_budget.daily_limit_minor == 1000
    assert len(connection.queries) == 6
    for query, params in connection.queries:
        if "clock_timestamp" not in query:
            assert params[:2] == ("org-org", "dev-project")
    assert result.blockers == ["RENEWAL_SOURCE_COST_AUTHORIZATION_MISSING"]


@pytest.mark.parametrize("defect", ["writable", "read-committed"])
def test_reader_rejects_wrong_transaction_before_any_sql(defect):
    from psycopg import IsolationLevel
    from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalReviewUnavailable
    from aos_api.tenant_scope import TenantScope
    connection = UnitSnapshotConnection(read_only=defect != "writable")
    if defect == "read-committed":
        connection.isolation_level = IsolationLevel.READ_COMMITTED
    reader, scopes = reader_fixture(connection)
    with pytest.raises(BudgetPolicyRenewalReviewUnavailable):
        reader.read(TenantScope("org-org", "dev-project"), "fixture-policy")
    assert len(scopes) == 1 and connection.queries == []


def test_reader_rejects_cross_tenant_before_opening_connection():
    from aos_api.tenant_scope import TenantScope
    connection = UnitSnapshotConnection()
    reader, scopes = reader_fixture(connection)
    with pytest.raises(ValueError):
        reader.read(TenantScope("dev-org", "dev-project"), "fixture-policy")
    assert scopes == [] and connection.queries == []


@pytest.mark.parametrize("missing", ["budget", "budget-head"])
def test_reader_preserves_missing_budget_without_fabricated_amounts_or_refs(missing):
    from aos_api.tenant_scope import TenantScope
    reader, _ = reader_fixture(UnitSnapshotConnection(missing=missing))
    result = reader.read(TenantScope("org-org", "dev-project"), "fixture-policy")
    assert result.state == "blocked" and result.approval_verified is False
    if missing == "budget":
        assert result.source_budget is None and result.current_budget is None
        assert result.budget_window == "unknown"
        assert "RENEWAL_SOURCE_BUDGET_MISSING" in result.blockers
    else:
        assert result.source_budget is not None and result.current_budget is None
    assert "RENEWAL_CURRENT_BUDGET_MISSING" in result.blockers


def test_reader_preserves_root_policy_not_found():
    from aos_api.aip_model_governance_policy_store import ModelGovernancePolicyNotFound
    from aos_api.tenant_scope import TenantScope
    reader, _ = reader_fixture(UnitSnapshotConnection(missing="policy"))
    with pytest.raises(ModelGovernancePolicyNotFound):
        reader.read(TenantScope("org-org", "dev-project"), "fixture-policy")


@pytest.mark.parametrize("kind,code,status", [
    ("missing", "AIP_MODEL_GOVERNANCE_POLICY_NOT_FOUND", 404),
    ("unavailable", "AIP_BUDGET_RENEWAL_SOURCE_UNAVAILABLE", 503),
])
def test_source_http_maps_missing_and_unavailable_without_private_details(kind, code, status):
    from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalReviewUnavailable
    from aos_api.aip_model_governance_policy_store import ModelGovernancePolicyNotFound
    client, _ = unit_reader_client()

    class FailedReader:
        def read(self, scope, policy_id):
            if kind == "missing":
                raise ModelGovernancePolicyNotFound("model governance policy not found")
            raise BudgetPolicyRenewalReviewUnavailable("private SQL/DSN must stay internal")

    client.app.dependency_overrides[router.get_budget_renewal_review_reader] = lambda: FailedReader()
    with client:
        response = client.get(PATH)
    assert response.status_code == status
    assert response.json()["code"] == code
    assert "private SQL" not in response.text

# Executable DESIGN candidate only. Positive Principal is an explicit unsigned
# unit dependency fixture, NOT original human authentication or budget consent.
CHECKER_PATH = '/v1/aip/model-governance-policies/renewal-checker'
CHECKER_SUBJECT = '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'


def checker_view():
    return {'schemaVersion':'aos.budget-policy-renewal.review-checker/v1',
            'tenant':{'orgId':'org-org','projectId':'dev-project'},
            'subject':CHECKER_SUBJECT,'tokenKind':'oidc','role':'admin',
            'evaluatedAt':'2026-10-16T00:00:00Z','approvalVerified':False,
            'activationEligible':False}


def checker_unit_client(subject=CHECKER_SUBJECT, org='org-org', project='dev-project', kind='oidc', failure=None):
    instance = app()
    calls = []
    class FixtureReader:
        def read_checker(self, scope, identity):
            calls.append((scope.key, identity))
            if failure == 'denied':
                from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalCheckerDenied
                raise BudgetPolicyRenewalCheckerDenied('unit-fixture-denied')
            if failure == 'unavailable':
                from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalReviewUnavailable
                raise BudgetPolicyRenewalReviewUnavailable('unit-private-details')
            return checker_view()
    instance.dependency_overrides[require_principal] = lambda: Principal(
        subject=subject, org_id=org, project_id=project, token_kind=kind)
    instance.dependency_overrides[router.get_budget_renewal_review_reader] = lambda: FixtureReader()
    return TestClient(instance), calls


def test_checker_original_no_token_is_401():
    with TestClient(app()) as client:
        response=client.get(CHECKER_PATH)
    assert response.status_code==401
    assert response.json()['code']=='AUTH_REQUIRED'


def test_checker_unit_projection_is_not_permission_or_bootstrap(monkeypatch):
    from aos_api import membership
    def no_bootstrap(*args, **kwargs):
        raise AssertionError('checker must not bootstrap any member')
    monkeypatch.setattr(membership, 'ensure_default_membership', no_bootstrap)
    client,calls=checker_unit_client()
    with client:
        response=client.get(CHECKER_PATH)
    assert response.status_code==200, response.text
    assert response.json()==checker_view()
    assert calls==[(('org-org','dev-project'),CHECKER_SUBJECT)]


@pytest.mark.parametrize('mutation', ['dev','subject','org','project'])
def test_checker_invalid_unit_identity_refuses_before_reader(mutation):
    values={}
    if mutation=='dev':values['kind']='dev'
    if mutation=='subject':values['subject']='unit-other-not-a-real-person'
    if mutation=='org':values['org']='dev-org'
    if mutation=='project':values['project']='other'
    client,calls=checker_unit_client(**values)
    with client:response=client.get(CHECKER_PATH)
    assert response.status_code==403
    assert calls==[]


@pytest.mark.parametrize('request_kind', ['query','body','post'])
def test_checker_has_no_public_identity_or_write_inputs(request_kind):
    client,calls=checker_unit_client()
    with client:
        if request_kind=='query':response=client.get(CHECKER_PATH+'?subject=other')
        elif request_kind=='body':response=client.request('GET',CHECKER_PATH,json={'subject':'other'})
        else:response=client.post(CHECKER_PATH,json={'approved':True})
    assert response.status_code==(405 if request_kind=='post' else 400)
    assert calls==[]


@pytest.mark.parametrize('failure,status', [('denied',403),('unavailable',503)])
def test_checker_failure_mapping_is_closed_and_sanitized(failure,status):
    client,_=checker_unit_client(failure=failure)
    with client:response=client.get(CHECKER_PATH)
    assert response.status_code==status
    assert 'unit-private-details' not in response.text


class CheckerUnitConnection:
    def __init__(self, role='admin', read_only=True):
        from psycopg import IsolationLevel
        self.role=role;self.read_only=read_only
        self.isolation_level=IsolationLevel.REPEATABLE_READ;self.queries=[]
    def execute(self, query, params):
        from datetime import datetime, UTC
        assert self.read_only is True
        assert query==('SELECT lower(role) AS role, clock_timestamp() AS evaluated_at '
                       'FROM public.meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s')
        self.queries.append((query,params))
        value=None if self.role is None else {'role':self.role,'evaluated_at':datetime(2026,10,16,tzinfo=UTC)}
        class Result:
            def fetchone(self):return value
        return Result()


@pytest.mark.parametrize('role', ['admin','owner'])
def test_checker_reader_exact_current_role_single_readonly_query(role):
    from aos_api.tenant_scope import TenantScope
    connection=CheckerUnitConnection(role);reader,scopes=reader_fixture(connection)
    result=reader.read_checker(TenantScope('org-org','dev-project'),CHECKER_SUBJECT)
    assert result.role==role and result.subject==CHECKER_SUBJECT
    assert result.approval_verified is result.activation_eligible is False
    assert scopes==[('org-org','dev-project')]
    assert len(connection.queries)==1
    assert connection.queries[0][1]==('org-org','dev-project',CHECKER_SUBJECT)


@pytest.mark.parametrize('role', [None,'viewer','developer',''])
def test_checker_reader_missing_or_demoted_current_member_is_denied(role):
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalCheckerDenied
    connection=CheckerUnitConnection(role);reader,_=reader_fixture(connection)
    with pytest.raises(BudgetPolicyRenewalCheckerDenied):
        reader.read_checker(TenantScope('org-org','dev-project'),CHECKER_SUBJECT)
    assert len(connection.queries)==1


def test_checker_reader_does_not_open_for_other_subject():
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalCheckerDenied
    connection=CheckerUnitConnection();reader,scopes=reader_fixture(connection)
    with pytest.raises(BudgetPolicyRenewalCheckerDenied):
        reader.read_checker(TenantScope('org-org','dev-project'),'unit-other')
    assert scopes==[] and connection.queries==[]


@pytest.mark.parametrize('defect', ['writable','read-committed'])
def test_checker_reader_requires_snapshot_before_sql(defect):
    from psycopg import IsolationLevel
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalReviewUnavailable
    connection=CheckerUnitConnection(read_only=defect!='writable')
    if defect=='read-committed':connection.isolation_level=IsolationLevel.READ_COMMITTED
    reader,_=reader_fixture(connection)
    with pytest.raises(BudgetPolicyRenewalReviewUnavailable):
        reader.read_checker(TenantScope('org-org','dev-project'),CHECKER_SUBJECT)
    assert connection.queries==[]


@pytest.mark.parametrize('field,value', [('approvalVerified',True),('approvalVerified',0),
    ('activationEligible',True),('activationEligible',0),('role','viewer'),
    ('subject','unit-other'),('tokenKind','dev'),('evaluatedAt','2026-10-16T00:00:00')])
def test_checker_dto_cannot_fabricate_identity_or_permission(field,value):
    from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalCheckerView
    body=checker_view();body[field]=value
    with pytest.raises(ValidationError):BudgetPolicyRenewalCheckerView.model_validate(body)


@pytest.mark.parametrize("body", [b"{}", b"[]", b"null", b" ", b"\x00"])
def test_source_rejects_any_nonempty_get_body_before_reading(body):
    client, calls = unit_reader_client()
    with client:
        response = client.request("GET", PATH, content=body)
    assert response.status_code == 400
    assert response.json()["code"] == "AIP_INVALID_ARGUMENT"
    assert calls == []


@pytest.mark.parametrize("checker", [False, True])
def test_successful_renewal_read_is_not_cacheable_or_authorizing(checker):
    client, calls = checker_unit_client() if checker else unit_reader_client()
    with client:
        response = client.get(CHECKER_PATH if checker else PATH)
    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "no-store"
    assert response.json()["approvalVerified"] is False
    assert response.json()["activationEligible"] is False
    assert len(calls) == 1


@pytest.mark.parametrize("checker", [False, True])
def test_sync_renewal_reader_does_not_block_http_event_loop(checker):
    # This compares actual worker IDs against the HTTP loop, rather than
    # mocking the scheduling helper. Identity/data remain explicit unit fixtures.
    import threading
    client, _ = checker_unit_client() if checker else unit_reader_client()
    loop_threads, reader_threads = [], []

    @client.app.middleware("http")
    async def observe_loop(request, call_next):
        loop_threads.append(threading.get_ident())
        return await call_next(request)

    class ThreadReader:
        def read(self, scope, policy_id):
            reader_threads.append(threading.get_ident())
            return snapshot()

        def read_checker(self, scope, identity):
            reader_threads.append(threading.get_ident())
            return checker_view()

    client.app.dependency_overrides[router.get_budget_renewal_review_reader] = lambda: ThreadReader()
    with client:
        response = client.get(CHECKER_PATH if checker else PATH)
    assert response.status_code == 200
    assert len(loop_threads) == len(reader_threads) == 1
    assert reader_threads[0] != loop_threads[0]
