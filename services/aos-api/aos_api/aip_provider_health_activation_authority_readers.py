"""Exact read-only Action authority and Binding owners for activation audit."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Literal

from aos_api.aip_action_store import canonical_hash
from aos_api.aip_provider_health_action import (
    PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
)
from aos_api.aip_provider_health_activation_change_packet import CANONICAL_TENANT
from aos_api.aip_provider_health_activation_fact_readers import (
    AuthorityFactSnapshot,
    BindingFactSnapshot,
    OwnerReader,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope, apply_transaction_scope


ConnectFactory = Callable[[], AbstractContextManager[Any]]
ActionRowsReader = Callable[[str, datetime], "ActionAuthorityRows"]
BindingRowsReader = Callable[[str, datetime], "BindingAuthorityRows"]


def _sha256(value: str, field: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{field} must be a sha256 digest")
    return normalized


def _aware(value: datetime | None) -> bool:
    return value is not None and value.tzinfo is not None


@dataclass(frozen=True, slots=True)
class ExactActionAuthoritySelection:
    proposal_id: str
    proposal_hash: str
    proposal_version: int
    lease_id: str
    lease_owner_id: str
    action_type_revision_hash: str

    def __post_init__(self) -> None:
        for field in ("proposal_id", "lease_id", "lease_owner_id"):
            value = getattr(self, field)
            if not value.strip():
                raise ValueError(f"{field} is required")
        if self.proposal_version < 1:
            raise ValueError("proposal_version must be positive")
        object.__setattr__(self, "proposal_hash", _sha256(self.proposal_hash, "proposal_hash"))
        object.__setattr__(
            self,
            "action_type_revision_hash",
            _sha256(self.action_type_revision_hash, "action_type_revision_hash"),
        )


@dataclass(frozen=True, slots=True)
class ExactBindingRef:
    kind: Literal["capability", "skill"]
    binding_id: str
    version: int
    dependency_snapshot_hash: str

    def __post_init__(self) -> None:
        if self.kind not in {"capability", "skill"}:
            raise ValueError("binding kind must be capability or skill")
        if not self.binding_id.strip():
            raise ValueError("binding_id is required")
        if self.version < 1:
            raise ValueError("binding version must be positive")
        object.__setattr__(
            self,
            "dependency_snapshot_hash",
            _sha256(self.dependency_snapshot_hash, "dependency_snapshot_hash"),
        )


@dataclass(frozen=True, slots=True)
class ExactBindingSelection:
    refs: tuple[ExactBindingRef, ...]

    def __post_init__(self) -> None:
        if not self.refs:
            raise ValueError("at least one exact binding ref is required")
        keys = [(item.kind, item.binding_id) for item in self.refs]
        if len(keys) != len(set(keys)):
            raise ValueError("exact binding refs must be unique")


@dataclass(frozen=True, slots=True)
class ActionAuthorityRows:
    observed_at: datetime
    proposal: Mapping[str, Any] | None
    approvals: tuple[Mapping[str, Any], ...]
    lease: Mapping[str, Any] | None
    initial_receipt_count: int

    def __post_init__(self) -> None:
        if not _aware(self.observed_at):
            raise ValueError("Action authority observed_at must be timezone-aware")
        if self.initial_receipt_count < 0:
            raise ValueError("initial_receipt_count cannot be negative")
        object.__setattr__(
            self,
            "proposal",
            None if self.proposal is None else MappingProxyType(dict(self.proposal)),
        )
        object.__setattr__(
            self,
            "approvals",
            tuple(MappingProxyType(dict(item)) for item in self.approvals),
        )
        object.__setattr__(
            self,
            "lease",
            None if self.lease is None else MappingProxyType(dict(self.lease)),
        )


@dataclass(frozen=True, slots=True)
class BindingAuthorityRows:
    observed_at: datetime
    items: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        if not _aware(self.observed_at):
            raise ValueError("Binding authority observed_at must be timezone-aware")
        object.__setattr__(
            self,
            "items",
            tuple(MappingProxyType(dict(item)) for item in self.items),
        )


def _default_connect() -> AbstractContextManager[Any]:
    return db_connect(inherit_scope=False)


def postgres_action_authority_rows_reader(
    selection: ExactActionAuthoritySelection,
    *,
    connect_factory: ConnectFactory = _default_connect,
) -> ActionRowsReader:
    """Select only authority metadata in one tenant-scoped read-only snapshot."""

    def read(tenant: str, evaluated_at: datetime) -> ActionAuthorityRows:
        scope = _scope(tenant)
        with connect_factory() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            apply_transaction_scope(conn, scope)
            observed_at = conn.execute(
                "SELECT CURRENT_TIMESTAMP AS observed_at"
            ).fetchone()["observed_at"]
            proposal = conn.execute(
                """SELECT proposal_id,proposal_hash,version,status,expires_at,
                          action_type_id,action_type_revision_hash,action_binding_hash,
                          approval_policy_hash,
                          COALESCE((policy_snapshot->>'minimumApprovals')::int,1)
                            AS minimum_approvals
                     FROM aip_action_proposal
                    WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
                (*scope.key, selection.proposal_id),
            ).fetchone()
            approvals = conn.execute(
                """SELECT approval_event_id,actor_id,slot_id,decision,expires_at,
                          proposal_hash,action_binding_hash,approval_policy_hash,
                          eligibility_snapshot_hash
                     FROM aip_action_approval_event
                    WHERE org_id=%s AND project_id=%s AND proposal_id=%s
                    ORDER BY created_at,approval_event_id""",
                (*scope.key, selection.proposal_id),
            ).fetchall()
            lease = conn.execute(
                """SELECT lease_id,proposal_id,proposal_hash,status,owner_id,expires_at,
                          action_binding_hash,approval_set_hash
                     FROM aip_action_execution_lease
                    WHERE org_id=%s AND project_id=%s AND lease_id=%s""",
                (*scope.key, selection.lease_id),
            ).fetchone()
            receipt_count = conn.execute(
                """SELECT COUNT(*) AS n FROM aip_action_receipt
                    WHERE org_id=%s AND project_id=%s AND lease_id=%s
                      AND receipt_kind='initial'""",
                (*scope.key, selection.lease_id),
            ).fetchone()["n"]
        return ActionAuthorityRows(
            observed_at=observed_at,
            proposal=proposal,
            approvals=tuple(approvals),
            lease=lease,
            initial_receipt_count=int(receipt_count),
        )

    return read


def postgres_binding_authority_rows_reader(
    selection: ExactBindingSelection,
    *,
    connect_factory: ConnectFactory = _default_connect,
) -> BindingRowsReader:
    """Select exact capability/skill binding metadata without SecretRef values."""
    capability_ids = [item.binding_id for item in selection.refs if item.kind == "capability"]
    skill_ids = [item.binding_id for item in selection.refs if item.kind == "skill"]

    def read(tenant: str, evaluated_at: datetime) -> BindingAuthorityRows:
        scope = _scope(tenant)
        with connect_factory() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            apply_transaction_scope(conn, scope)
            observed_at = conn.execute(
                "SELECT CURRENT_TIMESTAMP AS observed_at"
            ).fetchone()["observed_at"]
            items: list[Mapping[str, Any]] = []
            if capability_ids:
                rows = conn.execute(
                    """SELECT 'capability' AS kind,binding_id,version,status,
                              dependency_snapshot_hash,
                              operational_readiness AS readiness,
                              last_evaluated_at,readiness_expires_at
                         FROM aip_capability_binding
                        WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)
                        ORDER BY binding_id""",
                    (*scope.key, capability_ids),
                ).fetchall()
                items.extend(rows)
            if skill_ids:
                rows = conn.execute(
                    """SELECT 'skill' AS kind,binding_id,version,status,
                              dependency_snapshot_hash,readiness,
                              last_evaluated_at,readiness_expires_at
                         FROM aip_skill_binding
                        WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)
                        ORDER BY binding_id""",
                    (*scope.key, skill_ids),
                ).fetchall()
                items.extend(rows)
        return BindingAuthorityRows(observed_at=observed_at, items=tuple(items))

    return read


def build_exact_action_authority_owner_reader(
    selection: ExactActionAuthoritySelection,
    *,
    rows_reader: ActionRowsReader | None = None,
) -> OwnerReader:
    source = rows_reader or postgres_action_authority_rows_reader(selection)

    def read(tenant: str, evaluated_at: datetime) -> AuthorityFactSnapshot:
        _scope(tenant)
        rows = source(tenant, evaluated_at)
        proposal = rows.proposal
        lease = rows.lease
        proposal_exact = bool(
            proposal
            and proposal.get("proposal_id") == selection.proposal_id
            and proposal.get("proposal_hash") == selection.proposal_hash
            and int(proposal.get("version", 0)) == selection.proposal_version
            and proposal.get("status") == "leased"
            and proposal.get("expires_at") is not None
            and proposal["expires_at"] > evaluated_at
            and proposal.get("action_type_id") == PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
            and proposal.get("action_type_revision_hash")
            == selection.action_type_revision_hash
        )
        valid_approvals = [
            item
            for item in rows.approvals
            if item.get("decision") == "approved"
            and (item.get("expires_at") is None or item["expires_at"] > evaluated_at)
        ]
        approval_keys = [(item.get("actor_id"), item.get("slot_id")) for item in valid_approvals]
        minimum = int(proposal.get("minimum_approvals", 1)) if proposal else 1
        approval_exact = bool(
            proposal_exact
            and len(valid_approvals) >= minimum
            and len(approval_keys) == len(set(approval_keys))
            and all(
                item.get("proposal_hash") == selection.proposal_hash
                and item.get("action_binding_hash") == proposal.get("action_binding_hash")
                and item.get("approval_policy_hash") == proposal.get("approval_policy_hash")
                and item.get("eligibility_snapshot_hash")
                for item in valid_approvals
            )
        )
        approval_set_hash = canonical_hash(
            [
                {
                    "approvalEventId": item.get("approval_event_id"),
                    "actorId": item.get("actor_id"),
                    "slotId": item.get("slot_id"),
                    "eligibilitySnapshotHash": item.get("eligibility_snapshot_hash"),
                    "expiresAt": item.get("expires_at"),
                }
                for item in valid_approvals
            ]
        )
        lease_exact = bool(
            approval_exact
            and lease
            and lease.get("lease_id") == selection.lease_id
            and lease.get("proposal_id") == selection.proposal_id
            and lease.get("proposal_hash") == selection.proposal_hash
            and lease.get("status") == "active"
            and lease.get("owner_id") == selection.lease_owner_id
            and lease.get("expires_at") is not None
            and lease["expires_at"] > evaluated_at
            and lease.get("action_binding_hash") == proposal.get("action_binding_hash")
            and lease.get("approval_set_hash") == approval_set_hash
        )
        return AuthorityFactSnapshot(
            tenant=tenant,
            observed_at=rows.observed_at,
            proposal_exact=proposal_exact,
            approval_exact=approval_exact,
            lease_exact=lease_exact,
            receipt_authority_exact=lease_exact and rows.initial_receipt_count == 0,
            lease_expires_at=(lease.get("expires_at") if lease else None),
        )

    return read


def build_exact_binding_owner_reader(
    selection: ExactBindingSelection,
    *,
    rows_reader: BindingRowsReader | None = None,
) -> OwnerReader:
    source = rows_reader or postgres_binding_authority_rows_reader(selection)
    expected = {(item.kind, item.binding_id): item for item in selection.refs}

    def read(tenant: str, evaluated_at: datetime) -> BindingFactSnapshot:
        _scope(tenant)
        rows = source(tenant, evaluated_at)
        by_key = {(item.get("kind"), item.get("binding_id")): item for item in rows.items}
        unique = len(by_key) == len(rows.items)
        exact = unique and set(by_key) == set(expected)
        if exact:
            exact = all(
                int(by_key[key].get("version", 0)) == ref.version
                and by_key[key].get("dependency_snapshot_hash")
                == ref.dependency_snapshot_hash
                and by_key[key].get("status") == "active"
                for key, ref in expected.items()
            )
        cutoffs = [item.get("last_evaluated_at") for item in rows.items]
        expires = [item.get("readiness_expires_at") for item in rows.items]
        cutoff_exact = bool(
            cutoffs
            and all(_aware(item) for item in cutoffs)
            and len(set(cutoffs)) == 1
        )
        common_cutoff = (
            cutoffs[0]
            if cutoff_exact
            else rows.observed_at
        )
        operational = bool(
            exact
            and cutoff_exact
            and all(item.get("readiness") == "available" for item in rows.items)
            and all(_aware(item) and item > evaluated_at for item in expires)
        )
        return BindingFactSnapshot(
            tenant=tenant,
            observed_at=rows.observed_at,
            exact=exact,
            operational=operational,
            expires_at=min(expires) if expires and all(_aware(item) for item in expires) else None,
            cutoff=common_cutoff,
        )

    return read


def _scope(tenant: str) -> TenantScope:
    if tenant != CANONICAL_TENANT:
        raise ValueError("Provider Health activation tenant is not canonical")
    org_id, project_id = tenant.split("/", 1)
    return TenantScope(org_id, project_id)


__all__ = [
    "ActionAuthorityRows",
    "BindingAuthorityRows",
    "ExactActionAuthoritySelection",
    "ExactBindingRef",
    "ExactBindingSelection",
    "build_exact_action_authority_owner_reader",
    "build_exact_binding_owner_reader",
    "postgres_action_authority_rows_reader",
    "postgres_binding_authority_rows_reader",
]
