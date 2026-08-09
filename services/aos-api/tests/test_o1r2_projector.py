from __future__ import annotations

import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from psycopg.errors import InsufficientPrivilege

from aos_api.db import connect
from aos_api.ecom_projector import project_pending
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("dev-org", "dev-project")


def _event_payload(object_id: str, *, deleted: bool = False) -> dict:
    return {
        "schemaVersion": 1,
        "entityKind": "object",
        "changeKind": "objects_tombstoned" if deleted else "objects_written",
        "objectType": "Product",
        "identity": {
            "orgId": SCOPE.org_id,
            "workspaceId": SCOPE.project_id,
            "platform": "niushop",
            "shopOrMarketplaceId": "1",
            "externalId": object_id,
        },
        "record": {
            "identity": {
                "orgId": SCOPE.org_id,
                "workspaceId": SCOPE.project_id,
                "platform": "niushop",
                "shopOrMarketplaceId": "1",
                "externalId": object_id,
            },
            "objectType": "Product",
            "sourceUpdatedAt": "2026-08-09T00:00:00Z",
            "sourceTimezone": "+08:00",
            "status": {"canonical": "active", "raw": "ACTIVE"},
            "isDeleted": deleted,
            "schemaVersion": 1,
            "properties": {"title": "real product"},
        },
    }


def _enqueue(payload: dict) -> int:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode()).hexdigest()
    with connect() as conn:
        row = conn.execute(
            "INSERT INTO projection_outbox "
            "(org_id,project_id,workspace_id,input_revision,change_kind,object_type,external_id,"
            "platform,shop_or_marketplace_id,payload,event_key,payload_hash,event_source,authority_tx_id,projected,created_at) "
            "VALUES (%s,%s,%s,nextval('projection_input_revision_seq'),%s,%s,%s,%s,%s,%s::jsonb,%s,%s,'authoritative_store',%s,FALSE,now()) "
            "RETURNING outbox_id",
            (
                *SCOPE.key,
                SCOPE.project_id,
                payload["changeKind"],
                "Product",
                payload["record"]["identity"]["externalId"],
                "niushop",
                "1",
                raw,
                hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest(),
                digest,
                hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest(),
            ),
        ).fetchone()
    return int(row["outbox_id"])


def test_projector_is_single_owner_and_replay_is_noop() -> None:
    object_id = f"niushop:1:test-{uuid.uuid4()}"
    outbox_id = _enqueue(_event_payload(object_id))
    assert project_pending(SCOPE)["projected"] >= 1
    with connect(SCOPE) as conn:
        row = conn.execute(
            "SELECT props FROM obj_instance WHERE org_id=%s AND project_id=%s "
            "AND object_type='Product' AND object_id=%s",
            (*SCOPE.key, object_id),
        ).fetchone()
        event = conn.execute(
            "SELECT projected,projected_at FROM projection_outbox WHERE outbox_id=%s",
            (outbox_id,),
        ).fetchone()
    assert row["props"]["title"] == "real product"
    assert event["projected"] is True and event["projected_at"] is not None
    assert project_pending(SCOPE)["projected"] == 0


def test_non_projector_cannot_write_ecommerce_compatibility_row() -> None:
    with pytest.raises(InsufficientPrivilege):
        with connect(SCOPE) as conn:
            conn.execute(
                "INSERT INTO obj_instance (org_id,project_id,object_type,object_id,props) "
                "VALUES (%s,%s,'Product',%s,'{}'::jsonb)",
                (*SCOPE.key, f"forbidden-{uuid.uuid4()}"),
            )


def test_tombstone_removes_projected_object() -> None:
    object_id = f"niushop:1:delete-{uuid.uuid4()}"
    _enqueue(_event_payload(object_id))
    project_pending(SCOPE)
    _enqueue(_event_payload(object_id, deleted=True))
    project_pending(SCOPE)
    with connect(SCOPE) as conn:
        row = conn.execute(
            "SELECT 1 FROM obj_instance WHERE org_id=%s AND project_id=%s "
            "AND object_type='Product' AND object_id=%s",
            (*SCOPE.key, object_id),
        ).fetchone()
    assert row is None


def test_concurrent_projectors_lease_each_event_once() -> None:
    object_id = f"niushop:1:concurrent-{uuid.uuid4()}"
    _enqueue(_event_payload(object_id))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: project_pending(SCOPE), range(2)))
    assert sum(item["projected"] for item in results) == 1


def test_executor_has_no_compatibility_dual_write_or_fake_outbox() -> None:
    source = (Path(__file__).parents[1] / "aos_api" / "ec_live_executor.py").read_text()
    assert "INSERT INTO obj_instance" not in source
    assert "INSERT INTO projection_outbox" not in source
    assert "_write_obj_instances" not in source
    assert "_mark_projection_outbox" not in source
