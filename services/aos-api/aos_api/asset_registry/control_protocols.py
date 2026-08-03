"""Shared, transport-neutral Protocols for parallel M2-B implementation."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from aos_api.asset_registry.composition_contracts import (
        ApproveInstallationRequest,
        CompositionRequest,
        CreateInstallationRequest,
        CurrentInstallationRef,
        EmptyInstallationActionRequest,
        InstallationListQuery,
        InstallationListResponse,
        InstallationResponse,
        RejectInstallationRequest,
        RollbackInstallationRequest,
        StoredCompositionLock,
    )
    from aos_api.asset_registry.installation_store import (
        CommandReceipt,
        CommandResult,
    )


class IdempotentCommandHandler(Protocol):
    def __call__(self, conn: Any) -> CommandResult: ...


class IdempotentCommandStore(Protocol):
    def execute_idempotent(
        self,
        *,
        org_id: str,
        project_id: str,
        operation: str,
        idempotency_key: str,
        subject: str,
        request_hash: str,
        handler: IdempotentCommandHandler,
    ) -> CommandReceipt: ...


class CompositionControl(Protocol):
    def resolve(
        self,
        *,
        request: CompositionRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
    ) -> CommandReceipt: ...

    def get_lock(
        self,
        *,
        org_id: str,
        project_id: str,
        composition_id: str,
        revision: int,
        roles: Collection[str],
        markings: Collection[str],
    ) -> StoredCompositionLock: ...


@dataclass(frozen=True, slots=True)
class ActiveInstallationBaseline:
    server_ref: CurrentInstallationRef
    lock: StoredCompositionLock


class ActiveBaselineReader(Protocol):
    def load_active_baseline_in_transaction(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        requested_ref: CurrentInstallationRef,
    ) -> ActiveInstallationBaseline: ...


class InstallationControl(Protocol):
    def create(
        self,
        *,
        request: CreateInstallationRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
    ) -> CommandReceipt: ...

    def list(
        self,
        *,
        query: InstallationListQuery,
        org_id: str,
        project_id: str,
        roles: Collection[str],
        markings: Collection[str],
    ) -> InstallationListResponse: ...

    def get(
        self,
        *,
        installation_id: str,
        org_id: str,
        project_id: str,
        roles: Collection[str],
        markings: Collection[str],
    ) -> InstallationResponse: ...

    def submit(
        self,
        *,
        installation_id: str,
        request: EmptyInstallationActionRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt: ...

    def approve(
        self,
        *,
        installation_id: str,
        request: ApproveInstallationRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt: ...

    def reject(
        self,
        *,
        installation_id: str,
        request: RejectInstallationRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt: ...

    def apply(
        self,
        *,
        installation_id: str,
        request: EmptyInstallationActionRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt: ...

    def verify(
        self,
        *,
        installation_id: str,
        request: EmptyInstallationActionRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt: ...

    def rollback(
        self,
        *,
        installation_id: str,
        request: RollbackInstallationRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt: ...
