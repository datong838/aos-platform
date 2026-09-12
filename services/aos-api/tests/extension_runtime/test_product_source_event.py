from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "bundles/domains/ecommerce-core/backend"))
from ecommerce_core.product_source_event import validate_product_source_event
from aos_api.ecom_consistency_store import EcomConsistencyStore, metadata, projection_outbox
from test_ecom_consistency_store import obj, batch


@pytest.fixture
def event():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    store = EcomConsistencyStore(engine)
    store.apply_batch(batch(obj("Product", "product-1")))
    with engine.connect() as conn:
        row = dict(conn.execute(select(projection_outbox)).mappings().one())
    engine.dispose()
    return row


def check(row):
    return validate_product_source_event(row, org_id="org-a", project_id="workspace-a")


def rehash(row):
    row["payload_hash"] = hashlib.sha256(json.dumps(row["payload"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_actual_owner_event_is_stable_and_minimal(event):
    before = deepcopy(event)
    ref = check(event)
    assert ref == check(event)
    assert ref.source_event_id == event["event_key"]
    assert ref.object_type == "Product"
    assert ref.external_id == "product-1"
    assert event == before
    assert "properties" not in asdict(ref)
    assert "payload" not in asdict(ref)


@pytest.mark.parametrize("field,value", [
    ("org_id", "other"), ("project_id", "other"), ("workspace_id", "other"),
    ("event_source", "legacy_post_projection"), ("event_key", "bad"),
    ("authority_tx_id", None), ("input_revision", True), ("input_revision", 0),
    ("outbox_id", False), ("object_type", "Customer"), ("change_kind", "links_written"),
    ("external_id", "another-product"), ("payload_hash", "0" * 64),
])
def test_rejects_untrusted_or_drifting_metadata(event, field, value):
    event[field] = value
    with pytest.raises(ValueError, match="^PRODUCT_SOURCE_EVENT_"):
        check(event)


@pytest.mark.parametrize("mutation", ["scope", "identity", "type", "deleted", "schema", "nan"])
def test_rehashed_payload_still_requires_same_identity_and_semantics(event, mutation):
    payload = event["payload"]
    if mutation == "scope": payload["record"]["identity"]["org_id"] = "other"
    elif mutation == "identity": payload["identity"]["external_id"] = "other"
    elif mutation == "type": payload["record"]["object_type"] = "Customer"
    elif mutation == "deleted": payload["record"]["is_deleted"] = True
    elif mutation == "schema": payload["schemaVersion"] = True
    elif mutation == "nan": payload["record"]["properties"]["secret"] = float("nan")
    rehash(event)
    with pytest.raises(ValueError, match="^PRODUCT_SOURCE_EVENT_"):
        check(event)


@pytest.mark.parametrize("object_type,deleted", [("Product", True), ("ProductSku", False), ("ProductSku", True)])
def test_owner_sku_and_tombstone_contract(object_type, deleted):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    EcomConsistencyStore(engine).apply_batch(batch(obj(object_type, "item-1", deleted=deleted)))
    with engine.connect() as conn:
        row = dict(conn.execute(select(projection_outbox)).mappings().one())
    engine.dispose()
    ref = check(row)
    assert ref.object_type == object_type
    assert ref.deleted is deleted
