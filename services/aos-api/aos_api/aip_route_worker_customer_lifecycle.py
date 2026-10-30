"""Business-semantic install, disable, and restore receipts for Route workers."""

from __future__ import annotations

from collections.abc import Callable, Collection
from datetime import UTC, datetime
from pathlib import Path
from re import fullmatch
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.aip_route_worker_installation import RouteWorkerIdentityInstallation
from aos_api.asset_registry.control_policy import (
    APPLY_INSTALLATION_OPERATION,
    UNINSTALL_INSTALLATION_OPERATION,
    require_control_role,
    validate_idempotency_key,
)
from aos_api.asset_registry.installation_store import (
    CommandReceipt,
    CommandResult,
    command_request_hash,
)

_EXPECTED_SCOPE = ("org-org", "dev-project")
_PREPARE_OPERATION = "route_worker_identity.customer_lifecycle.prepare"
_COMPLETE_OPERATION = "route_worker_identity.customer_lifecycle.complete"
_Action = Literal["enable", "disable", "restore"]


class RouteWorkerConfigurationCheck(BaseModel):
    """One customer-readable prerequisite without internal coordinates."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        hide_input_in_errors=True,
    )
    key: Literal[
        "current_customer_installation",
        "background_identity",
        "protected_storage",
        "identity_credential",
        "configuration_submission",
    ]
    label: str = Field(min_length=1, max_length=80)
    passed: bool
    detail: str = Field(min_length=1, max_length=240)


class RouteWorkerConfigurationSideEffects(BaseModel):
    """A preview is read-only and cannot authorize runtime effects."""

    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", populate_by_name=True
    )
    database_write: Literal[False] = Field(alias="databaseWrite")
    configuration_write: Literal[False] = Field(alias="configurationWrite")
    token_request: Literal[False] = Field(alias="tokenRequest")
    business_processing: Literal[False] = Field(alias="businessProcessing")
    external_effect: Literal[False] = Field(alias="externalEffect")


class RouteWorkerConfigurationPreview(BaseModel):
    """Read-only approval material for saving the protected configuration."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        hide_input_in_errors=True,
    )
    schema_version: Literal["aos.route-worker-configuration-preview/v1"] = Field(
        alias="schemaVersion"
    )
    status: Literal["reviewable", "needs_input"]
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=240)
    approval_allowed: bool = Field(alias="approvalAllowed")
    checks: tuple[RouteWorkerConfigurationCheck, ...] = Field(
        min_length=5, max_length=5
    )
    next_actions: tuple[str, ...] = Field(
        alias="nextActions", min_length=1, max_length=5
    )
    side_effects: RouteWorkerConfigurationSideEffects = Field(alias="sideEffects")
    can_process_business_tasks: Literal[False] = Field(
        alias="canProcessBusinessTasks"
    )
    evaluated_at: datetime = Field(alias="evaluatedAt")

    @field_validator("evaluated_at")
    @classmethod
    def aware_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("aware preview time required")
        return value

    @model_validator(mode="after")
    def coherent_preview(self) -> RouteWorkerConfigurationPreview:
        expected_keys = (
            "current_customer_installation",
            "background_identity",
            "protected_storage",
            "identity_credential",
            "configuration_submission",
        )
        if tuple(item.key for item in self.checks) != expected_keys:
            raise ValueError("configuration preview checks are incoherent")
        ready = all(item.passed for item in self.checks)
        expected_title = (
            "后台处理配置可以确认" if ready else "后台处理配置条件未齐"
        )
        if (
            self.approval_allowed is not ready
            or self.status != ("reviewable" if ready else "needs_input")
            or self.title != expected_title
        ):
            raise ValueError("configuration preview state is incoherent")
        return self


class RouteWorkerCustomerStatus(BaseModel):
    """Current customer-facing state without installation coordinates."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        hide_input_in_errors=True,
    )
    schema_version: Literal["aos.route-worker-customer-status/v1"] = Field(
        alias="schemaVersion"
    )
    state: Literal["unconfigured", "configuration_ready", "disabled", "needs_review"]
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=240)
    can_process_business_tasks: Literal[False] = Field(alias="canProcessBusinessTasks")
    checked_at: datetime = Field(alias="checkedAt")

    @field_validator("checked_at")
    @classmethod
    def aware_checked_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("aware check time required")
        return value

    @model_validator(mode="after")
    def coherent_business_state(self) -> RouteWorkerCustomerStatus:
        expected = {
            "unconfigured": "后台处理尚未配置",
            "configuration_ready": "后台处理配置已就绪",
            "disabled": "后台处理已停用",
            "needs_review": "后台处理状态待核对",
        }[self.state]
        if self.title != expected:
            raise ValueError("business lifecycle status is incoherent")
        return self


class RouteWorkerCustomerTenant(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", populate_by_name=True
    )
    org_id: Literal["org-org"] = Field(alias="orgId")
    project_id: Literal["dev-project"] = Field(alias="projectId")


class RouteWorkerCustomerStatusEnvelope(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", populate_by_name=True
    )
    tenant: RouteWorkerCustomerTenant
    status: RouteWorkerCustomerStatus


class RouteWorkerConfigurationPreviewEnvelope(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", populate_by_name=True
    )
    tenant: RouteWorkerCustomerTenant
    preview: RouteWorkerConfigurationPreview


class RouteWorkerCustomerLifecycleBlocked(RuntimeError):
    """Stable business lifecycle failure without internal installation details."""


class RouteWorkerCustomerReceipt(BaseModel):
    """Public result: business state only, never installation internals."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        hide_input_in_errors=True,
    )
    schema_version: Literal["aos.route-worker-customer-receipt/v1"] = Field(
        alias="schemaVersion"
    )
    receipt_id: str = Field(alias="receiptId")
    action: _Action
    state: Literal["configuration_ready", "disabled"]
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=240)
    can_process_business_tasks: Literal[False] = Field(alias="canProcessBusinessTasks")
    completed_at: datetime = Field(alias="completedAt")

    @field_validator("receipt_id")
    @classmethod
    def canonical_receipt_id(cls, value: str) -> str:
        try:
            if str(UUID(value)) != value:
                raise ValueError
        except (TypeError, ValueError, AttributeError):
            raise ValueError("canonical receipt id required") from None
        return value

    @field_validator("completed_at", mode="before")
    @classmethod
    def aware_completion_time(cls, value) -> datetime:
        if type(value) is str:
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("aware completion time required") from None
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError("aware completion time required")
        return value

    @model_validator(mode="after")
    def coherent_business_result(self) -> RouteWorkerCustomerReceipt:
        expected = {
            "enable": ("configuration_ready", "后台处理配置已就绪"),
            "disable": ("disabled", "后台处理已停用"),
            "restore": ("configuration_ready", "后台处理配置已恢复"),
        }[self.action]
        if (self.state, self.title) != expected:
            raise ValueError("business lifecycle result is incoherent")
        return self


class RouteWorkerCustomerReceiptEnvelope(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", populate_by_name=True
    )
    tenant: RouteWorkerCustomerTenant
    result: RouteWorkerCustomerReceipt


class _PreparedLifecycleReceipt(BaseModel):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        hide_input_in_errors=True,
    )
    schema_version: Literal["aos.route-worker-customer-prepare/v1"] = Field(
        alias="schemaVersion"
    )
    receipt_id: str = Field(alias="receiptId")
    action: _Action
    expected_current_hash: str | None = Field(alias="expectedCurrentHash")
    target_document: dict[str, Any] | None = Field(alias="targetDocument")

    @field_validator("receipt_id")
    @classmethod
    def canonical_receipt_id(cls, value: str) -> str:
        try:
            if str(UUID(value)) != value:
                raise ValueError
        except (TypeError, ValueError, AttributeError):
            raise ValueError("canonical receipt id required") from None
        return value

    @field_validator("expected_current_hash")
    @classmethod
    def canonical_expected_hash(cls, value: str | None) -> str | None:
        if value is not None and fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
            raise ValueError("canonical expected hash required")
        return value

    @model_validator(mode="after")
    def coherent_target(self) -> _PreparedLifecycleReceipt:
        if (self.action == "disable") != (self.target_document is None):
            raise ValueError("prepared lifecycle target is incoherent")
        return self


class _ReceiptStore(Protocol):
    def execute_idempotent(self, **kwargs) -> CommandReceipt: ...


class _Coordinator(Protocol):
    def install(
        self,
        path: str | Path,
        document: RouteWorkerIdentityInstallation,
        *,
        expected_current_hash: str | None = None,
    ) -> str: ...

    def uninstall(
        self, path: str | Path, *, expected_current_hash: str
    ) -> RouteWorkerIdentityInstallation: ...


class _Authority(Protocol):
    def assert_current(self, document: RouteWorkerIdentityInstallation) -> bool: ...


class RouteWorkerCustomerLifecycleService:
    """Persist intent, reconcile exact file state, then persist business result."""

    def __init__(
        self,
        *,
        receipt_store: _ReceiptStore,
        coordinator: _Coordinator,
        authority: _Authority,
        current_reader: Callable[[], RouteWorkerIdentityInstallation | None],
        document_factory: Callable[[], RouteWorkerIdentityInstallation],
        config_path: Path,
        latest_completion_reader: Callable[[], dict[str, Any] | None] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        uuid_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        if (
            not callable(getattr(receipt_store, "execute_idempotent", None))
            or not callable(getattr(coordinator, "install", None))
            or not callable(getattr(coordinator, "uninstall", None))
            or not callable(getattr(authority, "assert_current", None))
            or not callable(current_reader)
            or not callable(document_factory)
            or not callable(clock)
            or not callable(uuid_factory)
            or (
                latest_completion_reader is not None
                and not callable(latest_completion_reader)
            )
            or not isinstance(config_path, Path)
            or not config_path.is_absolute()
        ):
            raise ValueError("complete route worker lifecycle dependencies required")
        self._receipt_store = receipt_store
        self._coordinator = coordinator
        self._authority = authority
        self._current_reader = current_reader
        self._document_factory = document_factory
        self._config_path = config_path
        self._latest_completion_reader = latest_completion_reader
        self._clock = clock
        self._uuid_factory = uuid_factory

    def enable(self, **kwargs) -> RouteWorkerCustomerReceipt:
        return self._change(action="enable", **kwargs)

    def disable(self, **kwargs) -> RouteWorkerCustomerReceipt:
        return self._change(action="disable", **kwargs)

    def restore(self, **kwargs) -> RouteWorkerCustomerReceipt:
        return self._change(action="restore", **kwargs)

    def read_status(self) -> RouteWorkerCustomerStatus:
        now = self._clock()
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise RouteWorkerCustomerLifecycleBlocked(
                "ROUTE_WORKER_STATUS_TIME_INVALID"
            )
        try:
            current = self._current_reader()
            if current is not None:
                if type(current) is not RouteWorkerIdentityInstallation:
                    raise ValueError
                self._authority.assert_current(current)
                state = "configuration_ready"
            else:
                latest = (
                    None
                    if self._latest_completion_reader is None
                    else self._latest_completion_reader()
                )
                if latest is None:
                    state = "unconfigured"
                else:
                    receipt = RouteWorkerCustomerReceipt.model_validate(latest)
                    state = (
                        "disabled" if receipt.action == "disable" else "needs_review"
                    )
        except Exception:
            state = "needs_review"
        title, summary = {
            "unconfigured": (
                "后台处理尚未配置",
                "当前不会自动处理业务；可在条件齐备后配置后台处理。",
            ),
            "configuration_ready": (
                "后台处理配置已就绪",
                "配置已经就绪，但运行开关仍保持关闭。",
            ),
            "disabled": (
                "后台处理已停用",
                "当前不会自动处理业务；已有密钥未被删除。",
            ),
            "needs_review": (
                "后台处理状态待核对",
                "当前不会自动处理业务；请重新读取或由管理员核对配置。",
            ),
        }[state]
        return RouteWorkerCustomerStatus(
            schemaVersion="aos.route-worker-customer-status/v1",
            state=state,
            title=title,
            summary=summary,
            canProcessBusinessTasks=False,
            checkedAt=now,
        )

    def _change(
        self,
        *,
        action: _Action,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        idempotency_key: str | None,
    ) -> RouteWorkerCustomerReceipt:
        if (org_id, project_id) != _EXPECTED_SCOPE:
            raise RouteWorkerCustomerLifecycleBlocked(
                "ROUTE_WORKER_POSITIVE_SCOPE_REQUIRED"
            )
        permission = (
            UNINSTALL_INSTALLATION_OPERATION
            if action == "disable"
            else APPLY_INSTALLATION_OPERATION
        )
        require_control_role(roles=roles, operation=permission)
        key = validate_idempotency_key(idempotency_key)
        request_hash = command_request_hash(
            subject=actor,
            path_params={},
            body={"action": action},
            if_match=None,
        )
        prepared = self._prepare(
            action=action,
            org_id=org_id,
            project_id=project_id,
            actor=actor,
            key=key,
            request_hash=request_hash,
        )
        self._apply_or_reconcile(prepared)
        return self._complete(
            prepared=prepared,
            org_id=org_id,
            project_id=project_id,
            actor=actor,
            key=key,
            request_hash=request_hash,
        )

    def _prepare(
        self,
        *,
        action: _Action,
        org_id: str,
        project_id: str,
        actor: str,
        key: str,
        request_hash: str,
    ) -> _PreparedLifecycleReceipt:
        def handler(_conn) -> CommandResult:
            current = self._current_reader()
            if (
                current is not None
                and type(current) is not RouteWorkerIdentityInstallation
            ):
                raise RouteWorkerCustomerLifecycleBlocked(
                    "ROUTE_WORKER_CURRENT_CONFIGURATION_INVALID"
                )
            target = None
            if action != "disable":
                target = self._document_factory()
                if type(target) is not RouteWorkerIdentityInstallation:
                    raise RouteWorkerCustomerLifecycleBlocked(
                        "ROUTE_WORKER_TARGET_CONFIGURATION_INVALID"
                    )
                self._authority.assert_current(target)
            prepared = _PreparedLifecycleReceipt(
                schemaVersion="aos.route-worker-customer-prepare/v1",
                receiptId=str(self._uuid_factory()),
                action=action,
                expectedCurrentHash=(
                    None if current is None else current.content_hash()
                ),
                targetDocument=None if target is None else target.wire(),
            )
            return CommandResult(
                status_code=202,
                response_json=prepared.model_dump(mode="json", by_alias=True),
            )

        receipt = self._receipt_store.execute_idempotent(
            org_id=org_id,
            project_id=project_id,
            operation=_PREPARE_OPERATION,
            idempotency_key=key,
            subject=actor,
            request_hash=request_hash,
            handler=handler,
        )
        try:
            return _PreparedLifecycleReceipt.model_validate(receipt.response_json)
        except Exception:
            raise RouteWorkerCustomerLifecycleBlocked(
                "ROUTE_WORKER_PREPARE_RECEIPT_INVALID"
            ) from None

    def _apply_or_reconcile(self, prepared: _PreparedLifecycleReceipt) -> None:
        current = self._current_reader()
        if current is not None and type(current) is not RouteWorkerIdentityInstallation:
            raise RouteWorkerCustomerLifecycleBlocked(
                "ROUTE_WORKER_CURRENT_CONFIGURATION_INVALID"
            )
        current_hash = None if current is None else current.content_hash()
        if prepared.action == "disable":
            if current is None:
                return
            if current_hash != prepared.expected_current_hash:
                raise RouteWorkerCustomerLifecycleBlocked(
                    "ROUTE_WORKER_CURRENT_CONFIGURATION_CHANGED"
                )
            self._coordinator.uninstall(
                self._config_path,
                expected_current_hash=prepared.expected_current_hash,
            )
            if self._current_reader() is not None:
                raise RouteWorkerCustomerLifecycleBlocked(
                    "ROUTE_WORKER_DISABLE_READBACK_FAILED"
                )
            return

        try:
            target = RouteWorkerIdentityInstallation.model_validate(
                prepared.target_document
            )
        except Exception:
            raise RouteWorkerCustomerLifecycleBlocked(
                "ROUTE_WORKER_PREPARE_RECEIPT_INVALID"
            ) from None
        target_hash = target.content_hash()
        if current_hash == target_hash:
            self._authority.assert_current(target)
        elif current_hash == prepared.expected_current_hash:
            self._coordinator.install(
                self._config_path,
                target,
                expected_current_hash=prepared.expected_current_hash,
            )
        else:
            raise RouteWorkerCustomerLifecycleBlocked(
                "ROUTE_WORKER_CURRENT_CONFIGURATION_CHANGED"
            )
        readback = self._current_reader()
        if readback != target:
            raise RouteWorkerCustomerLifecycleBlocked(
                "ROUTE_WORKER_CONFIGURATION_READBACK_FAILED"
            )
        self._authority.assert_current(target)

    def _complete(
        self,
        *,
        prepared: _PreparedLifecycleReceipt,
        org_id: str,
        project_id: str,
        actor: str,
        key: str,
        request_hash: str,
    ) -> RouteWorkerCustomerReceipt:
        def handler(_conn) -> CommandResult:
            now = self._clock()
            if (
                not isinstance(now, datetime)
                or now.tzinfo is None
                or now.utcoffset() is None
            ):
                raise RouteWorkerCustomerLifecycleBlocked(
                    "ROUTE_WORKER_COMPLETION_TIME_INVALID"
                )
            state, title, summary = {
                "enable": (
                    "configuration_ready",
                    "后台处理配置已就绪",
                    "当前工作区的后台处理身份配置已经就绪；运行开关仍保持关闭。",
                ),
                "disable": (
                    "disabled",
                    "后台处理已停用",
                    "当前工作区已停止使用后台处理身份配置；已有密钥未被删除。",
                ),
                "restore": (
                    "configuration_ready",
                    "后台处理配置已恢复",
                    "当前工作区的后台处理身份配置已经恢复；运行开关仍保持关闭。",
                ),
            }[prepared.action]
            result = RouteWorkerCustomerReceipt(
                schemaVersion="aos.route-worker-customer-receipt/v1",
                receiptId=prepared.receipt_id,
                action=prepared.action,
                state=state,
                title=title,
                summary=summary,
                canProcessBusinessTasks=False,
                completedAt=now,
            )
            return CommandResult(
                status_code=200,
                response_json=result.model_dump(mode="json", by_alias=True),
            )

        receipt = self._receipt_store.execute_idempotent(
            org_id=org_id,
            project_id=project_id,
            operation=_COMPLETE_OPERATION,
            idempotency_key=key,
            subject=actor,
            request_hash=request_hash,
            handler=handler,
        )
        try:
            return RouteWorkerCustomerReceipt.model_validate(receipt.response_json)
        except Exception:
            raise RouteWorkerCustomerLifecycleBlocked(
                "ROUTE_WORKER_COMPLETE_RECEIPT_INVALID"
            ) from None
