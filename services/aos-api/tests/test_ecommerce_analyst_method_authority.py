from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_analyst_authority_contracts import MethodRevision, AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import (
    EcommerceAnalystAuthorityStore, AnalystAuthorityConflict, AnalystAuthorityNotFound,
    AnalystAuthorityIdempotencyConflict, canonical_hash,
)
from aos_api.ecommerce_analyst_growth_plan_sources import require_current_revision
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")


def method():
    result = MethodRevision(tenant=dict(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        methodId="descriptive-snapshot", revision=1, version=1, contentHash="a" * 64,
        name="来源事实画像", description="归纳已披露事实并保留来源与限制", algorithm="descriptive_snapshot_v1",
        insightKind="observation", minSourceItems=1, maxSourceAgeSeconds=86400,
        limitations=["描述观察结果，不证明因果关系"], createdBy="compiler", createdAt=datetime.now(timezone.utc))
    return hashed(result)


def hashed(item):
    return item.model_copy(update={"content_hash": canonical_hash(item.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))})


@pytest.mark.parametrize("field,value", [("algorithm", "arbitrary"), ("insight_kind", "causal_claim"), ("min_source_items", 0),
    ("min_source_items", True), ("min_source_items", 101), ("max_source_age_seconds", 0), ("max_source_age_seconds", 31536001),
    ("limitations", []), ("limitations", [" "]), ("name", " "), ("description", ""), ("revision", 2)])
def test_method_contract_rejects_unsupported_or_incomplete_definition(field, value):
    body = method().model_dump(mode="python")
    body[field] = value
    with pytest.raises(ValueError): MethodRevision.model_validate(body)


@pytest.mark.parametrize("drift", ["hash", "actor", "tenant", "key", "version"])
def test_invalid_publication_is_rejected_before_storage(drift):
    def forbidden(scope): raise AssertionError("invalid publication must not connect")
    item, actor, key, version = method(), "compiler", "method", 0
    if drift == "hash": item = item.model_copy(update={"description": "changed"})
    elif drift == "actor": actor = "other"
    elif drift == "tenant": item = item.model_copy(update={"tenant": item.tenant.model_copy(update={"org_id": "dev-org"})})
    elif drift == "key": key = " "
    else: version = True
    with pytest.raises(AnalystAuthorityConflict): EcommerceAnalystAuthorityStore(forbidden).publish_method(SCOPE, actor, key, item, expected_version=version)


@pytest.mark.parametrize("change", ["body", "identity", "hash", "kind", "tenant"])
def test_exact_read_rejects_payload_and_scope_drift(change):
    from test_ecommerce_analyst_authority_store import Connection, factory
    item = method()
    ref = AnalystExactRef(resourceType="MethodRevision", resourceId=item.method_id, revision=1, contentHash=item.content_hash)
    body = item.model_dump(mode="json", by_alias=True)
    if change == "body": body["description"] = "changed"
    elif change == "identity": body["methodId"] = "other"
    elif change == "hash": body["contentHash"] = "b" * 64
    elif change == "kind": ref = ref.model_copy(update={"resource_type": "InsightRevision"})
    else: body["tenant"]["orgId"] = "dev-org"
    with pytest.raises((AnalystAuthorityNotFound, AnalystAuthorityConflict)):
        EcommerceAnalystAuthorityStore(factory(Connection(rows=[dict(payload=body, content_hash=item.content_hash)]))).get_method_exact(SCOPE, ref)


def apply_migrations(connect):
    for filename in ["a0v_012_agent_text_output.py", "a0v_013_analyst_method.py"]:
        path = Path(__file__).resolve().parents[1] / "alembic/versions" / filename
        spec = importlib.util.spec_from_file_location("method_test_" + filename[:-3], path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with connect(SCOPE) as conn:
            migration.op = SimpleNamespace(execute=conn.execute)
            migration.upgrade()


@pytest.mark.skipif(os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1", reason="explicit disposable database required")
def test_real_method_concurrency_history_prior_and_atomic_rollback():
    from concurrent.futures import ThreadPoolExecutor
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
    with disposable_database() as connect:
        apply_migrations(connect)
        item = method()
        owner = EcommerceAnalystAuthorityStore(connect)
        class CommitFailure(RuntimeError): pass
        class Failing:
            def __init__(self, conn): self.conn = conn
            def __getattr__(self, name): return getattr(self.conn, name)
            def commit(self): raise CommitFailure("injected before commit")
        @contextmanager
        def failing(scope):
            with connect(scope) as conn: yield Failing(conn)
        with pytest.raises(CommitFailure):
            EcommerceAnalystAuthorityStore(failing).publish_method(SCOPE, "compiler", "method", item, expected_version=0)
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_method_head").fetchone()["n"] == 0
            assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_method_revision").fetchone()["n"] == 0
            assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_authority_receipt WHERE operation='analyst.method_publish'").fetchone()["n"] == 0
        with ThreadPoolExecutor(max_workers=2) as pool:
            refs = list(pool.map(lambda _: owner.publish_method(SCOPE, "compiler", "method", item, expected_version=0), range(2)))
        first = refs[0]
        assert first == refs[1] and owner.get_method_exact(SCOPE, first) == item
        with pytest.raises(AnalystAuthorityIdempotencyConflict):
            owner.publish_method(SCOPE, "compiler", "method", hashed(item.model_copy(update={"method_id": "other"})), expected_version=0)
        with pytest.raises(AnalystAuthorityConflict): owner.publish_method(SCOPE, "compiler", "different-key", item, expected_version=0)
        second_item = hashed(item.model_copy(update={"revision": 2, "version": 2, "prior_ref": first, "min_source_items": 2}))
        bad = hashed(second_item.model_copy(update={"prior_ref": first.model_copy(update={"content_hash": "b" * 64})}))
        with pytest.raises(AnalystAuthorityNotFound): owner.publish_method(SCOPE, "compiler", "bad-prior", bad, expected_version=1)
        second = owner.publish_method(SCOPE, "compiler", "successor", second_item, expected_version=1)
        assert owner.get_method_exact(SCOPE, first) == item
        assert owner.publish_method(SCOPE, "compiler", "method", item, expected_version=0) == first
        with connect(SCOPE) as conn:
            assert require_current_revision(conn, SCOPE, second) == second_item
            with pytest.raises(ValueError): require_current_revision(conn, SCOPE, first)
            assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_method_revision").fetchone()["n"] == 2
            assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_authority_receipt WHERE operation='analyst.method_publish'").fetchone()["n"] == 2


@pytest.mark.skipif(os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1", reason="explicit disposable database required")
def test_real_method_runtime_rls_and_immutable_history():
    import psycopg
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
    with disposable_database() as connect:
        apply_migrations(connect)
        @contextmanager
        def runtime(scope):
            with connect(SCOPE) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
                yield conn
        owner = EcommerceAnalystAuthorityStore(runtime)
        item = method()
        ref = owner.publish_method(SCOPE, "compiler", "runtime-method", item, expected_version=0)
        assert owner.get_method_exact(SCOPE, ref) == item
        canary = TenantScope("dev-org", "dev-project")
        with pytest.raises(AnalystAuthorityNotFound): owner.get_method_exact(canary, ref)
        with runtime(canary) as conn:
            assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_method_revision").fetchone()["n"] == 0
        for statement in ["UPDATE ecommerce_analyst_method_revision SET created_by='other'", "DELETE FROM ecommerce_analyst_method_revision", "TRUNCATE ecommerce_analyst_method_revision"]:
            with pytest.raises(psycopg.Error):
                with connect(SCOPE) as conn: conn.execute(statement)
        with runtime(SCOPE) as conn:
            assert not conn.execute("SELECT has_table_privilege(current_user,'ecommerce_analyst_method_revision','UPDATE') AS permitted").fetchone()["permitted"]
        assert owner.get_method_exact(SCOPE, ref) == item
