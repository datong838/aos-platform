"""Large strict-link Store batch stays bounded on the isolated PostgreSQL host."""
from datetime import datetime, timezone
from time import monotonic
import uuid

import psycopg
from psycopg import sql
import pytest
from sqlalchemy import create_engine, insert, select, func, text

from aos_api.ecom_consistency_store import (
    EcomConsistencyStore, ecom_ingest_receipt, ecom_link, ecom_object,
    metadata, projection_outbox,
)
from aos_api.ecom_core_models import BatchCommand, CoreLinkRecord, SyncScope
from aos_api.public_contracts import ExternalIdentityKey, StableCursor


pytestmark = pytest.mark.skipif(
    __import__("os").getenv("AOS_EXTENSION_PG_TEST") != "1",
    reason="dedicated database opt-in required",
)
NOW = datetime(2026, 9, 19, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def pg_store():
    schema = "strict_link_" + uuid.uuid4().hex
    owner = psycopg.connect(
        host="127.0.0.1", port=18432, user="postgres", dbname="postgres", autocommit=True,
    )
    owner.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    engine = create_engine(
        "postgresql+psycopg://postgres@127.0.0.1:18432/postgres",
        connect_args={"options": f"-c search_path={schema}"},
    )
    try:
        metadata.create_all(engine)
        owner.execute(sql.SQL("CREATE SEQUENCE {}.projection_input_revision_seq").format(
            sql.Identifier(schema)
        ))
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(
            sql.Identifier(schema)
        ))
        owner.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {} TO aos_runtime").format(
            sql.Identifier(schema)
        ))
        owner.execute(sql.SQL("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA {} TO aos_runtime").format(
            sql.Identifier(schema)
        ))
        yield EcomConsistencyStore(engine), engine
    finally:
        engine.dispose()
        owner.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        owner.close()


def _identity(external_id):
    return ExternalIdentityKey(
        org_id="org-org", workspace_id="dev-project", platform="synthetic",
        shop_or_marketplace_id="shop-a", external_id=external_id,
    )


def test_1168_strict_links_commit_and_replay_well_inside_attempt_window(pg_store):
    store, engine = pg_store
    source = _identity("shop")
    targets = tuple(_identity(f"product-{index:04d}") for index in range(1168))
    endpoint_rows = [dict(
        org_id="org-org", workspace_id="dev-project", platform="synthetic",
        shop_or_marketplace_id="shop-a", object_type="Shop", external_id="shop",
        properties={}, source_updated_at=NOW, source_timezone="+00:00",
        canonical_status="active", raw_status="ACTIVE", schema_version=1,
        payload_hash="a" * 64, deleted_at=None, created_at=NOW, updated_at=NOW,
        derived_revision=0, derived_input_revision=None, derived_input_hash=None,
        derived_computed_at=None, derived_payload={}, derived_payload_hash=None,
    )] + [dict(
        org_id="org-org", workspace_id="dev-project", platform="synthetic",
        shop_or_marketplace_id="shop-a", object_type="Product", external_id=target.external_id,
        properties={}, source_updated_at=NOW, source_timezone="+00:00",
        canonical_status="active", raw_status="ACTIVE", schema_version=1,
        payload_hash="b" * 64, deleted_at=None, created_at=NOW, updated_at=NOW,
        derived_revision=0, derived_input_revision=None, derived_input_hash=None,
        derived_computed_at=None, derived_payload={}, derived_payload_hash=None,
    ) for target in targets]
    with engine.begin() as conn:
        conn.execute(insert(ecom_object), endpoint_rows)

    links = [CoreLinkRecord(
        link_type="Shop.sellsProduct", source_type="Shop", source=source,
        target_type="Product", target=target, source_updated_at=NOW,
        cursor_external_id=f"link-{index:04d}", is_deleted=False,
    ) for index, target in enumerate(targets)]
    command = BatchCommand(
        scope=SyncScope(org_id="org-org", workspace_id="dev-project", platform="synthetic",
                        shop_or_marketplace_id="shop-a", stream="strict-links-1168"),
        idempotency_key="strict-links-1168", expected_checkpoint_version=0,
        next_checkpoint=StableCursor(source_updated_at_utc=NOW, external_id="link-1167"),
        objects=[], links=links,
    )

    started = monotonic()
    result = store.apply_strict_link_batch(command)
    elapsed = monotonic() - started
    replay = store.apply_strict_link_batch(command)

    assert result.links_written == 1168 and not result.replayed
    assert replay.replayed and replay.links_written == 1168
    assert elapsed < 120
    with engine.begin() as conn:
        assert conn.execute(select(func.count()).select_from(ecom_link)).scalar_one() == 1168
        assert conn.execute(select(func.count()).select_from(ecom_ingest_receipt)).scalar_one() == 1
        assert conn.execute(select(func.count()).select_from(projection_outbox)).scalar_one() == 1168
