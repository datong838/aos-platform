from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def candidate(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "scripts"))
    return importlib.import_module("prepare_niushop_product_observation_candidate")


def source(candidate):
    return yaml.safe_load((candidate.CANDIDATES / candidate.SOURCE / candidate.P02).read_text())


def test_successor_only_changes_explicit_time_contract(candidate):
    original = source(candidate)
    value = candidate.successor_mapping(original)
    assert original["snapshot_materialization"]["schema_version"] == "aos.snapshot-materialization/v2"
    assert value["snapshot_materialization"] == {
        "schema_version": "aos.snapshot-materialization/v3",
        "platform": "niushop", "shop_key": "site_id", "source_timezone": "+08:00",
        "property_defaults": {"currency": "CNY"}, "time_basis": "observation",
        "deletion_basis": {"field": "is_delete", "live_value": 0, "deleted_value": 1},
        "status": {"field": "goods_state", "property_target": "status",
                   "values": {"0": "INACTIVE", "1": "ACTIVE"}},
    }
    assert {key: value[key] for key in value if key not in {"snapshot_materialization", "notes"}} == {
        key: original[key] for key in original if key not in {"snapshot_materialization", "notes"}
    }


def test_candidate_mapping_uses_honest_observation_version(candidate):
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping, materialize_snapshot

    mapping = candidate.successor_mapping(source(candidate))
    compiled = compile_snapshot_mapping(mapping, candidate._read_spec(mapping))
    row = candidate._sample(mapping)
    now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    first = materialize_snapshot([row], compiled, observed_at=now)[0]
    same = materialize_snapshot([deepcopy(row)], compiled, observed_at=now)[0]
    later = materialize_snapshot([deepcopy(row)], compiled, observed_at=now + timedelta(seconds=1))[0]
    assert first == same and first != later
    assert first["source_updated_at"] == now
    assert first["properties"]["sourceUpdatedAtBasis"] == "observation"
    assert first["properties"]["sourceModificationTimeKnown"] is False
    assert first["properties"]["createdAt"] == "2023-11-14T22:13:20Z"
    assert first["properties"]["modifyTime"] == "2023-11-14T22:13:20Z"


def test_source_and_invalid_declaration_are_fail_closed(candidate):
    original = source(candidate)
    changed = deepcopy(original)
    changed["snapshot_materialization"]["source_updated_at"]["primary"] = "create_time"
    with pytest.raises(ValueError, match="exact unreliable"):
        candidate.successor_mapping(changed)
    mapping = candidate.successor_mapping(original)
    mapping["snapshot_materialization"]["time_basis"] = "source"
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping
    with pytest.raises(ValueError, match="SNAPSHOT_MAPPING_INVALID"):
        compile_snapshot_mapping(mapping, candidate._read_spec(mapping))


def test_static_evaluation_is_complete_and_not_real_acceptance(candidate):
    report = candidate.evaluate(candidate.successor_mapping(source(candidate)))
    assert report["status"] == "passed"
    assert report["realTenantAcceptance"] is False
    assert set(report["checks"]) == {
        "p02-v3-compiled", "same-observation-deterministic", "later-observation-new-version",
        "observation-provenance-explicit", "invalid-time-basis-refused",
    }
