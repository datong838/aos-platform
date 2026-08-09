"""Transactional persistence for the platform-neutral ecommerce core.

The store owns only the new ``ecom_*`` tables.  It intentionally does not
read or mutate legacy ``obj_instance`` / ``graph_edge`` state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from threading import RLock
from typing import Any

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
    _jsonable,
)

metadata = MetaData()
_PROCESS_IDEMPOTENCY_LOCKS = tuple(RLock() for _ in range(64))

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


class EcomConsistencyStore:
    """Apply one normalized page atomically and advance its checkpoint by CAS."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._last_dangling_links: list[CoreLinkRecord] = []

    def apply_batch(self, command: BatchCommand) -> BatchResult:
        # Pydantic's frozen models are shallow: callers could otherwise mutate
        # nested lists/dicts after construction and bypass the scope and shape
        # validators.  Rebuild a detached, validated snapshot before hashing or
        # opening the transaction.
        command = BatchCommand.model_validate(command.model_dump(mode="python"))
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
                replay = self._get_receipt(conn, command)
                if replay is not None:
                    if replay["request_hash"] != request_hash:
                        raise EcomConsistencyError(
                            "IDEMPOTENCY_CONFLICT",
                            "idempotency key was already used with a different request",
                        )
                    saved = dict(replay["result"])
                    saved["replayed"] = True
                    return BatchResult.model_validate(saved)

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
                    if not self._object_exists(
                        conn, link.source, link.source_type, allow_tombstone=link.is_deleted
                    ) or not self._object_exists(
                        conn, link.target, link.target_type, allow_tombstone=link.is_deleted
                    ):
                        dangling_links.append(link)
                        counters["links_ignored"] += 1
                        continue
                    outcome = self._upsert_link_checked(conn, link)
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
                conn.execute(
                    insert(ecom_ingest_receipt).values(
                        org_id=command.scope.org_id,
                        workspace_id=command.scope.workspace_id,
                        platform=command.scope.platform,
                        shop_or_marketplace_id=command.scope.shop_or_marketplace_id,
                        stream=command.scope.stream,
                        idempotency_key=command.idempotency_key,
                        request_hash=request_hash,
                        result=result.model_dump(mode="json"),
                        created_at=_utcnow(),
                    )
                )
                return result
        except IntegrityError as exc:
            raise EcomConsistencyError(
                "CONCURRENT_WRITE_CONFLICT",
                "a concurrent write changed the consistency state",
            ) from exc

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

    def update_derived_metrics(
        self, command: DerivedMetricCommand
    ) -> DerivedMetricResult:
        """O1 §5.2.10：CAS、Receipt 和 Outbox 同事务的派生更新。"""
        command = DerivedMetricCommand.model_validate(command.model_dump(mode="python"))
        identity = command.identity
        request_hash = command.request_hash()
        receipt_id = hashlib.sha256(
            "\x1f".join(
                (
                    identity.org_id,
                    identity.workspace_id,
                    identity.platform,
                    identity.shop_or_marketplace_id,
                    command.stream,
                    command.idempotency_key,
                )
            ).encode("utf-8")
        ).hexdigest()
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
    def _get_receipt(conn: Connection, command: BatchCommand):
        return (
            conn.execute(
                select(ecom_ingest_receipt)
                .where(
                    and_(
                        _scope_clause(ecom_ingest_receipt, command),
                        ecom_ingest_receipt.c.idempotency_key
                        == command.idempotency_key,
                    )
                )
                .with_for_update()
            )
            .mappings()
            .first()
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
                if (
                    legacy_properties == dict(record.properties)
                    and existing["source_timezone"] == record.source_timezone
                    and existing["canonical_status"] == record.status.canonical_value
                    and existing["raw_status"] == record.status.raw_status
                    and int(existing["schema_version"]) == record.schema_version
                    and (existing["deleted_at"] is not None) == record.is_deleted
                ):
                    conn.execute(
                        update(ecom_object)
                        .where(clause)
                        .values(
                            properties=dict(record.properties),
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

    def _upsert_link_checked(self, conn: Connection, link: CoreLinkRecord) -> str:
        """Upsert link after endpoint existence is already verified (by apply_batch)."""

        clause = _link_clause(link)
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
        event_material = "\x1f".join(
            (
                *command.scope.key(),
                command.idempotency_key,
                outcome,
                *identity_material,
            )
        )
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
                event_key=hashlib.sha256(event_material.encode("utf-8")).hexdigest(),
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
