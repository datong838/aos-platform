"""Read-only source inquiry cannot promote a draft or trust caller snapshots."""
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from test_budget_policy_renewal_proposal import proposal
from aos_api.aip_budget_policy_renewal_preflight import BudgetPolicyRenewalPreflight, BudgetPolicyRenewalBlocked
from aos_api.aip_budget_activation_store import BudgetActivationDenied
from pydantic import ValidationError
from aos_api.aip_budget_policy_renewal_proposal import BudgetPolicyRenewalProposal
from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_store import materialize_revision
from aos_api.aip_model_governance_policy_store import canonical_hash
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def inquiry(proposal):
    tenant = proposal["tenant"]
    budget = materialize_revision(TenantScope("org-org", "dev-project"), "owner",
        BudgetRevisionCreate(budgetId="budget", revision=1, lifecycle="active",
        dailyLimitMinor=100, monthlyLimitMinor=1000, alertThresholdPct=80,
        effectiveFrom="2026-01-01T00:00:00Z", effectiveUntil="2027-01-01T00:00:00Z",
        owner="owner", overBudgetApprover="human-checker"))
    ref = lambda kind: dict(assetType=kind, assetId="asset", revision=1, contentHash="a"*64)
    provider = dict(tenant=tenant, providerInstanceId="provider", revision=1,
        pluginRef=ref("ProviderPluginRevision"), endpointProfile=dict(
            baseUrl="https://provider.invalid", region="test", timeoutMs=1000, metadata={}),
        secretRef="vault://test/provider", secretVersion="test",
        egressPolicyRef=ref("EgressPolicyRevision"),
        dataClassificationPolicyRef=ref("DataClassificationPolicyRevision"),
        lifecycle="active", createdBy="owner", createdAt="2026-01-01T00:00:00Z")
    provider["contentHash"] = canonical_hash({k:v for k,v in provider.items()
        if k not in {"tenant","revision","createdBy","createdAt"}})
    raw = proposal["sourcePolicy"].model_dump(mode="json", by_alias=True)
    raw["budgetRevisionRef"]["contentHash"] = budget.content_hash
    raw["developmentCostAuthorization"]["provider"]["contentHash"] = provider["contentHash"]
    raw["contentHash"] = canonical_hash({k:v for k,v in raw.items()
        if k not in {"tenant","contentHash","createdBy","createdAt"}})
    proposal["sourcePolicy"] = raw
    proposal["targetPolicy"]["budgetRevisionRef"]["contentHash"] = budget.content_hash
    proposal["targetPolicy"]["developmentCostAuthorization"]["provider"]["contentHash"] = provider["contentHash"]
    p = BudgetPolicyRenewalProposal.model_validate(proposal)
    rows = [
        dict(role="aos_runtime",org_id="org-org",project_id="dev-project",ro="on",isolation="repeatable read"),
        dict(unsafe=False), [dict(role="admin")], [dict(role="admin")],
        dict(current_revision=13, version=13, payload=p.source_policy.model_dump(mode="json",by_alias=True),
             content_hash=p.source_policy.content_hash, revision=13, lifecycle="active"),
        dict(payload=budget.model_dump(mode="json",by_alias=True),content_hash=budget.content_hash,
             revision=1,lifecycle="active"),
        dict(now=datetime(2026,10,13,4,10,tzinfo=UTC)),
        dict(payload=provider,content_hash=provider["contentHash"],revision=1,lifecycle="active"),
    ]
    conn = SimpleNamespace(read_only=True, queries=[])
    def execute(sql, params=None):
        assert sql.strip().upper().startswith("SELECT")
        assert not any(word in sql.upper() for word in ["FOR SHARE","FOR UPDATE","COMMIT"])
        conn.queries.append((sql,params))
        row = rows[len(conn.queries)-1]
        return SimpleNamespace(fetchone=lambda:row,fetchall=lambda:row)
    conn.execute=execute
    @contextmanager
    def factory(scope):
        assert scope.key == ("org-org","dev-project")
        yield conn
    principal=Principal(subject="machine-maker",org_id="org-org",project_id="dev-project",
                        roles=["admin"],token_kind="oidc")
    return BudgetPolicyRenewalPreflight(factory), principal, p, conn, rows


def test_positive_is_observation_only_and_preserves_owner_refs(inquiry):
    reader, principal, p, conn, rows = inquiry
    value=reader.inquire(principal,p)
    assert value["status"]=="observed" and value["activationEligible"] is False
    assert value["approvalVerified"] is False and value["proposalHash"]==p.proposal_hash
    assert value["sourceHeadVersion"]==13
    assert len(conn.queries)==8
    assert all(params[:2]==("org-org","dev-project") for _,params in conn.queries if params)
    assert not any(k in str(value) for k in ["dailyLimitMinor","secretRef","endpointProfile"])


@pytest.mark.parametrize("index,key,value", [
    (0,"ro","off"),(0,"org_id","dev-org"),(1,"unsafe",True),
    (4,"version",14),(4,"current_revision",14),(4,"content_hash","f"*64),
    (4,"lifecycle","revoked"),(5,"revision",2),(5,"lifecycle","suspended"),
    (5,"content_hash","f"*64),(6,"now",datetime(2028,1,1,tzinfo=UTC)),
    (7,"content_hash","f"*64),(7,"lifecycle","revoked"),
])
def test_source_identity_and_version_drift_fail_closed(inquiry,index,key,value):
    reader, principal, p, conn, rows=inquiry
    rows[index][key]=value
    with pytest.raises((BudgetPolicyRenewalBlocked, BudgetActivationDenied, ValidationError)):
        reader.inquire(principal,p)


@pytest.mark.parametrize("index",[2,3])
def test_missing_members_never_observe(inquiry,index):
    reader,principal,p,conn,rows=inquiry;rows[index]=[]
    with pytest.raises((BudgetPolicyRenewalBlocked, BudgetActivationDenied, ValidationError)):reader.inquire(principal,p)


def test_non_readonly_connection_refused(inquiry):
    reader,principal,p,conn,rows=inquiry;conn.read_only=False
    with pytest.raises((BudgetPolicyRenewalBlocked, BudgetActivationDenied, ValidationError)):reader.inquire(principal,p)


def test_provider_payload_tampering_is_not_trusted(inquiry):
    reader,principal,p,conn,rows=inquiry
    rows[7]["payload"]["endpointProfile"]["region"]="changed"
    with pytest.raises((BudgetPolicyRenewalBlocked, BudgetActivationDenied, ValidationError)):reader.inquire(principal,p)


def test_caller_policy_payload_cannot_replace_owner(inquiry):
    reader,principal,p,conn,rows=inquiry
    rows[4]["payload"]["owner"]="changed"
    with pytest.raises((BudgetPolicyRenewalBlocked, BudgetActivationDenied, ValidationError)):reader.inquire(principal,p)


def test_copied_nested_mutation_is_revalidated_before_db(inquiry):
    reader,principal,p,conn,rows=inquiry
    p.target_policy.budget_revision_ref.content_hash="f"*64
    with pytest.raises((BudgetPolicyRenewalBlocked, BudgetActivationDenied, ValidationError)):reader.inquire(principal,p)
    assert conn.queries==[]


def test_wrong_maker_cannot_query(inquiry):
    reader,principal,p,conn,rows=inquiry
    principal.subject="other"
    with pytest.raises((BudgetPolicyRenewalBlocked, BudgetActivationDenied, ValidationError)):reader.inquire(principal,p)
    assert conn.queries==[]
