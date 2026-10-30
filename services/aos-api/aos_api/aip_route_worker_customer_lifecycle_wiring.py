"""Fail-closed runtime wiring for the Route worker customer lifecycle."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aos_api.aip_route_worker_customer_lifecycle import (
    RouteWorkerConfigurationCheck,
    RouteWorkerConfigurationPreview,
    RouteWorkerConfigurationSideEffects,
    RouteWorkerCustomerLifecycleService,
)
from aos_api.aip_route_worker_identity import RouteWorkerIdentityConfig
from aos_api.aip_route_worker_lifecycle_command_connection import (
    connect_route_worker_lifecycle_command,
    probe_route_worker_lifecycle_command,
)
from aos_api.aip_route_worker_installation import (
    RouteWorkerIdentityInstallationStore,
)
from aos_api.aip_route_worker_installation_authority import (
    CurrentRouteWorkerInstallationAuthority,
    RouteWorkerSignedInstallationCoordinator,
)
from aos_api.aip_secret_backend import SecretClient, default_secret_client
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.db import connect_read_only

_SCOPE = ("org-org", "dev-project")
_COMPLETE_OPERATION = "route_worker_identity.customer_lifecycle.complete"
_CONFIGURATION_POST_ENABLED = "AOS_ROUTE_WORKER_CONFIGURATION_POST_ENABLED"


def route_worker_configuration_post_enabled() -> bool:
    return os.environ.get(_CONFIGURATION_POST_ENABLED, "") == "1"


class RouteWorkerBusinessEntryFactory:
    """Build one request-scoped lifecycle service without starting the worker."""

    def __init__(
        self,
        *,
        connect_factory: Callable[..., Any] = connect_route_worker_lifecycle_command,
        read_connect_factory: Callable[..., Any] = connect_read_only,
        secret_client: SecretClient | None = None,
        authority_factory: Callable[
            [], CurrentRouteWorkerInstallationAuthority
        ] = CurrentRouteWorkerInstallationAuthority.from_runtime,
        config_factory: Callable[
            [], RouteWorkerIdentityConfig
        ] = RouteWorkerIdentityConfig.from_control_env,
        path_factory: Callable[[], Path] | None = None,
        command_readiness_probe: Callable[[], bool] = (
            probe_route_worker_lifecycle_command
        ),
        configuration_post_enabled: Callable[[], bool] = (
            route_worker_configuration_post_enabled
        ),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not all(
            callable(item)
            for item in (
                connect_factory,
                read_connect_factory,
                authority_factory,
                config_factory,
                command_readiness_probe,
                configuration_post_enabled,
                clock,
            )
        ):
            raise ValueError(
                "complete route worker business entry dependencies required"
            )
        self._connect_factory = connect_factory
        self._read_connect_factory = read_connect_factory
        self._secret_client = secret_client or default_secret_client()
        self._authority_factory = authority_factory
        self._config_factory = config_factory
        self._path_factory = path_factory or self._configured_path
        self._command_readiness_probe = command_readiness_probe
        self._configuration_post_enabled = configuration_post_enabled
        self._clock = clock

    @staticmethod
    def _configured_path() -> Path:
        raw = os.environ.get("AOS_ROUTE_WORKER_IDENTITY_FILE", "").strip()
        path = Path(raw)
        if not raw or not path.is_absolute():
            raise ValueError("protected route worker configuration path required")
        return path

    def _latest_completion(self) -> dict[str, Any] | None:
        with self._read_connect_factory() as conn:
            apply_asset_transaction_scope(conn, org_id=_SCOPE[0], project_id=_SCOPE[1])
            rows = conn.execute(
                """
                SELECT response_json
                  FROM bundle_installation_command
                 WHERE org_id = %s AND project_id = %s AND operation = %s
                 ORDER BY created_at DESC, idempotency_key DESC
                 LIMIT 2
                """,
                (*_SCOPE, _COMPLETE_OPERATION),
            ).fetchall()
            if not rows:
                return None
            return rows[0]["response_json"]

    def preview_configuration(
        self, *, installation_id: str
    ) -> RouteWorkerConfigurationPreview:
        """Evaluate configuration prerequisites without writes or secret reads."""

        authority = None
        installation_ready = False
        try:
            authority = self._authority_factory()
            installation_ready = (
                authority.assert_installation_current(installation_id) is True
            )
        except Exception:
            installation_ready = False

        identity = None
        identity_ready = False
        try:
            identity = self._config_factory()
            identity_ready = type(identity) is RouteWorkerIdentityConfig
        except Exception:
            identity_ready = False

        storage_ready = False
        try:
            RouteWorkerIdentityInstallationStore.validate_target_path(
                self._path_factory()
            )
            storage_ready = True
        except Exception:
            storage_ready = False

        credential_ready = False
        if installation_ready and identity_ready and authority is not None:
            try:
                target = authority.build_document(
                    config=identity, installation_id=installation_id
                )
                credential_ready = self._secret_client.exists(target.locator()) is True
            except Exception:
                credential_ready = False

        submission_ready = False
        try:
            submission_ready = (
                self._configuration_post_enabled() is True
                and self._command_readiness_probe() is True
            )
        except Exception:
            submission_ready = False

        states = (
            installation_ready,
            identity_ready,
            storage_ready,
            credential_ready,
            submission_ready,
        )
        checks = (
            RouteWorkerConfigurationCheck(
                key="current_customer_installation",
                label="当前客户安装",
                passed=installation_ready,
                detail=(
                    "当前客户安装已通过正式校验。"
                    if installation_ready
                    else "当前客户安装仍需完成正式校验。"
                ),
            ),
            RouteWorkerConfigurationCheck(
                key="background_identity",
                label="后台业务身份",
                passed=identity_ready,
                detail=(
                    "后台业务身份坐标已准备。"
                    if identity_ready
                    else "后台业务身份尚未准备。"
                ),
            ),
            RouteWorkerConfigurationCheck(
                key="protected_storage",
                label="受保护保存位置",
                passed=storage_ready,
                detail=(
                    "受保护保存位置已准备。"
                    if storage_ready
                    else "受保护保存位置尚未准备。"
                ),
            ),
            RouteWorkerConfigurationCheck(
                key="identity_credential",
                label="身份凭据",
                passed=credential_ready,
                detail=(
                    "当前身份凭据已安全就绪。"
                    if credential_ready
                    else "当前身份凭据尚未安全就绪。"
                ),
            ),
            RouteWorkerConfigurationCheck(
                key="configuration_submission",
                label="配置保存通道",
                passed=submission_ready,
                detail=(
                    "配置保存通道已安全开通。"
                    if submission_ready
                    else "配置保存通道尚未安全开通。"
                ),
            ),
        )
        ready = all(states)
        missing_actions = tuple(
            action
            for passed, action in zip(
                states,
                (
                    "等待当前客户安装通过正式校验。",
                    "配置当前客户的后台业务身份。",
                    "准备受保护的配置保存位置。",
                    "由安全管理员准备当前身份凭据。",
                    "安全开通当前客户的配置保存通道。",
                ),
                strict=True,
            )
            if not passed
        )
        return RouteWorkerConfigurationPreview(
            schemaVersion="aos.route-worker-configuration-preview/v1",
            status="reviewable" if ready else "needs_input",
            title=(
                "后台处理配置可以确认" if ready else "后台处理配置条件未齐"
            ),
            summary=(
                "确认后只保存后台处理配置；当前不会自动处理业务。"
                if ready
                else "当前不会自动处理业务；请先补齐配置条件。"
            ),
            approvalAllowed=ready,
            checks=checks,
            nextActions=(
                ("确认后只保存配置；运行仍需另行满足审批和预算。",)
                if ready
                else missing_actions
            ),
            sideEffects=RouteWorkerConfigurationSideEffects(
                databaseWrite=False,
                configurationWrite=False,
                tokenRequest=False,
                businessProcessing=False,
                externalEffect=False,
            ),
            canProcessBusinessTasks=False,
            evaluatedAt=self._clock(),
        )

    def build(self, *, installation_id: str) -> RouteWorkerCustomerLifecycleService:
        path = self._path_factory()
        if not isinstance(path, Path) or not path.is_absolute():
            raise ValueError("protected route worker configuration path required")
        authority = self._authority_factory()
        store = RouteWorkerIdentityInstallationStore(secret_client=self._secret_client)

        def current_reader():
            try:
                path.lstat()
            except FileNotFoundError:
                return None
            return store.load(path)

        return RouteWorkerCustomerLifecycleService(
            receipt_store=PostgresInstallationStore(
                connect_factory=self._connect_factory
            ),
            coordinator=RouteWorkerSignedInstallationCoordinator(
                store=store, authority=authority
            ),
            authority=authority,
            current_reader=current_reader,
            document_factory=lambda: authority.build_document(
                config=self._config_factory(), installation_id=installation_id
            ),
            config_path=path,
            latest_completion_reader=self._latest_completion,
        )
