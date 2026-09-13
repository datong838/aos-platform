"""Read-only projection for the canonical extension-runtime control API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from typing import Any, Literal
from uuid import UUID

import psycopg
from pydantic import BaseModel, ConfigDict, Field

from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.db import connect_read_only


ConnectFactory = Callable[[], AbstractContextManager[Any]]
UiSessionResolver = Callable[..., "RuntimeUiSessionView | None"]
RuntimeAction = Literal["runtime-apply", "runtime-verify", "configure", "enable", "disable"]


class RuntimeBindingView(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    generation: str
    installationRevision: int = Field(ge=1)
    profileRef: str
    configRef: dict[str, Any] | None
    executionEpoch: int = Field(ge=1)
    desiredState: str
    observedState: str
    enabled: bool
    operationFence: bool
    revision: int = Field(ge=1)


class RuntimeOperationEventView(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    type: str
    payloadHash: str
    occurredAt: str


class RuntimeOperationView(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    operationId: str
    installationId: str
    kind: str
    phase: str
    status: str
    revision: int = Field(ge=1)
    requestedBy: str
    approvedBy: str | None
    expectedInstallationEtag: int = Field(ge=1)
    expectedBindingRevision: int | None
    deadline: str
    failureCode: str | None
    createdAt: str
    events: tuple[RuntimeOperationEventView, ...] = ()


class RuntimeUiSessionView(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=160)
    signedResourceUrl: str = Field(min_length=1, max_length=2048)
    resourceHash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    initialRoute: str = Field(min_length=1, max_length=512)
    routeClaims: tuple[str, ...]
    readOperationClaims: tuple[str, ...]
    commandOperationClaims: tuple[str, ...]


class RuntimeInstallationView(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    installationId: str
    installationRevision: int = Field(ge=1)
    installationEtag: int = Field(ge=1)
    installationState: str
    effectiveState: str
    binding: RuntimeBindingView | None
    currentOperation: RuntimeOperationView | None
    ui: RuntimeUiSessionView | None = None
    allowedActions: tuple[RuntimeAction, ...]
    reasons: tuple[str, ...]


def _values(row: Any, names: tuple[str, ...]) -> tuple[Any, ...]:
    if isinstance(row, Mapping):
        return tuple(row[name] for name in names)
    return tuple(row)


def _iso(value: Any) -> str:
    return value.isoformat()


class RuntimeViewReader:
    """Projects existing Installation/runtime truth without creating a second authority."""

    def __init__(
        self,
        *,
        installation_reader: Any,
        connect_factory: ConnectFactory = connect_read_only,
        ui_session_resolver: UiSessionResolver | None = None,
    ) -> None:
        self._installation_reader = installation_reader
        self._connect_factory = connect_factory
        self._ui_session_resolver = ui_session_resolver

    def get_installation(
        self,
        *,
        installation_id: str,
        org_id: str,
        project_id: str,
        roles: list[str],
        markings: list[str],
        requested_route: str | None = None,
    ) -> RuntimeInstallationView:
        if requested_route is not None:
            from aos_api.extension_runtime.ui_resources import _canonical_route
            if type(requested_route) is not str or len(requested_route) > 512 or not _canonical_route(requested_route):
                raise ValueError('canonical runtime UI route required')
        installation_id = str(UUID(str(installation_id)))
        installation = self._installation_reader.get(
            installation_id=installation_id,
            org_id=org_id,
            project_id=project_id,
            roles=roles,
            markings=markings,
        )
        runtime_storage_available = True
        resources_live = False
        try:
            with self._connect_factory() as conn:
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                binding_row = conn.execute(
                    """
                    SELECT generation, installation_revision, profile_ref, config_ref,
                           execution_epoch, desired_state, observed_state, enabled,
                           operation_fence, revision
                      FROM extension_runtime_binding
                     WHERE org_id=%s AND project_id=%s AND installation_id=%s
                     ORDER BY (installation_revision=%s) DESC,
                              (desired_state<>'uninstalled') DESC,
                              revision DESC, generation DESC
                     LIMIT 1
                    """,
                    (org_id, project_id, UUID(installation_id), installation.current_revision),
                ).fetchone()
                operation_row = conn.execute(
                    """
                    SELECT operation_id, installation_id, kind, phase, status, revision,
                           requested_by, approved_by, expected_installation_etag,
                           expected_binding_revision, deadline, failure_code, created_at
                      FROM extension_runtime_operation
                     WHERE org_id=%s AND project_id=%s AND installation_id=%s
                     ORDER BY (status NOT IN ('succeeded','failed','cancelled')) DESC,
                              created_at DESC, operation_id DESC
                     LIMIT 1
                    """,
                    (org_id, project_id, UUID(installation_id)),
                ).fetchone()
                operation = self._operation_from_row(conn, org_id, project_id, operation_row)
                binding = self._binding_from_row(binding_row)
                if binding is not None:
                    from .runtime_resource_health import current_resources_live
                    resources_live = current_resources_live(conn, org_id=org_id, project_id=project_id,
                        installation_id=installation_id, generation=binding.generation)
                conn.commit()
        except psycopg.errors.UndefinedTable:
            # A read-only audit process must describe an environment that has
            # not received the runtime migration without attempting DDL.
            runtime_storage_available = False
            binding_row = None
            operation = None

        binding = self._binding_from_row(binding_row)
        installation_state = str(getattr(installation.state, "value", installation.state))
        installation_revision = int(installation.current_revision)
        installation_etag = int(installation.etag_version)
        effective_state, actions, reasons = _derive_control_state(
            installation_state=installation_state,
            installation_revision=installation_revision,
            binding=binding,
            operation=operation,
            runtime_storage_available=runtime_storage_available,
        )
        if effective_state == "ready" and not resources_live:
            effective_state, actions, reasons = "needs_attention", ("disable",), (
                "运行资源已释放、租约已过期或存活证据不足；请先禁入并完成恢复对账。",
            )
        ui = None
        if effective_state == "ready" and binding is not None:
            if self._ui_session_resolver is None:
                reasons = (*reasons, "前端扩展资源会话尚未建立；运行实例可用，扩展页面保持关闭。")
            else:
                try:
                    ui = self._ui_session_resolver(
                        installation=installation,
                        org_id=org_id,
                        project_id=project_id,
                        installation_id=installation_id,
                        installation_revision=installation_revision,
                        generation=binding.generation,
                        execution_epoch=binding.executionEpoch,
                        roles=roles,
                        markings=markings,
                        **({'requested_route': requested_route} if requested_route is not None else {}),
                    )
                except Exception:
                    reasons = (*reasons, "前端扩展资源会话校验失败；扩展页面保持关闭。")
                if ui is None and not reasons:
                    reasons = ("当前安装没有可加载的前端扩展资源。",)
        return RuntimeInstallationView(
            installationId=installation_id,
            installationRevision=installation_revision,
            installationEtag=installation_etag,
            installationState=installation_state,
            effectiveState=effective_state,
            binding=binding,
            currentOperation=operation,
            ui=ui,
            allowedActions=actions,
            reasons=reasons,
        )

    def list_configurations(self, *, installation_id, org_id, project_id, roles, markings):
        from aos_api.asset_registry.control_policy import APPLY_INSTALLATION_OPERATION, require_control_role
        from .configuration_catalog import read_catalog
        require_control_role(roles=roles, operation=APPLY_INSTALLATION_OPERATION)
        view=self.get_installation(installation_id=installation_id,org_id=org_id,
            project_id=project_id,roles=roles,markings=markings)
        with self._connect_factory() as conn:
            apply_asset_transaction_scope(conn,org_id=org_id,project_id=project_id)
            result=read_catalog(conn,org_id=org_id,project_id=project_id,view=view)
            conn.commit()
        return result

    def list_configuration_sources(self, *, installation_id, org_id, project_id, roles, markings):
        from aos_api.asset_registry.control_policy import APPLY_INSTALLATION_OPERATION, require_control_role
        from .configuration_source_catalog import read_source_catalog
        require_control_role(roles=roles, operation=APPLY_INSTALLATION_OPERATION)
        view=self.get_installation(installation_id=installation_id,org_id=org_id,
            project_id=project_id,roles=roles,markings=markings)
        with self._connect_factory() as conn:
            apply_asset_transaction_scope(conn,org_id=org_id,project_id=project_id)
            result=read_source_catalog(conn,org_id=org_id,project_id=project_id,view=view)
            conn.commit()
        return result

    def get_operation(
        self,
        *,
        operation_id: str,
        org_id: str,
        project_id: str,
        roles: list[str],
        markings: list[str],
    ) -> RuntimeOperationView:
        operation_id = str(UUID(str(operation_id)))
        with self._connect_factory() as conn:
            apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
            row = conn.execute(
                """
                SELECT operation_id, installation_id, kind, phase, status, revision,
                       requested_by, approved_by, expected_installation_etag,
                       expected_binding_revision, deadline, failure_code, created_at
                  FROM extension_runtime_operation
                 WHERE org_id=%s AND project_id=%s AND operation_id=%s
                """,
                (org_id, project_id, UUID(operation_id)),
            ).fetchone()
            if row is None:
                raise LookupError("runtime operation not found")
            installation_id = str(_values(row, (
                "operation_id", "installation_id", "kind", "phase", "status", "revision",
                "requested_by", "approved_by", "expected_installation_etag",
                "expected_binding_revision", "deadline", "failure_code", "created_at",
            ))[1])
            self._installation_reader.get(
                installation_id=installation_id,
                org_id=org_id,
                project_id=project_id,
                roles=roles,
                markings=markings,
            )
            operation = self._operation_from_row(conn, org_id, project_id, row)
            conn.commit()
        assert operation is not None
        return operation

    @staticmethod
    def _binding_from_row(row: Any) -> RuntimeBindingView | None:
        if row is None:
            return None
        names = (
            "generation", "installation_revision", "profile_ref", "config_ref",
            "execution_epoch", "desired_state", "observed_state", "enabled",
            "operation_fence", "revision",
        )
        values = _values(row, names)
        return RuntimeBindingView(
            generation=str(values[0]),
            installationRevision=values[1],
            profileRef=values[2],
            configRef=values[3],
            executionEpoch=values[4],
            desiredState=values[5],
            observedState=values[6],
            enabled=values[7],
            operationFence=values[8],
            revision=values[9],
        )

    @staticmethod
    def _operation_from_row(conn: Any, org_id: str, project_id: str, row: Any) -> RuntimeOperationView | None:
        if row is None:
            return None
        names = (
            "operation_id", "installation_id", "kind", "phase", "status", "revision",
            "requested_by", "approved_by", "expected_installation_etag",
            "expected_binding_revision", "deadline", "failure_code", "created_at",
        )
        values = _values(row, names)
        event_rows = conn.execute(
            """
            SELECT sequence, type, payload_hash, occurred_at
              FROM extension_runtime_event
             WHERE org_id=%s AND project_id=%s AND operation_id=%s
             ORDER BY sequence
            """,
            (org_id, project_id, values[0]),
        ).fetchall()
        events = tuple(
            RuntimeOperationEventView(
                sequence=event[0], type=event[1], payloadHash=event[2], occurredAt=_iso(event[3])
            )
            for event in (_values(item, ("sequence", "type", "payload_hash", "occurred_at")) for item in event_rows)
        )
        return RuntimeOperationView(
            operationId=str(values[0]), installationId=str(values[1]), kind=values[2],
            phase=values[3], status=values[4], revision=values[5], requestedBy=values[6],
            approvedBy=values[7], expectedInstallationEtag=values[8],
            expectedBindingRevision=values[9], deadline=_iso(values[10]),
            failureCode=values[11], createdAt=_iso(values[12]), events=events,
        )


def _derive_control_state(
    *,
    installation_state: str,
    installation_revision: int,
    binding: RuntimeBindingView | None,
    operation: RuntimeOperationView | None,
    runtime_storage_available: bool = True,
) -> tuple[str, tuple[RuntimeAction, ...], tuple[str, ...]]:
    if not runtime_storage_available:
        return "runtime_storage_unavailable", (), (
            "当前环境尚未安装运行存储；安装事实可读，运行操作保持关闭。",
        )
    if operation is not None and operation.status not in {"succeeded", "failed", "cancelled"}:
        return "operation_in_progress", (), ("运行操作正在处理中，请刷新查看最新进度。",)
    if binding is None:
        if installation_state == "approved":
            return "not_prepared", ("runtime-apply",), ("运行资源尚未准备。",)
        if installation_state == "applied":
            return "awaiting_verification", ("runtime-verify",), ("运行资源已准备，等待验证。",)
        return "not_available", (), ("当前安装状态尚不能进入运行生命周期。",)
    if binding.installationRevision != installation_revision:
        return "stale_binding", (), ("运行绑定与当前安装修订不一致，需要重新对账。",)
    if binding.desiredState == "uninstalled":
        return "uninstalled", (), ("运行实例已卸载，历史记录仍可读取。",)
    if binding.enabled and binding.observedState == "ready" and not binding.operationFence:
        return "ready", ("disable",), ()
    if (
        not binding.enabled
        and binding.desiredState == "disabled"
        and binding.observedState == "ready"
        and binding.operationFence
        and binding.configRef is None
        and operation is not None
        and operation.status == "succeeded"
        and operation.kind == "runtime-verify"
    ):
        return "configuration_required", ("configure",), (
            "运行资源已完成验证，需要选择已批准配置。",
        )
    if (
        not binding.enabled
        and binding.desiredState == "disabled"
        and binding.observedState == "unknown"
        and binding.operationFence
        and binding.configRef is not None
        and operation is not None
        and operation.status == "succeeded"
        and operation.kind in {"configure", "disable"}
    ):
        return "disabled", ("configure", "enable"), (
            "运行实例已完成配置或停用，可调整配置后重新启用。",
        )
    if binding.operationFence or binding.observedState == "draining":
        return "fenced", (), ("运行实例正在禁入或排空，请刷新查看进度。",)
    if binding.observedState == "ready" and not binding.enabled:
        if binding.configRef is None:
            return "configuration_required", ("configure",), ("运行实例已验证，需要选择已批准配置。",)
        return "disabled", ("configure", "enable"), ("运行实例当前停用。",)
    return "needs_attention", (), ("运行状态需要对账后才能继续操作。",)
