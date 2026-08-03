"""Transport-neutral M2-B CompositionService tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    CurrentInstallationRef,
    StoredCompositionLock,
)
from aos_api.asset_registry.composition_service import CompositionService
from aos_api.asset_registry.control_protocols import ActiveInstallationBaseline
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    CurrentInstallationStaleError,
    LockIntegrityCorruptError,
    MarkingAccessDeniedError,
)
from aos_api.asset_registry.installation_store import CommandReceipt
from tests.asset_registry.test_composition_store import _inputs


def _stored(payload: CompositionLockPayload) -> StoredCompositionLock:
    return StoredCompositionLock.model_validate(
        {
            "compositionId": "11111111-1111-4111-8111-111111111111",
            "revision": 1,
            "payload": payload,
            "lockHash": canonical_sha256(payload.hash_payload_dump()),
            "permissionDiffHash": canonical_sha256(
                payload.permission_diff.model_dump(
                    mode="json", by_alias=True, exclude_none=False
                )
            ),
            "migrationPlanHash": canonical_sha256(
                payload.migration_plan.model_dump(
                    mode="json", by_alias=True, exclude_none=False
                )
            ),
            "contributionDiffHash": canonical_sha256(
                payload.contribution_diff.model_dump(
                    mode="json", by_alias=True, exclude_none=False
                )
            ),
            "createdAt": datetime.now(UTC),
        }
    )


def _receipt(
    stored: StoredCompositionLock, *, replayed: bool = False
) -> CommandReceipt:
    return CommandReceipt(
        status_code=201,
        response_json=stored.model_dump(mode="json", by_alias=True, exclude_none=False),
        replayed=replayed,
    )


class _CommandStore:
    def __init__(self, *, replay: CommandReceipt | None = None) -> None:
        self.conn = object()
        self.replay = replay
        self.calls: list[dict] = []

    def execute_idempotent(self, **kwargs):
        self.calls.append(kwargs)
        if self.replay is not None:
            return self.replay
        result = kwargs["handler"](self.conn)
        return CommandReceipt(
            status_code=result.status_code,
            response_json=result.response_json,
            response_etag=result.response_etag,
        )


class _CompositionStore:
    def __init__(self, stored: StoredCompositionLock) -> None:
        self.stored = stored
        self.created: list[dict] = []
        self.gets: list[dict] = []

    def create_or_get_in_transaction(self, conn, **kwargs):
        self.created.append({"conn": conn, **kwargs})
        return self.stored

    def get_lock(self, **kwargs):
        self.gets.append(kwargs)
        return self.stored


class _SnapshotReader:
    def __init__(self, snapshot) -> None:
        self.snapshot = snapshot
        self.calls = 0

    def read(self):
        self.calls += 1
        return self.snapshot


class _BaselineReader:
    def __init__(self, baseline: ActiveInstallationBaseline | None = None) -> None:
        self.baseline = baseline
        self.calls: list[dict] = []

    def load_active_baseline_in_transaction(self, conn, **kwargs):
        self.calls.append({"conn": conn, **kwargs})
        assert self.baseline is not None
        return self.baseline


def _service(*, replay: CommandReceipt | None = None, payload=None):
    request, snapshot, default_payload = _inputs()
    resolved = payload or default_payload
    stored = _stored(resolved)
    command_store = _CommandStore(replay=replay)
    composition_store = _CompositionStore(stored)
    snapshot_reader = _SnapshotReader(snapshot)
    baseline_reader = _BaselineReader()
    resolver_calls: list[tuple] = []

    def resolver(*args):
        resolver_calls.append(args)
        return resolved

    service = CompositionService(
        snapshot_reader=snapshot_reader,
        composition_store=composition_store,
        command_store=command_store,
        baseline_reader=baseline_reader,
        resolver=resolver,
    )
    return SimpleNamespace(
        service=service,
        request=request,
        snapshot=snapshot,
        payload=resolved,
        stored=stored,
        command_store=command_store,
        composition_store=composition_store,
        snapshot_reader=snapshot_reader,
        baseline_reader=baseline_reader,
        resolver_calls=resolver_calls,
    )


def test_resolve_writes_lock_and_receipt_in_the_same_handler_connection() -> None:
    ctx = _service()

    receipt = ctx.service.resolve(
        request=ctx.request,
        org_id="org-a",
        project_id="project-a",
        actor="developer-a",
        roles=["developer"],
        markings=[],
        idempotency_key="resolve-1",
    )

    assert receipt.status_code == 201
    assert receipt.response_etag is None
    assert ctx.snapshot_reader.calls == 1
    assert ctx.resolver_calls == [(ctx.request, ctx.snapshot, None)]
    assert ctx.composition_store.created[0]["conn"] is ctx.command_store.conn
    call = ctx.command_store.calls[0]
    assert call["operation"] == "bundle_compositions.resolve"
    assert call["subject"] == "developer-a"
    assert call["request_hash"].startswith("sha256:")


def test_resolve_replay_uses_receipt_without_snapshot_or_persistence() -> None:
    initial = _service()
    ctx = _service(replay=_receipt(initial.stored, replayed=True))

    receipt = ctx.service.resolve(
        request=ctx.request,
        org_id="org-a",
        project_id="project-a",
        actor="developer-a",
        roles=["developer"],
        markings=[],
        idempotency_key="resolve-1",
    )

    assert receipt.replayed is True
    assert ctx.snapshot_reader.calls == 0
    assert ctx.composition_store.created == []
    assert ctx.resolver_calls == []


def test_resolve_uses_server_active_baseline_and_rejects_environment_drift() -> None:
    request, _snapshot, payload = _inputs()
    current_ref = CurrentInstallationRef.model_validate(
        {
            "installationId": "22222222-2222-4222-8222-222222222222",
            "revision": 3,
            "lockHash": payload.registry_snapshot_hash,
            "overlayRevision": "overlay-3",
        }
    )
    request_data = request.model_dump(mode="python", by_alias=True, exclude_none=False)
    request_data["currentInstallationRef"] = current_ref.model_dump(
        mode="python", by_alias=True, exclude_none=False
    )
    request_with_ref = request.model_validate(request_data)
    baseline = ActiveInstallationBaseline(
        server_ref=current_ref,
        lock=_stored(payload),
    )
    ctx = _service()
    ctx.baseline_reader.baseline = baseline

    ctx.service.resolve(
        request=request_with_ref,
        org_id="org-a",
        project_id="project-a",
        actor="developer-a",
        roles=["developer"],
        markings=[],
        idempotency_key="resolve-baseline",
    )
    assert ctx.baseline_reader.calls[0]["conn"] is ctx.command_store.conn

    drifted_payload = payload.model_dump(
        mode="python", by_alias=True, exclude_none=False
    )
    drifted_payload["request"]["environment"] = "prod"
    ctx.baseline_reader.baseline = ActiveInstallationBaseline(
        server_ref=current_ref,
        lock=_stored(CompositionLockPayload.model_validate(drifted_payload)),
    )
    with pytest.raises(CurrentInstallationStaleError):
        ctx.service.resolve(
            request=request_with_ref,
            org_id="org-a",
            project_id="project-a",
            actor="developer-a",
            roles=["developer"],
            markings=[],
            idempotency_key="resolve-drift",
        )


def test_get_lock_conceals_missing_marking() -> None:
    ctx = _service()
    changed = ctx.payload.model_dump(mode="python", by_alias=True, exclude_none=False)
    changed["permissionDiff"]["target"]["markings"] = ["secret"]
    changed["permissionDiff"]["added"]["markings"] = ["secret"]
    marked = CompositionLockPayload.model_validate(changed)
    ctx = _service(payload=marked)

    with pytest.raises(AssetNotFoundError):
        ctx.service.get_lock(
            org_id="org-a",
            project_id="project-a",
            composition_id=ctx.stored.composition_id,
            revision=1,
            roles=["developer"],
            markings=[],
        )

    assert (
        ctx.service.get_lock(
            org_id="org-a",
            project_id="project-a",
            composition_id=ctx.stored.composition_id,
            revision=1,
            roles=["developer"],
            markings=["secret"],
        )
        == ctx.stored
    )


def test_resolve_replay_rechecks_marking_and_receipt_integrity() -> None:
    base = _service()
    changed = base.payload.model_dump(mode="python", by_alias=True, exclude_none=False)
    changed["permissionDiff"]["target"]["markings"] = ["secret"]
    changed["permissionDiff"]["added"]["markings"] = ["secret"]
    marked = CompositionLockPayload.model_validate(changed)
    marked_stored = _stored(marked)
    ctx = _service(payload=marked, replay=_receipt(marked_stored, replayed=True))

    with pytest.raises(MarkingAccessDeniedError):
        ctx.service.resolve(
            request=ctx.request,
            org_id="org-a",
            project_id="project-a",
            actor="developer-a",
            roles=["developer"],
            markings=[],
            idempotency_key="resolve-replay",
        )

    bad = CommandReceipt(status_code=200, response_json={})
    ctx = _service(replay=bad)
    with pytest.raises(LockIntegrityCorruptError):
        ctx.service.resolve(
            request=ctx.request,
            org_id="org-a",
            project_id="project-a",
            actor="developer-a",
            roles=["developer"],
            markings=[],
            idempotency_key="resolve-corrupt",
        )
