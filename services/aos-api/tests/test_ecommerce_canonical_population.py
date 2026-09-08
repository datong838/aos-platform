from datetime import UTC, datetime
import json

import pytest

from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_canonical_population import CanonicalPopulationReader
from aos_api.ecommerce_business_investigation_case_selection import PostgresCanonicalShopSelectionSource
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 8, tzinfo=UTC)
SHOP = dict(platform="niushop", shop_or_marketplace_id="region:1", external_id="shop:1",
            schema_version=1, payload_hash="a" * 64, source_updated_at=NOW)


def object_row(identity="product:1", **changes):
    return {**SHOP, "org_id": SCOPE.org_id, "workspace_id": SCOPE.project_id,
            "external_id": identity, "object_type": "Product", **changes}


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows=(), isolation="repeatable read"):
        self.rows = list(rows)
        self.isolation = isolation
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "transaction_isolation" in sql:
            return Result([{"transaction_isolation": self.isolation}])
        if "object_type='Shop'" in sql:
            assert params == SCOPE.key
            return Result([SHOP])
        assert "platform=%s" in sql and "shop_or_marketplace_id=%s" in sql
        assert "deleted_at IS NULL" in sql
        assert "source_updated_at<" not in sql
        assert params == (*SCOPE.key, "niushop", "region:1", ["Product"], 100)
        return Result(self.rows)


def run(conn, *, changed_ref=False, object_types=("Product",)):
    tx = HostTransaction(conn)
    selected = PostgresCanonicalShopSelectionSource(TransactionBoundConnectFactory(tx, SCOPE)).read(SCOPE)
    channel = selected.channel_ref
    if changed_ref:
        channel = channel.model_copy(update={"content_hash": "sha256:" + "b" * 64})
    return CanonicalPopulationReader(tx, SCOPE).read(
        channel_ref=channel, entity_ref=selected.business_entity_ref,
        binding_ref=selected.entity_channel_binding_ref, object_types=object_types)


def test_complete_current_collection_preserves_collision_safe_identity():
    snapshot = run(Connection([object_row()]))
    assert snapshot.collection_domain == "current_canonical_store"
    assert snapshot.sources[0].resource_type == "EcommerceObjectRevision"
    assert json.loads(snapshot.sources[0].resource_id.removeprefix("ecom/v1:")) == [
        "org-org", "dev-project", "niushop", "region:1", "Product", "product:1"]
    assert snapshot.sources[0].revision == "a" * 64
    assert snapshot.source_version_times == (NOW,)


def test_empty_and_boundaries():
    assert run(Connection()).sources == ()
    assert len(run(Connection([object_row(str(i)) for i in range(99)])).sources) == 99
    with pytest.raises(ValueError, match="limit"):
        run(Connection([object_row(str(i)) for i in range(100)]))


@pytest.mark.parametrize("isolation", ["read committed", "read uncommitted"])
def test_unstable_transaction_rejected(isolation):
    with pytest.raises(ValueError, match="snapshot"):
        run(Connection(isolation=isolation))


def test_selection_drift_rejected():
    with pytest.raises(ValueError, match="selection"):
        run(Connection(), changed_ref=True)


@pytest.mark.parametrize("changes", [
    {"org_id": "dev-org"}, {"workspace_id": "other"}, {"platform": "other"},
    {"shop_or_marketplace_id": "other"}, {"object_type": "Order"},
    {"external_id": " bad "}, {"payload_hash": "bad"}, {"source_updated_at": NOW.replace(tzinfo=None)},
])
def test_untrusted_row_scope_or_identity_rejected(changes):
    with pytest.raises(ValueError):
        run(Connection([object_row(**changes)]))


def test_duplicate_identity_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        run(Connection([object_row(), object_row()]))


@pytest.mark.parametrize("object_types", [(), ["Product"], ("Product", "Product"),
    ("Unknown",), ("Product; DROP TABLE ecom_object",), (1,), (None,)])
def test_invalid_object_types_rejected_before_population_read(object_types):
    conn = Connection()
    with pytest.raises(ValueError, match="object types"):
        run(conn, object_types=object_types)
    assert len(conn.calls) == 1  # The test's initial selection only.


def test_serializable_snapshot_and_version_time_are_preserved_without_freshness_claim():
    old_time = NOW.replace(year=2020)
    conn = Connection([object_row(source_updated_at=old_time)], isolation="serializable")
    snapshot = run(conn)
    assert snapshot.source_version_times == (old_time,)
    assert snapshot.sources[0].authority == "postgres:ecom_object"
    sql = conn.calls[-1][0]
    assert "canonical_status='active'" in sql
    assert "payload," not in sql and "attributes" not in sql


def test_missing_current_shop_is_rejected():
    class MissingShop(Connection):
        def execute(self, sql, params=()):
            if "object_type='Shop'" in sql:
                return Result([])
            return super().execute(sql, params)

    selected = PostgresCanonicalShopSelectionSource(
        TransactionBoundConnectFactory(HostTransaction(Connection()), SCOPE)).read(SCOPE)
    with pytest.raises(ValueError, match="selection"):
        CanonicalPopulationReader(HostTransaction(MissingShop()), SCOPE).read(
            channel_ref=selected.channel_ref, entity_ref=selected.business_entity_ref,
            binding_ref=selected.entity_channel_binding_ref, object_types=("Product",))


@pytest.mark.parametrize("changes", [{"payload_hash": None}, {"payload_hash": "A" * 64},
    {"source_updated_at": None}, {"source_updated_at": "2026-09-08T00:00:00Z"},
    {"external_id": 1}, {"external_id": ""}])
def test_additional_noncanonical_rows_rejected(changes):
    with pytest.raises(ValueError):
        run(Connection([object_row(**changes)]))
