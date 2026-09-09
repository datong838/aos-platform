from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from aos_api.source_read_observation import SourceReadObservation, observed_rows_hash


NOW = datetime(2026, 9, 9, tzinfo=UTC)


def observation(**changes):
    return SourceReadObservation(
        tenant={"orgId": "org-org", "projectId": "dev-project"},
        sourceId="source-1", specId="niushop.product-observation/v1", siteId=1,
        readStartedAt=NOW, readFinishedAt=NOW + timedelta(seconds=1),
        fetchedCount=2, excludedCount=1, retainedCount=1,
        rowsHash=observed_rows_hash([{"goods_id": 1}]), **changes)


def test_hash_is_typed_order_stable_and_rejects_body_drift():
    assert observed_rows_hash([{"a": 1, "b": "x"}]) == observed_rows_hash([{"b": "x", "a": 1}])
    values = [1, "1", True, 1.0, Decimal("1"), NOW, NOW.isoformat(), None]
    assert len({observed_rows_hash([{"v": v}]) for v in values}) == len(values)
    assert observed_rows_hash([{"v": NOW}]) == observed_rows_hash([
        {"v": NOW.astimezone(timezone(timedelta(hours=8)))}])
    item = observation()
    item.verify_rows([{"goods_id": 1}])
    with pytest.raises(ValueError, match="rows"):
        item.verify_rows([{"goods_id": 2}])
    assert item.source_configuration_ref is None and item.upstream_snapshot_at is None


def test_observation_and_nested_tenant_are_immutable():
    item = observation()
    with pytest.raises(ValueError, match="frozen"):
        item.read_started_at = NOW - timedelta(days=1)
    with pytest.raises(ValueError, match="frozen"):
        item.tenant.org_id = "dev-org"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), Decimal("NaN"),
    NOW.replace(tzinfo=None), b"bytes", object()])
def test_unsupported_or_ambiguous_rows_rejected(value):
    with pytest.raises((ValueError, TypeError)):
        observed_rows_hash([{"v": value}])


@pytest.mark.parametrize("changes", [
    {"read_finished_at": NOW - timedelta(seconds=1)},
    {"read_started_at": NOW.replace(tzinfo=None)},
    {"fetched_count": 101}, {"retained_count": 2}, {"excluded_count": -1},
    {"site_id": True}, {"source_configuration_ref": "invented"},
    {"upstream_snapshot_at": NOW}, {"source_id": " source-1 "},
])
def test_invalid_observation_cannot_be_revalidated(changes):
    with pytest.raises(ValueError):
        SourceReadObservation.model_validate(observation().model_copy(update=changes).model_dump())


@pytest.mark.parametrize("changes", [
    {"spec_id": "niushop.product-quality-observation/v1"},
    {"cleaning_version": "niushop.product-quality-fields/v1"},
    {"spec_id": "niushop.product-quality-observation/v1", "cleaning_version": "niushop.product-quality-fields/v1"},
])
def test_quality_spec_must_pair_its_version_and_retain_all_rows(changes):
    with pytest.raises(ValueError):
        SourceReadObservation.model_validate(observation().model_copy(update=changes).model_dump())


def test_quality_contract_preserves_old_default_and_has_explicit_new_pair():
    original = observation()
    assert original.spec_id == "niushop.product-observation/v1"
    assert original.cleaning_version == "niushop.product-public-fields/v1"
    raw = original.model_dump()
    raw.update(spec_id="niushop.product-quality-observation/v1", cleaning_version="niushop.product-quality-fields/v1",
        fetched_count=1, excluded_count=0)
    item = SourceReadObservation.model_validate(raw)
    item.verify_rows([{"goods_id": 1}])
    assert item.upstream_snapshot_at is None
