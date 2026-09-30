"""BI AIP stage, responsibility and Skill-selection authority tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aos_api.aip_production_contracts import (
    BriefLifecycle,
    ContractReadiness,
    ExactRevisionRef,
)
from aos_api.aip_responsibility_template_authority import (
    published_template_ref,
    resolve_responsibility_template,
)
from aos_api.aip_stage_template_authority import (
    published_investigation_profile_source_ref,
    resolve_stage_template_source,
)
from aos_api.ecommerce_business_investigation_aip_authority import (
    BusinessInvestigationAuthorityMaterializer,
    build_responsibility_plan_request,
    build_stage_template_request,
    selected_skill_refs,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
VERSIONS = {
    "ecommerce.data_advisor.default": 3,
    "ecommerce.customer_service.default": 3,
    "ecommerce.content_officer.default": 15,
    "ecommerce.private_domain_manager.default": 5,
    "ecommerce.campaign_planner.default": 4,
    "ecommerce.shopping_advisor.default": 3,
}


def test_signed_bi_plan_preparation_rejects_dev_identity_before_database_access() -> None:
    from aos_api.auth import Principal
    from aos_api.ecommerce_business_investigation_aip_authority import (
        SignedBIPlanPreparationService,
    )

    def unexpected_connect(_scope):
        pytest.fail("dev identity must not open a configuration write transaction")

    service = SignedBIPlanPreparationService(connect_factory=unexpected_connect)
    principal = Principal(
        subject="user:dev", org_id="org-org", project_id="dev-project",
        roles=["admin"], token_kind="dev",
    )
    with pytest.raises(PermissionError, match="formal authenticated actor required"):
        service.prepare(
            SCOPE, installation_id="42785d78-5914-4a54-a078-e5d2c7f48481",
            expected_etag_version=3, principal=principal,
            idempotency_key="bi-plan-prep-exact-1",
        )


def test_signed_bi_plan_preparation_rejects_cross_tenant_oidc_before_database_access() -> None:
    from aos_api.auth import Principal
    from aos_api.ecommerce_business_investigation_aip_authority import (
        SignedBIPlanPreparationService,
    )

    def unexpected_connect(_scope):
        pytest.fail("cross tenant principal must not open a configuration transaction")

    service = SignedBIPlanPreparationService(connect_factory=unexpected_connect)
    principal = Principal(
        subject="test:wrong-tenant", org_id="dev-org", project_id="dev-project",
        roles=["admin"], token_kind="oidc",
    )
    with pytest.raises(PermissionError, match="formal authenticated actor required"):
        service.prepare(
            SCOPE, installation_id="42785d78-5914-4a54-a078-e5d2c7f48481",
            expected_etag_version=3, principal=principal,
            idempotency_key="bi-plan-prep-cross-tenant",
        )


def test_signed_bi_admission_rejects_non_oidc_before_database_access() -> None:
    from aos_api.auth import Principal
    from aos_api.ecommerce_business_investigation_aip_authority import SignedBIPlanAdmissionReader

    def unexpected_connect(_scope):
        pytest.fail("invalid principal must not open a read transaction")

    reader = SignedBIPlanAdmissionReader(connect_factory=unexpected_connect)
    principal = Principal(subject="user:dev", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="dev")
    with pytest.raises(PermissionError, match="formal authenticated actor required"):
        reader.read(SCOPE, installation_id="42785d78-5914-4a54-a078-e5d2c7f48481",
                    principal=principal)


def test_signed_bi_admission_rejects_cross_tenant_oidc_before_database_access() -> None:
    from aos_api.auth import Principal
    from aos_api.ecommerce_business_investigation_aip_authority import SignedBIPlanAdmissionReader

    def unexpected_connect(_scope):
        pytest.fail("cross-tenant identity must not open a read transaction")

    reader = SignedBIPlanAdmissionReader(connect_factory=unexpected_connect)
    principal = Principal(subject="person:other", org_id="dev-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    with pytest.raises(PermissionError, match="formal authenticated actor required"):
        reader.read(SCOPE, installation_id="42785d78-5914-4a54-a078-e5d2c7f48481",
                    principal=principal)


def test_signed_bi_admission_rejects_unsupported_remote_permission_before_database(monkeypatch) -> None:
    from aos_api.auth import Principal
    from aos_api import ecommerce_business_investigation_aip_authority as module

    monkeypatch.setattr(module, "openfga_api_url", lambda: "https://auth.example.invalid")
    reader = module.SignedBIPlanAdmissionReader(
        connect_factory=lambda _scope: pytest.fail("remote adapter cannot produce BI candidate"))
    principal = Principal(subject="person:current", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    with pytest.raises(PermissionError, match="permission adapter unavailable"):
        reader.read(SCOPE, installation_id="42785d78-5914-4a54-a078-e5d2c7f48481",
                    principal=principal)


def test_signed_bi_admission_checks_persisted_role_before_installation_or_signature(monkeypatch) -> None:
    from aos_api.auth import Principal
    from aos_api import ecommerce_business_investigation_aip_authority as module

    events = []
    class Connection:
        def execute(self, sql, params):
            events.append("membership")
            assert "FROM meta_membership" in sql
            return SimpleNamespace(fetchall=lambda: [])
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()
    monkeypatch.setattr(module, "apply_asset_transaction_scope", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.PostgresInstallationStore, "get_installation",
                        lambda *args, **kwargs: pytest.fail("installation disclosed before membership"))
    reader = module.SignedBIPlanAdmissionReader(connect_factory=connect)
    principal = Principal(subject="person:current", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    with pytest.raises(PermissionError, match="current persisted membership required"):
        reader.read(SCOPE, installation_id="42785d78-5914-4a54-a078-e5d2c7f48481",
                    principal=principal)
    assert events == ["membership"]


def test_signed_bi_admission_rejects_unprivileged_member_before_installation(monkeypatch) -> None:
    from aos_api.auth import Principal
    from aos_api import ecommerce_business_investigation_aip_authority as module

    class Connection:
        def execute(self, sql, params):
            assert "FROM meta_membership" in sql
            return SimpleNamespace(fetchall=lambda: [{"role": "viewer"}])
    @contextmanager
    def connect(_scope):
        yield Connection()
    monkeypatch.setattr(module, "apply_asset_transaction_scope", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.PostgresInstallationStore, "get_installation",
                        lambda *args, **kwargs: pytest.fail("installation disclosed before role"))
    reader = module.SignedBIPlanAdmissionReader(connect_factory=connect)
    principal = Principal(subject="person:viewer", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    with pytest.raises(PermissionError, match="current configuration role required"):
        reader.read(SCOPE, installation_id="42785d78-5914-4a54-a078-e5d2c7f48481",
                    principal=principal)


def test_signed_bi_admission_reports_missing_signed_source_and_six_instances_without_write(monkeypatch) -> None:
    from aos_api.auth import Principal
    from aos_api import ecommerce_business_investigation_aip_authority as module

    installation_id = "42785d78-5914-4a54-a078-e5d2c7f48481"
    record = SimpleNamespace(installation_id=installation_id, current_revision=3,
                             etag_version=4, state="approved", active_revision=None,
                             current=SimpleNamespace(composition_id="composition-1", lock_revision=1,
                                                     lock_hash="a" * 64, permission_diff_hash="b" * 64,
                                                     migration_plan_hash="c" * 64, contribution_diff_hash="d" * 64))
    class Connection:
        def execute(self, sql, params):
            if "FROM meta_membership" in sql:
                return SimpleNamespace(fetchall=lambda: [{"role": "owner"}])
            if "FROM authz_tuple" in sql:
                return SimpleNamespace(fetchall=lambda: [])
            if "FROM aip_agent_instance" in sql:
                return SimpleNamespace(fetchall=lambda: [])
            pytest.fail(f"unexpected SQL: {sql}")
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()
    class Resolver:
        def select(self, scope): return None
    monkeypatch.setattr(module, "apply_asset_transaction_scope", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.PostgresInstallationStore, "get_installation",
                        lambda *args, **kwargs: record)
    monkeypatch.setattr(module, "load_stored_lock", lambda *args, **kwargs: (
        None, SimpleNamespace(lock_hash="a" * 64, permission_diff_hash="b" * 64,
                              migration_plan_hash="c" * 64, contribution_diff_hash="d" * 64,
                              payload=SimpleNamespace(permission_diff=SimpleNamespace(
                                  target=SimpleNamespace(markings=[]))))))
    reader = module.SignedBIPlanAdmissionReader(
        connect_factory=connect, preparation_resolver=Resolver())
    principal = Principal(subject="person:current", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    snapshot = reader.read(SCOPE, installation_id=installation_id, principal=principal)
    assert snapshot.installation_etag == 4
    assert snapshot.template_ref is None
    assert snapshot.active_instance_versions == {}
    assert snapshot.blockers == ["SIGNED_APPROVED_BI_TEMPLATE_UNAVAILABLE", "SIX_ACTIVE_AGENT_INSTANCES_MISSING"]
    assert snapshot.candidate_ready is False
    assert snapshot.write_revalidation_required is True
    record.state = "active"
    record.active_revision = 3
    active_snapshot = reader.read(SCOPE, installation_id=installation_id, principal=principal)
    assert active_snapshot.blockers[0] == "APPROVED_INACTIVE_INSTALLATION_REQUIRED"
    record.state = "approved"
    record.active_revision = None
    from aos_api.asset_registry.errors import AssetNotFoundError
    monkeypatch.setattr(module, "load_stored_lock", lambda *args, **kwargs: (
        None, SimpleNamespace(lock_hash="a" * 64, permission_diff_hash="b" * 64,
                              migration_plan_hash="c" * 64, contribution_diff_hash="d" * 64,
                              payload=SimpleNamespace(permission_diff=SimpleNamespace(
                                  target=SimpleNamespace(markings=["restricted"]))))))
    with pytest.raises(AssetNotFoundError):
        reader.read(SCOPE, installation_id=installation_id, principal=principal)


def test_signed_bi_admission_route_uses_authenticated_scope_without_mutation() -> None:
    from aos_api.auth import Principal
    from aos_api.ecommerce_business_investigation_aip_authority import SignedBIPlanAdmissionSnapshot
    from aos_api.routers.aip_production_contracts import read_signed_bi_plan_admission

    seen = []
    class Reader:
        def read(self, scope, **kwargs):
            seen.append((scope, kwargs))
            return SignedBIPlanAdmissionSnapshot(
                installation_id=kwargs["installation_id"], installation_revision=3,
                installation_etag=4, template_ref=None, active_instance_versions={},
                blockers=["SIGNED_APPROVED_BI_TEMPLATE_UNAVAILABLE"],
                candidate_ready=False)
    principal = Principal(subject="person:current", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    installation_id = "42785d78-5914-4a54-a078-e5d2c7f48481"
    snapshot = read_signed_bi_plan_admission(
        installation_id=installation_id, principal=principal, reader=Reader())
    assert snapshot.candidate_ready is False
    assert seen == [(SCOPE, {"installation_id": installation_id, "principal": principal})]


def test_signed_bi_receipt_readback_rejects_dev_identity_before_database_access() -> None:
    from aos_api.auth import Principal
    from aos_api.aip_production_contract_store import SignedBIPlanReceiptReader

    reader = SignedBIPlanReceiptReader(connect_factory=lambda _scope: pytest.fail("dev token opened DB"))
    principal = Principal(subject="user:dev", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="dev")
    with pytest.raises(PermissionError, match="formal authenticated actor required"):
        reader.read(SCOPE, principal=principal, idempotency_key="bi-receipt-1")
    wrong_tenant = Principal(subject="person:current", org_id="dev-org", project_id="dev-project",
                             roles=["admin"], token_kind="oidc")
    with pytest.raises(PermissionError, match="formal authenticated actor required"):
        reader.read(SCOPE, principal=wrong_tenant, idempotency_key="bi-receipt-1")


def test_signed_bi_receipt_readback_rejects_nonmember_before_receipt_query(monkeypatch) -> None:
    from aos_api.auth import Principal
    from aos_api import aip_production_contract_store as module

    class Connection:
        def execute(self, sql, params):
            assert "FROM meta_membership" in sql
            return SimpleNamespace(fetchall=lambda: [])
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()
    monkeypatch.setattr(module, "apply_asset_transaction_scope", lambda *args, **kwargs: None)
    reader = module.SignedBIPlanReceiptReader(connect_factory=connect)
    principal = Principal(subject="person:former", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    with pytest.raises(PermissionError, match="current persisted membership required"):
        reader.read(SCOPE, principal=principal, idempotency_key="bi-receipt-1")


def test_signed_bi_receipt_readback_rejects_low_current_role(monkeypatch) -> None:
    from aos_api.auth import Principal
    from aos_api import aip_production_contract_store as module

    class Connection:
        def execute(self, sql, params):
            assert "FROM meta_membership" in sql
            return SimpleNamespace(fetchall=lambda: [{"role": "viewer"}])
    @contextmanager
    def connect(_scope):
        yield Connection()
    monkeypatch.setattr(module, "apply_asset_transaction_scope", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "openfga_api_url", lambda: None)
    principal = Principal(subject="person:current", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    with pytest.raises(PermissionError, match="current configuration role required"):
        module.SignedBIPlanReceiptReader(connect_factory=connect).read(
            SCOPE, principal=principal, idempotency_key="bi-receipt-1")


def test_signed_bi_receipt_readback_is_actor_scoped_and_never_resends(monkeypatch) -> None:
    from aos_api.auth import Principal
    from aos_api.aip_production_contract_store import ProductionContractNotFound
    from aos_api import aip_production_contract_store as module

    calls = []
    receipt = {"receipt_id": "w2r-current", "request_hash": "a" * 64,
               "result_ref": {"resourceType": "ResponsibilityPlanRevision", "resourceId": "plan-1",
                              "revision": 1, "contentHash": "b" * 64},
               "created_at": datetime(2026, 9, 30, tzinfo=UTC)}
    class Connection:
        def execute(self, sql, params):
            assert sql.lstrip().startswith("SELECT") and "FOR UPDATE" not in sql
            calls.append((sql, params))
            if "FROM meta_membership" in sql:
                return SimpleNamespace(fetchall=lambda: [{"role": "owner"}])
            assert "FROM aip_production_contract_receipt" in sql
            assert params == (*SCOPE.key, "bi_responsibility_plan.prepare", "bi-receipt-1", "person:current")
            return SimpleNamespace(fetchone=lambda: receipt if not missing[0] else None)
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()
    missing = [False]
    monkeypatch.setattr(module, "apply_asset_transaction_scope", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "openfga_api_url", lambda: None)
    reader = module.SignedBIPlanReceiptReader(connect_factory=connect)
    principal = Principal(subject="person:current", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    result = reader.read(SCOPE, principal=principal, idempotency_key="bi-receipt-1")
    assert result.result_ref.resource_id == "plan-1"
    assert result.installation_binding_verified is False
    assert len(calls) == 2
    receipt["result_ref"]["installationBinding"] = {
        "installationId": "42785d78-5914-4a54-a078-e5d2c7f48481",
        "installationETag": 3,
        "templateRef": {"resourceType": "ResponsibilityTemplateRevision",
                        "resourceId": "template-1", "revision": 1,
                        "contentHash": "c" * 64},
        "actor": "person:current",
    }
    assert reader.read(SCOPE, principal=principal,
                       idempotency_key="bi-receipt-1").installation_binding_verified is False
    missing[0] = True
    with pytest.raises(ProductionContractNotFound):
        reader.read(SCOPE, principal=principal, idempotency_key="bi-receipt-1")


def test_bi_receipt_binding_rejects_partial_or_cross_actor_evidence() -> None:
    from aos_api.aip_production_contract_store import (
        ProductionContractConflict, _require_bi_installation_binding,
    )
    ref = {"resourceType": "ResponsibilityTemplateRevision", "resourceId": "template-1",
           "revision": 1, "contentHash": "c" * 64}
    binding = {"installationId": "42785d78-5914-4a54-a078-e5d2c7f48481",
               "installationETag": 3, "templateRef": ref, "actor": "person:current"}
    assert _require_bi_installation_binding(binding, "person:current") == binding
    for invalid in (
        {**binding, "actor": "person:other"},
        {**binding, "installationETag": 0},
        {**binding, "installationId": "test-only"},
        {**binding, "templateRef": {**ref, "contentHash": "bad"}},
        {key: value for key, value in binding.items() if key != "templateRef"},
    ):
        with pytest.raises(ProductionContractConflict):
            _require_bi_installation_binding(invalid, "person:current")


def test_signed_bi_receipt_route_preserves_authenticated_actor_and_unknown() -> None:
    from aos_api.auth import Principal
    from aos_api.aip_production_contract_store import ProductionContractNotFound
    from aos_api.routers.aip_production_contracts import read_signed_bi_plan_receipt
    from aos_api.errors import ApiError

    principal = Principal(subject="person:current", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    class Reader:
        def read(self, scope, *, principal: Principal, idempotency_key: str):
            assert scope == SCOPE and principal.subject == "person:current"
            assert idempotency_key == "bi-receipt-1"
            raise ProductionContractNotFound("BI preparation receipt not found")
    with pytest.raises(ApiError) as error:
        read_signed_bi_plan_receipt("bi-receipt-1", principal=principal, reader=Reader())
    assert error.value.status_code == 404


def test_signed_bi_plan_preparation_orders_current_checks_before_one_receipt(monkeypatch) -> None:
    from aos_api.auth import Principal
    from aos_api import ecommerce_business_investigation_aip_authority as module

    events = []
    installation_id = "42785d78-5914-4a54-a078-e5d2c7f48481"
    template_ref = ExactRevisionRef(
        resource_type="ResponsibilityTemplateRevision",
        resource_id=("bundle://a0v-growth-112/solution.ecommerce.growth/1.12.0/"
                     "content/responsibility-templates/business-investigation.readonly.json"),
        revision=3, content_hash="a" * 64,
    )
    class Connection:
        def execute(self, sql, params):
            assert "FROM aip_agent_instance" in sql and "FOR SHARE" in sql
            events.append("instances")
            return SimpleNamespace(fetchall=lambda: [
                {"instance_id": instance_id, "version": version}
                for instance_id, version in VERSIONS.items()
            ])
        def commit(self): events.append("commit")
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        events.append("connect")
        yield Connection()
    class Resolver:
        def select(self, scope):
            events.append("signed-select")
            return SimpleNamespace(installation_id=installation_id, template_ref=template_ref)
        def resolve(self, scope, ref): return scope == SCOPE and ref == template_ref
    monkeypatch.setattr(module, "apply_asset_transaction_scope", lambda *args, **kw: events.append("scope"))
    def lock(self, conn, **kwargs):
        events.append("installation-lock")
        assert kwargs["expected_etag_version"] == 3
        return SimpleNamespace(record=SimpleNamespace(state="approved", active_revision=None))
    monkeypatch.setattr(module.PostgresInstallationStore, "lock_for_transition_in_transaction", lock)
    monkeypatch.setattr(module.CurrentControlPermission, "__call__",
                        lambda self, **kwargs: events.append("current-permission"))
    service = module.SignedBIPlanPreparationService(
        connect_factory=connect, preparation_resolver=Resolver())
    def create(conn, scope, actor, key, body, *, operation, request_context):
        events.append("receipt")
        assert actor == "person:current" and operation == "bi_responsibility_plan.prepare"
        assert request_context["installationId"] == installation_id
        assert request_context["actor"] == actor
        assert body.template_ref == template_ref
        return "draft-plan"
    monkeypatch.setattr(service._plan_store, "create_responsibility_plan_in_transaction", create)
    principal = Principal(subject="person:current", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    assert service.prepare(SCOPE, installation_id=installation_id, expected_etag_version=3,
                           principal=principal, idempotency_key="bi-plan-prep-exact-1") == "draft-plan"
    assert events == ["connect", "scope", "installation-lock", "current-permission",
                      "signed-select", "instances", "receipt", "commit"]


def test_signed_bi_plan_route_uses_principal_and_strong_installation_etag() -> None:
    from aos_api.auth import Principal
    from aos_api.errors import ApiError
    from pydantic import ValidationError
    from aos_api.routers.aip_production_contracts import (
        SignedBIPlanPreparationRequest, prepare_signed_bi_responsibility_plan,
    )
    seen = []
    class Service:
        def prepare(self, scope, **kwargs):
            seen.append((scope, kwargs))
            return "draft-plan"
    principal = Principal(subject="person:current", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    body = SignedBIPlanPreparationRequest(
        installationId="42785d78-5914-4a54-a078-e5d2c7f48481")
    with pytest.raises(ValidationError):
        SignedBIPlanPreparationRequest.model_validate({
            "installationId": body.installation_id, "actor": "arbitrary",
        })
    assert prepare_signed_bi_responsibility_plan(
        body, idempotency_key="bi-plan-1", if_match='"3"', principal=principal,
        service=Service()) == "draft-plan"
    assert seen == [(SCOPE, dict(
        installation_id=body.installation_id, expected_etag_version=3,
        principal=principal, idempotency_key="bi-plan-1"))]
    with pytest.raises(ApiError) as error:
        prepare_signed_bi_responsibility_plan(
            body, idempotency_key="bi-plan-2", if_match="3", principal=principal,
            service=Service())
    assert error.value.status_code == 400
    assert len(seen) == 1


def test_bi_plan_later_failure_rolls_back_draft_receipt_in_isolated_pg() -> None:
    """Database rollback proof only; injected template authority is not acceptance."""
    from aos_api.aip_production_contract_store import (
        AipProductionContractStore, ProductionContractIdempotencyConflict,
    )
    from aos_api.db import connect

    key = f"bi-du-rollback-{uuid4().hex}"
    installation_id = str(uuid4())
    template_id = f"bi-du-test-{uuid4().hex[:16]}"
    store = AipProductionContractStore(
        responsibility_template_resolver=lambda scope, ref: scope == SCOPE)
    class StopAfterPlan(RuntimeError): pass
    with pytest.raises(StopAfterPlan):
        with connect(SCOPE) as conn:
            conn.execute("""INSERT INTO aip_agent_template_revision
                (template_id,revision,display_name,role_key,lifecycle,source_ref,
                 source_license,manifest,content_hash,created_by)
                VALUES(%s,1,'BI test only','content_officer','published',
                       '{}','internal','{}',%s,'test:bi-du')""",
                (template_id, "b" * 64))
            for instance_id, version in VERSIONS.items():
                conn.execute("""INSERT INTO aip_agent_instance
                    (org_id,project_id,instance_id,template_id,template_revision,status,
                     overlay,version,created_by)
                    VALUES(%s,%s,%s,%s,1,'active','{}',%s,'test:bi-du')""",
                    (*SCOPE.key, instance_id, template_id, version))
            request = build_responsibility_plan_request(VERSIONS)
            context = {"installationId": installation_id, "installationETag": 3,
                       "templateRef": request.template_ref.model_dump(mode="json", by_alias=True),
                       "actor": "test:bi-du"}
            plan = store.create_responsibility_plan_in_transaction(
                conn, SCOPE, "test:bi-du", key, request,
                operation="bi_responsibility_plan.prepare",
                request_context=context,
            )
            assert plan.lifecycle is BriefLifecycle.DRAFT
            stored = conn.execute("""SELECT result_ref FROM aip_production_contract_receipt
                WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s""",
                (*SCOPE.key, "bi_responsibility_plan.prepare", key)).fetchone()["result_ref"]
            assert stored["installationBinding"] == context
            replay = store.create_responsibility_plan_in_transaction(
                conn, SCOPE, "test:bi-du", key, request,
                operation="bi_responsibility_plan.prepare",
                request_context=context,
            )
            assert replay.plan_id == plan.plan_id
            with pytest.raises(ProductionContractIdempotencyConflict):
                store.create_responsibility_plan_in_transaction(
                    conn, SCOPE, "test:bi-du", key, request,
                    operation="bi_responsibility_plan.prepare",
                    request_context={**context, "installationId": str(uuid4())},
                )
            raise StopAfterPlan()
    with connect(SCOPE) as conn:
        assert conn.execute("""SELECT count(*) AS n FROM aip_production_contract_receipt
            WHERE org_id=%s AND project_id=%s AND operation='bi_responsibility_plan.prepare'
              AND idempotency_key=%s""", (*SCOPE.key, key)).fetchone()["n"] == 0
        assert conn.execute("""SELECT count(*) AS n FROM aip_responsibility_plan_revision
            WHERE org_id=%s AND project_id=%s AND created_by='test:bi-du'""",
            SCOPE.key).fetchone()["n"] == 0


def test_skill_selection_is_exact_and_d03_is_explicit_r4() -> None:
    refs = selected_skill_refs()
    assert list(refs) == ["ecommerce.skill.D01", "ecommerce.skill.D02", "ecommerce.skill.D03"]
    assert refs["ecommerce.skill.D03"].revision == 4
    assert refs["ecommerce.skill.D03"].content_hash == (
        "3b60ef1e7147b761d1582d8dd0c62934e24d28a8ad8306caf12b1db02306a704"
    )


def test_stage_blueprint_is_ordered_receipt_first_and_read_only() -> None:
    body = build_stage_template_request()
    assert [stage.stage_id for stage in body.stages] == [
        "portrait",
        "diagnosis",
        "solution-design",
    ]
    assert [stage.depends_on for stage in body.stages] == [[], ["portrait"], ["diagnosis"]]
    assert all(stage.retry_policy == {"automatic": False} for stage in body.stages)
    assert all(stage.compensation_policy == {"externalEffect": "none"} for stage in body.stages)
    assert resolve_stage_template_source(SCOPE, body.source_bundle_ref) is True


def test_six_responsibilities_bind_six_current_coworkers_by_capability() -> None:
    from aos_api.aip_business_investigation_responsibility_template import BI_ROLE_BLUEPRINTS
    body = build_responsibility_plan_request(VERSIONS)
    assert len(body.slots) == 6
    assert len({slot.slot_id for slot in body.slots}) == 6
    assert len({slot.assignee.resource_id for slot in body.slots}) == 6
    assert all(slot.required_capability_ids for slot in body.slots)
    assert [(slot.slot_id, slot.responsibility_type,
             tuple(slot.required_capability_ids), slot.return_stage)
            for slot in body.slots] == [
                (slot_id, role, capabilities, stage)
                for slot_id, role, _instance_id, capabilities, stage in BI_ROLE_BLUEPRINTS
            ]
    assert resolve_responsibility_template(SCOPE, body.template_ref) is False


def test_plan_can_carry_exact_signed_preparation_template_ref() -> None:
    exact = ExactRevisionRef(
        resource_type="ResponsibilityTemplateRevision",
        resource_id=("bundle://a0v-growth-112/solution.ecommerce.growth/1.12.0/"
                     "content/responsibility-templates/business-investigation.readonly.json"),
        revision=3, content_hash="a" * 64,
    )
    assert build_responsibility_plan_request(VERSIONS, template_ref=exact).template_ref == exact


def test_materializer_requires_preparation_selection_before_stage_write() -> None:
    store = Store()
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()
    class Unavailable:
        def select(self, scope):
            return None
    runner = BusinessInvestigationAuthorityMaterializer(
        store=store, connect_factory=connect, preparation_resolver=Unavailable())
    with pytest.raises(ValueError, match="signed installed BI responsibility template unavailable"):
        runner.ensure(SCOPE, actor="unit-test-actor")
    assert store.calls == []


def test_materializer_rejects_external_active_only_store_before_stage_write() -> None:
    from aos_api.aip_production_contract_store import AipProductionContractStore
    exact = ExactRevisionRef(
        resource_type="ResponsibilityTemplateRevision",
        resource_id=("bundle://a0v-growth-112/solution.ecommerce.growth/1.12.0/"
                     "content/responsibility-templates/business-investigation.readonly.json"),
        revision=3, content_hash="a" * 64,
    )
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()
    class Preparation:
        def select(self, scope):
            return SimpleNamespace(template_ref=exact)
        def resolve(self, scope, ref):
            return scope == SCOPE and ref == exact
    store = AipProductionContractStore(
        connect_factory=connect,
        responsibility_template_resolver=lambda scope, ref: False,
    )
    runner = BusinessInvestigationAuthorityMaterializer(
        store=store, connect_factory=connect, preparation_resolver=Preparation())
    with pytest.raises(ValueError, match="Plan store rejects signed BI preparation template"):
        runner.ensure(SCOPE, actor="unit-test-actor")


def test_missing_active_coworker_version_fails_closed() -> None:
    versions = dict(VERSIONS)
    versions.pop("ecommerce.shopping_advisor.default")
    with pytest.raises(ValueError, match="active digital coworker versions missing"):
        build_responsibility_plan_request(versions)


def test_code_authorities_reject_hash_drift() -> None:
    stage = published_investigation_profile_source_ref()
    responsibility = published_template_ref("ecommerce.business-investigation.readonly")
    assert resolve_stage_template_source(
        SCOPE, stage.model_copy(update={"content_hash": "0" * 64})
    ) is False
    assert resolve_responsibility_template(
        SCOPE, responsibility.model_copy(update={"content_hash": "0" * 64})
    ) is False


class Result:
    def fetchall(self):
        return [
            {"instance_id": instance_id, "version": version}
            for instance_id, version in VERSIONS.items()
        ]


class Connection:
    def execute(self, sql, params):
        assert "aip_agent_instance" in sql
        assert tuple(params[:2]) == SCOPE.key
        return Result()


class Store:
    def __init__(self, plan_readiness=ContractReadiness.BLOCKED):
        self.plan_readiness = plan_readiness
        self.calls = []
        self.stage = None
        self.plan = None

    def create_stage_template(self, scope, actor, key, body):
        self.calls.append(("create-stage", key, body))
        self.stage = self.stage or SimpleNamespace(
            lifecycle=BriefLifecycle.DRAFT,
            template_id="stage-1",
            version=1,
        )
        return self.stage

    def get_stage_template(self, scope, template_id):
        self.calls.append(("get-stage", template_id))
        return self.stage

    def freeze_stage_template(self, scope, actor, template_id, version, key):
        self.calls.append(("freeze-stage", key, template_id, version))
        self.stage = SimpleNamespace(
            lifecycle=BriefLifecycle.FROZEN,
            template_id=template_id,
            version=2,
        )
        return self.stage

    def create_responsibility_plan(self, scope, actor, key, body):
        self.calls.append(("create-plan", key, body))
        self.plan = self.plan or SimpleNamespace(
            lifecycle=BriefLifecycle.DRAFT,
            readiness=self.plan_readiness,
            plan_id="plan-1",
            version=1,
        )
        return self.plan

    def get_responsibility_plan(self, scope, plan_id):
        self.calls.append(("get-plan", plan_id))
        return self.plan

    def freeze_responsibility_plan(self, scope, actor, plan_id, version, key):
        self.calls.append(("freeze-plan", key, plan_id, version))
        self.plan = SimpleNamespace(
            lifecycle=BriefLifecycle.FROZEN,
            readiness=ContractReadiness.READY,
            plan_id=plan_id,
            version=2,
        )
        return self.plan


def materializer(store, monkeypatch):
    signed_ref = ExactRevisionRef(
        resource_type="ResponsibilityTemplateRevision",
        resource_id=("bundle://a0v-growth-112/solution.ecommerce.growth/1.12.0/"
                     "content/responsibility-templates/business-investigation.readonly.json"),
        revision=3, content_hash="a" * 64,
    )
    class Preparation:
        def select(self, scope):
            return SimpleNamespace(template_ref=signed_ref) if scope == SCOPE else None
        def resolve(self, scope, ref):
            return scope == SCOPE and ref == signed_ref
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()

    return BusinessInvestigationAuthorityMaterializer(
        store=store,
        connect_factory=connect,
        preparation_resolver=Preparation(),
    )


def test_materializer_rejects_unsigned_local_template_before_metadata_writes() -> None:
    store = Store()
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()
    runner = BusinessInvestigationAuthorityMaterializer(store=store, connect_factory=connect)
    with pytest.raises(ValueError, match="signed installed BI responsibility template unavailable"):
        runner.ensure(SCOPE, actor="unit-test-actor")
    assert store.calls == []


def test_materializer_freezes_stage_but_keeps_blocked_plan_draft(monkeypatch) -> None:
    store = Store()
    actual = materializer(store, monkeypatch).ensure(SCOPE, actor="unit-test-actor")
    assert actual.stage_template.lifecycle is BriefLifecycle.FROZEN
    assert actual.responsibility_plan.lifecycle is BriefLifecycle.DRAFT
    assert [call[0] for call in store.calls] == [
        "create-stage",
        "get-stage",
        "freeze-stage",
        "create-plan",
        "get-plan",
    ]


def test_materializer_freezes_plan_only_after_canonical_readiness(monkeypatch) -> None:
    store = Store(ContractReadiness.READY)
    actual = materializer(store, monkeypatch).ensure(SCOPE, actor="unit-test-actor")
    assert actual.responsibility_plan.lifecycle is BriefLifecycle.FROZEN
    assert [call[0] for call in store.calls][-1] == "freeze-plan"


def test_materializer_reentry_uses_current_heads_and_does_not_refreeze(monkeypatch) -> None:
    store = Store(ContractReadiness.READY)
    runner = materializer(store, monkeypatch)
    first = runner.ensure(SCOPE, actor="unit-test-actor")
    first_call_count = len(store.calls)
    second = runner.ensure(SCOPE, actor="unit-test-actor")
    reentry_calls = store.calls[first_call_count:]
    assert second.stage_template is first.stage_template
    assert second.responsibility_plan is first.responsibility_plan
    assert [call[0] for call in reentry_calls] == [
        "create-stage",
        "get-stage",
        "create-plan",
        "get-plan",
    ]


def test_finalize_responsibility_plan_freezes_only_ready_draft(monkeypatch) -> None:
    store = Store(ContractReadiness.READY)
    runner = materializer(store, monkeypatch)
    created = runner.ensure(SCOPE, actor="unit-test-actor")
    store.plan = SimpleNamespace(
        lifecycle=BriefLifecycle.DRAFT,
        readiness=ContractReadiness.READY,
        plan_id=created.responsibility_plan.plan_id,
        version=3,
    )
    actual = runner.finalize_responsibility_plan(SCOPE, store.plan.plan_id, actor="unit-test-actor")
    assert actual.lifecycle is BriefLifecycle.FROZEN
    assert store.calls[-1][0] == "freeze-plan"


def test_finalize_responsibility_plan_keeps_blocked_draft(monkeypatch) -> None:
    store = Store(ContractReadiness.BLOCKED)
    runner = materializer(store, monkeypatch)
    runner.ensure(SCOPE, actor="unit-test-actor")
    before = store.plan
    actual = runner.finalize_responsibility_plan(SCOPE, before.plan_id, actor="unit-test-actor")
    assert actual is before
    assert store.calls[-1][0] == "get-plan"
