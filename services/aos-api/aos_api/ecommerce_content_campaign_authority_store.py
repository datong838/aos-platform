"""Internal tenant-safe Store and readers for content-campaign authorities."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any, TypeVar

import psycopg

from aos_api.db import connect as db_connect
from aos_api.ecommerce_content_campaign_authority_contracts import (
    CalendarDecisionRevision,
    CalendarEntryRevision,
    CampaignRevision,
    ContentCampaignAuthorityReceipt,
    ContentCampaignExactRef,
    MasterContentIntentRevision,
)
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]
RevisionT = TypeVar(
    "RevisionT", CampaignRevision, CalendarEntryRevision, MasterContentIntentRevision
)


class ContentCampaignAuthorityStoreError(RuntimeError):
    code = "CONTENT_CAMPAIGN_AUTHORITY_ERROR"


class ContentCampaignAuthorityConflict(ContentCampaignAuthorityStoreError):
    code = "CONTENT_CAMPAIGN_AUTHORITY_VERSION_CONFLICT"


class ContentCampaignAuthorityIdempotencyConflict(
    ContentCampaignAuthorityStoreError
):
    code = "CONTENT_CAMPAIGN_AUTHORITY_IDEMPOTENCY_CONFLICT"


class ContentCampaignAuthorityReadError(ContentCampaignAuthorityStoreError):
    code = "CONTENT_CAMPAIGN_AUTHORITY_READ_FAILED"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class EcommerceContentCampaignAuthorityStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def publish_campaign(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: CampaignRevision,
        *,
        expected_version: int,
    ) -> ContentCampaignExactRef:
        return self._publish_revision(
            scope,
            actor,
            key,
            item,
            expected_version=expected_version,
            operation="content_campaign.campaign_publish",
            resource_type="CampaignRevision",
            identity=item.campaign_id,
            identity_column="campaign_id",
            head_table="ecommerce_campaign_head",
            revision_table="ecommerce_campaign_revision",
        )

    def publish_calendar_entry(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: CalendarEntryRevision,
        *,
        expected_version: int,
    ) -> ContentCampaignExactRef:
        self._require_scope(
            scope,
            item.campaign_ref,
            *item.content_artifact_refs,
            *((item.conflict_decision_ref,) if item.conflict_decision_ref else ()),
        )
        return self._publish_revision(
            scope,
            actor,
            key,
            item,
            expected_version=expected_version,
            operation="content_campaign.calendar_publish",
            resource_type="CalendarEntryRevision",
            identity=item.entry_id,
            identity_column="entry_id",
            head_table="ecommerce_content_calendar_head",
            revision_table="ecommerce_content_calendar_entry_revision",
            extra_columns=(
                "timezone,resolved_start,resolved_end",
                (item.timezone, item.resolved_start, item.resolved_end),
            ),
        )

    def publish_intent(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: MasterContentIntentRevision,
        *,
        expected_version: int,
    ) -> ContentCampaignExactRef:
        refs = [item.campaign_ref]
        if item.brief_ref:
            refs.append(item.brief_ref)
        if item.master_artifact_ref:
            refs.append(item.master_artifact_ref)
        self._require_scope(scope, *refs)
        return self._publish_revision(
            scope,
            actor,
            key,
            item,
            expected_version=expected_version,
            operation="content_campaign.intent_publish",
            resource_type="MasterContentIntentRevision",
            identity=item.intent_id,
            identity_column="intent_id",
            head_table="ecommerce_master_content_intent_head",
            revision_table="ecommerce_master_content_intent_revision",
        )

    def append_calendar_decision(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: CalendarDecisionRevision,
    ) -> ContentCampaignExactRef:
        self._require_item_scope(scope, item.tenant.org_id, item.tenant.project_id)
        self._require_actor(actor, item.created_by)
        if item.revision != 1:
            raise ContentCampaignAuthorityConflict(
                "calendar decisions use a unique identity at revision 1"
            )
        payload = item.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        operation = "content_campaign.calendar_decision_append"
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay is not None:
                return ContentCampaignExactRef.model_validate(replay)
            conn.execute(
                "INSERT INTO ecommerce_content_calendar_decision_revision"
                "(org_id,project_id,decision_id,revision,parent_revision,content_hash,"
                "authority_data,created_by,created_at,entry_id) "
                "VALUES(%s,%s,%s,1,NULL,%s,%s::jsonb,%s,%s,%s)",
                (
                    *scope.key,
                    item.decision_id,
                    item.content_hash,
                    self._json(payload),
                    actor,
                    item.created_at,
                    item.from_entry_ref.resource_id,
                ),
            )
            result = self._ref(
                "CalendarDecisionRevision",
                item.decision_id,
                item.revision,
                item.content_hash,
            )
            self._receipt(conn, scope, operation, key, request_hash, result, actor)
            conn.commit()
            return result

    def list_campaigns(
        self, scope: TenantScope, *, cutoff: datetime, limit: int = 100
    ) -> list[CampaignRevision]:
        return self._list_current(
            scope,
            cutoff=cutoff,
            limit=limit,
            model=CampaignRevision,
            head_table="ecommerce_campaign_head",
            revision_table="ecommerce_campaign_revision",
            identity_column="campaign_id",
        )

    def list_calendar_entries(
        self, scope: TenantScope, *, cutoff: datetime, limit: int = 100
    ) -> list[CalendarEntryRevision]:
        return self._list_current(
            scope,
            cutoff=cutoff,
            limit=limit,
            model=CalendarEntryRevision,
            head_table="ecommerce_content_calendar_head",
            revision_table="ecommerce_content_calendar_entry_revision",
            identity_column="entry_id",
        )

    def list_intents(
        self, scope: TenantScope, *, cutoff: datetime, limit: int = 100
    ) -> list[MasterContentIntentRevision]:
        return self._list_current(
            scope,
            cutoff=cutoff,
            limit=limit,
            model=MasterContentIntentRevision,
            head_table="ecommerce_master_content_intent_head",
            revision_table="ecommerce_master_content_intent_revision",
            identity_column="intent_id",
        )

    def get_receipt(
        self, scope: TenantScope, *, operation: str, idempotency_key: str
    ) -> ContentCampaignAuthorityReceipt:
        try:
            with self._connect_factory(scope) as conn:
                conn.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                row = conn.execute(
                    "SELECT receipt_id,operation,idempotency_key,request_hash,"
                    "result_ref,created_by,created_at "
                    "FROM ecommerce_content_campaign_authority_receipt "
                    "WHERE org_id=%s AND project_id=%s AND operation=%s "
                    "AND idempotency_key=%s",
                    (*scope.key, operation, idempotency_key),
                ).fetchone()
            if row is None:
                raise ContentCampaignAuthorityReadError(
                    "content-campaign authority Receipt not found"
                )
            return ContentCampaignAuthorityReceipt(
                tenant={"orgId": scope.org_id, "projectId": scope.project_id},
                receiptId=row["receipt_id"],
                operation=row["operation"],
                idempotencyKey=row["idempotency_key"],
                requestHash=row["request_hash"],
                resultRef=self._load(row["result_ref"]),
                createdBy=row["created_by"],
                createdAt=row["created_at"],
            )
        except ContentCampaignAuthorityReadError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise ContentCampaignAuthorityReadError(
                "content-campaign authority Receipt read failed closed"
            ) from exc

    def _publish_revision(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: RevisionT,
        *,
        expected_version: int,
        operation: str,
        resource_type: str,
        identity: str,
        identity_column: str,
        head_table: str,
        revision_table: str,
        extra_columns: tuple[str, tuple[Any, ...]] | None = None,
    ) -> ContentCampaignExactRef:
        self._require_item_scope(scope, item.tenant.org_id, item.tenant.project_id)
        self._require_actor(actor, item.created_by)
        payload = item.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(
            {"expectedVersion": expected_version, "revision": payload}
        )
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay is not None:
                return ContentCampaignExactRef.model_validate(replay)
            head = conn.execute(
                f"SELECT current_revision,version FROM {head_table} "
                f"WHERE org_id=%s AND project_id=%s AND {identity_column}=%s FOR UPDATE",
                (*scope.key, identity),
            ).fetchone()
            version = int(head["version"]) if head else 0
            if version != expected_version:
                raise ContentCampaignAuthorityConflict("stale authority version")
            if item.revision != version + 1 or item.version != version + 1:
                raise ContentCampaignAuthorityConflict(
                    "authority revision/version must advance exactly once"
                )
            if head:
                conn.execute(
                    f"UPDATE {head_table} SET current_revision=%s,"
                    "version=version+1,updated_at=NOW() "
                    f"WHERE org_id=%s AND project_id=%s AND {identity_column}=%s",
                    (item.revision, *scope.key, identity),
                )
            else:
                conn.execute(
                    f"INSERT INTO {head_table}"
                    f"(org_id,project_id,{identity_column},current_revision,version) "
                    "VALUES(%s,%s,%s,%s,1)",
                    (*scope.key, identity, item.revision),
                )
            parent_revision = item.revision - 1 if item.revision > 1 else None
            column_suffix = ""
            value_suffix = ""
            extra_values: tuple[Any, ...] = ()
            if extra_columns:
                column_suffix = "," + extra_columns[0]
                value_suffix = "," + ",".join("%s" for _ in extra_columns[1])
                extra_values = extra_columns[1]
            conn.execute(
                f"INSERT INTO {revision_table}"
                f"(org_id,project_id,{identity_column},revision,parent_revision,"
                f"content_hash,authority_data,created_by,created_at{column_suffix}) "
                f"VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s{value_suffix})",
                (
                    *scope.key,
                    identity,
                    item.revision,
                    parent_revision,
                    item.content_hash,
                    self._json(payload),
                    actor,
                    item.created_at,
                    *extra_values,
                ),
            )
            result = self._ref(
                resource_type, identity, item.revision, item.content_hash
            )
            self._receipt(conn, scope, operation, key, request_hash, result, actor)
            conn.commit()
            return result

    def _list_current(
        self,
        scope: TenantScope,
        *,
        cutoff: datetime,
        limit: int,
        model: type[RevisionT],
        head_table: str,
        revision_table: str,
        identity_column: str,
    ) -> list[RevisionT]:
        if cutoff.utcoffset() is None:
            raise ValueError("authority cutoff requires a timezone")
        if not 1 <= limit <= 100:
            raise ValueError("authority read limit must be between 1 and 100")
        try:
            with self._connect_factory(scope) as conn:
                conn.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                rows = conn.execute(
                    f"SELECT revision.org_id,revision.project_id,"
                    f"revision.authority_data FROM {head_table} head "
                    f"JOIN {revision_table} revision "
                    "ON revision.org_id=head.org_id "
                    "AND revision.project_id=head.project_id "
                    f"AND revision.{identity_column}=head.{identity_column} "
                    "AND revision.revision=head.current_revision "
                    "WHERE head.org_id=%s AND head.project_id=%s "
                    "AND revision.created_at<=%s "
                    f"ORDER BY revision.created_at DESC,revision.{identity_column} "
                    "LIMIT %s",
                    (*scope.key, cutoff, limit),
                ).fetchall()
            items = []
            for row in rows:
                if (row["org_id"], row["project_id"]) != scope.key:
                    raise ValueError("content-campaign authority tenant scope drift")
                item = model.model_validate(self._load(row["authority_data"]))
                self._require_item_scope(
                    scope, item.tenant.org_id, item.tenant.project_id
                )
                items.append(item)
            return items
        except ContentCampaignAuthorityConflict as exc:
            raise ContentCampaignAuthorityReadError(str(exc)) from exc
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise ContentCampaignAuthorityReadError(
                "content-campaign authority read failed closed"
            ) from exc

    @staticmethod
    def _require_item_scope(
        scope: TenantScope, org_id: str, project_id: str
    ) -> None:
        if scope.key != (org_id, project_id):
            raise ContentCampaignAuthorityConflict("tenant scope mismatch")

    @staticmethod
    def _require_scope(
        scope: TenantScope, *refs: ContentCampaignExactRef
    ) -> None:
        # Exact refs deliberately carry no tenant. Their tenant binding comes from
        # the scoped transaction and canonical lookup performed by later commands.
        if not scope.org_id or not scope.project_id or any(not ref.resource_id for ref in refs):
            raise ContentCampaignAuthorityConflict("invalid tenant-bound exact ref")

    @staticmethod
    def _require_actor(actor: str, created_by: str) -> None:
        if not actor.strip() or actor != created_by:
            raise ContentCampaignAuthorityConflict("actor mismatch")

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    @staticmethod
    def _ref(
        resource_type: str, resource_id: str, revision: int, content_hash: str
    ) -> ContentCampaignExactRef:
        return ContentCampaignExactRef(
            resource_type=resource_type,
            resource_id=resource_id,
            revision=revision,
            content_hash=content_hash,
        )

    def _replay(
        self,
        conn: Any,
        scope: TenantScope,
        operation: str,
        key: str,
        request_hash: str,
    ) -> Any | None:
        row = conn.execute(
            "SELECT request_hash,result_ref "
            "FROM ecommerce_content_campaign_authority_receipt "
            "WHERE org_id=%s AND project_id=%s AND operation=%s "
            "AND idempotency_key=%s",
            (*scope.key, operation, key),
        ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise ContentCampaignAuthorityIdempotencyConflict(
                "idempotency key was used with a different request"
            )
        return self._load(row["result_ref"])

    def _receipt(
        self,
        conn: Any,
        scope: TenantScope,
        operation: str,
        key: str,
        request_hash: str,
        result: ContentCampaignExactRef,
        actor: str,
    ) -> None:
        conn.execute(
            "INSERT INTO ecommerce_content_campaign_authority_receipt"
            "(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,"
            "result_ref,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
            (
                *scope.key,
                f"ccar-{uuid.uuid4().hex}",
                operation,
                key,
                request_hash,
                self._json(result.model_dump(mode="json", by_alias=True)),
                actor,
            ),
        )


__all__ = [
    "ContentCampaignAuthorityConflict",
    "ContentCampaignAuthorityIdempotencyConflict",
    "ContentCampaignAuthorityReadError",
    "ContentCampaignAuthorityStoreError",
    "EcommerceContentCampaignAuthorityStore",
    "canonical_hash",
]
