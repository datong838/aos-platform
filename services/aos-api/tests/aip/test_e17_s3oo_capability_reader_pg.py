"""E17-s3o-o: real, least-privileged Capability readiness catalog/scoped reads."""

from __future__ import annotations

import os
import secrets
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from aos_api.aip_agent_registry_contracts import (
    EvaluateOperationalBindingRequest, OperationalBindingDependencies,
    UpdateCapabilityBindingRequest, VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict, AipAgentRegistryPersistenceError,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_binding_readiness_service import (
    AipBindingReadinessService, PostgresBindingDependencyAuthority,
)
from aos_api.aip_binding_readiness_reader_connection import (
    READINESS_READER_LOGIN, READINESS_READER_TABLES,
    ReadinessReaderConnectionBlocked, ReadinessReaderConnectionFactory,
    ReadinessReaderDatabaseConfig,
)
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_registry_issuer_connection import (
    RegistryIssuerConnectionBlocked, RegistryIssuerConnectionFactory,
)
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope

from tests.aip.test_e17_s3ol_capability_issuer_pg import capability_case, capability_issuer


@pytest.fixture()
def readiness_reader(capability_case):
    parts = conninfo_to_dict(get_dsn())
    database = parts["dbname"]
    assert database.startswith("aos_test_") and database.endswith("_ti4_test")
    password = secrets.token_urlsafe(32)
    with psycopg.connect(get_dsn()) as admin:
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",
                             (READINESS_READER_LOGIN,)).fetchone() is None
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}")
                      .format(sql.Identifier(READINESS_READER_LOGIN), sql.Literal(password)))
        admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}")
                      .format(sql.Identifier(READINESS_READER_LOGIN)))
        for table in READINESS_READER_TABLES:
            admin.execute(sql.SQL("GRANT SELECT ON {} TO {}")
                          .format(sql.Identifier(table), sql.Identifier(READINESS_READER_LOGIN)))
            if table != "aip_capability_revision":
                admin.execute(sql.SQL("""CREATE POLICY s3oo_reader_scope ON {} TO {}
                    USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
                       AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
                              .format(sql.Identifier(table), sql.Identifier(READINESS_READER_LOGIN)))
    with tempfile.TemporaryDirectory(prefix="aos-s3oo-reader-") as directory:
        passfile = Path(directory) / "pgpass"
        fd = os.open(passfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"127.0.0.1:5433:{database}:{READINESS_READER_LOGIN}:{password}\n")
        factory = ReadinessReaderConnectionFactory(ReadinessReaderDatabaseConfig(
            host="127.0.0.1", port=5433, database=database, passfile=passfile))
        try:
            yield factory
        finally:
            with psycopg.connect(get_dsn()) as admin:
                for table in READINESS_READER_TABLES:
                    if table != "aip_capability_revision":
                        admin.execute(sql.SQL("DROP POLICY IF EXISTS s3oo_reader_scope ON {}")
                                      .format(sql.Identifier(table)))
                admin.execute(sql.SQL("DROP OWNED BY {}")
                              .format(sql.Identifier(READINESS_READER_LOGIN)))
                admin.execute(sql.SQL("DROP ROLE {}")
                              .format(sql.Identifier(READINESS_READER_LOGIN)))


def test_reader_global_catalog_and_scoped_dataset_are_read_only(capability_case, readiness_reader):
    scope, request = capability_case
    dataset_id = f"s3oo-dataset-{uuid4().hex[:12]}"
    with connect(scope) as owner:
        owner.execute("""INSERT INTO aip_eval_dataset_revision
            (org_id,project_id,dataset_id,revision,content_hash,source_hash,
             redaction_policy_ref,manifest,actor)
            VALUES (%s,%s,%s,1,%s,%s,'{}'::jsonb,'{}'::jsonb,'test-only')""",
            (*scope.key, dataset_id, "a" * 64, "b" * 64))
        owner.commit()
    for selected_scope, expected in ((None, 0), (scope, 1),
                                     (TenantScope("org-org", "other-project"), 0)):
        with readiness_reader(selected_scope) as reader:
            identity = reader.execute("""SELECT session_user AS login,current_user AS role,
                current_setting('transaction_read_only') AS readonly""").fetchone()
            assert identity == {"login": READINESS_READER_LOGIN,
                                "role": READINESS_READER_LOGIN, "readonly": "on"}
            assert reader.execute("SELECT count(*) AS n FROM aip_capability_revision "
                                  "WHERE capability_id=%s", (request.binding.capability.asset_id,)
                                  ).fetchone()["n"] == 1
            assert reader.execute("SELECT count(*) AS n FROM aip_eval_dataset_revision "
                                  "WHERE dataset_id=%s", (dataset_id,)).fetchone()["n"] == expected
            assert not reader.execute("""SELECT has_table_privilege(current_user,
                'aip_eval_dataset_revision','INSERT') AS granted""").fetchone()["granted"]
            with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
                reader.execute("CREATE TEMP TABLE s3oo_write_probe(id int)")


def test_reader_cannot_resolve_absent_exact_budget_policy(capability_case, readiness_reader):
    scope, _ = capability_case
    authority = PostgresBindingDependencyAuthority(readiness_reader)
    budget = VersionedAssetRef(
        asset_type="BudgetPolicyRevision", asset_id=f"absent-{uuid4().hex}",
        revision=1, content_hash="a" * 64,
    )
    assert not authority.budget_policy_available(scope, budget, datetime.now(UTC))


def test_reader_rechecks_exact_bundle_revocation_and_requires_revoke_acl(
    capability_case, readiness_reader,
):
    scope, _ = capability_case
    bundle_id = f"s3owam-{uuid4().hex}"
    content_hash = "c" * 64
    evidence = VersionedAssetRef(
        asset_type="EvidenceBundleRevision", asset_id=bundle_id,
        revision=1, content_hash=content_hash,
    )
    with connect(scope) as owner:
        owner.execute("""INSERT INTO aip_evidence_bundle_revision
            (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,
             item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
             license_summary,content_hash,lifecycle,created_by)
            VALUES(%s,%s,%s,1,'{}'::jsonb,'[]'::jsonb,NOW(),'[]'::jsonb,
                   'complete','[]'::jsonb,'[]'::jsonb,'[]'::jsonb,'fresh',
                   '{}'::jsonb,'{}'::jsonb,%s,'frozen','test-only')""",
            (*scope.key, bundle_id, content_hash),
        )
        owner.commit()
    authority = PostgresBindingDependencyAuthority(readiness_reader)
    with readiness_reader(scope) as reader:
        identity = reader.execute("""SELECT session_user AS login,current_user AS role,
            current_setting('transaction_read_only') AS readonly""").fetchone()
        assert identity == {"login": READINESS_READER_LOGIN,
                            "role": READINESS_READER_LOGIN, "readonly": "on"}
    assert authority.exact_assets_available(scope, [evidence])
    assert not authority.exact_assets_available(
        TenantScope("org-org", "other-project"), [evidence]
    )
    with connect(scope) as owner:
        owner.execute("""INSERT INTO aip_evidence_bundle_revoke_event
            (org_id,project_id,event_id,bundle_id,revision,content_hash,reason,actor)
            VALUES(%s,%s,%s,%s,1,%s,'test-only-revocation','test-only')""",
            (*scope.key, f"revoke-{uuid4().hex}", bundle_id, content_hash),
        )
        owner.commit()
    assert not authority.exact_assets_available(scope, [evidence])
    with connect() as owner:
        owner.execute(sql.SQL("REVOKE SELECT ON aip_evidence_bundle_revoke_event FROM {}")
                      .format(sql.Identifier(READINESS_READER_LOGIN)))
        owner.commit()
    with pytest.raises(ReadinessReaderConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        authority.exact_assets_available(scope, [evidence])


def test_reader_rechecks_license_bundle_revocation_and_requires_revoke_acl(
    capability_case, readiness_reader,
):
    scope, _ = capability_case
    bundle_id = f"s3owaob9-{uuid4().hex}"
    content_hash = "d" * 64
    evidence = ResourceRef(
        resource_type="EvidenceBundleRevision", resource_id=bundle_id,
        revision="1", authority="test-only",
    )
    with connect(scope) as owner:
        owner.execute("""INSERT INTO aip_evidence_bundle_revision
            (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,
             item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
             license_summary,content_hash,lifecycle,created_by)
            VALUES(%s,%s,%s,1,'{}'::jsonb,'[]'::jsonb,NOW(),'[]'::jsonb,
                   'complete','[]'::jsonb,'[]'::jsonb,'[]'::jsonb,'fresh',
                   '{}'::jsonb,'{"license":"test-only"}'::jsonb,%s,'frozen','test-only')""",
            (*scope.key, bundle_id, content_hash),
        )
        owner.commit()
    authority = PostgresBindingDependencyAuthority(readiness_reader)
    assert authority.license_evidence_available(scope, [evidence])
    assert not authority.license_evidence_available(
        TenantScope("org-org", "other-project"), [evidence]
    )
    assert not authority.license_evidence_available(
        TenantScope("dev-org", "dev-project"), [evidence]
    )
    with connect(scope) as owner:
        owner.execute("""INSERT INTO aip_evidence_bundle_revoke_event
            (org_id,project_id,event_id,bundle_id,revision,content_hash,reason,actor)
            VALUES(%s,%s,%s,%s,1,%s,'test-only-revocation','test-only')""",
            (*scope.key, f"revoke-{uuid4().hex}", bundle_id, content_hash),
        )
        owner.commit()
    assert not authority.license_evidence_available(scope, [evidence])
    with connect() as owner:
        owner.execute(sql.SQL("REVOKE SELECT ON aip_evidence_bundle_revoke_event FROM {}")
                      .format(sql.Identifier(READINESS_READER_LOGIN)))
        owner.commit()
    with pytest.raises(ReadinessReaderConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        authority.license_evidence_available(scope, [evidence])


def test_reader_rejects_missing_required_acl(capability_case, readiness_reader):
    scope, _ = capability_case
    with connect() as owner:
        owner.execute(sql.SQL("REVOKE SELECT ON aip_capability_revision FROM {}")
                      .format(sql.Identifier(READINESS_READER_LOGIN)))
        owner.commit()
    with pytest.raises(ReadinessReaderConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        with readiness_reader(scope):
            pass


def test_reader_rejects_cross_domain_grant(capability_case, readiness_reader):
    scope, _ = capability_case
    with connect() as owner:
        owner.execute(sql.SQL("GRANT SELECT ON aip_capability_binding TO {}")
                      .format(sql.Identifier(READINESS_READER_LOGIN)))
        owner.commit()
    with pytest.raises(ReadinessReaderConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        with readiness_reader(scope):
            pass


def test_reader_rejects_inherit_role(capability_case, readiness_reader):
    scope, _ = capability_case
    with connect() as owner:
        owner.execute(sql.SQL("ALTER ROLE {} INHERIT")
                      .format(sql.Identifier(READINESS_READER_LOGIN)))
        owner.commit()
    with pytest.raises(ReadinessReaderConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        with readiness_reader(scope):
            pass


def test_reader_rejects_loose_private_file_and_pg_env(
    capability_case, readiness_reader, monkeypatch,
):
    scope, _ = capability_case
    os.chmod(readiness_reader.config.passfile, 0o644)
    try:
        with pytest.raises(ReadinessReaderConnectionBlocked, match="PRIVATE_CREDENTIAL_REQUIRED"):
            with readiness_reader(scope):
                pass
    finally:
        os.chmod(readiness_reader.config.passfile, 0o600)
    monkeypatch.setenv("PGPASSWORD", "test-only-forbidden")
    with pytest.raises(ReadinessReaderConnectionBlocked, match="EXACT_CONNECTION_REQUIRED"):
        with readiness_reader(scope):
            pass


def test_lifecycle_issuer_requires_exact_update_without_delete(
    capability_case, capability_issuer,
):
    scope, _ = capability_case
    lifecycle_issuer = RegistryIssuerConnectionFactory(
        capability_issuer.config, command_family="capability_lifecycle")
    with pytest.raises(RegistryIssuerConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        with lifecycle_issuer(scope):
            pass
    with connect() as owner:
        owner.execute("REVOKE DELETE ON aip_capability_binding FROM aos_aip_capability_issuer")
        owner.commit()
    with pytest.raises(RegistryIssuerConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        with lifecycle_issuer(scope):
            pass
    with connect() as owner:
        owner.execute("GRANT UPDATE,DELETE ON aip_capability_binding TO aos_aip_capability_issuer")
        owner.commit()
    with pytest.raises(RegistryIssuerConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        with lifecycle_issuer(scope):
            pass


def test_column_grants_keep_readiness_out_of_ordinary_issuer_dml(
    capability_case, capability_issuer,
):
    scope, request = capability_case
    AipCapabilityBindingService(connect_factory=capability_issuer).create(
        scope, request,
        idempotency_key=f"b63:create:{request.binding_id}",
        actor="test-only", occurred_at=datetime.now(UTC),
    )
    with connect() as owner:
        owner.execute("""GRANT UPDATE(status,health,observed_at,version,updated_at)
            ON aip_capability_binding TO aos_aip_capability_issuer""")
        owner.commit()
    config = capability_issuer.config
    with psycopg.connect(host=config.host, port=config.port, dbname=config.database,
                         user="aos_aip_capability_issuer", passfile=str(config.passfile)) as limited:
        limited.execute("SELECT set_config('aos.org_id',%s,true),"
                        "set_config('aos.project_id',%s,true)", scope.key)
        assert limited.execute("""SELECT
            has_column_privilege(session_user,'aip_capability_binding',
                'status','UPDATE'),
            has_column_privilege(session_user,'aip_capability_binding',
                'operational_readiness','UPDATE')""").fetchone() == (True, False)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            limited.execute("""UPDATE aip_capability_binding
                SET operational_readiness='available'
                WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
                (*scope.key, request.binding_id))


def test_lifecycle_issuer_can_omit_readiness_column_write_grants(
    capability_case, capability_issuer,
):
    scope, _ = capability_case
    with connect() as owner:
        owner.execute("""GRANT UPDATE(status,health,observed_at,version,updated_at)
            ON aip_capability_binding TO aos_aip_capability_issuer""")
        owner.commit()
    lifecycle_issuer = RegistryIssuerConnectionFactory(
        capability_issuer.config, command_family="capability_lifecycle")
    with lifecycle_issuer(scope) as limited:
        privileges = limited.execute("""SELECT
            has_column_privilege(session_user,'aip_capability_binding',
                'operational_readiness','UPDATE') AS readiness_write,
            has_column_privilege(session_user,'aip_capability_binding',
                'status','UPDATE') AS status_write""").fetchone()
        assert privileges == {"readiness_write": False, "status_write": True}


@pytest.mark.parametrize("columns", [
    "status,health,observed_at,updated_at",
    "status,health,observed_at,version,updated_at,operational_readiness",
])
def test_lifecycle_issuer_rejects_missing_or_extra_update_column(
    capability_case, capability_issuer, columns,
):
    scope, _ = capability_case
    with connect() as owner:
        owner.execute(sql.SQL("GRANT UPDATE({}) ON aip_capability_binding "
                              "TO aos_aip_capability_issuer").format(
                                  sql.SQL(",").join(
                                      sql.Identifier(name) for name in columns.split(","))))
        owner.commit()
    lifecycle_issuer = RegistryIssuerConnectionFactory(
        capability_issuer.config, command_family="capability_lifecycle")
    with pytest.raises(RegistryIssuerConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        with lifecycle_issuer(scope):
            pass


def test_original_capability_evaluate_fails_closed_under_narrow_issuer_acl(
    capability_case, capability_issuer, readiness_reader,
):
    scope, request = capability_case
    created, _ = AipCapabilityBindingService(connect_factory=capability_issuer).create(
        scope, request,
        idempotency_key=f"s3oo:create:{request.binding_id}",
        actor="test-only", occurred_at=datetime.now(UTC))
    with connect() as owner:
        owner.execute("""GRANT UPDATE(status,health,observed_at,version,updated_at)
            ON aip_capability_binding TO aos_aip_capability_issuer""")
        owner.commit()
    lifecycle_issuer = RegistryIssuerConnectionFactory(
        capability_issuer.config, command_family="capability_lifecycle")
    observed: list[tuple[TenantScope | None, str, str]] = []

    @contextmanager
    def traced_readiness_reader(selected_scope=None):
        with readiness_reader(selected_scope) as reader:
            row = reader.execute("""SELECT session_user AS login,
                current_setting('transaction_read_only') AS readonly""").fetchone()
            observed.append((selected_scope, row["login"], row["readonly"]))
            yield reader

    service = AipCapabilityBindingService(connect_factory=lifecycle_issuer,
        readiness_service=AipBindingReadinessService(
            authority=PostgresBindingDependencyAuthority(traced_readiness_reader),
            model_store=AipModelRuntimeStore(traced_readiness_reader)))
    dependencies = OperationalBindingDependencies(license_evidence_refs=[ResourceRef(
        resource_type="EvidenceBundleRevision", resource_id="s3oo-absent",
        revision="1", authority="test-only")])
    command = EvaluateOperationalBindingRequest(expected_version=1, dependencies=dependencies)
    with pytest.raises(AipAgentRegistryConflict) as failure:
        service.evaluate(
            scope, created.binding_id, command,
            idempotency_key=f"s3oo:evaluate:{created.binding_id}",
            actor="test-only", evaluated_at=datetime.now(UTC))
    assert failure.value.code == "AIP_BINDING_EVALUATOR_REQUIRED"
    assert observed == []
    from aos_api.routers.aip_bindings import _map_error
    mapped = _map_error(failure.value)
    assert mapped.status_code == 409 and mapped.code == "AIP_BINDING_EVALUATOR_REQUIRED"
    with connect(scope) as owner:
        assert owner.execute("SELECT version FROM aip_capability_binding WHERE binding_id=%s",
            (created.binding_id,)).fetchone()["version"] == 1
        assert owner.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
            "WHERE operation='capability_binding.evaluate' AND result_ref->>'resourceId'=%s",
            (created.binding_id,)).fetchone()["n"] == 0
    with pytest.raises(AipAgentRegistryTransitionBlocked):
        service.update(scope, created.binding_id, UpdateCapabilityBindingRequest(
            expected_version=1, from_status="provisioning", to_status="active",
            health="healthy", observed_at=datetime.now(UTC)),
            idempotency_key=f"s3oo:active:{created.binding_id}", actor="test-only")
    revoked, receipt = service.update(scope, created.binding_id,
        UpdateCapabilityBindingRequest(
            expected_version=1, from_status="provisioning", to_status="revoked",
            health="revoked", observed_at=datetime.now(UTC)),
        idempotency_key=f"s3oo:revoke:{created.binding_id}", actor="test-only")
    assert revoked.version == 2 and revoked.status == "revoked"
    assert receipt.operation == "capability_binding.update"
