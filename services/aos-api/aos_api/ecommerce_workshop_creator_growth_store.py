"""Tenant-bound append-only Store for W2-04 candidate and match authorities."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

import psycopg

from aos_api.db import connect as db_connect
from aos_api.ecommerce_workshop_creator_growth_authorities import (
    CreatorCandidateRevision,
    CreatorMatchDecision,
    CreatorMatchObservation,
)
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]
AuthorityT = TypeVar("AuthorityT", CreatorCandidateRevision, CreatorMatchObservation, CreatorMatchDecision)


@dataclass(frozen=True)
class CreatorAuthorityObservation(Generic[AuthorityT]):
    authority: AuthorityT
    receipt_id: str

    def __post_init__(self) -> None:
        if not self.receipt_id.strip():
            raise ValueError("creator authority requires an exact Receipt")


class CreatorAuthorityStoreError(RuntimeError):
    code = "CREATOR_AUTHORITY_STORE_ERROR"


class CreatorAuthorityReadError(CreatorAuthorityStoreError):
    code = "CREATOR_AUTHORITY_READ_FAILED"


class EcommerceWorkshopCreatorGrowthStore:
    """Append new immutable rows and read bounded same-tenant observations."""

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def append_candidate(self, scope: TenantScope, item: CreatorCandidateRevision, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_candidate_revision", "candidate_id", item.candidate_id, item, receipt_id)

    def append_match_observation(self, scope: TenantScope, item: CreatorMatchObservation, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_match_observation", "observation_id", item.observation_id, item, receipt_id)

    def append_match_decision(self, scope: TenantScope, item: CreatorMatchDecision, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_match_decision", "decision_id", item.decision_id, item, receipt_id)

    def list_candidates(self, scope: TenantScope, *, cutoff: datetime, limit: int = 100) -> list[CreatorAuthorityObservation[CreatorCandidateRevision]]:
        return self._list(scope, "ecommerce_creator_candidate_revision", CreatorCandidateRevision, cutoff, limit)

    def list_match_observations(self, scope: TenantScope, *, cutoff: datetime, limit: int = 100) -> list[CreatorAuthorityObservation[CreatorMatchObservation]]:
        return self._list(scope, "ecommerce_creator_match_observation", CreatorMatchObservation, cutoff, limit)

    def list_match_decisions(self, scope: TenantScope, *, cutoff: datetime, limit: int = 100) -> list[CreatorAuthorityObservation[CreatorMatchDecision]]:
        return self._list(scope, "ecommerce_creator_match_decision", CreatorMatchDecision, cutoff, limit)

    def _append(self, scope: TenantScope, table: str, identity_column: str, identity: str, item: AuthorityT, receipt_id: str) -> None:
        tenant = item.tenant
        if (tenant.org_id, tenant.project_id) != scope.key:
            raise ValueError("creator authority tenant scope drift")
        if not receipt_id.strip():
            raise ValueError("creator authority append requires receiptId")
        payload = item.model_dump(mode="json", by_alias=True)
        with self._connect_factory(scope) as conn:
            conn.execute(
                f"INSERT INTO {table}(org_id,project_id,{identity_column},revision,content_hash,receipt_id,authority_data,created_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                (*scope.key, identity, item.revision, item.content_hash, receipt_id, json.dumps(payload, separators=(",", ":")), self._time(item)),
            )
            conn.commit()

    def _list(self, scope: TenantScope, table: str, model: type[AuthorityT], cutoff: datetime, limit: int) -> list[CreatorAuthorityObservation[AuthorityT]]:
        if cutoff.utcoffset() is None or not 1 <= limit <= 100:
            raise ValueError("creator authority read requires aware cutoff and bounded limit")
        try:
            with self._connect_factory(scope) as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                rows = conn.execute(
                    f"SELECT org_id,project_id,receipt_id,authority_data FROM {table} "
                    "WHERE org_id=%s AND project_id=%s AND created_at<=%s ORDER BY created_at DESC LIMIT %s",
                    (*scope.key, cutoff, limit),
                ).fetchall()
            result = []
            for row in rows:
                if (row["org_id"], row["project_id"]) != scope.key:
                    raise ValueError("creator authority tenant scope drift")
                result.append(CreatorAuthorityObservation(authority=model.model_validate(row["authority_data"]), receipt_id=row["receipt_id"]))
            return result
        except (psycopg.Error, AttributeError, KeyError, TypeError, ValueError) as exc:
            raise CreatorAuthorityReadError("creator authority read failed closed") from exc

    @staticmethod
    def _time(item: AuthorityT) -> datetime:
        return getattr(item, "observed_at", getattr(item, "decided_at", None))


__all__ = ["CreatorAuthorityObservation", "CreatorAuthorityReadError", "EcommerceWorkshopCreatorGrowthStore"]
