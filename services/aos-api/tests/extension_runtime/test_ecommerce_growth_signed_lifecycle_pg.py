"""Signed two-generation ecommerce runtime lifecycle on one tenant/schema."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import psycopg
from psycopg import IsolationLevel, sql
from psycopg.rows import dict_row
import pytest
from sqlalchemy import create_engine, text

from aos_api.asset_registry.composition_contracts import (
    ApproveInstallationRequest,
    CreateInstallationRequest,
    EmptyInstallationActionRequest,
    UninstallInstallationRequest,
)
from aos_api.asset_registry.control_policy import (
    APPLY_INSTALLATION_OPERATION,
    CONFIGURE_RUNTIME_OPERATION,
    DISABLE_RUNTIME_OPERATION,
    ENABLE_RUNTIME_OPERATION,
    VERIFY_INSTALLATION_OPERATION,
)
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.ecommerce_growth_cutover import (
    EcommerceGrowthCutoverBlocked,
    EcommerceGrowthCutoverConflict,
    EcommerceGrowthCutoverStore,
)
from aos_api.ecommerce_growth_canonical_router import IssuedDispatchRef
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthHostConflict, LockedEcommerceGrowthHostPort
from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
from aos_api.extension_runtime.configuration_consumer import ConfigurationConsumer
from aos_api.extension_runtime.configuration_service import RuntimeConfigurationService
from aos_api.extension_runtime.configuration_store import append_configuration
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.extension_runtime.disable_executor import RuntimeDisableExecutor
from aos_api.extension_runtime.disable_service import RuntimeDisableService
from aos_api.extension_runtime.oci_driver import OciDriver
from aos_api.extension_runtime.preparation_worker import PreparationWorker
from aos_api.extension_runtime.runtime_uninstall import RuntimeUninstallGuard
from aos_api.extension_runtime.schema_conditions import CurrentSchemaConditions, schema_package_id
from aos_api.extension_runtime.schema_registry import SchemaRequirement, apply_once
from aos_api.tenant_scope import TenantScope

from current_configuration_sources_case import install_current_configuration_sources
from signed_installation_case import SCHEMA_PROBE_SQL, run_signed_installation
from test_ecommerce_growth_cutover_pg import (
    _commit_request,
    _finalize_request,
    _migration,
    _seed,
    _validate_ref,
)


pytestmark = [
    pytest.mark.skipif(os.getenv("AOS_EXTENSION_PG_TEST") != "1", reason="dedicated database opt-in required"),
    pytest.mark.skipif(os.getenv("AOS_EXTENSION_OCI_TEST") != "1", reason="isolated OCI opt-in required"),
]

PG = dict(host="127.0.0.1", port=18432, user="postgres", dbname="postgres")


@pytest.fixture
def database():
    root = Path(__file__).resolve().parents[2]
    schema = "ar2_signed_" + uuid.uuid4().hex
    role = "ar2_signed_" + uuid.uuid4().hex[:16]
    owner = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    created_roles = []
    for required in ("aos_app", "aos_runtime", "aos_extension_maintainer"):
        if owner.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (required,)).fetchone() is None:
            owner.execute(sql.SQL("CREATE ROLE {} NOSUPERUSER NOBYPASSRLS NOLOGIN").format(sql.Identifier(required)))
            created_roles.append(required)
    owner.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT").format(sql.Identifier(role)))
    for granted in ("aos_app", "aos_runtime", "aos_extension_maintainer"):
        owner.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(granted), sql.Identifier(role)))
    owner.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    helper_path = root / "tests/asset_registry/test_m2_core_integration.py"
    spec = importlib.util.spec_from_file_location("ar2_signed_core_helpers", helper_path)
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)
    engine = create_engine("postgresql+psycopg://postgres@127.0.0.1:18432/postgres")
    try:
        with engine.begin() as connection:
            connection.execute(text(f'SET search_path TO "{schema}"'))
            with Operations.context(MigrationContext.configure(connection)):
                paths = (*helper.MIGRATION_PATHS, *(root / "alembic/versions" / name for name in (
                    "w1e_001_bundle_installation_uninstall.py",
                    "ar1_001_extension_runtime_authority.py",
                    "ar1_002_runtime_configuration.py",
                    "ar1_004_runtime_execution_attempt.py",
                    "ar2_001_ecommerce_dispatch_authority.py",
                    "ar2_002_automation_occurrence.py",
                )))
                for index, path in enumerate(paths):
                    helper._load_migration(path, index).upgrade()
        owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        for table in ("bundle_composition", "bundle_composition_lock", "bundle_installation",
                      "bundle_installation_command", "bundle_installation_decision",
                      "bundle_installation_event", "bundle_installation_revision"):
            qualified = sql.Identifier(schema, table)
            owner.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE ON {} TO aos_runtime").format(qualified))
            owner.execute(sql.SQL("CREATE POLICY {} ON {} TO aos_runtime,aos_app USING "
                "(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) "
                "WITH CHECK (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))")
                .format(sql.Identifier("tenant_scope_" + table + "_d6d2"), qualified))
            owner.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(qualified))
            owner.execute(sql.SQL("ALTER TABLE {} FORCE ROW LEVEL SECURITY").format(qualified))
        for table, privileges in (
            ("bundle_composition", "SELECT"),
            ("bundle_composition_lock", "SELECT"),
            ("bundle_installation", "SELECT,UPDATE"),
            ("bundle_installation_command", "SELECT,INSERT"),
            ("bundle_installation_decision", "SELECT"),
            ("bundle_installation_event", "SELECT,INSERT"),
            ("bundle_installation_revision", "SELECT,INSERT"),
        ):
            owner.execute(sql.SQL("GRANT {} ON {} TO aos_app").format(
                sql.SQL(privileges), sql.Identifier(schema, table)))
        for table, fields in (("meta_membership", "subject text,role text"),
                              ("authz_tuple", "user_key text,relation text,object_key text")):
            owner.execute(sql.SQL("CREATE TABLE {} (org_id text,project_id text,{})")
                          .format(sql.Identifier(schema, table), sql.SQL(fields)))
            owner.execute(sql.SQL("GRANT SELECT,UPDATE ON {} TO aos_runtime").format(sql.Identifier(schema, table)))
        owner.execute("INSERT INTO meta_membership VALUES('org-org','dev-project','test-author','admin')")
        for table in ("asset_bundle", "asset_bundle_version", "asset_bundle_artifact", "asset_bundle_evidence"):
            owner.execute(sql.SQL("GRANT SELECT ON {} TO aos_runtime").format(sql.Identifier(schema, table)))
        owner.execute("""CREATE TABLE aip_action_proposal(
            org_id text NOT NULL,project_id text NOT NULL,proposal_id text NOT NULL,
            action_type_id text NOT NULL,action_type_snapshot jsonb NOT NULL,task_id text,run_id text,
            object_ref jsonb,purpose text NOT NULL,risk_level text NOT NULL,policy_snapshot jsonb NOT NULL,
            payload jsonb NOT NULL,diff jsonb NOT NULL,evidence_refs jsonb NOT NULL,
            impact_preview_id text,impact_preview_revision bigint,impact_preview_hash text,
            action_binding_hash text,source_draft_id text,source_draft_revision bigint,
            source_draft_hash text,approval_policy_hash text,proposal_hash text NOT NULL,
            status text NOT NULL,version bigint NOT NULL,expires_at timestamptz NOT NULL,
            created_by text NOT NULL,PRIMARY KEY(org_id,project_id,proposal_id))""")
        owner.execute("""CREATE TABLE aip_action_draft(
            org_id text NOT NULL,project_id text NOT NULL,proposal_id text NOT NULL,
            proposal_hash text NOT NULL,snapshot jsonb NOT NULL,PRIMARY KEY(org_id,project_id,proposal_id))""")
        owner.execute("""CREATE TABLE aip_action_approval_event(
            org_id text NOT NULL,project_id text NOT NULL,approval_event_id text NOT NULL,
            proposal_id text NOT NULL,proposal_version bigint NOT NULL,proposal_hash text NOT NULL,
            decision text NOT NULL,actor_id text NOT NULL,reason text NOT NULL,expires_at timestamptz,
            created_at timestamptz NOT NULL,action_binding_hash text,
            PRIMARY KEY(org_id,project_id,approval_event_id))""")
        for table in ("aip_action_proposal", "aip_action_draft", "aip_action_approval_event"):
            owner.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            owner.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            owner.execute(f"""CREATE POLICY tenant_scope ON {table}
                USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
                WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))""")
        for migration in (
            "ar2_013_ecommerce_growth_cutover.py", "ar2_014_ecommerce_growth_cutover_commit.py",
            "ar2_015_ecommerce_growth_cutover_finalize.py", "ar2_016_ecommerce_growth_cutover_rollback.py",
            "ar2_017_ecommerce_growth_disable_detach.py", "ar2_018_runtime_uninstall_authority.py",
            "a0v_028_dispatch_read_lock.py",
        ):
            _migration(root, migration, owner, schema=schema)
        for granted in ("aos_app", "aos_runtime", "aos_extension_maintainer"):
            owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}")
                          .format(sql.Identifier(schema), sql.Identifier(granted)))
        assert owner.execute("SELECT has_table_privilege('aos_app',%s,'UPDATE') AS allowed",
            (schema+'.bundle_installation_revision',)).fetchone()['allowed'] is False
        yield SimpleNamespace(owner=owner, schema=schema, role=role, root=root, helper=helper)
    finally:
        engine.dispose()
        owner.execute("RESET ROLE")
        owner.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        for granted in ("aos_app", "aos_runtime", "aos_extension_maintainer"):
            owner.execute(sql.SQL("REVOKE {} FROM {}").format(sql.Identifier(granted), sql.Identifier(role)))
        owner.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        for created in reversed(created_roles):
            owner.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(created)))
        owner.close()


def _scoped_connect(database):
    @contextmanager
    def connect():
        with psycopg.connect(**PG, row_factory=dict_row) as conn:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
            yield conn
    return connect


def _runtime_connect(database):
    @contextmanager
    def connect():
        conn = psycopg.connect(**{**PG, "user": database.role}, row_factory=dict_row)
        try:
            conn.execute("SET ROLE aos_runtime")
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
            conn.commit()
            yield conn
        finally:
            conn.close()
    return connect


def _app_connect(database):
    @contextmanager
    def connect():
        conn = psycopg.connect(**{**PG, "user": database.role}, row_factory=dict_row)
        try:
            conn.execute("SET ROLE aos_app")
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
            conn.commit()
            yield conn
        finally:
            conn.close()
    return connect


def _cutover_connect(database):
    @contextmanager
    def connect(scope):
        conn = psycopg.connect(**{**PG, "user": database.role}, row_factory=dict_row)
        try:
            conn.isolation_level = IsolationLevel.SERIALIZABLE
            conn.execute("SET ROLE aos_extension_maintainer")
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return connect


def test_signed_disable_uninstall_reinstall_routes_exact_ecommerce_group(database, tmp_path):
    connect = _scoped_connect(database)
    scope = TenantScope("org-org", "dev-project")
    scope_dict = dict(org_id=scope.org_id, project_id=scope.project_id)
    context = "colima-aos-extension"
    OciDriver(context=context).require_isolation()
    def owned_container_ids():
        return set(subprocess.check_output(["docker", "--context", context, "ps", "-aq",
            "--filter", "label=aos.extension.owner"], text=True, timeout=15).split())
    existing_containers = owned_container_ids()

    def package_probe(**package):
        store = package["store"]
        legacy = package["legacy"]
        lock = package["lock"]
        selected = package["selected"]
        revalidator = package["revalidator"]
        lifecycle = package["lifecycle"]
        record = package["record"]
        read_artifact = package["read_artifact"]
        policy = package["policy"]
        with database.owner.transaction():
            database.owner.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(database.schema)))
            requirement = SchemaRequirement(schema_package_id(selected.publisher, selected.id), "1",
                "sha256:" + hashlib.sha256(SCHEMA_PROBE_SQL.encode()).hexdigest())
            def migrate(conn):
                conn.execute(SCHEMA_PROBE_SQL)
            assert apply_once(database.owner, requirement, migrate) is True
        database.owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
        _, sources = install_current_configuration_sources(database.owner, database.schema)
        document = sources["configuration"]
        database.owner.execute("RESET ROLE")
        database.owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))

        def permission(operation):
            return CurrentControlPermission(operation=operation)

        def configuration_permission(conn, *, installation_id, actor, **_):
            etag = conn.execute("""SELECT etag_version FROM bundle_installation
                WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
                (*scope.key, installation_id)).fetchone()["etag_version"]
            locked = store.lock_for_transition_in_transaction(conn, **scope_dict,
                installation_id=installation_id, expected_etag_version=etag)
            return permission(CONFIGURE_RUNTIME_OPERATION)(conn=conn, locked=locked, actor=actor)

        from aos_api.aip_runtime_configuration_sources import build_current_configuration_authorization
        authorize = build_current_configuration_authorization(permission=configuration_permission)
        conditions = CurrentSchemaConditions(load_record=lambda member: record,
            read_artifact=lambda member, path, limit: read_artifact(path, limit), policy=policy)
        runtime_connect = _runtime_connect(database)
        runtime_store = PostgresInstallationStore(runtime_connect)

        async def install_generation(index):
            suffix = f"-d6d2-{index}"
            draft = store.create_draft(**scope_dict, request=CreateInstallationRequest(
                compositionId=lock.composition_id, lockRevision=lock.revision,
                overlayRevision="isolated-test", displayName=f"签名电商运行代次 {index}"),
                requested_by="test-author")
            action = dict(**scope_dict, installation_id=draft.installation_id, markings=[],
                roles=["asset-installer"], actor="test-author")
            legacy.submit(**action, request=EmptyInstallationActionRequest(),
                idempotency_key="d6d2-submit" + suffix, if_match=f'"{draft.etag_version}"')
            submitted = store.get_installation(**scope_dict, installation_id=draft.installation_id)
            legacy.approve(**{**action, "actor": "test-reviewer", "roles": ["asset-install-approver"]},
                request=ApproveInstallationRequest(lockHash=lock.lock_hash,
                    permissionDiffHash=lock.permission_diff_hash,
                    migrationPlanHash=lock.migration_plan_hash,
                    contributionDiffHash=lock.contribution_diff_hash),
                idempotency_key="d6d2-approve" + suffix, if_match=f'"{submitted.etag_version}"')
            approved = store.get_installation(**scope_dict, installation_id=draft.installation_id)
            accepted = lifecycle.request_preparation(**action, kind="runtime-apply",
                preparation_admission=lambda: True,
                idempotency_key="d6d2-runtime-apply" + suffix,
                if_match=f'"{approved.etag_version}"')
            worker = PreparationWorker(connect=runtime_connect, driver=OciDriver(context=context),
                installation_store=store, revalidator=revalidator,
                check_current_permission=permission(APPLY_INSTALLATION_OPERATION),
                load_record=lambda member: record, read_artifact=read_artifact, policy=policy,
                platform=package["platform"], check_current_conditions=conditions,
                check_verification_permission=permission(VERIFY_INSTALLATION_OPERATION),
                configuration_authorize=authorize,
                check_enable_permission=permission(ENABLE_RUNTIME_OPERATION))
            job = await worker.start(**scope_dict, operation_id=accepted.response_json["operationId"],
                expected_revision=accepted.response_json["revision"])
            applied = await job.prepared()
            requested = lifecycle.request_preparation(**action, kind="runtime-verify",
                preparation_admission=lambda: True,
                idempotency_key="d6d2-runtime-verify" + suffix, if_match=f'"{applied.etag_version}"')
            verified = await job.verify(operation_id=requested.response_json["operationId"],
                expected_revision=requested.response_json["revision"])
            with runtime_connect() as conn:
                with conn.transaction():
                    apply_asset_transaction_scope(conn, **scope_dict)
                    config = append_configuration(conn, **scope_dict,
                        installation_id=verified.installation_id, generation=str(job.plan.generation),
                        actor=action["actor"], expected_installation_etag=verified.etag_version,
                        expected_binding_revision=1, idempotency_key="d6d2-config" + suffix,
                        configuration=document, authorize=authorize)
            configuration = RuntimeConfigurationService(installation_store=runtime_store,
                installation_reader=legacy, revalidator=revalidator, authorize=authorize)
            target = dict(generation=str(job.plan.generation), bindingRevision=1,
                configRef=config.model_dump(mode="json"))
            configured = configuration.request(**action, kind="configure",
                idempotency_key="d6d2-configure" + suffix,
                if_match=f'"{verified.etag_version}"', target=target)
            consumer = ConfigurationConsumer(connect=runtime_connect, authorize=authorize,
                check_drained=lambda *args, **kwargs: True)
            deliveries = []
            for _ in range(30):
                delivered = consumer.run_once(**scope_dict)
                if delivered is None:
                    break
                deliveries.append(delivered)
                if str(delivered.operation_id) == configured.response_json["operationId"]:
                    break
            assert any(str(item.operation_id) == configured.response_json["operationId"]
                and item.operation_status == "succeeded" for item in deliveries)
            target["bindingRevision"] = 3
            enabled = configuration.request(**action, kind="enable",
                idempotency_key="d6d2-enable" + suffix,
                if_match=f'"{verified.etag_version}"', target=target)
            await job.enable(operation_id=enabled.response_json["operationId"],
                expected_revision=enabled.response_json["revision"])
            with connect() as conn:
                binding = conn.execute("""SELECT generation,execution_epoch,revision,enabled,
                        operation_fence,observed_state FROM extension_runtime_binding
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
                    (*scope.key, draft.installation_id)).fetchone()
                resource = conn.execute("""SELECT resource_id,container_id,package_hash,cleanup_state,
                        observed_release FROM extension_runtime_resource_lease
                    WHERE org_id=%s AND project_id=%s AND resource_id=%s AND generation=%s""",
                    (*scope.key, job.plan.members[0].intent.resource_id, job.plan.generation)).fetchone()
            assert binding["enabled"] is True and binding["operation_fence"] is False
            assert binding["observed_state"] == "ready"
            assert resource["cleanup_state"] == "pending" and resource["observed_release"] is False
            running = subprocess.check_output(["docker", "--context", context, "inspect", "--format",
                "{{.Id}}|{{.State.Running}}|{{index .Config.Labels \"aos.extension.owner\"}}",
                job.plan.members[0].intent.identity.name], text=True, timeout=15).strip().split("|")
            assert running == [resource["container_id"], "true", job.plan.members[0].intent.identity.owner]
            return dict(index=index, suffix=suffix, draft=draft, action=action, verified=verified,
                worker=worker, job=job, binding=binding, resource=resource)

        def activate(generation, *, existing_group=None, expected_group_revision=11,
                     stale_validate_ref=None):
            request = _seed(database, scope, pending_receipt=False, suffix=generation["suffix"],
                existing_group=existing_group, expected_group_revision=expected_group_revision,
                target_execution_epoch=generation["binding"]["execution_epoch"],
                target_runtime_revision=generation["binding"]["revision"],
                target_installation_id=generation["draft"].installation_id,
                target_generation=generation["job"].plan.generation)
            cutover = EcommerceGrowthCutoverStore(_cutover_connect(database), schema=database.schema)
            prepared = cutover.prepare_activation(scope, request, actor="runtime-owner")
            commit_request = _commit_request(prepared, suffix=generation["suffix"])
            cutover.begin_activation_commit(scope, commit_request, actor="runtime-owner")
            committed = cutover.commit_activation(scope, commit_request, actor="runtime-owner")
            finalize_request = _finalize_request(committed, suffix=generation["suffix"])
            validated = cutover.validate_activation(scope, finalize_request, actor="runtime-owner")
            if stale_validate_ref is not None:
                with pytest.raises(EcommerceGrowthCutoverConflict,
                                   match="validate Receipt reference drifted"):
                    cutover.resume_activation(scope, finalize_request,
                        validate_receipt_ref=stale_validate_ref, actor="runtime-owner")
            cutover.resume_activation(scope, finalize_request,
                validate_receipt_ref=_validate_ref(validated), actor="runtime-owner")
            return request, prepared, finalize_request, validated

        async def disable_and_release(generation):
            dependent = EcommerceGrowthDisableDependent(schema=database.schema)
            with connect() as conn:
                current_binding_revision = conn.execute("""SELECT revision FROM extension_runtime_binding
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s""",
                    (*scope.key, generation["draft"].installation_id,
                     generation["job"].plan.generation)).fetchone()["revision"]
            service = RuntimeDisableService(installation_store=runtime_store, installation_reader=legacy,
                check_current_permission=permission(DISABLE_RUNTIME_OPERATION), dependent=dependent)
            accepted = service.request(**generation["action"],
                idempotency_key="d6d2-disable" + generation["suffix"],
                if_match=f'"{generation["verified"].etag_version}"',
                target=dict(generation=str(generation["job"].plan.generation),
                    bindingRevision=current_binding_revision))
            from aos_api.extension_runtime.disable_consumer import RuntimeDisableConsumer
            from aos_api.extension_runtime.runtime_host import RuntimeHost, RuntimeTenantAssignment
            from aos_api.extension_runtime.live_installation_scheduler import LiveInstallationScheduler
            from aos_api.extension_runtime.live_installation_owner import LiveInstallationLifecycleOwner
            from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
            consumer = RuntimeDisableConsumer(connect=runtime_connect, installation_store=runtime_store,
                check_current_permission=permission(DISABLE_RUNTIME_OPERATION),
                check_drained=GenerationDrainReader(), dependent=dependent)
            # Real Owner cleanup changes the binding revision. Exercise the Host
            # coordination boundary instead of calling the executor directly.
            scheduler=object.__new__(LiveInstallationScheduler)
            scheduler.directory=SimpleNamespace(scope=scope)
            owner=object.__new__(LiveInstallationLifecycleOwner)
            installation=uuid.UUID(str(generation['draft'].installation_id))
            scheduler.find_owner=lambda target: owner if target==installation else None
            async def release(target,expected):
                assert target==installation and expected is owner
                await generation['job'].stop()
            scheduler.revoke=release
            assignment=RuntimeTenantAssignment(scope,lifecycle=scheduler,consumers=(consumer,))
            host=RuntimeHost(assignments=lambda:(assignment,))
            result=None
            for _ in range(30):
                delivered=await host._consume(assignment,consumer)
                if delivered and str(delivered.operation_id)==accepted.response_json['operationId']:
                    result=delivered;break
            assert result is not None and result.operation_status=='succeeded'
            with connect() as conn:
                detached = conn.execute("""SELECT count(*) AS n FROM extension_operation_dispatch_binding
                    WHERE org_id=%s AND project_id=%s AND handler_kind='legacy' AND operation_fence=false""",
                    scope.key).fetchone()["n"]
            assert detached == len(ECOMMERCE_GROWTH_OPERATIONS)
            absent = subprocess.run(["docker", "--context", context, "inspect",
                generation["job"].plan.members[0].intent.identity.name], capture_output=True, text=True, timeout=15)
            assert absent.returncode != 0 and "no such" in absent.stderr.lower()
            with connect() as conn:
                release = conn.execute("""SELECT cleanup_state,observed_release FROM extension_runtime_resource_lease
                    WHERE resource_id=%s""", (generation["resource"]["resource_id"],)).fetchone()
            assert release == {"cleanup_state": "released", "observed_release": True}

        async def scenario():
            first = await install_generation(1)
            first_cutover = activate(first)
            old_dispatch = database.owner.execute("""SELECT operation_id,handler_kind,revision,installation_id,
                    generation,execution_epoch,cutover_group_id,cutover_group_revision
                FROM extension_operation_dispatch_binding WHERE operation_id=%s""",
                (sorted(ECOMMERCE_GROWTH_OPERATIONS)[0],)).fetchone()
            old_ref = IssuedDispatchRef(org_id=scope.org_id, project_id=scope.project_id, **{
                "operation_id": old_dispatch["operation_id"], "handler_kind": old_dispatch["handler_kind"],
                "dispatch_revision": old_dispatch["revision"], "installation_id": str(old_dispatch["installation_id"]),
                "generation": str(old_dispatch["generation"]), "execution_epoch": old_dispatch["execution_epoch"],
                "cutover_group_id": str(old_dispatch["cutover_group_id"]),
                "cutover_group_revision": old_dispatch["cutover_group_revision"],
            })
            await disable_and_release(first)
            app_store = PostgresInstallationStore(_app_connect(database))
            guarded = InstallationService(store=app_store, composition_store=package["composition_store"],
                revalidator=InstallationRevalidator(release_policy=policy), planning_revalidator=revalidator,
                runtime_uninstall_guard=RuntimeUninstallGuard())
            current = store.get_installation(**scope_dict, installation_id=first["draft"].installation_id)
            guarded.uninstall(**first["action"], request=UninstallInstallationRequest(reason="D6D2 first generation retired"),
                idempotency_key="d6d2-uninstall", if_match=f'"{current.etag_version}"')
            assert store.get_installation(**scope_dict,
                installation_id=first["draft"].installation_id).state == "uninstalled"

            second = await install_generation(2)
            legacy_revision = database.owner.execute("""SELECT min(cutover_group_revision) AS revision
                FROM extension_operation_dispatch_binding WHERE cutover_group_id=%s AND handler_kind='legacy'""",
                (first_cutover[0].cutover_group_id,)).fetchone()["revision"]
            stale = _seed(database, scope, pending_receipt=False, suffix="-d6d2-stale",
                existing_group=first_cutover[0].cutover_group_id,
                expected_group_revision=legacy_revision,
                target_execution_epoch=second["binding"]["execution_epoch"],
                target_runtime_revision=second["binding"]["revision"],
                target_installation_id=second["draft"].installation_id,
                target_generation=second["job"].plan.generation)
            stale = stale.model_copy(update={"approval_ref": first_cutover[0].approval_ref})
            cutover = EcommerceGrowthCutoverStore(_cutover_connect(database), schema=database.schema)
            with pytest.raises(EcommerceGrowthCutoverBlocked, match="approval is not bound to this exact group"):
                cutover.prepare_activation(scope, stale, actor="runtime-owner")
            second_cutover = activate(second, existing_group=first_cutover[0].cutover_group_id,
                expected_group_revision=legacy_revision,
                stale_validate_ref=_validate_ref(first_cutover[3]))
            with psycopg.connect(**{**PG, "user": database.role}, row_factory=dict_row) as conn:
                conn.isolation_level = IsolationLevel.SERIALIZABLE
                conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
                conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
                conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
                conn.execute("SET LOCAL ROLE aos_runtime")
                class SchemaLockConnection:
                    # Only this historical private-schema fixture relocates the fixed function.
                    def execute(self, query, params=()):
                        return conn.execute(query.replace(
                            "public.extension_dispatch_lock_group_a0v_028",
                            database.schema + ".extension_dispatch_lock_group_a0v_028",
                        ), params)
                with pytest.raises(EcommerceGrowthHostConflict, match="exact dispatch authority drifted"):
                    LockedEcommerceGrowthHostPort._lock_and_revalidate(SchemaLockConnection(), scope, old_ref)
            rows = database.owner.execute("""SELECT installation_id,generation,handler_kind,operation_fence,
                    cutover_group_revision FROM extension_operation_dispatch_binding ORDER BY operation_id""").fetchall()
            assert len(rows) == len(ECOMMERCE_GROWTH_OPERATIONS)
            assert all(row["installation_id"] == second_cutover[0].target_installation_id
                and row["generation"] == second_cutover[0].target_generation
                and row["handler_kind"] == "extension" and row["operation_fence"] is False
                and row["cutover_group_revision"] > old_ref.cutover_group_revision for row in rows)
            operations = database.owner.execute("""SELECT installation_id,operation_id FROM extension_runtime_operation
                WHERE kind='runtime-apply' AND idempotency_key LIKE 'd6d2-runtime-apply-d6d2-%'
                ORDER BY installation_id""").fetchall()
            assert len(operations) == 2 and len({row["installation_id"] for row in operations}) == 2
            assert first["resource"]["package_hash"] == second["resource"]["package_hash"]
            assert first["resource"]["container_id"] != second["resource"]["container_id"]
            first_history = database.owner.execute("""SELECT
                (SELECT count(*) FROM bundle_installation_revision r
                  JOIN bundle_installation i USING(org_id,project_id,installation_pk)
                 WHERE i.installation_id=%s) AS installation_revisions,
                (SELECT count(*) FROM bundle_installation_event e
                  JOIN bundle_installation i USING(org_id,project_id,installation_pk)
                 WHERE i.installation_id=%s) AS installation_events,
                (SELECT count(*) FROM extension_runtime_operation
                 WHERE installation_id=%s) AS runtime_operations,
                (SELECT count(*) FROM extension_dispatch_cutover_receipt
                 WHERE cutover_operation_id=%s) AS cutover_receipts,
                (SELECT count(*) FROM extension_dispatch_lifecycle_receipt r
                  JOIN extension_dispatch_lifecycle_operation o
                    USING(org_id,project_id,runtime_operation_id)
                 WHERE o.activation_operation_id=%s) AS lifecycle_receipts,
                (SELECT count(*) FROM extension_runtime_uninstall_receipt
                 WHERE installation_id=%s) AS uninstall_receipts""",
                (first_cutover[0].target_installation_id,
                 first_cutover[0].target_installation_id,
                 first_cutover[0].target_installation_id,
                 first_cutover[0].cutover_operation_id,
                 first_cutover[0].cutover_operation_id,
                 first_cutover[0].target_installation_id)).fetchone()
            assert first_history["installation_revisions"] == 6
            assert first_history["installation_events"] == 6
            assert first_history["runtime_operations"] == 5
            assert first_history["cutover_receipts"] >= 4
            assert first_history["lifecycle_receipts"] == 2
            assert first_history["uninstall_receipts"] == 1
            await disable_and_release(second)
            return first, second

        first, second = asyncio.run(scenario())
        assert package["manifest_digest"].startswith("sha256:")
        assert package["config_digest"].startswith("sha256:")
        return first, second

    result = run_signed_installation(connect, database.helper, tmp_path, package_probe=package_probe)
    assert result[0]["draft"].installation_id != result[1]["draft"].installation_id
    assert owned_container_ids() == existing_containers
