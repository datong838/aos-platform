"""Transactional persistence for the platform-neutral ecommerce core.

The store owns only the new ``ecom_*`` tables.  It intentionally does not
read or mutate legacy ``obj_instance`` / ``graph_edge`` state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from threading import RLock
from typing import Any, Mapping

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    func,
    insert,
    or_,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from aos_api.ecom_core_models import (
    BatchCommand,
    BatchResult,
    CoreLinkRecord,
    CoreObjectRecord,
    DERIVED_PROPERTIES,
    DerivedMetricCommand,
    DerivedMetricResult,
    EcomConsistencyError,
    StorageIdentity,
    SyncScope,
    _jsonable,
)

metadata = MetaData()
_PROCESS_IDEMPOTENCY_LOCKS = tuple(RLock() for _ in range(64))
_NOT_PRELOADED = object()

ecom_object = Table(
    "ecom_object",
    metadata,
    Column("org_id", String, primary_key=True),
    Column("workspace_id", String, primary_key=True),
    Column("platform", String, primary_key=True),
    Column("shop_or_marketplace_id", String, primary_key=True),
    Column("object_type", String, primary_key=True),
    Column("external_id", String, primary_key=True),
    Column("properties", JSON, nullable=False),
    Column("source_updated_at", DateTime(timezone=True), nullable=False),
    Column("source_timezone", String, nullable=False),
    Column("canonical_status", String, nullable=False),
    Column("raw_status", Text, nullable=False, default=""),
    Column("schema_version", Integer, nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("derived_revision", BigInteger, nullable=False, default=0),
    Column("derived_input_revision", BigInteger, nullable=True),
    Column("derived_input_hash", String(64), nullable=True),
    Column("derived_computed_at", DateTime(timezone=True), nullable=True),
    Column("derived_payload", JSON, nullable=False, default=dict),
    Column("derived_payload_hash", String(64), nullable=True),
)

ecom_link = Table(
    "ecom_link",
    metadata,
    Column("org_id", String, primary_key=True),
    Column("workspace_id", String, primary_key=True),
    Column("link_type", String, primary_key=True),
    Column("source_platform", String, primary_key=True),
    Column("source_shop_or_marketplace_id", String, primary_key=True),
    Column("source_object_type", String, primary_key=True),
    Column("source_external_id", String, primary_key=True),
    Column("target_platform", String, primary_key=True),
    Column("target_shop_or_marketplace_id", String, primary_key=True),
    Column("target_object_type", String, primary_key=True),
    Column("target_external_id", String, primary_key=True),
    Column("properties", JSON, nullable=False),
    Column("source_updated_at", DateTime(timezone=True), nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "source_platform = target_platform AND "
        "source_shop_or_marketplace_id = target_shop_or_marketplace_id",
        name="ck_ecom_link_same_shop",
    ),
    CheckConstraint(
        "(link_type = 'Order.lines' AND source_object_type = 'Order' AND target_object_type = 'OrderLine') OR "
        "(link_type = 'OrderLine.ofSku' AND source_object_type = 'OrderLine' AND target_object_type = 'ProductSku') OR "
        "(link_type = 'OrderLine.ofProduct' AND source_object_type = 'OrderLine' AND target_object_type = 'Product') OR "
        "(link_type = 'ProductSku.ofProduct' AND source_object_type = 'ProductSku' AND target_object_type = 'Product') OR "
        "(link_type = 'Product.inCategory' AND source_object_type = 'Product' AND target_object_type = 'Category') OR "
        "(link_type = 'Shop.sellsProduct' AND source_object_type = 'Shop' AND target_object_type = 'Product') OR "
        "(link_type = 'Order.fulfilledBy' AND source_object_type = 'Order' AND target_object_type = 'Shipment') OR "
        "(link_type = 'Order.placedByLite' AND source_object_type = 'Order' AND target_object_type = 'CustomerLite') OR "
        "(link_type = 'Shop.hasWeapp' AND source_object_type = 'Shop' AND target_object_type = 'Weapp') OR "
        "(link_type = 'Product.hasReview' AND source_object_type = 'Product' AND target_object_type = 'ProductReview') OR "
        "(link_type = 'ProductReview.ofSku' AND source_object_type = 'ProductReview' AND target_object_type = 'ProductSku') OR "
        "(link_type = 'ProductReview.byMember' AND source_object_type = 'ProductReview' AND target_object_type = 'CustomerLite') OR "
        "(link_type = 'Order.hasPayment' AND source_object_type = 'Order' AND target_object_type = 'Payment') OR "
        "(link_type = 'Order.fromWeapp' AND source_object_type = 'Order' AND target_object_type = 'Weapp')",
        name="ck_ecom_link_endpoint_types",
    ),
)

ecom_sync_checkpoint = Table(
    "ecom_sync_checkpoint",
    metadata,
    Column("org_id", String, primary_key=True),
    Column("workspace_id", String, primary_key=True),
    Column("platform", String, primary_key=True),
    Column("shop_or_marketplace_id", String, primary_key=True),
    Column("stream", String, primary_key=True),
    Column("cursor_updated_at", DateTime(timezone=True), nullable=False),
    Column("cursor_external_id", String, nullable=False),
    Column("version", BigInteger, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

ecom_ingest_receipt = Table(
    "ecom_ingest_receipt",
    metadata,
    Column("org_id", String, primary_key=True),
    Column("workspace_id", String, primary_key=True),
    Column("platform", String, primary_key=True),
    Column("shop_or_marketplace_id", String, primary_key=True),
    Column("stream", String, primary_key=True),
    Column("idempotency_key", String, primary_key=True),
    Column("request_hash", String(64), nullable=False),
    Column("result", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

ecom_derived_receipt = Table(
    "ecom_derived_receipt",
    metadata,
    Column("org_id", String, primary_key=True),
    Column("project_id", String, primary_key=True),
    Column("workspace_id", String, nullable=False),
    Column("receipt_id", String, primary_key=True),
    Column("object_type", String, nullable=False),
    Column("external_id", String, nullable=False),
    Column("calculator_version", String, nullable=False),
    Column("idempotency_key", String, nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("derived_revision", BigInteger, nullable=False),
    Column("input_revision", BigInteger, nullable=False),
    Column("input_hash", String(64), nullable=False),
    Column("computed_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("platform", String, nullable=False, default=""),
    Column("shop_or_marketplace_id", String, nullable=False, default=""),
    Column("stream", String, nullable=False, default=""),
    Column("expected_revision", BigInteger, nullable=False, default=0),
    Column("resulting_revision", BigInteger, nullable=False, default=0),
    Column("actor", String, nullable=False, default=""),
    Column("request_hash", String(64), nullable=False, default="0" * 64),
    Column("result_json", JSON, nullable=False, default=dict),
)

projection_outbox = Table(
    "projection_outbox",
    metadata,
    Column(
        "outbox_id",
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    ),
    Column("org_id", String, nullable=False),
    Column("project_id", String, nullable=False),
    Column("workspace_id", String, nullable=False),
    Column("input_revision", BigInteger, nullable=False),
    Column("change_kind", String, nullable=False),
    Column("object_type", String, nullable=True),
    Column("external_id", String, nullable=True),
    Column("link_type", String, nullable=True),
    Column("source_external_id", String, nullable=True),
    Column("target_external_id", String, nullable=True),
    Column("platform", String, nullable=False),
    Column("shop_or_marketplace_id", String, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("event_key", String(64), nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("event_source", String, nullable=False),
    Column("authority_tx_id", String(64), nullable=False),
    Column("projected", Boolean, nullable=False, default=False),
    Column("projected_at", DateTime(timezone=True), nullable=True),
    Column("projection_error", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _db_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _apply_transaction_scope(
    conn: Connection, *, org_id: str, workspace_id: str
) -> None:
    """Bind a SQLAlchemy transaction to the canonical runtime role and GUCs."""
    if conn.dialect.name != "postgresql":
        return
    conn.execute(text("SET LOCAL ROLE aos_runtime"))
    conn.execute(
        text(
            "SELECT set_config('aos.org_id', :org_id, true), "
            "set_config('aos.project_id', :workspace_id, true)"
        ),
        {"org_id": org_id, "workspace_id": workspace_id},
    )


def _scope_clause(table: Table, command: BatchCommand):
    scope = command.scope
    return and_(
        table.c.org_id == scope.org_id,
        table.c.workspace_id == scope.workspace_id,
        table.c.platform == scope.platform,
        table.c.shop_or_marketplace_id == scope.shop_or_marketplace_id,
        table.c.stream == scope.stream,
    )


def _object_clause(identity: StorageIdentity, object_type: str):
    return and_(
        ecom_object.c.org_id == identity.org_id,
        ecom_object.c.workspace_id == identity.workspace_id,
        ecom_object.c.platform == identity.platform,
        ecom_object.c.shop_or_marketplace_id == identity.shop_or_marketplace_id,
        ecom_object.c.object_type == object_type,
        ecom_object.c.external_id == identity.external_id,
    )


def _link_clause(link: CoreLinkRecord):
    return and_(
        ecom_link.c.org_id == link.source.org_id,
        ecom_link.c.workspace_id == link.source.workspace_id,
        ecom_link.c.link_type == link.link_type,
        ecom_link.c.source_platform == link.source.platform,
        ecom_link.c.source_shop_or_marketplace_id == link.source.shop_or_marketplace_id,
        ecom_link.c.source_object_type == link.source_type,
        ecom_link.c.source_external_id == link.source.external_id,
        ecom_link.c.target_platform == link.target.platform,
        ecom_link.c.target_shop_or_marketplace_id == link.target.shop_or_marketplace_id,
        ecom_link.c.target_object_type == link.target_type,
        ecom_link.c.target_external_id == link.target.external_id,
    )


@dataclass(frozen=True)
class ProjectionEventEvidence:
    """Read-only exact event identity; never permission to execute a projection."""
    event_key: str
    payload_hash: str
    input_revision: int
    projected: bool


class EcomConsistencyStore:
    """Apply one normalized page atomically and advance its checkpoint by CAS."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._last_dangling_links: list[CoreLinkRecord] = []

    def apply_batch(self, command: BatchCommand) -> BatchResult:
        return self._apply_batch(command, strict_links=False)

    def apply_strict_link_batch(self, command: BatchCommand) -> BatchResult:
        """Commit only if every original link and authoritative event is current."""
        return self._apply_batch(command, strict_links=True)

    def apply_strict_link_retirement_batch(self, command: BatchCommand) -> BatchResult:
        """Retire exact active link payloads under the original transaction locks."""
        return self._apply_batch(command, strict_links=True, retire_links=True)

    def _apply_batch(self, command: BatchCommand, *, strict_links: bool, retire_links: bool = False) -> BatchResult:
        # Pydantic's frozen models are shallow: callers could otherwise mutate
        # nested lists/dicts after construction and bypass the scope and shape
        # validators.  Rebuild a detached, validated snapshot before hashing or
        # opening the transaction.
        command = BatchCommand.model_validate(command.model_dump(mode="python"))
        if strict_links and (command.objects or not command.links):
            raise EcomConsistencyError(
                "LINK_ONLY_BATCH_REQUIRED", "strict application requires a nonempty link-only batch"
            )
        if retire_links:
            for link in command.links:
                prior = link.properties.get("retirementExpectedPayloadHash")
                if (not link.is_deleted or type(prior) is not str or len(prior) != 64
                        or any(c not in "0123456789abcdef" for c in prior)):
                    raise EcomConsistencyError("RETIREMENT_COMMAND_REQUIRED", "tombstone with bound prior payload required")
        request_hash = command.request_hash()
        lock_key = self._idempotency_lock_key(command)
        process_lock = _PROCESS_IDEMPOTENCY_LOCKS[
            lock_key % len(_PROCESS_IDEMPOTENCY_LOCKS)
        ]
        try:
            with process_lock, self._engine.begin() as conn:
                _apply_transaction_scope(
                    conn,
                    org_id=command.scope.org_id,
                    workspace_id=command.scope.workspace_id,
                )
                self._lock_idempotency_key(conn, lock_key)
                strict_snapshot = None
                if strict_links:
                    strict_snapshot = self._lock_strict_link_records(conn, command)
                replay = self._get_receipt(conn, command)
                if replay is not None:
                    if not self._receipt_matches_request(
                        command=command,
                        receipt=replay,
                        request_hash=request_hash,
                    ):
                        raise EcomConsistencyError(
                            "IDEMPOTENCY_CONFLICT",
                            "idempotency key was already used with a different request",
                        )
                    if retire_links and replay["result"].get("retirementPreconditionChecked") != request_hash:
                        raise EcomConsistencyError("RETIREMENT_EVIDENCE_REQUIRED", "original retirement precondition evidence required")
                    if strict_links:
                        self._reconcile_base_events(conn, command, replay)
                    saved = dict(replay["result"])
                    saved["replayed"] = True
                    return BatchResult.model_validate(saved)

                if retire_links:
                    for link in command.links:
                        original = conn.execute(select(ecom_link.c.payload_hash, ecom_link.c.deleted_at)
                            .where(_link_clause(link))).mappings().first()
                        if (original is None or original["deleted_at"] is not None
                                or original["payload_hash"] != link.properties["retirementExpectedPayloadHash"]):
                            raise EcomConsistencyError("RETIREMENT_PRIOR_PAYLOAD_CHANGED", "exact active prior link payload required")

                counters = {
                    "objects_written": 0,
                    "objects_ignored": 0,
                    "objects_tombstoned": 0,
                    "links_written": 0,
                    "links_ignored": 0,
                    "links_tombstoned": 0,
                }

                # Phase 1: upsert all objects first (within the same transaction)
                for record in command.ordered_objects():
                    outcome = self._upsert_object(conn, record)
                    counters[outcome] += 1
                    if outcome in {"objects_written", "objects_tombstoned"}:
                        self._write_projection_event(
                            conn,
                            command=command,
                            outcome=outcome,
                            entity=record,
                            authority_tx_id=request_hash,
                        )

                # Phase 2: upsert links, collecting dangling links for DLQ
                # instead of aborting the entire batch
                dangling_links: list[CoreLinkRecord] = []
                for link in command.ordered_links():
                    if strict_snapshot is None:
                        source_exists = self._object_exists(
                            conn, link.source, link.source_type, allow_tombstone=link.is_deleted
                        )
                        target_exists = self._object_exists(
                            conn, link.target, link.target_type, allow_tombstone=link.is_deleted
                        )
                        existing = _NOT_PRELOADED
                    else:
                        endpoints, links = strict_snapshot
                        source_exists = self._locked_endpoint_exists(
                            endpoints, link.source, link.source_type, allow_tombstone=link.is_deleted
                        )
                        target_exists = self._locked_endpoint_exists(
                            endpoints, link.target, link.target_type, allow_tombstone=link.is_deleted
                        )
                        existing = links.get(self._link_identity(link))
                    if not source_exists or not target_exists:
                        dangling_links.append(link)
                        counters["links_ignored"] += 1
                        continue
                    outcome = self._upsert_link_checked(conn, link, existing=existing)
                    counters[outcome] += 1
                    if outcome in {"links_written", "links_tombstoned"}:
                        self._write_projection_event(
                            conn,
                            command=command,
                            outcome=outcome,
                            entity=link,
                            authority_tx_id=request_hash,
                        )

                # Store dangling link info for DLQ (accessible via get_dangling_links)
                if dangling_links:
                    self._last_dangling_links = dangling_links
                else:
                    self._last_dangling_links = []

                checkpoint_version = self._advance_checkpoint(conn, command)
                result = BatchResult(
                    **counters,
                    checkpoint_version=checkpoint_version,
                    checkpoint=command.next_checkpoint,
                )
                result_payload = result.model_dump(mode="json")
                if retire_links:
                    result_payload["retirementPreconditionChecked"] = request_hash
                conn.execute(
                    insert(ecom_ingest_receipt).values(
                        org_id=command.scope.org_id,
                        workspace_id=command.scope.workspace_id,
                        platform=command.scope.platform,
                        shop_or_marketplace_id=command.scope.shop_or_marketplace_id,
                        stream=command.scope.stream,
                        idempotency_key=command.idempotency_key,
                        request_hash=request_hash,
                        result=result_payload,
                        created_at=_utcnow(),
                    )
                )
                if strict_links:
                    # Validate inside the same transaction: ignored stale/dangling
                    # links must roll back the receipt, checkpoint and all writes.
                    self._reconcile_base_events(
                        conn, command, {"result": result_payload}
                    )
                return result
        except IntegrityError as exc:
            raise EcomConsistencyError(
                "CONCURRENT_WRITE_CONFLICT",
                "a concurrent write changed the consistency state",
            ) from exc

    @staticmethod
    def _link_identity(link: CoreLinkRecord) -> tuple[str, ...]:
        return (
            link.link_type,
            link.source.platform,
            link.source.shop_or_marketplace_id,
            link.source_type,
            link.source.external_id,
            link.target.platform,
            link.target.shop_or_marketplace_id,
            link.target_type,
            link.target.external_id,
        )

    @staticmethod
    def _endpoint_identity(identity: StorageIdentity, object_type: str) -> tuple[str, ...]:
        return (
            object_type,
            identity.platform,
            identity.shop_or_marketplace_id,
            identity.external_id,
        )

    @staticmethod
    def _locked_endpoint_exists(endpoints, identity: StorageIdentity, object_type: str,
                                *, allow_tombstone: bool) -> bool:
        row = endpoints.get(EcomConsistencyStore._endpoint_identity(identity, object_type))
        return row is not None and (allow_tombstone or row["deleted_at"] is None)

    @staticmethod
    def _lock_strict_link_records(conn: Connection, command: BatchCommand):
        # Preserve endpoint state until commit; lock endpoints before links,
        # matching the original object's cascade-write order.
        endpoint_keys = set()
        for link in command.links:
            for identity, object_type in ((link.source, link.source_type), (link.target, link.target_type)):
                endpoint_keys.add(EcomConsistencyStore._endpoint_identity(identity, object_type))
        endpoint_columns = (
            ecom_object.c.object_type,
            ecom_object.c.platform,
            ecom_object.c.shop_or_marketplace_id,
            ecom_object.c.external_id,
        )
        endpoint_rows = conn.execute(select(ecom_object).where(
            ecom_object.c.org_id == command.scope.org_id,
            ecom_object.c.workspace_id == command.scope.workspace_id,
            tuple_(*endpoint_columns).in_(sorted(endpoint_keys)),
        ).order_by(*endpoint_columns).with_for_update(read=True)).mappings().all()
        endpoints = {
            (row["object_type"], row["platform"], row["shop_or_marketplace_id"], row["external_id"]): row
            for row in endpoint_rows
        }

        link_columns = (
            ecom_link.c.link_type,
            ecom_link.c.source_platform,
            ecom_link.c.source_shop_or_marketplace_id,
            ecom_link.c.source_object_type,
            ecom_link.c.source_external_id,
            ecom_link.c.target_platform,
            ecom_link.c.target_shop_or_marketplace_id,
            ecom_link.c.target_object_type,
            ecom_link.c.target_external_id,
        )
        link_keys = sorted(EcomConsistencyStore._link_identity(link) for link in command.links)
        link_rows = conn.execute(select(ecom_link).where(
            ecom_link.c.org_id == command.scope.org_id,
            ecom_link.c.workspace_id == command.scope.workspace_id,
            tuple_(*link_columns).in_(link_keys),
        ).order_by(*link_columns).with_for_update()).mappings().all()
        links = {
            tuple(row[column.name] for column in link_columns): row
            for row in link_rows
        }
        return endpoints, links

    def read_committed_batch(self, command: BatchCommand) -> BatchResult | None:
        """Read exact committed evidence without replaying a batch or advancing it."""
        return self._read_committed_batch(command, retirement=False)

    def read_committed_link_retirement(self, command: BatchCommand) -> BatchResult | None:
        """Read a proven conditional retirement, never replay or write it."""
        return self._read_committed_batch(command, retirement=True)

    def _read_committed_batch(self, command: BatchCommand, *, retirement: bool) -> BatchResult | None:
        command = BatchCommand.model_validate(command.model_dump(mode="python"))
        with self._engine.begin() as conn:
            _apply_transaction_scope(conn, org_id=command.scope.org_id, workspace_id=command.scope.workspace_id)
            receipt = self._get_receipt(conn, command, for_update=False)
            if receipt is None:
                return None
            if not self._receipt_matches_request(command=command, receipt=receipt, request_hash=command.request_hash()):
                raise EcomConsistencyError("IDEMPOTENCY_CONFLICT", "stored receipt does not match the original command")
            if retirement:
                if receipt["result"].get("retirementPreconditionChecked") != command.request_hash():
                    raise EcomConsistencyError("RETIREMENT_EVIDENCE_REQUIRED", "original retirement precondition evidence required")
                self._reconcile_base_events(conn, command, receipt)
            return BatchResult.model_validate(receipt["result"])

    def read_committed_batch_revision(self, command: BatchCommand) -> int:
        """Return the original batch outbox boundary, never the latest tenant revision."""
        command = BatchCommand.model_validate(command.model_dump(mode="python"))
        with self._engine.begin() as conn:
            _apply_transaction_scope(conn, org_id=command.scope.org_id, workspace_id=command.scope.workspace_id)
            receipt = self._get_receipt(conn, command, for_update=False)
            if receipt is None:
                raise EcomConsistencyError("BASE_RECEIPT_REQUIRED", "committed base receipt required")
            if not self._receipt_matches_request(command=command, receipt=receipt, request_hash=command.request_hash()):
                raise EcomConsistencyError("IDEMPOTENCY_CONFLICT", "stored receipt does not match the original command")
            events = self._reconcile_base_events(conn,command,receipt)
            return max(int(row['input_revision']) for row in events)

    @staticmethod
    def _base_projection_event_key(command, entity, outcome):
        identity = ((entity.object_type,entity.identity.external_id) if isinstance(entity,CoreObjectRecord)
                    else (entity.link_type,entity.source_type,entity.source.external_id,entity.target_type,entity.target.external_id))
        material = "\x1f".join((*command.scope.key(),command.idempotency_key,outcome,*identity))
        return hashlib.sha256(material.encode('utf-8')).hexdigest()

    def _reconcile_base_events(self, conn, command, receipt):
        """Prove exact current records and their effective authoritative events."""
        result = BatchResult.model_validate(receipt['result'])
        object_count = result.objects_written+result.objects_tombstoned+result.objects_ignored
        link_count = result.links_written+result.links_tombstoned+result.links_ignored
        written = result.objects_written+result.objects_tombstoned+result.links_written+result.links_tombstoned
        if object_count != len(command.objects) or link_count != len(command.links):
            raise EcomConsistencyError('BASE_RECEIPT_COUNT_DRIFT','base receipt counts do not match original command')
        scope_filter = (
            projection_outbox.c.org_id == command.scope.org_id,
            projection_outbox.c.workspace_id == command.scope.workspace_id,
            projection_outbox.c.platform == command.scope.platform,
            projection_outbox.c.shop_or_marketplace_id == command.scope.shop_or_marketplace_id,
            projection_outbox.c.event_source == 'authoritative_store',
        )
        batch_keys = [self._base_projection_event_key(command,entity,
            ('objects_' if isinstance(entity,CoreObjectRecord) else 'links_')+('tombstoned' if entity.is_deleted else 'written'))
            for entity in (*command.objects,*command.links)]
        actual = conn.execute(select(func.count()).select_from(projection_outbox).where(
            *scope_filter,projection_outbox.c.event_key.in_(batch_keys),
            projection_outbox.c.change_kind.in_(('objects_written','objects_tombstoned','links_written','links_tombstoned')),
        )).scalar_one()
        if actual != written:
            raise EcomConsistencyError('BASE_OUTBOX_INCOMPLETE','base outbox evidence is incomplete')

        objects = tuple(command.objects)
        links = tuple(command.links)
        current_objects = {}
        if objects:
            rows = conn.execute(select(
                ecom_object.c.object_type,
                ecom_object.c.external_id,
                ecom_object.c.payload_hash,
            ).where(
                ecom_object.c.org_id == command.scope.org_id,
                ecom_object.c.workspace_id == command.scope.workspace_id,
                ecom_object.c.platform == command.scope.platform,
                ecom_object.c.shop_or_marketplace_id == command.scope.shop_or_marketplace_id,
                ecom_object.c.object_type.in_({item.object_type for item in objects}),
                ecom_object.c.external_id.in_({item.identity.external_id for item in objects}),
            )).mappings().all()
            current_objects = {
                (row['object_type'], row['external_id']): row['payload_hash'] for row in rows
            }

        current_links = {}
        endpoints = {}
        if links:
            rows = conn.execute(select(
                ecom_link.c.link_type,
                ecom_link.c.source_object_type,
                ecom_link.c.source_external_id,
                ecom_link.c.target_object_type,
                ecom_link.c.target_external_id,
                ecom_link.c.payload_hash,
            ).where(
                ecom_link.c.org_id == command.scope.org_id,
                ecom_link.c.workspace_id == command.scope.workspace_id,
                ecom_link.c.source_platform == command.scope.platform,
                ecom_link.c.source_shop_or_marketplace_id == command.scope.shop_or_marketplace_id,
                ecom_link.c.target_platform == command.scope.platform,
                ecom_link.c.target_shop_or_marketplace_id == command.scope.shop_or_marketplace_id,
                ecom_link.c.link_type.in_({item.link_type for item in links}),
                ecom_link.c.source_object_type.in_({item.source_type for item in links}),
                ecom_link.c.source_external_id.in_({item.source.external_id for item in links}),
                ecom_link.c.target_object_type.in_({item.target_type for item in links}),
                ecom_link.c.target_external_id.in_({item.target.external_id for item in links}),
            )).mappings().all()
            current_links = {
                (row['link_type'], row['source_object_type'], row['source_external_id'],
                 row['target_object_type'], row['target_external_id']): row['payload_hash']
                for row in rows
            }
            endpoint_types = {item.source_type for item in links} | {item.target_type for item in links}
            endpoint_ids = ({item.source.external_id for item in links}
                            | {item.target.external_id for item in links})
            rows = conn.execute(select(
                ecom_object.c.object_type,
                ecom_object.c.external_id,
                ecom_object.c.deleted_at,
            ).where(
                ecom_object.c.org_id == command.scope.org_id,
                ecom_object.c.workspace_id == command.scope.workspace_id,
                ecom_object.c.platform == command.scope.platform,
                ecom_object.c.shop_or_marketplace_id == command.scope.shop_or_marketplace_id,
                ecom_object.c.object_type.in_(endpoint_types),
                ecom_object.c.external_id.in_(endpoint_ids),
            )).mappings().all()
            endpoints = {
                (row['object_type'], row['external_id']): row['deleted_at'] for row in rows
            }

        expected_events = []
        for entity in (*objects, *links):
            is_object = isinstance(entity, CoreObjectRecord)
            if is_object:
                current = current_objects.get((entity.object_type, entity.identity.external_id))
            else:
                identity = (entity.link_type, entity.source_type, entity.source.external_id,
                            entity.target_type, entity.target.external_id)
                current = current_links.get(identity)
                for endpoint in ((entity.source_type, entity.source.external_id),
                                 (entity.target_type, entity.target.external_id)):
                    if endpoint not in endpoints or (not entity.is_deleted and endpoints[endpoint] is not None):
                        raise EcomConsistencyError('BASE_RECORD_NOT_CURRENT',
                                                   'original base record has unavailable link endpoints')
            if current != entity.payload_hash():
                raise EcomConsistencyError('BASE_RECORD_NOT_CURRENT',
                                           'original base record is missing or has been superseded')
            outcome = ('objects_' if is_object else 'links_') + ('tombstoned' if entity.is_deleted else 'written')
            payload = {'schemaVersion': 1, 'entityKind': 'object' if is_object else 'link',
                       'changeKind': outcome, 'record': entity.model_dump(mode='json')}
            if is_object:
                payload.update(objectType=entity.object_type,
                               identity=entity.identity.model_dump(mode='json'))
            digest = hashlib.sha256(json.dumps(_jsonable(payload), ensure_ascii=False,
                sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            expected_events.append((outcome, digest))

        candidates = conn.execute(select(
            projection_outbox.c.event_key,
            projection_outbox.c.payload_hash,
            projection_outbox.c.input_revision,
            projection_outbox.c.projected,
            projection_outbox.c.change_kind,
        ).where(
            *scope_filter,
            projection_outbox.c.change_kind.in_(('objects_written', 'objects_tombstoned',
                                                  'links_written', 'links_tombstoned')),
            projection_outbox.c.payload_hash.in_({digest for _, digest in expected_events}),
        )).mappings().all()
        grouped = {}
        for row in candidates:
            grouped.setdefault((row['change_kind'], row['payload_hash']), []).append(row)
        events = {}
        for outcome, digest in expected_events:
            matches = grouped.get((outcome, digest), ())
            if len(matches) != 1 or int(matches[0]['input_revision']) <= 0:
                raise EcomConsistencyError('BASE_OUTBOX_INCOMPLETE','exact original base outbox evidence is missing or ambiguous')
            events[matches[0]['event_key']] = matches[0]
        return list(events.values())

    def get_derived_revision(
        self, identity: StorageIdentity, object_type: str
    ) -> int:
        with self._engine.begin() as conn:
            _apply_transaction_scope(
                conn, org_id=identity.org_id, workspace_id=identity.workspace_id
            )
            value = conn.execute(
                select(ecom_object.c.derived_revision).where(
                    _object_clause(identity, object_type)
                )
            ).scalar_one_or_none()
            if value is None:
                raise EcomConsistencyError("OBJECT_NOT_FOUND", "derived target not found")
            return int(value)

    def get_latest_authoritative_revision(self, identity: StorageIdentity) -> int:
        """返回 scope 内最新非派生权威 Outbox revision，作为派生输入水位。"""
        with self._engine.begin() as conn:
            _apply_transaction_scope(
                conn, org_id=identity.org_id, workspace_id=identity.workspace_id
            )
            value = conn.execute(
                select(func.coalesce(func.max(projection_outbox.c.input_revision), 0)).where(
                    and_(
                        projection_outbox.c.org_id == identity.org_id,
                        projection_outbox.c.workspace_id == identity.workspace_id,
                        projection_outbox.c.event_source == "authoritative_store",
                        projection_outbox.c.change_kind.notin_(
                            ("derived_upsert", "derived_tombstoned")
                        ),
                    )
                )
            ).scalar_one()
            return int(value)

    @staticmethod
    def _derived_receipt_id(command: DerivedMetricCommand) -> str:
        identity = command.identity
        return hashlib.sha256("\x1f".join((identity.org_id,identity.workspace_id,identity.platform,
            identity.shop_or_marketplace_id,command.stream,command.idempotency_key)).encode("utf-8")).hexdigest()

    @classmethod
    def _read_derived_receipt(cls, conn, command):
        row = conn.execute(select(ecom_derived_receipt).where(
            ecom_derived_receipt.c.org_id == command.identity.org_id,
            ecom_derived_receipt.c.project_id == command.identity.workspace_id,
            ecom_derived_receipt.c.receipt_id == cls._derived_receipt_id(command),
        )).mappings().first()
        if row is not None and row['request_hash'] != command.request_hash():
            raise EcomConsistencyError('IDEMPOTENCY_CONFLICT','derived idempotency key was reused with a different request')
        return row

    def read_committed_derived(self, command: DerivedMetricCommand) -> DerivedMetricResult | None:
        """Read exact evidence without advancing derived CAS or creating an event."""
        command = DerivedMetricCommand.model_validate(command.model_dump(mode='python'))
        with self._engine.begin() as conn:
            _apply_transaction_scope(conn,org_id=command.identity.org_id,workspace_id=command.identity.workspace_id)
            row = self._read_derived_receipt(conn,command)
            return None if row is None else DerivedMetricResult.model_validate(row['result_json'])

    def read_batch_projection_completion(self, command: BatchCommand, derived_commands) -> dict[str,int]:
        evidence=self.read_batch_projection_evidence(command,derived_commands)
        projected=sum(item.projected for item in evidence)
        return {'expected':len(evidence),'projected':projected,'pending':len(evidence)-projected}

    def read_batch_projection_evidence(self, command: BatchCommand, derived_commands) -> tuple[ProjectionEventEvidence,...]:
        """Reconcile exact events; caller must pass the full saved derived list.

        These immutable identities are evidence, not an execution grant. A writer
        must still hold current authorization and revalidate the event rows.
        """
        command = BatchCommand.model_validate(command.model_dump(mode='python'))
        derived = [DerivedMetricCommand.model_validate(item.model_dump(mode='python')) for item in derived_commands]
        allowed = {(item.object_type,item.identity.scoped_key()) for item in command.objects if not item.is_deleted}
        seen = set()
        for item in derived:
            key = (item.object_type,item.identity.scoped_key())
            if key not in allowed or key in seen or item.stream != command.scope.stream:
                raise EcomConsistencyError('DERIVED_BINDING_DRIFT','derived command binding does not match original batch')
            seen.add(key)
        with self._engine.begin() as conn:
            _apply_transaction_scope(conn,org_id=command.scope.org_id,workspace_id=command.scope.workspace_id)
            base = self._get_receipt(conn,command,for_update=False)
            if base is None or not self._receipt_matches_request(command=command,receipt=base,request_hash=command.request_hash()):
                raise EcomConsistencyError('BASE_RECEIPT_REQUIRED','exact base receipt required')
            base_events = self._reconcile_base_events(conn,command,base)
            revision = max(int(row['input_revision']) for row in base_events)
            if any(item.input_revision != revision for item in derived):
                raise EcomConsistencyError('DERIVED_BINDING_DRIFT','derived command binding does not match original batch')
            groups = []
            for item in derived:
                receipt = self._read_derived_receipt(conn,item)
                if receipt is None:
                    raise EcomConsistencyError('DERIVED_RECEIPT_REQUIRED','committed derived receipt required')
                saved = DerivedMetricResult.model_validate(receipt['result_json'])
                if saved.updated:
                    groups.append(((receipt['request_hash'],),1))
                else:
                    # A no-change receipt has no new event, but the effective
                    # prior derived write must still have reached projection.
                    candidates = conn.execute(select(ecom_derived_receipt.c.request_hash,ecom_derived_receipt.c.result_json).where(
                        ecom_derived_receipt.c.org_id == item.identity.org_id,
                        ecom_derived_receipt.c.project_id == item.identity.workspace_id,
                        ecom_derived_receipt.c.object_type == item.object_type,
                        ecom_derived_receipt.c.external_id == item.identity.external_id,
                        ecom_derived_receipt.c.derived_revision == saved.resulting_revision,
                        ecom_derived_receipt.c.input_revision == item.input_revision,
                        ecom_derived_receipt.c.input_hash == item.input_hash,
                        ecom_derived_receipt.c.payload_hash == saved.payload_hash,
                    )).mappings().all()
                    hashes = tuple(row['request_hash'] for row in candidates if row['result_json'].get('updated') is True)
                    if not hashes:
                        raise EcomConsistencyError('DERIVED_PREDECESSOR_REQUIRED','effective derived write receipt required')
                    groups.append((hashes,1))
            all_events=list(base_events)
            for authority,count in groups:
                events = conn.execute(select(projection_outbox.c.event_key,projection_outbox.c.payload_hash,
                    projection_outbox.c.input_revision,projection_outbox.c.projected).where(
                    projection_outbox.c.org_id == command.scope.org_id,
                    projection_outbox.c.workspace_id == command.scope.workspace_id,
                    projection_outbox.c.platform == command.scope.platform,
                    projection_outbox.c.shop_or_marketplace_id == command.scope.shop_or_marketplace_id,
                    projection_outbox.c.event_source == 'authoritative_store',
                    projection_outbox.c.authority_tx_id.in_(authority),
                )).mappings().all()
                if len(events) != count:
                    raise EcomConsistencyError('OUTBOX_INCOMPLETE','original command outbox evidence is incomplete')
                all_events.extend(events)
            if len({row['event_key'] for row in all_events})!=len(all_events):
                raise EcomConsistencyError('OUTBOX_INCOMPLETE','original event identities are ambiguous')
            return tuple(ProjectionEventEvidence(row['event_key'],row['payload_hash'],int(row['input_revision']),row['projected'] is True)
                         for row in sorted(all_events,key=lambda row:(int(row['input_revision']),row['event_key'])))

    def update_derived_metrics(
        self, command: DerivedMetricCommand, *, expected_base: CoreObjectRecord | None = None
    ) -> DerivedMetricResult:
        """O1 §5.2.10：CAS、Receipt 和 Outbox 同事务的派生更新。"""
        command = DerivedMetricCommand.model_validate(command.model_dump(mode="python"))
        identity = command.identity
        if expected_base is not None:
            expected_base = CoreObjectRecord.model_validate(expected_base.model_dump(mode='python'))
            if expected_base.identity != identity or expected_base.object_type != command.object_type or expected_base.is_deleted:
                raise EcomConsistencyError('DERIVED_BASE_BINDING_MISMATCH','expected base identity does not match derived target')
        request_hash = command.request_hash()
        receipt_id = self._derived_receipt_id(command)
        lock_key = int.from_bytes(bytes.fromhex(receipt_id[:16]), byteorder="big", signed=True)
        process_lock = _PROCESS_IDEMPOTENCY_LOCKS[
            lock_key % len(_PROCESS_IDEMPOTENCY_LOCKS)
        ]
        with process_lock, self._engine.begin() as conn:
            _apply_transaction_scope(
                conn, org_id=identity.org_id, workspace_id=identity.workspace_id
            )
            self._lock_idempotency_key(conn, lock_key)
            receipt = conn.execute(
                select(ecom_derived_receipt).where(
                    and_(
                        ecom_derived_receipt.c.org_id == identity.org_id,
                        ecom_derived_receipt.c.project_id == identity.workspace_id,
                        ecom_derived_receipt.c.receipt_id == receipt_id,
                    )
                )
            ).mappings().first()
            if receipt is not None:
                if receipt["request_hash"] != request_hash:
                    raise EcomConsistencyError(
                        "IDEMPOTENCY_CONFLICT",
                        "derived idempotency key was reused with a different request",
                    )
                saved = dict(receipt["result_json"])
                saved["replayed"] = True
                return DerivedMetricResult.model_validate(saved)

            stored = conn.execute(
                select(ecom_object)
                .where(_object_clause(identity, command.object_type))
                .with_for_update()
            ).mappings().first()
            if stored is None:
                raise EcomConsistencyError("OBJECT_NOT_FOUND", "derived target not found")
            if stored["deleted_at"] is not None:
                raise EcomConsistencyError("OBJECT_TOMBSTONED", "derived target is deleted")

            if expected_base is not None and stored['payload_hash'] != expected_base.payload_hash():
                raise EcomConsistencyError('DERIVED_BASE_VERSION_DRIFT','expected base payload changed before derived write')

            current_revision = int(stored["derived_revision"] or 0)
            if current_revision != command.expected_derived_revision:
                raise EcomConsistencyError(
                    "DERIVED_REVISION_CONFLICT",
                    "derived revision CAS failed",
                    details={"currentRevision": current_revision},
                )
            stored_input_revision = stored["derived_input_revision"]
            stored_input_hash = stored["derived_input_hash"]
            stored_computed_at = stored["derived_computed_at"]
            if stored_input_revision is not None:
                if command.input_revision < int(stored_input_revision):
                    raise EcomConsistencyError(
                        "DERIVED_INPUT_REGRESSION", "derived input revision regressed"
                    )
                if (
                    command.input_revision == int(stored_input_revision)
                    and stored_input_hash != command.input_hash
                ):
                    raise EcomConsistencyError(
                        "DERIVED_INPUT_CONFLICT",
                        "same derived input revision has a different hash",
                    )
                if (
                    command.input_revision == int(stored_input_revision)
                    and stored_input_hash == command.input_hash
                    and stored_computed_at is not None
                    and command.computed_at < _db_time(stored_computed_at)
                ):
                    raise EcomConsistencyError(
                        "DERIVED_COMPUTED_AT_REGRESSION",
                        "derived computation time regressed",
                    )

            payload = dict(command.derived_props)
            payload_json = json.dumps(
                _jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            unchanged = (
                dict(stored["derived_payload"] or {}) == payload
                and stored_input_revision == command.input_revision
                and stored_input_hash == command.input_hash
                and stored_computed_at is not None
                and _db_time(stored_computed_at) == command.computed_at
            )
            resulting_revision = current_revision if unchanged else current_revision + 1
            if not unchanged:
                conn.execute(
                    update(ecom_object)
                    .where(_object_clause(identity, command.object_type))
                    .values(
                        derived_revision=resulting_revision,
                        derived_input_revision=command.input_revision,
                        derived_input_hash=command.input_hash,
                        derived_computed_at=command.computed_at,
                        derived_payload=payload,
                        derived_payload_hash=payload_hash,
                        updated_at=_utcnow(),
                    )
                )
                effective = dict(stored["properties"] or {})
                effective.update(payload)
                self._write_derived_projection_event(
                    conn,
                    command=command,
                    stored=stored,
                    effective_properties=effective,
                    authority_tx_id=request_hash,
                )

            result = DerivedMetricResult(
                updated=not unchanged,
                resulting_revision=resulting_revision,
                input_revision=command.input_revision,
                payload_hash=payload_hash,
            )
            conn.execute(
                insert(ecom_derived_receipt).values(
                    org_id=identity.org_id,
                    project_id=identity.workspace_id,
                    workspace_id=identity.workspace_id,
                    receipt_id=receipt_id,
                    object_type=command.object_type,
                    external_id=identity.external_id,
                    calculator_version=command.calculator_version,
                    idempotency_key=command.idempotency_key,
                    payload_hash=payload_hash,
                    derived_revision=resulting_revision,
                    input_revision=command.input_revision,
                    input_hash=command.input_hash,
                    computed_at=command.computed_at,
                    created_at=_utcnow(),
                    platform=identity.platform,
                    shop_or_marketplace_id=identity.shop_or_marketplace_id,
                    stream=command.stream,
                    expected_revision=command.expected_derived_revision,
                    resulting_revision=resulting_revision,
                    actor=command.actor,
                    request_hash=request_hash,
                    result_json=result.model_dump(mode="json"),
                )
            )
            return result

    def get_last_dangling_links(self) -> list[CoreLinkRecord]:
        """Return dangling links from the last apply_batch call (for DLQ)."""
        return getattr(self, "_last_dangling_links", [])

    def get_object(
        self, identity: StorageIdentity, object_type: str
    ) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            _apply_transaction_scope(
                conn, org_id=identity.org_id, workspace_id=identity.workspace_id
            )
            row = (
                conn.execute(
                    select(ecom_object).where(_object_clause(identity, object_type))
                )
                .mappings()
                .first()
            )
            return dict(row) if row else None

    def get_checkpoint(self, command: BatchCommand) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            _apply_transaction_scope(
                conn,
                org_id=command.scope.org_id,
                workspace_id=command.scope.workspace_id,
            )
            row = (
                conn.execute(
                    select(ecom_sync_checkpoint).where(
                        _scope_clause(ecom_sync_checkpoint, command)
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row else None

    def list_links(
        self,
        *,
        org_id: str,
        workspace_id: str,
        platform: str,
        shop_or_marketplace_id: str,
    ) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            _apply_transaction_scope(conn, org_id=org_id, workspace_id=workspace_id)
            rows = conn.execute(
                select(ecom_link).where(
                    and_(
                        ecom_link.c.org_id == org_id,
                        ecom_link.c.workspace_id == workspace_id,
                        ecom_link.c.source_platform == platform,
                        ecom_link.c.source_shop_or_marketplace_id
                        == shop_or_marketplace_id,
                    )
                )
            ).mappings()
            return [dict(row) for row in rows]

    def read_active_links_for_rows(self, sync_scope: SyncScope, selectors: tuple, *, limit: int = 24000) -> tuple:
        """Bounded present-row query; an empty selection never means all rows."""
        if type(sync_scope) is not SyncScope or type(selectors) is not tuple or len(selectors) > 32:
            raise ValueError('exact scope and bounded row selectors required')
        sync_scope = SyncScope.model_validate(sync_scope.model_dump())
        if type(limit) is not int or not 1 <= limit <= 24000:
            raise ValueError('bounded active relationship limit required')
        clauses = []
        for selector in selectors:
            if type(selector) is not tuple or len(selector) != 4:
                raise ValueError('exact relationship row selector required')
            link_type, side, object_type, identities = selector
            if (side not in ('source', 'target') or type(identities) is not tuple
                    or not 1 <= len(identities) < 1000
                    or any(type(v) is not str or not v or v != v.strip() or len(v) > 512
                           for v in (link_type, object_type, *identities))):
                raise ValueError('canonical nonempty relationship row selector required')
            clauses.append(and_(ecom_link.c.link_type == link_type,
                ecom_link.c[side + '_object_type'] == object_type,
                ecom_link.c[side + '_external_id'].in_(identities)))
        if not clauses:
            return ()
        with self._engine.begin() as conn:
            _apply_transaction_scope(conn, org_id=sync_scope.org_id, workspace_id=sync_scope.workspace_id)
            rows = conn.execute(select(ecom_link).where(
                ecom_link.c.org_id == sync_scope.org_id,
                ecom_link.c.workspace_id == sync_scope.workspace_id,
                ecom_link.c.source_platform == sync_scope.platform,
                ecom_link.c.target_platform == sync_scope.platform,
                ecom_link.c.source_shop_or_marketplace_id == sync_scope.shop_or_marketplace_id,
                ecom_link.c.target_shop_or_marketplace_id == sync_scope.shop_or_marketplace_id,
                ecom_link.c.deleted_at.is_(None), or_(*clauses),
            ).order_by(ecom_link.c.link_type, ecom_link.c.source_object_type,
                ecom_link.c.source_external_id, ecom_link.c.target_object_type,
                ecom_link.c.target_external_id).limit(limit + 1)).mappings().all()
            if len(rows) > limit:
                raise EcomConsistencyError('RELATIONSHIP_AUDIT_LIMIT_EXCEEDED', 'present-row relationship query exceeds bound')
            return tuple(dict(row) for row in rows)

    @staticmethod
    def _idempotency_lock_key(command: BatchCommand) -> int:
        material = "\x1f".join((*command.scope.key(), command.idempotency_key))
        raw = hashlib.sha256(material.encode("utf-8")).digest()[:8]
        return int.from_bytes(raw, byteorder="big", signed=True)

    @staticmethod
    def _lock_idempotency_key(conn: Connection, lock_key: int) -> None:
        if conn.dialect.name == "postgresql":
            conn.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": lock_key},
            )

    @staticmethod
    def _get_receipt(conn: Connection, command: BatchCommand, *, for_update: bool = True):
        query = select(ecom_ingest_receipt).where(
            and_(_scope_clause(ecom_ingest_receipt, command),
                 ecom_ingest_receipt.c.idempotency_key == command.idempotency_key)
        )
        if for_update:
            query = query.with_for_update()
        return conn.execute(query).mappings().first()

    @staticmethod
    def _receipt_matches_request(
        *,
        command: BatchCommand,
        receipt: Mapping[str, Any],
        request_hash: str,
    ) -> bool:
        stored_hash = str(receipt["request_hash"])
        if stored_hash == request_hash:
            return True

        # Receipts written before BI-W10 included the transaction CAS guard in
        # the request hash. The original expected version is recoverable from
        # the committed result only; no key-only or payload-relaxed fallback is
        # allowed.
        try:
            saved = BatchResult.model_validate(receipt["result"])
        except (TypeError, ValueError):
            return False
        original_expected_version = saved.checkpoint_version - 1
        if original_expected_version < 0:
            return False
        return stored_hash == command.legacy_request_hash(
            expected_checkpoint_version=original_expected_version
        )

    def _upsert_object(self, conn: Connection, record: CoreObjectRecord) -> str:
        clause = _object_clause(record.identity, record.object_type)
        existing = (
            conn.execute(select(ecom_object).where(clause).with_for_update())
            .mappings()
            .first()
        )
        payload_hash = record.payload_hash()
        incoming_time = record.source_updated_at
        now = _utcnow()

        if existing:
            stored_time = _db_time(existing["source_updated_at"])
            if incoming_time < stored_time:
                return "objects_ignored"
            if incoming_time == stored_time:
                if existing["payload_hash"] == payload_hash:
                    return "objects_ignored"
                # O1-A/P12 一次性兼容门：旧执行器把冻结的派生键
                # 写进 properties。仅当剔除该 ObjectType 的白名单派生键
                # 后基础记录完全相同，才允许收敛为新基础 payload。
                # 其他任何同版本差异仍 fail-closed。
                legacy_properties = dict(existing["properties"] or {})
                for key in DERIVED_PROPERTIES.get(record.object_type, frozenset()):
                    legacy_properties.pop(key, None)
                incoming_base_properties = dict(record.properties)
                for key in DERIVED_PROPERTIES.get(record.object_type, frozenset()):
                    incoming_base_properties.pop(key, None)
                additive_schema_upgrade = (
                    record.schema_version > int(existing["schema_version"])
                    and all(
                        key in incoming_base_properties
                        and incoming_base_properties[key] == value
                        for key, value in legacy_properties.items()
                    )
                    and existing["source_timezone"] == record.source_timezone
                    and existing["canonical_status"] == record.status.canonical_value
                    and existing["raw_status"] == record.status.raw_status
                    and (existing["deleted_at"] is not None) == record.is_deleted
                )
                # P08 隐私最小化一次性收敛：历史 CustomerLite 可能在同一源
                # 版本留下了已禁止的 PII 键。仅 schema v2 以上、且去掉白名单
                # PII 后其余所有键值完全一致时，允许删除这些键；绝不放宽到
                # 任意同版本 payload 差异。
                pii_redaction_keys = frozenset(
                    {
                        "mobile", "wx_openid", "nickname", "avatar",
                        "reg_address", "last_login_ip", "password", "pay_password",
                    }
                )
                legacy_without_pii = {
                    key: value
                    for key, value in dict(existing["properties"] or {}).items()
                    if key not in pii_redaction_keys
                }
                pii_redaction_upgrade = (
                    record.object_type == "CustomerLite"
                    and record.schema_version >= 2
                    and record.schema_version > int(existing["schema_version"])
                    and legacy_without_pii == dict(record.properties)
                    and existing["source_timezone"] == record.source_timezone
                    and existing["canonical_status"] == record.status.canonical_value
                    and existing["raw_status"] == record.status.raw_status
                    and (existing["deleted_at"] is not None) == record.is_deleted
                )
                if (
                    legacy_properties == dict(record.properties)
                    and existing["source_timezone"] == record.source_timezone
                    and existing["canonical_status"] == record.status.canonical_value
                    and existing["raw_status"] == record.status.raw_status
                    and int(existing["schema_version"]) == record.schema_version
                    and (existing["deleted_at"] is not None) == record.is_deleted
                ) or additive_schema_upgrade or pii_redaction_upgrade:
                    conn.execute(
                        update(ecom_object)
                        .where(clause)
                        .values(
                            properties=dict(record.properties),
                            schema_version=record.schema_version,
                            payload_hash=payload_hash,
                            updated_at=now,
                        )
                    )
                    return "objects_written"
                raise EcomConsistencyError(
                    "SOURCE_VERSION_CONFLICT",
                    "same source version has a different object payload",
                    details={"objectType": record.object_type},
                )
            conn.execute(
                update(ecom_object)
                .where(clause)
                .values(
                    **self._object_values(record, payload_hash, now, created_at=None)
                )
            )
        else:
            conn.execute(
                insert(ecom_object).values(
                    org_id=record.identity.org_id,
                    workspace_id=record.identity.workspace_id,
                    platform=record.identity.platform,
                    shop_or_marketplace_id=record.identity.shop_or_marketplace_id,
                    object_type=record.object_type,
                    external_id=record.identity.external_id,
                    **self._object_values(record, payload_hash, now, created_at=now),
                )
            )

        if record.is_deleted:
            self._tombstone_attached_links(
                conn, record.identity, record.object_type, incoming_time
            )
            return "objects_tombstoned"
        return "objects_written"

    @staticmethod
    def _object_values(
        record: CoreObjectRecord,
        payload_hash: str,
        now: datetime,
        *,
        created_at: datetime | None,
    ) -> dict[str, Any]:
        values: dict[str, Any] = {
            "properties": _jsonable(record.properties),
            "source_updated_at": record.source_updated_at,
            "source_timezone": record.source_timezone,
            "canonical_status": record.status.canonical_value,
            "raw_status": record.status.raw_status,
            "schema_version": record.schema_version,
            "payload_hash": payload_hash,
            "deleted_at": record.source_updated_at if record.is_deleted else None,
            "updated_at": now,
        }
        if created_at is not None:
            values["created_at"] = created_at
        return values

    @staticmethod
    def _object_exists(
        conn: Connection,
        identity: StorageIdentity,
        object_type: str,
        *,
        allow_tombstone: bool,
    ) -> bool:
        query = select(ecom_object.c.external_id).where(
            _object_clause(identity, object_type)
        )
        if not allow_tombstone:
            query = query.where(ecom_object.c.deleted_at.is_(None))
        return conn.execute(query).first() is not None

    def _upsert_link(self, conn: Connection, link: CoreLinkRecord) -> str:
        """Original method: checks existence then delegates to _upsert_link_checked.
        Kept for backward compatibility and direct-call scenarios.
        """
        if not self._object_exists(
            conn, link.source, link.source_type, allow_tombstone=link.is_deleted
        ) or not self._object_exists(
            conn, link.target, link.target_type, allow_tombstone=link.is_deleted
        ):
            raise EcomConsistencyError(
                "DANGLING_LINK",
                "link endpoints must exist in the same committed tenant scope",
                details={"linkType": link.link_type},
            )
        return self._upsert_link_checked(conn, link)

    def _upsert_link_checked(self, conn: Connection, link: CoreLinkRecord,
                             *, existing=_NOT_PRELOADED) -> str:
        """Upsert link after endpoint existence is already verified (by apply_batch)."""

        clause = _link_clause(link)
        if existing is _NOT_PRELOADED:
            existing = (
                conn.execute(select(ecom_link).where(clause).with_for_update())
                .mappings()
                .first()
            )
        payload_hash = link.payload_hash()
        now = _utcnow()
        values = {
            "properties": _jsonable(link.properties),
            "source_updated_at": link.source_updated_at,
            "payload_hash": payload_hash,
            "deleted_at": link.source_updated_at if link.is_deleted else None,
            "updated_at": now,
        }
        if existing:
            stored_time = _db_time(existing["source_updated_at"])
            if link.source_updated_at < stored_time:
                return "links_ignored"
            if link.source_updated_at == stored_time:
                if existing["payload_hash"] == payload_hash:
                    return "links_ignored"
                raise EcomConsistencyError(
                    "SOURCE_VERSION_CONFLICT",
                    "same source version has a different link payload",
                    details={"linkType": link.link_type},
                )
            stored_deleted_at = existing["deleted_at"]
            if stored_deleted_at is not None:
                tombstone_time = _db_time(stored_deleted_at)
                if link.source_updated_at <= tombstone_time:
                    return "links_ignored"
            conn.execute(update(ecom_link).where(clause).values(**values))
        else:
            conn.execute(
                insert(ecom_link).values(
                    org_id=link.source.org_id,
                    workspace_id=link.source.workspace_id,
                    link_type=link.link_type,
                    source_platform=link.source.platform,
                    source_shop_or_marketplace_id=link.source.shop_or_marketplace_id,
                    source_object_type=link.source_type,
                    source_external_id=link.source.external_id,
                    target_platform=link.target.platform,
                    target_shop_or_marketplace_id=link.target.shop_or_marketplace_id,
                    target_object_type=link.target_type,
                    target_external_id=link.target.external_id,
                    created_at=now,
                    **values,
                )
            )
        return "links_tombstoned" if link.is_deleted else "links_written"

    @staticmethod
    def _next_projection_revision(conn: Connection) -> int:
        if conn.dialect.name == "postgresql":
            return int(
                conn.execute(
                    text("SELECT nextval('projection_input_revision_seq')")
                ).scalar_one()
            )
        return int(
            conn.execute(
                select(func.coalesce(func.max(projection_outbox.c.input_revision), 0) + 1)
            ).scalar_one()
        )

    @classmethod
    def _write_projection_event(
        cls,
        conn: Connection,
        *,
        command: BatchCommand,
        outcome: str,
        entity: CoreObjectRecord | CoreLinkRecord,
        authority_tx_id: str,
    ) -> None:
        if isinstance(entity, CoreObjectRecord):
            identity = entity.identity
            identity_material = (
                entity.object_type,
                identity.external_id,
            )
            payload = {
                "schemaVersion": 1,
                "entityKind": "object",
                "changeKind": outcome,
                "objectType": entity.object_type,
                "identity": entity.identity.model_dump(mode="json"),
                "record": entity.model_dump(mode="json"),
            }
            identity_columns = {
                "object_type": entity.object_type,
                "external_id": identity.external_id,
                "link_type": None,
                "source_external_id": None,
                "target_external_id": None,
            }
        else:
            identity = entity.source
            identity_material = (
                entity.link_type,
                entity.source_type,
                entity.source.external_id,
                entity.target_type,
                entity.target.external_id,
            )
            payload = {
                "schemaVersion": 1,
                "entityKind": "link",
                "changeKind": outcome,
                "record": entity.model_dump(mode="json"),
            }
            identity_columns = {
                "object_type": None,
                "external_id": None,
                "link_type": entity.link_type,
                "source_external_id": entity.source.external_id,
                "target_external_id": entity.target.external_id,
            }

        payload_json = json.dumps(
            _jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        event_key = cls._base_projection_event_key(command,entity,outcome)
        conn.execute(
            insert(projection_outbox).values(
                org_id=identity.org_id,
                project_id=identity.workspace_id,
                workspace_id=identity.workspace_id,
                input_revision=cls._next_projection_revision(conn),
                change_kind=outcome,
                platform=identity.platform,
                shop_or_marketplace_id=identity.shop_or_marketplace_id,
                payload=json.loads(payload_json),
                event_key=event_key,
                payload_hash=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
                event_source="authoritative_store",
                authority_tx_id=authority_tx_id,
                projected=False,
                created_at=_utcnow(),
                **identity_columns,
            )
        )

    @classmethod
    def _write_derived_projection_event(
        cls,
        conn: Connection,
        *,
        command: DerivedMetricCommand,
        stored: Any,
        effective_properties: dict[str, Any],
        authority_tx_id: str,
    ) -> None:
        identity = command.identity
        record = {
            "identity": {
                "orgId": identity.org_id,
                "workspaceId": identity.workspace_id,
                "platform": identity.platform,
                "shopOrMarketplaceId": identity.shop_or_marketplace_id,
                "externalId": identity.external_id,
            },
            "objectType": command.object_type,
            "sourceUpdatedAt": _db_time(stored["source_updated_at"]).isoformat(),
            "sourceTimezone": stored["source_timezone"],
            "status": {
                "canonical": stored["canonical_status"],
                "rawStatus": stored["raw_status"],
                "unknown": False,
            },
            "isDeleted": False,
            "schemaVersion": int(stored["schema_version"]),
            "properties": effective_properties,
        }
        payload = {
            "schemaVersion": 1,
            "entityKind": "object",
            "changeKind": "derived_upsert",
            "objectType": command.object_type,
            "identity": record["identity"],
            "record": record,
        }
        payload_json = json.dumps(
            _jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        event_material = "\x1f".join(
            (
                identity.org_id,
                identity.workspace_id,
                identity.platform,
                identity.shop_or_marketplace_id,
                command.stream,
                command.idempotency_key,
                "derived_upsert",
                command.object_type,
                identity.external_id,
            )
        )
        conn.execute(
            insert(projection_outbox).values(
                org_id=identity.org_id,
                project_id=identity.workspace_id,
                workspace_id=identity.workspace_id,
                input_revision=cls._next_projection_revision(conn),
                change_kind="derived_upsert",
                object_type=command.object_type,
                external_id=identity.external_id,
                link_type=None,
                source_external_id=None,
                target_external_id=None,
                platform=identity.platform,
                shop_or_marketplace_id=identity.shop_or_marketplace_id,
                payload=json.loads(payload_json),
                event_key=hashlib.sha256(event_material.encode("utf-8")).hexdigest(),
                payload_hash=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
                event_source="authoritative_store",
                authority_tx_id=authority_tx_id,
                projected=False,
                created_at=_utcnow(),
            )
        )

    @staticmethod
    def _tombstone_attached_links(
        conn: Connection,
        identity: StorageIdentity,
        object_type: str,
        deleted_at: datetime,
    ) -> None:
        source_match = and_(
            ecom_link.c.source_platform == identity.platform,
            ecom_link.c.source_shop_or_marketplace_id
            == identity.shop_or_marketplace_id,
            ecom_link.c.source_object_type == object_type,
            ecom_link.c.source_external_id == identity.external_id,
        )
        target_match = and_(
            ecom_link.c.target_platform == identity.platform,
            ecom_link.c.target_shop_or_marketplace_id
            == identity.shop_or_marketplace_id,
            ecom_link.c.target_object_type == object_type,
            ecom_link.c.target_external_id == identity.external_id,
        )
        conn.execute(
            update(ecom_link)
            .where(
                and_(
                    ecom_link.c.org_id == identity.org_id,
                    ecom_link.c.workspace_id == identity.workspace_id,
                    or_(source_match, target_match),
                    or_(
                        ecom_link.c.deleted_at.is_(None),
                        ecom_link.c.deleted_at < deleted_at,
                    ),
                )
            )
            .values(deleted_at=deleted_at, updated_at=_utcnow())
        )

    @staticmethod
    def _advance_checkpoint(conn: Connection, command: BatchCommand) -> int:
        clause = _scope_clause(ecom_sync_checkpoint, command)
        existing = (
            conn.execute(select(ecom_sync_checkpoint).where(clause).with_for_update())
            .mappings()
            .first()
        )
        expected = command.expected_checkpoint_version
        next_cursor = command.next_checkpoint
        data_cursor = command.max_data_cursor()
        now = _utcnow()
        if existing is None:
            if expected != 0:
                raise EcomConsistencyError(
                    "CHECKPOINT_CAS_CONFLICT",
                    "checkpoint does not exist at the expected version",
                )
            if next_cursor.sort_key() != data_cursor:
                raise EcomConsistencyError(
                    "CHECKPOINT_BOUNDARY_INVALID",
                    "initial checkpoint must equal the last stable batch cursor",
                )
            conn.execute(
                insert(ecom_sync_checkpoint).values(
                    org_id=command.scope.org_id,
                    workspace_id=command.scope.workspace_id,
                    platform=command.scope.platform,
                    shop_or_marketplace_id=command.scope.shop_or_marketplace_id,
                    stream=command.scope.stream,
                    cursor_updated_at=next_cursor.source_updated_at_utc,
                    cursor_external_id=next_cursor.external_id,
                    version=1,
                    updated_at=now,
                )
            )
            return 1

        current_version = int(existing["version"])
        if current_version != expected:
            raise EcomConsistencyError(
                "CHECKPOINT_CAS_CONFLICT",
                "checkpoint changed since the batch was read",
                details={"expected": expected, "actual": current_version},
            )
        current_cursor = (
            _db_time(existing["cursor_updated_at"]),
            str(existing["cursor_external_id"]),
        )
        if next_cursor.sort_key() < current_cursor:
            raise EcomConsistencyError(
                "CHECKPOINT_REGRESSION",
                "checkpoint must not move backwards",
            )
        expected_cursor = max(current_cursor, data_cursor)
        if next_cursor.sort_key() != expected_cursor:
            raise EcomConsistencyError(
                "CHECKPOINT_BOUNDARY_INVALID",
                "checkpoint must equal the current or last stable batch cursor",
            )
        result = conn.execute(
            update(ecom_sync_checkpoint)
            .where(and_(clause, ecom_sync_checkpoint.c.version == expected))
            .values(
                cursor_updated_at=next_cursor.source_updated_at_utc,
                cursor_external_id=next_cursor.external_id,
                version=expected + 1,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            raise EcomConsistencyError(
                "CHECKPOINT_CAS_CONFLICT",
                "checkpoint changed concurrently",
            )
        return expected + 1
