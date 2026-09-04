from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from aos_api.ecommerce_content_campaign_authority_store import (
    ContentCampaignAuthorityObservation,
    ContentCampaignAuthorityReadError,
    ContentCampaignAuthoritySnapshot,
)
from aos_api.ecommerce_workshop_content_campaign_inputs import (
    EcommerceWorkshopContentCampaignInputs,
)


NOW = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)


class _Result:
    def __init__(self, rows): self._rows = rows
    def fetchall(self): return self._rows


class _Connection:
    def __init__(self, rows): self.rows = rows; self.calls = []
    def execute(self, sql, params=()): self.calls.append((sql, params)); return _Result(self.rows)


class _Context:
    def __init__(self, conn): self.conn = conn
    def __enter__(self): return self.conn
    def __exit__(self, *_): return None


def _row(object_type, external_id, properties, digest):
    return {
        "object_type": object_type,
        "external_id": external_id,
        "properties": properties,
        "source_updated_at": NOW,
        "payload_hash": digest,
    }


class _CampaignStore:
    def read_snapshot(self, scope, *, cutoff, limit):
        campaign = SimpleNamespace(
            campaign_id="campaign-business-1", revision=1, content_hash="c" * 64,
            lifecycle=SimpleNamespace(value="draft"), channel_ids=["微信小店"], created_at=NOW,
        )
        calendar = SimpleNamespace(
            entry_id="calendar-business-1", revision=1, content_hash="d" * 64,
            lifecycle=SimpleNamespace(value="scheduled"), local_start="2026-09-05T09:00",
            local_end="2026-09-05T18:00", created_at=NOW,
        )
        return ContentCampaignAuthoritySnapshot(
            campaigns=[ContentCampaignAuthorityObservation(revision=campaign, receipt_id="r1")],
            calendar_entries=[ContentCampaignAuthorityObservation(revision=calendar, receipt_id="r2")],
            intents=[], variants=[],
        )


class _FailedCampaignStore:
    def read_snapshot(self, scope, *, cutoff, limit):
        raise ContentCampaignAuthorityReadError("failed")


def _service(store=None):
    rows = [
        _row("Product", "niushop:1:65", {"title": "面膜套餐", "price": "99.00", "stock": "3.000", "state": 1, "secret": "never-return"}, "a" * 64),
        _row("ProductSku", "niushop:1:74", {"productId": "65", "stock": "3", "stockAlarm": "5", "stock_health": "low", "barcode": "private"}, "b" * 64),
    ]
    conn = _Connection(rows)
    return EcommerceWorkshopContentCampaignInputs(
        clock=lambda: NOW, connect_factory=lambda: _Context(conn),
        campaign_store=store or _CampaignStore(),
    ), conn


def test_reads_real_business_fields_and_exact_refs_without_raw_payload() -> None:
    service, conn = _service()
    body = service.read(org_id="org-org", project_id="dev-project").model_dump(by_alias=True)
    assert body["status"] == "ready"
    assert body["ledger"] == {"products": 1, "inventory": 1, "plans": 2, "unmatchedInventory": 0}
    assert body["products"][0]["title"] == "面膜套餐"
    assert body["products"][0]["productRef"]["resourceId"] == "niushop:1:65"
    assert body["inventory"][0]["productRef"]["resourceId"] == "niushop:1:65"
    assert "secret" not in str(body)
    assert "barcode" not in str(body)
    assert conn.calls[-1][1][:2] == ("org-org", "dev-project")


def test_campaign_failure_keeps_product_and_inventory_as_partial() -> None:
    service, _ = _service(_FailedCampaignStore())
    body = service.read(org_id="org-org", project_id="dev-project")
    assert body.status == "partial"
    assert body.unavailable_groups == ["plans"]
    assert len(body.products) == len(body.inventory) == 1


def test_unmatched_inventory_is_explicit_not_guessed() -> None:
    service, _ = _service()
    service._connect_factory = lambda: _Context(_Connection([
        _row("ProductSku", "niushop:1:99", {"productId": "missing", "stock": "8"}, "e" * 64)
    ]))
    body = service.read(org_id="org-org", project_id="dev-project")
    assert body.ledger.unmatched_inventory == 1
    assert body.inventory[0].product_ref is None
