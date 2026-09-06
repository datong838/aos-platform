"""Current AIP data/policy refs on the dedicated disposable PostgreSQL."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import time

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from test_lifecycle_pg import database, pytestmark


def _migration(conn, filename, name):
    path = Path(__file__).resolve().parents[2] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = SimpleNamespace(execute=conn.execute)
    module.upgrade()


@pytest.fixture
def source_case(database):
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from aos_api.aip_budget_contracts import BudgetRevisionCreate
    from aos_api.aip_budget_store import materialize_revision as materialize_budget_revision
    from aos_api.aip_contracts import TenantContext
    from aos_api.aip_model_governance_policy_contracts import (
        BudgetPolicyRevisionCreate, QuotaPolicyRevisionCreate,
    )
    from aos_api.aip_model_governance_policy_store import materialize_policy as materialize_governance
    from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle, RuntimePolicyRevision
    from aos_api.aip_model_runtime_store import canonical_hash
    from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
    from aos_api.aip_network_policy_store import materialize_policy as materialize_network
    from aos_api.aip_runtime_guard_policy_contracts import (
        DataClassificationPolicyRevisionCreate, EgressPolicyRevisionCreate,
    )
    from aos_api.aip_runtime_guard_policy_store import materialize_policy as materialize_guard
    from aos_api.extension_runtime.configuration_contracts import ConfigurationDocument, ConfigurationSourceRef
    from aos_api.tenant_scope import TenantScope

    conn, _, schema = database
    conn.execute("""CREATE FUNCTION guard_aip4_append_only() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'AIP4_APPEND_ONLY' USING ERRCODE='55000'; END; $$ LANGUAGE plpgsql""")
    conn.execute("CREATE TABLE twa_workspace(org_id text,project_id text,PRIMARY KEY(org_id,project_id))")
    conn.execute("INSERT INTO twa_workspace VALUES('org-org','dev-project')")
    _migration(conn, "w2_002_eval_responsibility.py", "ar1c_w2_responsibility")
    conn.execute("""ALTER TABLE aip_responsibility_plan_revision
        ADD COLUMN profile_recommendation_ref jsonb,
        ADD COLUMN profile_confirmation_id text,
        ADD COLUMN merge_policy_ref jsonb,
        ADD COLUMN merge_decision_receipt_ids jsonb NOT NULL DEFAULT '[]'::jsonb""")
    _migration(conn, "aip7_001_model_runtime_authority.py", "ar1c_aip7")
    _migration(conn, "aip10_001_budget_authority.py", "ar1c_aip10_budget")
    _migration(conn, "aip10_002_runtime_guard_policy_authority.py", "ar1c_aip10_guard")
    _migration(conn, "aip10_003_model_governance_policy_authority.py", "ar1c_aip10_governance")
    conn.execute("CREATE TABLE aip_release_gate_decision(decided_at timestamptz NOT NULL)")
    _migration(conn, "aip10_004_network_policy_eval_gate_expiry.py", "ar1c_aip10_network")
    now = datetime.now(timezone.utc)
    scope = TenantScope("org-org", "dev-project")
    from aos_api.aip_production_contracts import CreateResponsibilityPlanRequest
    from aos_api.aip_production_contract_store import canonical_hash as production_hash
    responsibility = CreateResponsibilityPlanRequest.model_validate({
        "profile": "qyh-extension-runtime",
        "templateRef": {"resourceType": "ResponsibilityTemplateRevision", "resourceId": "qyh-six-colleagues",
            "revision": 1, "contentHash": "1" * 64},
        "slots": [{"slotId": "investigation-owner", "responsibilityType": "business_investigation",
            "requiredCapabilityIds": ["business.query"],
            "inputSchemaRef": {"resourceType": "BusinessQuestion", "resourceId": "qyh-question-v1",
                "revision": "1", "authority": "solution.ecommerce.growth"},
            "outputSchemaRef": {"resourceType": "BusinessFinding", "resourceId": "qyh-finding-v1",
                "revision": "1", "authority": "solution.ecommerce.growth"},
            "gateRefs": [], "returnStage": "business-review",
            "assignee": {"kind": "human_principal", "resourceId": "qyh-business-owner", "version": 1}}],
        "mergeDecisions": [], "mergeDecisionReceiptIds": [],
    })
    responsibility_hash = production_hash(responsibility.model_dump(mode="json", by_alias=True))
    conn.execute("INSERT INTO aip_responsibility_plan_head VALUES(%s,%s,'qyh-runtime-roles',1,1,NOW())", scope.key)
    conn.execute("""INSERT INTO aip_responsibility_plan_revision
        (org_id,project_id,plan_id,revision,profile,template_ref,slots,merge_decisions,
         profile_recommendation_ref,profile_confirmation_id,merge_policy_ref,merge_decision_receipt_ids,
         content_hash,lifecycle,created_by,created_at)
        VALUES(%s,%s,'qyh-runtime-roles',1,%s,%s,%s,%s,NULL,NULL,NULL,%s,%s,'frozen','隔离测试',%s)""",
        (*scope.key, responsibility.profile, Jsonb(responsibility.template_ref.model_dump(mode="json", by_alias=True)),
         Jsonb([item.model_dump(mode="json", by_alias=True) for item in responsibility.slots]),
         Jsonb([]), Jsonb([]), responsibility_hash, now))
    egress = materialize_guard(scope, "隔离测试", EgressPolicyRevisionCreate(
        policyId="qyh-egress", revision=1, environment="development",
        allowedSchemes=["https"], allowedHosts=["apihub.agnes-ai.com"], allowedPorts=[443],
        allowPublicFallback=False, unknownDestinationBehavior="block", regionState="confirmed",
        region="cn-approved-development", effectiveFrom=now-timedelta(minutes=1),
        effectiveUntil=now+timedelta(minutes=5), owner="隔离测试",
        approvalRef="approval:isolated", lifecycle="active",
    ), created_at=now)
    data = materialize_guard(scope, "隔离测试", DataClassificationPolicyRevisionCreate(
        policyId="qyh-public-catalog", revision=1, environment="development",
        effectiveFrom=now-timedelta(minutes=1), effectiveUntil=now+timedelta(minutes=5),
        owner="隔离测试", approvalRef="approval:isolated", lifecycle="active",
        allowedClassifications=["public_catalog"], prohibitedClassifications=[
            "direct_pii", "raw_order_detail", "customer_conversation", "credential",
            "commercial_sensitive", "cross_tenant", "unknown",
        ],
        denyUnknown=True, allowDirectPii=False, allowCommercialSensitive=False, allowCrossTenant=False,
    ), created_at=now)
    for kind,item in (("egress",egress),("data_classification",data)):
        conn.execute("INSERT INTO aip_runtime_guard_policy_head VALUES(%s,%s,%s,%s,1,1,NOW())",
            (*scope.key,kind,item.policy_id))
        conn.execute("""INSERT INTO aip_runtime_guard_policy_revision
            (org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,effective_from,
             effective_until,payload,created_by,created_at) VALUES(%s,%s,%s,%s,1,%s,
             'active',%s,%s,%s,%s,%s)""", (*scope.key,kind,item.policy_id,item.content_hash,
             item.effective_from,item.effective_until,Jsonb(item.model_dump(mode="json",by_alias=True)),
             item.created_by,item.created_at))
    network = materialize_network(scope,"隔离测试",NetworkPolicyRevisionCreate(
        policyId="qyh-network",revision=1,allowedSchemes=["https"],
        allowedHosts=["apihub.agnes-ai.com"],allowedPorts=[443],tlsRequired=True,
        publicFallbackAllowed=False,egressPolicyRef=VersionedAssetRef(assetType="EgressPolicyRevision",
            assetId=egress.policy_id,revision=1,contentHash=egress.content_hash),
        effectiveFrom=now-timedelta(minutes=1),effectiveUntil=now+timedelta(minutes=5),
        owner="隔离测试",approvalRef="approval:isolated",lifecycle="active"),created_at=now)
    conn.execute("INSERT INTO aip_network_policy_head VALUES(%s,%s,%s,1,1,NOW())",(*scope.key,network.policy_id))
    conn.execute("""INSERT INTO aip_network_policy_revision
        (org_id,project_id,policy_id,revision,content_hash,lifecycle,effective_from,effective_until,
         payload,created_by,created_at) VALUES(%s,%s,%s,1,%s,'active',%s,%s,%s,%s,%s)""",
        (*scope.key,network.policy_id,network.content_hash,network.effective_from,network.effective_until,
         Jsonb(network.model_dump(mode="json",by_alias=True)),network.created_by,network.created_at))
    budget = materialize_budget_revision(scope,"隔离测试",BudgetRevisionCreate(
        budgetId="qyh-budget",revision=1,environment="development",currency="CNY",
        dailyLimitMinor=100000,monthlyLimitMinor=1000000,alertThresholdPct=80,hardStop=True,
        unknownUsageBehavior="block",effectiveFrom=now-timedelta(minutes=1),
        effectiveUntil=now+timedelta(minutes=5),owner="隔离测试",overBudgetApprover="隔离审批",
        lifecycle="active"),created_at=now)
    conn.execute("INSERT INTO aip_budget_head VALUES(%s,%s,%s,1,1,NOW())",(*scope.key,budget.budget_id))
    conn.execute("""INSERT INTO aip_budget_revision(org_id,project_id,budget_id,revision,content_hash,lifecycle,
        environment,currency,daily_limit_minor,monthly_limit_minor,alert_threshold_pct,hard_stop,
        unknown_usage_behavior,effective_from,effective_until,owner,over_budget_approver,payload,created_by,created_at)
        VALUES(%s,%s,%s,1,%s,'active','development','CNY',%s,%s,%s,true,'block',%s,%s,%s,%s,%s,%s,%s)""",
        (*scope.key,budget.budget_id,budget.content_hash,budget.daily_limit_minor,budget.monthly_limit_minor,
         budget.alert_threshold_pct,budget.effective_from,budget.effective_until,budget.owner,
         budget.over_budget_approver,Jsonb(budget.model_dump(mode="json",by_alias=True)),budget.created_by,budget.created_at))
    quota = materialize_governance(scope,"隔离测试",QuotaPolicyRevisionCreate(
        policyId="qyh-quota",revision=1,environment="development",effectiveFrom=now-timedelta(minutes=1),
        effectiveUntil=now+timedelta(minutes=5),owner="隔离测试",approvalRef="approval:isolated",
        lifecycle="active",maxConcurrency=2,maxInputTokens=8000,maxOutputTokens=2000,
        hourlyRequestLimit=20,dailyRequestLimit=100,reservationLeaseSeconds=60,
        overflowBehavior="queue",allowPublicProviderFallback=False,allowAutoScale=False),created_at=now)
    budget_policy = materialize_governance(scope,"隔离测试",BudgetPolicyRevisionCreate(
        policyId="qyh-budget-policy",revision=1,environment="development",
        effectiveFrom=now-timedelta(minutes=1),effectiveUntil=now+timedelta(minutes=5),
        owner="隔离测试",approvalRef="approval:isolated",lifecycle="active",
        budgetRevisionRef=VersionedAssetRef(assetType="BudgetRevision",assetId=budget.budget_id,
            revision=1,contentHash=budget.content_hash),currency="CNY",hardStop=True,
        unknownUsageBehavior="block",unknownPriceBehavior="block",allowZeroPrice=False),created_at=now)
    for kind,item in (("quota",quota),("budget",budget_policy)):
        conn.execute("INSERT INTO aip_model_governance_policy_head VALUES(%s,%s,%s,%s,1,1,NOW())",
            (*scope.key,kind,item.policy_id))
        conn.execute("""INSERT INTO aip_model_governance_policy_revision
            (org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,effective_from,
             effective_until,payload,created_by,created_at) VALUES(%s,%s,%s,%s,1,%s,'active',%s,%s,%s,%s,%s)""",
            (*scope.key,kind,item.policy_id,item.content_hash,item.effective_from,item.effective_until,
             Jsonb(item.model_dump(mode="json",by_alias=True)),item.created_by,item.created_at))
    policy_payload=dict(tenant=TenantContext(orgId=scope.org_id,projectId=scope.project_id),
        policyId="qyh-extension-runtime",revision=1,networkPolicyRef=VersionedAssetRef(
            assetType="NetworkPolicyRevision",assetId=network.policy_id,revision=1,contentHash=network.content_hash),
        egressPolicyRef=VersionedAssetRef(assetType="EgressPolicyRevision",assetId=egress.policy_id,
            revision=1,contentHash=egress.content_hash),
        dataClassificationPolicyRef=VersionedAssetRef(assetType="DataClassificationPolicyRevision",
            assetId=data.policy_id,revision=1,contentHash=data.content_hash),
        quotaPolicyRef=VersionedAssetRef(assetType="QuotaPolicyRevision",assetId=quota.policy_id,
            revision=1,contentHash=quota.content_hash),
        budgetPolicyRef=VersionedAssetRef(assetType="BudgetPolicyRevision",assetId=budget_policy.policy_id,
            revision=1,contentHash=budget_policy.content_hash),deadlineMs=10_000,maxAttempts=2,
        allowedFallbackReasons=[],unknownUsageBehavior="block",unknownPriceBehavior="block",
        killSwitchEnabled=False,lifecycle=ModelRuntimeLifecycle.ACTIVE,createdBy="隔离测试",createdAt=now)
    provisional=RuntimePolicyRevision(**policy_payload,contentHash="0"*64)
    content={key:value for key,value in provisional.model_dump(mode="json",by_alias=True).items()
        if key not in {"tenant","revision","contentHash","createdBy","createdAt"}}
    policy=RuntimePolicyRevision(**policy_payload,contentHash=canonical_hash(content))
    conn.execute("INSERT INTO aip_runtime_policy_head VALUES(%s,%s,%s,1,1,NOW())",(*scope.key,policy.policy_id))
    conn.execute("""INSERT INTO aip_runtime_policy_revision
        (org_id,project_id,runtime_policy_id,revision,content_hash,lifecycle,payload,created_by,created_at)
        VALUES(%s,%s,%s,1,%s,'active',%s,%s,%s)""",(*scope.key,policy.policy_id,policy.content_hash,
        Jsonb(policy.model_dump(mode="json",by_alias=True)),policy.created_by,policy.created_at))
    conn.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)",scope.key)
    refs={
        "role":ConfigurationSourceRef(authority="aip.responsibility_plan_revision",id="qyh-runtime-roles",
            revision=1,hash="sha256:"+responsibility_hash),
        "data":ConfigurationSourceRef(authority="aip.data_classification_policy_revision",id=data.policy_id,
            revision=1,hash="sha256:"+data.content_hash),
        "policy":ConfigurationSourceRef(authority="aip.runtime_policy_revision",id=policy.policy_id,
            revision=1,hash="sha256:"+policy.content_hash),
        "budget":ConfigurationSourceRef(authority="aip.budget_revision",id=budget.budget_id,
            revision=1,hash="sha256:"+budget.content_hash),
    }
    refs["configuration"]=ConfigurationDocument(roleRefs=(refs["role"],),dataRefs=(refs["data"],),
        budgetRef=refs["budget"],policyRef=refs["policy"])
    refs["runtime"]=policy
    refs["items"]={"network":network,"egress":egress,"data":data,"quota":quota,
        "budget_policy":budget_policy}
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))
    conn.execute("""GRANT SELECT ON aip_runtime_guard_policy_head,aip_runtime_guard_policy_revision,
                     aip_runtime_policy_head,aip_runtime_policy_revision,aip_network_policy_head,
                     aip_network_policy_revision,aip_model_governance_policy_head,
                     aip_model_governance_policy_revision,aip_budget_head,aip_budget_revision,
                     aip_responsibility_plan_head,aip_responsibility_plan_revision TO aos_runtime""")
    conn.execute("SET ROLE aos_runtime")
    return conn,refs


def test_current_responsibility_plan_ref_uses_original_frozen_authority(source_case):
    from aos_api.aip_runtime_configuration_sources import read_current_responsibility_plan_ref
    conn,refs=source_case
    with conn.transaction():
        assert read_current_responsibility_plan_ref(conn,org_id="org-org",project_id="dev-project",
            purpose="role",ref=refs["role"]) is True


@pytest.mark.parametrize("case",("scope","purpose","authority","hash","head","lifecycle","payload"))
def test_current_responsibility_plan_ref_fails_closed(source_case,case):
    from aos_api.aip_runtime_configuration_sources import read_current_responsibility_plan_ref
    conn,refs=source_case
    ref=refs["role"]
    org_id="org-org"
    purpose="role"
    mutation=case in {"head","lifecycle","payload"}
    conn.execute("BEGIN")
    if mutation:conn.execute("RESET ROLE")
    if case=="scope":org_id="dev-org"
    elif case=="purpose":purpose="data"
    elif case=="authority":ref=ref.model_copy(update={"authority":"test.role"})
    elif case=="hash":ref=ref.model_copy(update={"hash":"sha256:"+"f"*64})
    elif case=="head":conn.execute("UPDATE aip_responsibility_plan_head SET current_revision=2")
    elif case in {"lifecycle","payload"}:
        conn.execute("""INSERT INTO aip_responsibility_plan_revision
            (org_id,project_id,plan_id,revision,profile,template_ref,slots,merge_decisions,
             profile_recommendation_ref,profile_confirmation_id,merge_policy_ref,
             merge_decision_receipt_ids,content_hash,lifecycle,created_by,created_at)
            SELECT org_id,project_id,plan_id,2,%s,template_ref,slots,merge_decisions,
                   profile_recommendation_ref,profile_confirmation_id,merge_policy_ref,
                   merge_decision_receipt_ids,content_hash,%s,created_by,created_at
              FROM aip_responsibility_plan_revision WHERE revision=1""",
            ("drifted-profile" if case=="payload" else "qyh-extension-runtime",
             "draft" if case=="lifecycle" else "frozen"))
        conn.execute("UPDATE aip_responsibility_plan_head SET current_revision=2")
        ref=ref.model_copy(update={"revision":2})
    if mutation:conn.execute("SET ROLE aos_runtime")
    with pytest.raises((ValueError,LookupError,PermissionError)):
        with conn.transaction():
            read_current_responsibility_plan_ref(conn,org_id=org_id,project_id="dev-project",
                purpose=purpose,ref=ref)
    conn.execute("RESET ROLE")
    conn.execute("ROLLBACK")
    conn.execute("SET ROLE aos_runtime")


def test_current_responsibility_plan_ref_rejects_privileged_connection(source_case):
    from aos_api.aip_runtime_configuration_sources import read_current_responsibility_plan_ref
    conn,refs=source_case
    conn.execute("RESET ROLE")
    try:
        with pytest.raises(PermissionError):
            with conn.transaction():
                read_current_responsibility_plan_ref(conn,org_id="org-org",project_id="dev-project",
                    purpose="role",ref=refs["role"])
    finally:
        conn.execute("SET ROLE aos_runtime")


def test_current_responsibility_plan_head_is_locked_until_authorization_finishes(source_case):
    from aos_api.aip_runtime_configuration_sources import read_current_responsibility_plan_ref
    conn,refs=source_case
    conn.execute("RESET ROLE")
    schema=conn.execute("SELECT current_schema()").fetchone()[0]
    conn.execute("SET ROLE aos_runtime")
    with psycopg.connect(host="127.0.0.1",port=18432,user="postgres",dbname="postgres",autocommit=True) as writer:
        writer.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        writer.execute("SET statement_timeout='250ms'")
        with conn.transaction():
            assert read_current_responsibility_plan_ref(conn,org_id="org-org",project_id="dev-project",
                purpose="role",ref=refs["role"]) is True
            with pytest.raises(psycopg.errors.QueryCanceled):
                writer.execute("UPDATE aip_responsibility_plan_head SET version=version+1")


def test_current_data_and_runtime_policy_refs_use_original_authorities(source_case):
    from aos_api.aip_runtime_configuration_sources import (
        read_current_data_classification_ref, read_current_runtime_policy_ref,
    )
    conn,refs=source_case
    with conn.transaction():
        assert read_current_data_classification_ref(conn,org_id="org-org",project_id="dev-project",
            purpose="data",ref=refs["data"]) is True
        assert read_current_runtime_policy_ref(conn,org_id="org-org",project_id="dev-project",
            purpose="policy",ref=refs["policy"],configuration=refs["configuration"]) is True


def _assert_source_fails_closed(source_case,case):
    from aos_api.aip_runtime_configuration_sources import (
        read_current_data_classification_ref, read_current_runtime_policy_ref,
    )
    conn,refs=source_case
    conn.execute("BEGIN")
    reader=read_current_data_classification_ref
    purpose="data"
    ref=refs["data"]
    org_id="org-org"
    mutation=case in {"data_head","data_expired","policy_head","policy_inactive","policy_kill","payload"}
    if mutation:conn.execute("RESET ROLE")
    if case=="scope":org_id="dev-org"
    elif case=="purpose":purpose="policy"
    elif case=="authority":ref=ref.model_copy(update={"authority":"test.data"})
    elif case=="hash":ref=ref.model_copy(update={"hash":"sha256:"+"f"*64})
    elif case=="data_head":conn.execute("UPDATE aip_runtime_guard_policy_head SET current_revision=2")
    elif case=="data_expired":
        from aos_api.aip_runtime_guard_policy_contracts import DataClassificationPolicyRevisionCreate
        from aos_api.aip_runtime_guard_policy_store import materialize_policy
        from aos_api.tenant_scope import TenantScope
        payload=conn.execute("SELECT payload FROM aip_runtime_guard_policy_revision WHERE policy_kind='data_classification'").fetchone()[0]
        content={key:value for key,value in payload.items()
            if key not in {"tenant","contentHash","createdBy","createdAt"}}
        content.update(revision=2,effectiveFrom=datetime.now(timezone.utc)-timedelta(minutes=10),
            effectiveUntil=datetime.now(timezone.utc)-timedelta(seconds=1))
        expired=materialize_policy(TenantScope("org-org","dev-project"),"隔离测试",
            DataClassificationPolicyRevisionCreate.model_validate(content))
        conn.execute("""INSERT INTO aip_runtime_guard_policy_revision
            (org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,effective_from,
             effective_until,payload,created_by,created_at) VALUES('org-org','dev-project',
             'data_classification',%s,2,%s,'active',%s,%s,%s,%s,%s)""",
            (expired.policy_id,expired.content_hash,expired.effective_from,expired.effective_until,
             Jsonb(expired.model_dump(mode="json",by_alias=True)),expired.created_by,expired.created_at))
        conn.execute("UPDATE aip_runtime_guard_policy_head SET current_revision=2")
        ref=ref.model_copy(update={"revision":2,"hash":"sha256:"+expired.content_hash})
    elif case in {"policy_head","policy_inactive","policy_kill","payload"}:
        reader=read_current_runtime_policy_ref
        purpose="policy"
        ref=refs["policy"]
        if case=="policy_head":conn.execute("UPDATE aip_runtime_policy_head SET current_revision=2")
        if case in {"policy_inactive","policy_kill"}:
            from aos_api.aip_model_runtime_contracts import RuntimePolicyRevision
            from aos_api.aip_model_runtime_store import canonical_hash
            payload=conn.execute("SELECT payload FROM aip_runtime_policy_revision").fetchone()[0]
            payload.update(revision=2,killSwitchEnabled=case=="policy_kill",
                lifecycle="suspended" if case=="policy_inactive" else "active",contentHash="0"*64)
            content={key:value for key,value in payload.items()
                if key not in {"tenant","revision","contentHash","createdBy","createdAt"}}
            payload["contentHash"]=canonical_hash(content)
            policy=RuntimePolicyRevision.model_validate(payload)
            conn.execute("""INSERT INTO aip_runtime_policy_revision
                (org_id,project_id,runtime_policy_id,revision,content_hash,lifecycle,payload,created_by,created_at)
                VALUES('org-org','dev-project',%s,2,%s,%s,%s,%s,%s)""",
                (policy.policy_id,policy.content_hash,policy.lifecycle.value,
                 Jsonb(policy.model_dump(mode="json",by_alias=True)),policy.created_by,policy.created_at))
            conn.execute("UPDATE aip_runtime_policy_head SET current_revision=2")
            ref=ref.model_copy(update={"revision":2,"hash":"sha256:"+policy.content_hash})
        if case=="payload":
            conn.execute("""INSERT INTO aip_runtime_policy_revision
                (org_id,project_id,runtime_policy_id,revision,content_hash,lifecycle,payload,created_by,created_at)
                SELECT org_id,project_id,runtime_policy_id,2,%s,lifecycle,
                       jsonb_set(jsonb_set(jsonb_set(payload,'{revision}','2'),'{deadlineMs}','20000'),
                                 '{contentHash}',to_jsonb(%s::text)),created_by,created_at
                  FROM aip_runtime_policy_revision WHERE revision=1""",("e"*64,"e"*64))
            conn.execute("UPDATE aip_runtime_policy_head SET current_revision=2")
            ref=ref.model_copy(update={"revision":2,"hash":"sha256:"+"e"*64})
    if mutation:conn.execute("SET ROLE aos_runtime")
    with pytest.raises((ValueError,LookupError,PermissionError)):
        with conn.transaction():reader(conn,org_id=org_id,project_id="dev-project",purpose=purpose,ref=ref,
            **({"configuration":refs["configuration"]} if reader is read_current_runtime_policy_ref else {}))
    conn.execute("RESET ROLE")
    conn.execute("ROLLBACK")
    conn.execute("SET ROLE aos_runtime")


def test_current_sources_fail_closed(source_case):
    for case in (
        "scope","purpose","authority","hash","data_head","data_expired","policy_head",
        "policy_inactive","policy_kill","payload",
    ):
        _assert_source_fails_closed(source_case,case)


def test_current_sources_reject_privileged_connection(source_case):
    from aos_api.aip_runtime_configuration_sources import read_current_data_classification_ref
    conn,refs=source_case
    conn.execute("RESET ROLE")
    try:
        with pytest.raises(PermissionError):
            with conn.transaction():
                read_current_data_classification_ref(conn,org_id="org-org",project_id="dev-project",
                    purpose="data",ref=refs["data"])
    finally:
        conn.execute("SET ROLE aos_runtime")


def test_runtime_policy_fails_closed_when_any_dependency_head_drifts(source_case):
    from aos_api.aip_runtime_configuration_sources import read_current_runtime_policy_ref
    conn,refs=source_case
    mutations=(
        "UPDATE aip_network_policy_head SET current_revision=2",
        "UPDATE aip_runtime_guard_policy_head SET current_revision=2 WHERE policy_kind='egress'",
        "UPDATE aip_runtime_guard_policy_head SET current_revision=2 WHERE policy_kind='data_classification'",
        "UPDATE aip_model_governance_policy_head SET current_revision=2 WHERE policy_kind='quota'",
        "UPDATE aip_model_governance_policy_head SET current_revision=2 WHERE policy_kind='budget'",
        "UPDATE aip_budget_head SET current_revision=2",
    )
    for mutation in mutations:
        conn.execute("BEGIN")
        conn.execute("RESET ROLE")
        conn.execute(mutation)
        conn.execute("SET ROLE aos_runtime")
        with pytest.raises((ValueError,LookupError,PermissionError)):
            with conn.transaction():
                read_current_runtime_policy_ref(conn,org_id="org-org",project_id="dev-project",
                    purpose="policy",ref=refs["policy"],configuration=refs["configuration"])
        conn.execute("RESET ROLE")
        conn.execute("ROLLBACK")
        conn.execute("SET ROLE aos_runtime")


@pytest.mark.parametrize("binding",("missing_data","wrong_data","wrong_budget","missing_document"))
def test_runtime_policy_rejects_unbound_configuration(source_case,binding):
    from aos_api.aip_runtime_configuration_sources import read_current_runtime_policy_ref
    conn,refs=source_case
    document=refs["configuration"]
    if binding=="missing_data":document=document.model_copy(update={"dataRefs":()})
    elif binding=="wrong_data":document=document.model_copy(update={"dataRefs":(
        refs["data"].model_copy(update={"revision":2}),)})
    elif binding=="wrong_budget":document=document.model_copy(update={"budgetRef":
        refs["budget"].model_copy(update={"hash":"sha256:"+"f"*64})})
    else:document=None
    with pytest.raises((ValueError,PermissionError)):
        with conn.transaction():
            read_current_runtime_policy_ref(conn,org_id="org-org",project_id="dev-project",
                purpose="policy",ref=refs["policy"],configuration=document)


def _install_dependency_revision(conn,refs,key,mode):
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from aos_api.aip_model_governance_policy_contracts import (
        BudgetPolicyRevisionCreate, QuotaPolicyRevisionCreate,
    )
    from aos_api.aip_model_governance_policy_store import materialize_policy as governance
    from aos_api.aip_model_runtime_contracts import RuntimePolicyRevision
    from aos_api.aip_model_runtime_store import canonical_hash as runtime_hash
    from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
    from aos_api.aip_network_policy_store import materialize_policy as network
    from aos_api.aip_runtime_guard_policy_contracts import (
        DataClassificationPolicyRevisionCreate, EgressPolicyRevisionCreate,
    )
    from aos_api.aip_runtime_guard_policy_store import materialize_policy as guard
    from aos_api.tenant_scope import TenantScope

    specifications={
        "network":(NetworkPolicyRevisionCreate,network,"networkPolicyRef","NetworkPolicyRevision"),
        "egress":(EgressPolicyRevisionCreate,guard,"egressPolicyRef","EgressPolicyRevision"),
        "data":(DataClassificationPolicyRevisionCreate,guard,"dataClassificationPolicyRef",
            "DataClassificationPolicyRevision"),
        "quota":(QuotaPolicyRevisionCreate,governance,"quotaPolicyRef","QuotaPolicyRevision"),
        "budget_policy":(BudgetPolicyRevisionCreate,governance,"budgetPolicyRef","BudgetPolicyRevision"),
    }
    create,materialize,runtime_field,asset_type=specifications[key]
    original=refs["items"][key]
    content={name:value for name,value in original.model_dump(mode="json",by_alias=True).items()
        if name not in {"tenant","contentHash","createdBy","createdAt"}}
    content["revision"]=2
    if mode=="inactive":content["lifecycle"]="suspended"
    elif mode=="expired":
        content["effectiveFrom"]=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()
        content["effectiveUntil"]=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    elif mode=="network_egress_mismatch":
        content["egressPolicyRef"]={"assetType":"EgressPolicyRevision","assetId":"other-egress",
            "revision":1,"contentHash":"f"*64}
    item=materialize(TenantScope("org-org","dev-project"),"隔离测试",create.model_validate(content))
    payload=item.model_dump(mode="json",by_alias=True)
    content_hash=item.content_hash
    if mode=="payload":
        content_hash="e"*64
        payload["contentHash"]=content_hash
    if key=="network":
        conn.execute("""INSERT INTO aip_network_policy_revision(org_id,project_id,policy_id,revision,
            content_hash,lifecycle,effective_from,effective_until,payload,created_by,created_at)
            VALUES('org-org','dev-project',%s,2,%s,%s,%s,%s,%s,%s,%s)""",
            (item.policy_id,content_hash,item.lifecycle.value,item.effective_from,item.effective_until,
             Jsonb(payload),item.created_by,item.created_at))
        conn.execute("UPDATE aip_network_policy_head SET current_revision=2")
    elif key in {"egress","data"}:
        policy_kind="data_classification" if key=="data" else key
        conn.execute("""INSERT INTO aip_runtime_guard_policy_revision(org_id,project_id,policy_kind,
            policy_id,revision,content_hash,lifecycle,effective_from,effective_until,payload,created_by,created_at)
            VALUES('org-org','dev-project',%s,%s,2,%s,%s,%s,%s,%s,%s,%s)""",
            (policy_kind,item.policy_id,content_hash,item.lifecycle.value,item.effective_from,item.effective_until,
             Jsonb(payload),item.created_by,item.created_at))
        conn.execute("UPDATE aip_runtime_guard_policy_head SET current_revision=2 WHERE policy_kind=%s",
            (policy_kind,))
    else:
        policy_kind="budget" if key=="budget_policy" else key
        conn.execute("""INSERT INTO aip_model_governance_policy_revision(org_id,project_id,policy_kind,
            policy_id,revision,content_hash,lifecycle,effective_from,effective_until,payload,created_by,created_at)
            VALUES('org-org','dev-project',%s,%s,2,%s,%s,%s,%s,%s,%s,%s)""",
            (policy_kind,item.policy_id,content_hash,item.lifecycle.value,item.effective_from,item.effective_until,
             Jsonb(payload),item.created_by,item.created_at))
        conn.execute("UPDATE aip_model_governance_policy_head SET current_revision=2 WHERE policy_kind=%s",
            (policy_kind,))
    dependency_ref=VersionedAssetRef(assetType=asset_type,assetId=item.policy_id,revision=2,
        contentHash=content_hash)
    runtime_payload=refs["runtime"].model_dump(mode="json",by_alias=True)
    runtime_payload.update(revision=2,contentHash="0"*64)
    runtime_payload[runtime_field]=dependency_ref.model_dump(mode="json",by_alias=True)
    runtime_content={name:value for name,value in runtime_payload.items()
        if name not in {"tenant","revision","contentHash","createdBy","createdAt"}}
    runtime_payload["contentHash"]=runtime_hash(runtime_content)
    runtime=RuntimePolicyRevision.model_validate(runtime_payload)
    conn.execute("""INSERT INTO aip_runtime_policy_revision(org_id,project_id,runtime_policy_id,revision,
        content_hash,lifecycle,payload,created_by,created_at) VALUES('org-org','dev-project',%s,2,%s,
        'active',%s,%s,%s)""",(runtime.policy_id,runtime.content_hash,
        Jsonb(runtime.model_dump(mode="json",by_alias=True)),runtime.created_by,runtime.created_at))
    conn.execute("UPDATE aip_runtime_policy_head SET current_revision=2")
    policy_ref=refs["policy"].model_copy(update={"revision":2,"hash":"sha256:"+runtime.content_hash})
    configuration=refs["configuration"].model_copy(update={"policyRef":policy_ref})
    if key=="data":
        configuration=configuration.model_copy(update={"dataRefs":(
            refs["data"].model_copy(update={"revision":2,"hash":"sha256:"+content_hash}),)})
    return policy_ref,configuration


def test_runtime_dependencies_reject_lifecycle_time_payload_and_cross_binding_drift(source_case):
    from aos_api.aip_runtime_configuration_sources import read_current_runtime_policy_ref
    conn,refs=source_case
    cases=tuple((key,mode) for key in ("network","egress","quota","budget_policy")
        for mode in ("inactive","expired","payload"))+(("network","network_egress_mismatch"),)
    for key,mode in cases:
        conn.execute("BEGIN")
        conn.execute("RESET ROLE")
        policy_ref,configuration=_install_dependency_revision(conn,refs,key,mode)
        conn.execute("SET ROLE aos_runtime")
        with pytest.raises((ValueError,LookupError,PermissionError)):
            with conn.transaction():
                read_current_runtime_policy_ref(conn,org_id="org-org",project_id="dev-project",
                    purpose="policy",ref=policy_ref,configuration=configuration)
        conn.execute("RESET ROLE")
        conn.execute("ROLLBACK")
        conn.execute("SET ROLE aos_runtime")


def test_data_effective_time_is_checked_after_authority_lock_wait(source_case):
    from aos_api.aip_runtime_configuration_sources import read_current_data_classification_ref
    from aos_api.aip_runtime_guard_policy_contracts import DataClassificationPolicyRevisionCreate
    from aos_api.aip_runtime_guard_policy_store import materialize_policy
    from aos_api.tenant_scope import TenantScope

    conn,refs=source_case
    conn.execute("RESET ROLE")
    schema=conn.execute("SELECT current_schema()").fetchone()[0]
    payload=conn.execute("SELECT payload FROM aip_runtime_guard_policy_revision WHERE policy_kind='data_classification' AND revision=1").fetchone()[0]
    content={key:value for key,value in payload.items()
        if key not in {"tenant","contentHash","createdBy","createdAt"}}
    expires_at=datetime.now(timezone.utc)+timedelta(seconds=1)
    content.update(revision=2,effectiveFrom=datetime.now(timezone.utc)-timedelta(minutes=1),
        effectiveUntil=expires_at)
    short=materialize_policy(TenantScope("org-org","dev-project"),"隔离测试",
        DataClassificationPolicyRevisionCreate.model_validate(content))
    conn.execute("""INSERT INTO aip_runtime_guard_policy_revision
        (org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,effective_from,
         effective_until,payload,created_by,created_at) VALUES('org-org','dev-project',
         'data_classification',%s,2,%s,'active',%s,%s,%s,%s,%s)""",
        (short.policy_id,short.content_hash,short.effective_from,short.effective_until,
         Jsonb(short.model_dump(mode="json",by_alias=True)),short.created_by,short.created_at))
    conn.execute("UPDATE aip_runtime_guard_policy_head SET current_revision=2")
    ref=refs["data"].model_copy(update={"revision":2,"hash":"sha256:"+short.content_hash})
    with psycopg.connect(host="127.0.0.1",port=18432,user="postgres",dbname="postgres",autocommit=True) as worker:
        worker.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        worker.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
        worker.execute("SET ROLE aos_runtime")
        pid=worker.info.backend_pid
        def read():
            with worker.transaction():
                return read_current_data_classification_ref(worker,org_id="org-org",project_id="dev-project",
                    purpose="data",ref=ref)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with conn.transaction():
                conn.execute("SELECT current_revision FROM aip_runtime_guard_policy_head WHERE policy_kind='data_classification' FOR UPDATE")
                future=pool.submit(read)
                deadline=time.monotonic()+3
                while not conn.execute("SELECT cardinality(pg_blocking_pids(%s))>0",(pid,)).fetchone()[0]:
                    if time.monotonic()>deadline:raise AssertionError("reader did not wait on authority lock")
                    time.sleep(.02)
                time.sleep(max(0,(expires_at-datetime.now(timezone.utc)).total_seconds())+.1)
            with pytest.raises(PermissionError,match="not effective"):
                future.result(timeout=3)
    conn.execute("SET ROLE aos_runtime")


def test_combined_policy_rechecks_earlier_windows_after_later_lock_wait(source_case):
    from aos_api.aip_model_runtime_contracts import RuntimePolicyRevision
    from aos_api.aip_model_runtime_store import canonical_hash
    from aos_api.aip_runtime_configuration_sources import read_current_runtime_policy_ref
    from aos_api.aip_runtime_guard_policy_contracts import DataClassificationPolicyRevisionCreate
    from aos_api.aip_runtime_guard_policy_store import materialize_policy
    from aos_api.tenant_scope import TenantScope

    conn,refs=source_case
    conn.execute("RESET ROLE")
    schema=conn.execute("SELECT current_schema()").fetchone()[0]
    expires_at=datetime.now(timezone.utc)+timedelta(seconds=1)
    payload=conn.execute("SELECT payload FROM aip_runtime_guard_policy_revision "
        "WHERE policy_kind='data_classification' AND revision=1").fetchone()[0]
    content={key:value for key,value in payload.items()
        if key not in {"tenant","contentHash","createdBy","createdAt"}}
    content.update(revision=2,effectiveFrom=datetime.now(timezone.utc)-timedelta(minutes=1),
        effectiveUntil=expires_at)
    data=materialize_policy(TenantScope("org-org","dev-project"),"隔离测试",
        DataClassificationPolicyRevisionCreate.model_validate(content))
    conn.execute("""INSERT INTO aip_runtime_guard_policy_revision
        (org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,effective_from,
         effective_until,payload,created_by,created_at) VALUES('org-org','dev-project',
         'data_classification',%s,2,%s,'active',%s,%s,%s,%s,%s)""",
        (data.policy_id,data.content_hash,data.effective_from,data.effective_until,
         Jsonb(data.model_dump(mode="json",by_alias=True)),data.created_by,data.created_at))
    conn.execute("UPDATE aip_runtime_guard_policy_head SET current_revision=2 "
        "WHERE policy_kind='data_classification'")
    policy_payload=conn.execute("SELECT payload FROM aip_runtime_policy_revision WHERE revision=1").fetchone()[0]
    policy_payload.update(revision=2,contentHash="0"*64,dataClassificationPolicyRef={
        "assetType":"DataClassificationPolicyRevision","assetId":data.policy_id,
        "revision":2,"contentHash":data.content_hash})
    policy_content={key:value for key,value in policy_payload.items()
        if key not in {"tenant","revision","contentHash","createdBy","createdAt"}}
    policy_payload["contentHash"]=canonical_hash(policy_content)
    policy=RuntimePolicyRevision.model_validate(policy_payload)
    conn.execute("""INSERT INTO aip_runtime_policy_revision
        (org_id,project_id,runtime_policy_id,revision,content_hash,lifecycle,payload,created_by,created_at)
        VALUES('org-org','dev-project',%s,2,%s,'active',%s,%s,%s)""",
        (policy.policy_id,policy.content_hash,Jsonb(policy.model_dump(mode="json",by_alias=True)),
         policy.created_by,policy.created_at))
    conn.execute("UPDATE aip_runtime_policy_head SET current_revision=2")
    data_ref=refs["data"].model_copy(update={"revision":2,"hash":"sha256:"+data.content_hash})
    policy_ref=refs["policy"].model_copy(update={"revision":2,"hash":"sha256:"+policy.content_hash})
    configuration=refs["configuration"].model_copy(update={"dataRefs":(data_ref,),"policyRef":policy_ref})
    with psycopg.connect(host="127.0.0.1",port=18432,user="postgres",dbname="postgres",autocommit=True) as worker:
        worker.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        worker.execute("SELECT set_config('aos.org_id','org-org',false),"
            "set_config('aos.project_id','dev-project',false)")
        worker.execute("SET ROLE aos_runtime")
        pid=worker.info.backend_pid
        def read():
            with worker.transaction():
                return read_current_runtime_policy_ref(worker,org_id="org-org",project_id="dev-project",
                    purpose="policy",ref=policy_ref,configuration=configuration)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with conn.transaction():
                conn.execute("SELECT current_revision FROM aip_model_governance_policy_head "
                    "WHERE policy_kind='quota' FOR UPDATE")
                future=pool.submit(read)
                deadline=time.monotonic()+3
                while not conn.execute("SELECT cardinality(pg_blocking_pids(%s))>0",(pid,)).fetchone()[0]:
                    if time.monotonic()>deadline:raise AssertionError("combined reader did not wait on later lock")
                    time.sleep(.02)
                time.sleep(max(0,(expires_at-datetime.now(timezone.utc)).total_seconds())+.1)
            with pytest.raises(PermissionError,match="expired during"):
                future.result(timeout=3)
    conn.execute("SET ROLE aos_runtime")
