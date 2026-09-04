"""Tenant-bound append-only Store for W2-04 candidate and match authorities."""

from __future__ import annotations

import json
import hashlib
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

import psycopg

from aos_api.db import connect as db_connect
from aos_api.db import connect_read_only as db_read_only_connect
from aos_api.ecommerce_workshop_creator_growth_authorities import (
    CreatorCandidateRevision,
    CreatorContractRevision,
    CreatorDeliveryRevision,
    CreatorMatchDecision,
    CreatorMatchObservation,
    CreatorRelationshipRevision,
    CreatorTermDiffRevision,
    OutreachBatchRevision,
    OutreachItemRevision,
    OutreachStartLedger,
)
from aos_api.ecommerce_workshop_creator_lifecycle import (
    CreatorContractRevision as LifecycleContractRevision,
    CreatorDeliveryObservation,
    CreatorRelationshipRevision as LifecycleRelationshipRevision,
)
from aos_api.ecommerce_workshop_creator_prepare import (
    CreatorBatchPreparationRevision,
    CreatorNormalizerReceipt,
)
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]
AuthorityT = TypeVar("AuthorityT", CreatorCandidateRevision, CreatorMatchObservation, CreatorMatchDecision, OutreachItemRevision, OutreachBatchRevision, OutreachStartLedger, CreatorContractRevision, CreatorTermDiffRevision, CreatorDeliveryRevision, CreatorRelationshipRevision)


def authority_receipt_id(
    org_id: str,
    project_id: str,
    resource_type: str,
    resource_id: str,
    revision: int,
    content_hash: str,
) -> str:
    payload = ":".join((org_id, project_id, resource_type, resource_id, str(revision), content_hash))
    return f"creator-authority-{hashlib.sha256(payload.encode()).hexdigest()[:40]}"


@dataclass(frozen=True)
class CreatorAuthorityObservation(Generic[AuthorityT]):
    authority: AuthorityT
    receipt_id: str
    resource_type_override: str | None = None
    resource_id_override: str | None = None
    revision_override: int | None = None

    def __post_init__(self) -> None:
        if not self.receipt_id.strip():
            raise ValueError("creator authority requires an exact Receipt")

    @property
    def resource_type(self) -> str:
        return self.resource_type_override or type(self.authority).__name__

    @property
    def resource_id(self) -> str:
        if self.resource_id_override is not None:
            return self.resource_id_override
        return next(
            value
            for value in (
                getattr(self.authority, "candidate_id", None),
                getattr(self.authority, "batch_id", None),
                getattr(self.authority, "contract_id", None),
                getattr(self.authority, "collaboration_id", None),
                getattr(self.authority, "delivery_id", None),
                getattr(self.authority, "observation_id", None),
                getattr(self.authority, "relationship_id", None),
            )
            if value is not None
        )

    @property
    def revision(self) -> int:
        return self.revision_override or int(getattr(self.authority, "revision", 1))

    @property
    def content_hash(self) -> str:
        return str(getattr(self.authority, "content_hash"))

    @property
    def pii_refs(self) -> list[str]:
        return list(getattr(self.authority, "pii_refs", []))


class CreatorAuthorityStoreError(RuntimeError):
    code = "CREATOR_AUTHORITY_STORE_ERROR"


class CreatorAuthorityReadError(CreatorAuthorityStoreError):
    code = "CREATOR_AUTHORITY_READ_FAILED"


class EcommerceWorkshopCreatorGrowthStore:
    """Append new immutable rows and read bounded same-tenant observations."""

    def __init__(
        self,
        connect_factory: ConnectFactory | None = None,
        read_connect_factory: ConnectFactory | None = None,
    ) -> None:
        self._connect_factory = connect_factory or db_connect
        self._read_connect_factory = read_connect_factory or (
            connect_factory if connect_factory is not None else db_read_only_connect
        )

    def append_candidate(self, scope: TenantScope, item: CreatorCandidateRevision, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_candidate_revision", "candidate_id", item.candidate_id, item, receipt_id)

    def append_match_observation(self, scope: TenantScope, item: CreatorMatchObservation, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_match_observation", "observation_id", item.observation_id, item, receipt_id)

    def append_match_decision(self, scope: TenantScope, item: CreatorMatchDecision, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_match_decision", "decision_id", item.decision_id, item, receipt_id)

    def append_outreach_item(self, scope: TenantScope, item: OutreachItemRevision, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_outreach_item_revision", "item_id", item.item_id, item, receipt_id)

    def append_outreach_batch(self, scope: TenantScope, item: OutreachBatchRevision, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_outreach_batch_revision", "batch_id", item.batch_id, item, receipt_id)

    def append_start_ledger(self, scope: TenantScope, item: OutreachStartLedger, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_outreach_start_ledger", "ledger_id", item.ledger_id, item, receipt_id)

    def append_contract(self, scope: TenantScope, item: CreatorContractRevision, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_contract_revision", "contract_id", item.contract_id, item, receipt_id)

    def append_term_diff(self, scope: TenantScope, item: CreatorTermDiffRevision, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_term_diff_revision", "diff_id", item.diff_id, item, receipt_id)

    def append_delivery(self, scope: TenantScope, item: CreatorDeliveryRevision, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_delivery_revision", "delivery_id", item.delivery_id, item, receipt_id)

    def append_relationship(self, scope: TenantScope, item: CreatorRelationshipRevision, receipt_id: str) -> None:
        self._append(scope, "ecommerce_creator_relationship_revision", "relationship_id", item.relationship_id, item, receipt_id)

    def list_candidates(self, scope: TenantScope, *, cutoff: datetime, limit: int = 100) -> list[CreatorAuthorityObservation[CreatorCandidateRevision]]:
        return self._list_canonical(scope, "ecommerce_creator_normalizer_receipt", "receipt_id", "candidateId", "candidate_id", CreatorNormalizerReceipt, "CreatorCandidateRevision", cutoff, limit)

    def list_match_observations(self, scope: TenantScope, *, cutoff: datetime, limit: int = 100) -> list[CreatorAuthorityObservation[CreatorMatchObservation]]:
        return self._list(scope, "ecommerce_creator_match_observation", CreatorMatchObservation, cutoff, limit)

    def list_match_decisions(self, scope: TenantScope, *, cutoff: datetime, limit: int = 100) -> list[CreatorAuthorityObservation[CreatorMatchDecision]]:
        return self._list(scope, "ecommerce_creator_match_decision", CreatorMatchDecision, cutoff, limit)

    def list_outreach_batches(self, scope: TenantScope, *, cutoff: datetime, limit: int = 100) -> list[CreatorAuthorityObservation[OutreachBatchRevision]]:
        return self._list_canonical(scope, "ecommerce_creator_batch_preparation_revision", "authority_receipt_id", "batchId", "batch_id", CreatorBatchPreparationRevision, "CreatorBatchPreparationRevision", cutoff, limit)

    def list_contracts(self, scope: TenantScope, *, cutoff: datetime, limit: int = 100) -> list[CreatorAuthorityObservation[CreatorContractRevision]]:
        return self._list_canonical(scope, "ecommerce_creator_contract_revision", "authority_receipt_id", "collaborationId", "collaboration_id", LifecycleContractRevision, "CreatorContractRevision", cutoff, limit)

    def list_deliveries(self, scope: TenantScope, *, cutoff: datetime, limit: int = 100) -> list[CreatorAuthorityObservation[CreatorDeliveryRevision]]:
        return self._list_canonical(scope, "ecommerce_creator_delivery_observation", "authority_receipt_id", "observationId", "observation_id", CreatorDeliveryObservation, "CreatorDeliveryObservation", cutoff, limit)

    def list_relationships(self, scope: TenantScope, *, cutoff: datetime, limit: int = 100) -> list[CreatorAuthorityObservation[CreatorRelationshipRevision]]:
        return self._list_canonical(scope, "ecommerce_creator_relationship_revision", "authority_receipt_id", "relationshipId", "relationship_id", LifecycleRelationshipRevision, "CreatorRelationshipRevision", cutoff, limit)

    def _list_canonical(
        self,
        scope: TenantScope,
        table: str,
        receipt_column: str,
        identity_key: str,
        identity_attr: str,
        model: type[Any],
        resource_type: str,
        cutoff: datetime,
        limit: int,
    ) -> list[CreatorAuthorityObservation[Any]]:
        if cutoff.utcoffset() is None or not 1 <= limit <= 100:
            raise ValueError("creator authority read requires aware cutoff and bounded limit")
        try:
            with self._read_connect_factory(scope) as conn:
                rows = conn.execute(
                    f"SELECT org_id,project_id,{receipt_column} AS authority_receipt_id,content_hash,authority_data FROM ("
                    f"SELECT DISTINCT ON (authority_data->>'{identity_key}') org_id,project_id,{receipt_column},content_hash,authority_data,created_at,revision "
                    f"FROM {table} WHERE org_id=%s AND project_id=%s AND created_at<=%s "
                    f"ORDER BY authority_data->>'{identity_key}',revision DESC,created_at DESC) latest "
                    f"ORDER BY created_at DESC,authority_data->>'{identity_key}' LIMIT %s",
                    (*scope.key, cutoff, limit),
                ).fetchall()
            result = []
            for row in rows:
                if (row["org_id"], row["project_id"]) != scope.key:
                    raise ValueError("creator authority tenant scope drift")
                receipt_id = row["authority_receipt_id"]
                if not isinstance(receipt_id, str) or not receipt_id.strip():
                    raise ValueError("creator authority Receipt missing")
                authority = model.model_validate(row["authority_data"])
                if authority.tenant.org_id != scope.org_id or authority.tenant.project_id != scope.project_id:
                    raise ValueError("creator authority payload tenant drift")
                if authority.content_hash != row["content_hash"]:
                    raise ValueError("creator authority content hash drift")
                result.append(
                    CreatorAuthorityObservation(
                        authority=authority,
                        receipt_id=receipt_id,
                        resource_type_override=resource_type,
                        resource_id_override=getattr(authority, identity_attr),
                        revision_override=int(getattr(authority, "revision", 1)),
                    )
                )
            return result
        except (psycopg.Error, AttributeError, KeyError, TypeError, ValueError) as exc:
            raise CreatorAuthorityReadError("creator canonical authority read failed closed") from exc

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
            with self._read_connect_factory(scope) as conn:
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
        return next((value for value in (getattr(item, "observed_at", None), getattr(item, "decided_at", None), getattr(item, "prepared_at", None), getattr(item, "recorded_at", None)) if value is not None), None)


__all__ = ["CreatorAuthorityObservation", "CreatorAuthorityReadError", "EcommerceWorkshopCreatorGrowthStore", "authority_receipt_id"]
