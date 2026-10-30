from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from aos_api.aip_route_worker_customer_lifecycle import (
    RouteWorkerCustomerLifecycleBlocked,
    RouteWorkerCustomerLifecycleService,
)
from aos_api.aip_route_worker_installation import RouteWorkerInstallationBlocked
from aos_api.asset_registry.errors import DutySeparationRequiredError
from aos_api.asset_registry.installation_store import CommandReceipt
from tests.aip.test_aip_route_worker_installation import document


class ReceiptStore:
    def __init__(self) -> None:
        self.rows = {}
        self.calls = []
        self.fail_completion_once = False

    def execute_idempotent(self, **kwargs):
        key = (
            kwargs["org_id"],
            kwargs["project_id"],
            kwargs["operation"],
            kwargs["idempotency_key"],
        )
        self.calls.append(key)
        existing = self.rows.get(key)
        if existing is not None:
            subject, request_hash, result = existing
            if subject != kwargs["subject"] or request_hash != kwargs["request_hash"]:
                raise ValueError("idempotency conflict")
            return CommandReceipt(
                status_code=result.status_code,
                response_json=result.response_json,
                response_etag=result.response_etag,
                replayed=True,
            )
        if self.fail_completion_once and kwargs["operation"].endswith(".complete"):
            self.fail_completion_once = False
            raise RuntimeError("injected completion persistence failure")
        result = kwargs["handler"](None)
        self.rows[key] = (kwargs["subject"], kwargs["request_hash"], result)
        return CommandReceipt(
            status_code=result.status_code,
            response_json=result.response_json,
            response_etag=result.response_etag,
            replayed=False,
        )


class State:
    def __init__(self, current=None) -> None:
        self.current = current

    def read(self):
        return self.current


class Coordinator:
    def __init__(self, state: State) -> None:
        self.state = state
        self.installs = []
        self.uninstalls = []

    def install(self, path, target, *, expected_current_hash=None):
        current_hash = (
            None if self.state.current is None else self.state.current.content_hash()
        )
        if current_hash != expected_current_hash:
            raise RouteWorkerInstallationBlocked("injected install CAS drift")
        self.installs.append((Path(path), target, expected_current_hash))
        self.state.current = target
        return target.content_hash()

    def uninstall(self, path, *, expected_current_hash):
        if (
            self.state.current is None
            or self.state.current.content_hash() != expected_current_hash
        ):
            raise RouteWorkerInstallationBlocked("injected uninstall CAS drift")
        self.uninstalls.append((Path(path), expected_current_hash))
        removed = self.state.current
        self.state.current = None
        return removed


class Authority:
    def __init__(self) -> None:
        self.calls = []

    def assert_current(self, target):
        self.calls.append(target)
        return True


def service(*, state=None, receipts=None):
    state = state or State()
    receipts = receipts or ReceiptStore()
    coordinator = Coordinator(state)
    authority = Authority()
    sequence = iter(
        [
            UUID("00000000-0000-0000-0000-000000000201"),
            UUID("00000000-0000-0000-0000-000000000202"),
            UUID("00000000-0000-0000-0000-000000000203"),
        ]
    )
    lifecycle = RouteWorkerCustomerLifecycleService(
        receipt_store=receipts,
        coordinator=coordinator,
        authority=authority,
        current_reader=state.read,
        document_factory=document,
        config_path=Path("/private/var/db/aos/route-worker.json"),
        clock=lambda: datetime(2026, 10, 30, 13, 20, tzinfo=UTC),
        uuid_factory=lambda: next(sequence),
    )
    return lifecycle, state, receipts, coordinator, authority


def invoke(lifecycle, action, *, key="customer-command-1", roles=("asset-installer",)):
    return getattr(lifecycle, action)(
        org_id="org-org",
        project_id="dev-project",
        actor="operator-1",
        roles=roles,
        idempotency_key=key,
    )


def test_enable_returns_business_only_receipt_and_replay_does_not_rewrite():
    lifecycle, state, receipts, coordinator, authority = service()

    first = invoke(lifecycle, "enable")
    second = invoke(lifecycle, "enable")

    assert first == second
    assert first.title == "后台处理配置已就绪"
    assert first.state == "configuration_ready"
    assert first.can_process_business_tasks is False
    assert state.current == document()
    assert len(coordinator.installs) == 1
    assert authority.calls[-1] == document()
    wire = first.model_dump(mode="json", by_alias=True)
    rendered = str(wire)
    for forbidden in (
        "installationId",
        "revision",
        "etag",
        "lockHash",
        "bundleId",
        "signature",
        "secretVersion",
        "token",
    ):
        assert forbidden not in rendered
    assert len(receipts.rows) == 2


def test_completion_unknown_is_reconciled_without_repeating_file_effect():
    receipts = ReceiptStore()
    receipts.fail_completion_once = True
    lifecycle, state, _, coordinator, _ = service(receipts=receipts)

    with pytest.raises(RuntimeError, match="completion persistence failure"):
        invoke(lifecycle, "enable")
    assert state.current == document()
    assert len(coordinator.installs) == 1

    recovered = invoke(lifecycle, "enable")
    assert recovered.state == "configuration_ready"
    assert len(coordinator.installs) == 1


def test_disable_and_restore_are_business_operations_with_separate_receipts():
    lifecycle, state, _, coordinator, _ = service(state=State(document()))

    disabled = invoke(lifecycle, "disable", key="disable-1")
    restored = invoke(lifecycle, "restore", key="restore-1")

    assert disabled.title == "后台处理已停用"
    assert disabled.state == "disabled"
    assert restored.title == "后台处理配置已恢复"
    assert restored.state == "configuration_ready"
    assert len(coordinator.uninstalls) == 1
    assert len(coordinator.installs) == 1
    assert state.current == document()


def test_prepare_drift_never_overwrites_unexpected_file():
    original = document(secretVersion="v1")
    drifted = document(secretVersion="v3")
    state = State(original)
    receipts = ReceiptStore()
    lifecycle, _, _, coordinator, _ = service(state=state, receipts=receipts)

    original_execute = receipts.execute_idempotent

    def drift_after_prepare(**kwargs):
        receipt = original_execute(**kwargs)
        if kwargs["operation"].endswith(".prepare") and not receipt.replayed:
            state.current = drifted
        return receipt

    receipts.execute_idempotent = drift_after_prepare
    with pytest.raises(
        RouteWorkerCustomerLifecycleBlocked,
        match="CURRENT_CONFIGURATION_CHANGED",
    ):
        invoke(lifecycle, "enable")
    assert state.current == drifted
    assert coordinator.installs == []


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("receiptId", "not-a-uuid"),
        ("expectedCurrentHash", "sha256:not-a-canonical-hash"),
    ],
)
def test_invalid_prepare_receipt_is_rejected_before_file_effect(field, invalid):
    state = State(document())
    receipts = ReceiptStore()
    lifecycle, _, _, coordinator, _ = service(state=state, receipts=receipts)
    original_execute = receipts.execute_idempotent

    def corrupt_prepare(**kwargs):
        receipt = original_execute(**kwargs)
        if kwargs["operation"].endswith(".prepare"):
            response = dict(receipt.response_json)
            response[field] = invalid
            return CommandReceipt(
                status_code=receipt.status_code,
                response_json=response,
                response_etag=receipt.response_etag,
                replayed=receipt.replayed,
            )
        return receipt

    receipts.execute_idempotent = corrupt_prepare
    with pytest.raises(
        RouteWorkerCustomerLifecycleBlocked,
        match="PREPARE_RECEIPT_INVALID",
    ):
        invoke(lifecycle, "enable")
    assert state.current == document()
    assert coordinator.installs == []


def test_same_business_key_cannot_change_action():
    lifecycle, _, _, _, _ = service(state=State(document()))
    invoke(lifecycle, "disable", key="same-key")
    with pytest.raises(ValueError, match="idempotency conflict"):
        invoke(lifecycle, "restore", key="same-key")


def test_cross_tenant_and_unqualified_role_fail_before_receipt_or_file():
    lifecycle, _, receipts, coordinator, _ = service()
    with pytest.raises(
        RouteWorkerCustomerLifecycleBlocked,
        match="POSITIVE_SCOPE_REQUIRED",
    ):
        lifecycle.enable(
            org_id="dev-org",
            project_id="dev-project",
            actor="operator-1",
            roles=("asset-installer",),
            idempotency_key="cross-tenant",
        )
    with pytest.raises(DutySeparationRequiredError):
        invoke(lifecycle, "enable", roles=("viewer",))
    assert receipts.rows == {}
    assert coordinator.installs == []
