from dataclasses import replace

import pytest

from aos_api.aip_runtime_configuration_sources import (
    build_current_configuration_authorization,
)
from aos_api.asset_registry.control_policy import (
    APPLY_INSTALLATION_OPERATION,
    ENABLE_RUNTIME_OPERATION,
    VERIFY_INSTALLATION_OPERATION,
)
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.configuration_authorization import (
    CurrentConfigurationPermission,
)
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.extension_runtime.live_installation_scheduler import LiveInstallationScheduler
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.extension_runtime.oci_driver import OciDriver
from aos_api.extension_runtime.production_preparation import (
    ProductionPreparationDependencies,
)
from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator
from aos_api.extension_runtime.runtime_release_artifacts import CurrentRuntimeReleaseArtifacts
from aos_api.extension_runtime.schema_conditions import CurrentSchemaConditions
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _dependencies(tmp_path, calls):
    store = PostgresInstallationStore()
    policy = ReleasePolicy(trust_roots=None)

    def connect():
        calls.append("connect")
        raise AssertionError("composition must not connect")

    return ProductionPreparationDependencies(
        connect=connect,
        installation_store=store,
        revalidator=RuntimeReleaseRevalidator(release_policy=policy),
        policy=policy,
        loader=ManifestLoader({"test": tmp_path}),
        apply_permission=CurrentControlPermission(
            operation=APPLY_INSTALLATION_OPERATION
        ),
        verification_permission=CurrentControlPermission(
            operation=VERIFY_INSTALLATION_OPERATION
        ),
        enable_permission=CurrentControlPermission(operation=ENABLE_RUNTIME_OPERATION),
        configuration_authorize=build_current_configuration_authorization(
            permission=CurrentConfigurationPermission(installation_store=store)
        ),
        driver=OciDriver(context="colima-aos-extension"),
        platform="linux/arm64",
        live_directory=LivePreparedJobDirectory(),
    )


def test_builds_exact_same_tenant_unstarted_scheduler_without_access(tmp_path):
    calls = []
    dependencies = _dependencies(tmp_path, calls)
    scheduler = dependencies.build_scheduler(SCOPE)

    assert type(scheduler) is LiveInstallationScheduler
    assert scheduler.directory.scope == SCOPE
    assert scheduler.factory.scope == SCOPE
    assert scheduler.factory.connect is dependencies.connect
    assert scheduler.factory.live_directory is dependencies.live_directory
    assert scheduler.owners == ()

    worker = scheduler.factory.worker
    assert worker.connect is dependencies.connect
    assert worker.driver is dependencies.driver
    assert worker.store is dependencies.installation_store
    assert worker.revalidator is dependencies.revalidator
    assert worker.permission is dependencies.apply_permission
    assert worker.verification_permission is dependencies.verification_permission
    assert worker.enable_permission is dependencies.enable_permission
    assert worker.configuration_authorize is dependencies.configuration_authorize
    assert worker.policy is dependencies.policy
    assert worker.platform == "linux/arm64"
    assert type(worker.conditions) is CurrentSchemaConditions
    assert type(worker.load_record.__self__) is CurrentRuntimeReleaseArtifacts
    assert worker.load_record.__self__ is worker.read_member_artifact.__self__
    assert worker.conditions.load_record.__self__ is worker.load_record.__self__
    assert worker.conditions.read_artifact.__self__ is worker.load_record.__self__
    assert worker.load_record.__self__.scope == SCOPE
    assert worker.load_record.__self__.loader is dependencies.loader
    with pytest.raises(RuntimeError, match="selected runtime release"):
        worker.read_artifact("artifact", 1)
    assert calls == []


def test_each_tenant_gets_distinct_worker_but_one_process_live_directory(tmp_path):
    dependencies = _dependencies(tmp_path, [])
    first = dependencies.build_scheduler(SCOPE)
    second = dependencies.build_scheduler(TenantScope("other-org", "other-project"))
    assert first is not second
    assert first.factory.worker is not second.factory.worker
    assert first.factory.live_directory is dependencies.live_directory
    assert second.factory.live_directory is dependencies.live_directory
    assert first.directory.scope != second.directory.scope


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("connect", object(), TypeError),
        ("installation_store", object(), TypeError),
        ("revalidator", object(), TypeError),
        ("policy", object(), TypeError),
        ("loader", object(), TypeError),
        ("configuration_authorize", object(), TypeError),
        ("driver", object(), TypeError),
        ("live_directory", object(), TypeError),
        ("platform", "darwin/arm64", ValueError),
    ],
)
def test_rejects_inexact_production_dependency(tmp_path, field, value, error):
    dependencies = _dependencies(tmp_path, [])
    with pytest.raises(error):
        replace(dependencies, **{field: value})


@pytest.mark.parametrize(
    ("field", "operation"),
    [
        ("apply_permission", VERIFY_INSTALLATION_OPERATION),
        ("verification_permission", ENABLE_RUNTIME_OPERATION),
        ("enable_permission", APPLY_INSTALLATION_OPERATION),
    ],
)
def test_rejects_permission_operation_swap(tmp_path, field, operation):
    dependencies = _dependencies(tmp_path, [])
    with pytest.raises(TypeError, match="permissions"):
        replace(
            dependencies,
            **{field: CurrentControlPermission(operation=operation)},
        )


def test_rejects_non_exact_tenant_scope(tmp_path):
    dependencies = _dependencies(tmp_path, [])
    with pytest.raises(TypeError, match="tenant scope"):
        dependencies.build_scheduler(object())


def test_rejects_mixed_policy_trust_roots_or_installation_store(tmp_path):
    dependencies = _dependencies(tmp_path, [])
    other_policy = ReleasePolicy(trust_roots=None)
    with pytest.raises(TypeError, match="graph"):
        replace(
            dependencies,
            revalidator=RuntimeReleaseRevalidator(release_policy=other_policy),
        )

    class Roots:
        pass

    with pytest.raises(TypeError, match="graph"):
        replace(dependencies, loader=ManifestLoader({"test": tmp_path}, Roots()))

    other_store = PostgresInstallationStore()
    with pytest.raises(TypeError, match="graph"):
        replace(
            dependencies,
            configuration_authorize=build_current_configuration_authorization(
                permission=CurrentConfigurationPermission(
                    installation_store=other_store
                )
            ),
        )
