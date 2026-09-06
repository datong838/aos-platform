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
    from aos_api.aip_contracts import TenantContext
    from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle, RuntimePolicyRevision
    from aos_api.aip_model_runtime_store import canonical_hash
    from aos_api.aip_runtime_guard_policy_contracts import DataClassificationPolicyRevisionCreate
    from aos_api.aip_runtime_guard_policy_store import materialize_policy
    from aos_api.extension_runtime.configuration_contracts import ConfigurationSourceRef
    from aos_api.tenant_scope import TenantScope

    conn, _, schema = database
    conn.execute("""CREATE FUNCTION guard_aip4_append_only() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'AIP4_APPEND_ONLY' USING ERRCODE='55000'; END; $$ LANGUAGE plpgsql""")
    _migration(conn, "aip7_001_model_runtime_authority.py", "ar1c_aip7")
    _migration(conn, "aip10_002_runtime_guard_policy_authority.py", "ar1c_aip10_guard")
    now = datetime.now(timezone.utc)
    scope = TenantScope("org-org", "dev-project")
    data = materialize_policy(scope, "隔离测试", DataClassificationPolicyRevisionCreate(
        policyId="qyh-public-catalog", revision=1, environment="development",
        effectiveFrom=now-timedelta(minutes=1), effectiveUntil=now+timedelta(minutes=5),
        owner="隔离测试", approvalRef="approval:isolated", lifecycle="active",
        allowedClassifications=["public_catalog"], prohibitedClassifications=[
            "direct_pii", "raw_order_detail", "customer_conversation", "credential",
            "commercial_sensitive", "cross_tenant", "unknown",
        ],
        denyUnknown=True, allowDirectPii=False, allowCommercialSensitive=False, allowCrossTenant=False,
    ), created_at=now)
    data_payload=data.model_dump(mode="json", by_alias=True)
    conn.execute("INSERT INTO aip_runtime_guard_policy_head VALUES(%s,%s,'data_classification',%s,1,1,NOW())",
        (*scope.key, data.policy_id))
    conn.execute("""INSERT INTO aip_runtime_guard_policy_revision
        (org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,effective_from,
         effective_until,payload,created_by,created_at) VALUES(%s,%s,'data_classification',%s,1,%s,
         'active',%s,%s,%s,%s,%s)""", (*scope.key,data.policy_id,data.content_hash,
         data.effective_from,data.effective_until,Jsonb(data_payload),data.created_by,data.created_at))
    arbitrary=lambda kind,name,digit:VersionedAssetRef(assetType=kind,assetId=name,revision=1,contentHash=digit*64)
    policy_payload=dict(tenant=TenantContext(orgId=scope.org_id,projectId=scope.project_id),
        policyId="qyh-extension-runtime",revision=1,networkPolicyRef=arbitrary("NetworkPolicyRevision","network","1"),
        egressPolicyRef=arbitrary("EgressPolicyRevision","egress","2"),
        dataClassificationPolicyRef=VersionedAssetRef(assetType="DataClassificationPolicyRevision",
            assetId=data.policy_id,revision=1,contentHash=data.content_hash),
        quotaPolicyRef=arbitrary("QuotaPolicyRevision","quota","3"),
        budgetPolicyRef=arbitrary("BudgetPolicyRevision","budget","4"),deadlineMs=10_000,maxAttempts=2,
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
        "data":ConfigurationSourceRef(authority="aip.data_classification_policy_revision",id=data.policy_id,
            revision=1,hash="sha256:"+data.content_hash),
        "policy":ConfigurationSourceRef(authority="aip.runtime_policy_revision",id=policy.policy_id,
            revision=1,hash="sha256:"+policy.content_hash),
    }
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))
    conn.execute("""GRANT SELECT ON aip_runtime_guard_policy_head,aip_runtime_guard_policy_revision,
                     aip_runtime_policy_head,aip_runtime_policy_revision TO aos_runtime""")
    conn.execute("SET ROLE aos_runtime")
    return conn,refs


def test_current_data_and_runtime_policy_refs_use_original_authorities(source_case):
    from aos_api.aip_runtime_configuration_sources import (
        read_current_data_classification_ref, read_current_runtime_policy_ref,
    )
    conn,refs=source_case
    with conn.transaction():
        assert read_current_data_classification_ref(conn,org_id="org-org",project_id="dev-project",
            purpose="data",ref=refs["data"]) is True
        assert read_current_runtime_policy_ref(conn,org_id="org-org",project_id="dev-project",
            purpose="policy",ref=refs["policy"]) is True


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
        payload=conn.execute("SELECT payload FROM aip_runtime_guard_policy_revision").fetchone()[0]
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
        with conn.transaction():reader(conn,org_id=org_id,project_id="dev-project",purpose=purpose,ref=ref)
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


def test_data_effective_time_is_checked_after_authority_lock_wait(source_case):
    from aos_api.aip_runtime_configuration_sources import read_current_data_classification_ref
    from aos_api.aip_runtime_guard_policy_contracts import DataClassificationPolicyRevisionCreate
    from aos_api.aip_runtime_guard_policy_store import materialize_policy
    from aos_api.tenant_scope import TenantScope

    conn,refs=source_case
    conn.execute("RESET ROLE")
    schema=conn.execute("SELECT current_schema()").fetchone()[0]
    payload=conn.execute("SELECT payload FROM aip_runtime_guard_policy_revision WHERE revision=1").fetchone()[0]
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
                conn.execute("SELECT current_revision FROM aip_runtime_guard_policy_head FOR UPDATE")
                future=pool.submit(read)
                deadline=time.monotonic()+3
                while not conn.execute("SELECT cardinality(pg_blocking_pids(%s))>0",(pid,)).fetchone()[0]:
                    if time.monotonic()>deadline:raise AssertionError("reader did not wait on authority lock")
                    time.sleep(.02)
                time.sleep(max(0,(expires_at-datetime.now(timezone.utc)).total_seconds())+.1)
            with pytest.raises(PermissionError,match="not effective"):
                future.result(timeout=3)
    conn.execute("SET ROLE aos_runtime")
