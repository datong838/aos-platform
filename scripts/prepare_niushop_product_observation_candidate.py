"""Prepare an immutable Niushop P02 observation-version successor candidate."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import shutil
import sys

import yaml

from prepare_niushop_business_facts_candidate import ROOT, builder


CANDIDATES = ROOT / "bundles/candidates/ecommerce"
SOURCE = Path("platform.ecommerce.niushop/1.22.0")
TARGET = Path("platform.ecommerce.niushop/1.23.0")
BASE_HASH = "sha256:f0ef69161dbae032fb29da036fa3cf9e9ef6dca1224027d9225d25df49eb8088"
P02 = Path("content/mappings/p02-product.yaml")


def successor_mapping(original: dict) -> dict:
    value = deepcopy(original)
    config = value.get("snapshot_materialization")
    if not isinstance(config, dict) or config.get("schema_version") != "aos.snapshot-materialization/v2":
        raise ValueError("exact P02 v2 source required")
    if config.get("source_updated_at") != {"primary": "modify_time", "fallback": "create_time"}:
        raise ValueError("exact unreliable P02 source clock declaration required")
    value["snapshot_materialization"] = {
        "schema_version": "aos.snapshot-materialization/v3",
        "platform": config["platform"],
        "shop_key": config["shop_key"],
        "source_timezone": config["source_timezone"],
        "property_defaults": deepcopy(config["property_defaults"]),
        "time_basis": "observation",
        "deletion_basis": deepcopy(config["tombstone"]),
        "status": deepcopy(config["status"]),
    }
    notes = list(value.get("notes") or [])
    notes.append("Complete Product observations use host observation time because stock and sales may change without modify_time.")
    notes.append("Source create_time/modify_time remain mapped business facts and are not asserted as a reliable version clock.")
    value["notes"] = notes
    return value


def _read_spec(mapping):
    from aos_api.pipeline_source_selection import MappingReadSpec

    return MappingReadSpec(
        mapping["source_table"], mapping["target_ot"], mapping["primary_key"],
        tuple(item["source"] for item in mapping["field_mappings"]), (("site_id", 1),),
    )


def _sample(mapping):
    row = {}
    for field in mapping["field_mappings"]:
        source, kind = field["source"], field["type"]
        if kind == "int":
            row[source] = 1
        elif kind == "timestamp":
            row[source] = 1_700_000_000
        elif kind == "decimal":
            row[source] = Decimal("1.000")
        else:
            row[source] = "sample"
    row.update(goods_id=1, site_id=1, goods_state=1, is_delete=0, category_id=",1,")
    return row


def evaluate(mapping: dict) -> dict:
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping, materialize_snapshot

    compiled = compile_snapshot_mapping(mapping, _read_spec(mapping))
    row = _sample(mapping)
    first_at = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
    first = materialize_snapshot([row], compiled, observed_at=first_at)[0]
    replay = materialize_snapshot([deepcopy(row)], compiled, observed_at=first_at)[0]
    later = materialize_snapshot([deepcopy(row)], compiled, observed_at=first_at + timedelta(minutes=1))[0]
    if first != replay or first["source_updated_at"] != first_at or later["source_updated_at"] == first_at:
        raise ValueError("observation version semantics differ")
    props = first["properties"]
    if (props.get("sourceUpdatedAtBasis"), props.get("sourceModificationTimeKnown")) != ("observation", False):
        raise ValueError("observation provenance missing")
    invalid = deepcopy(mapping)
    invalid["snapshot_materialization"]["time_basis"] = "source"
    try:
        compile_snapshot_mapping(invalid, _read_spec(invalid))
    except ValueError:
        pass
    else:
        raise ValueError("invalid time basis accepted")
    return {
        "status": "passed",
        "checks": ["p02-v3-compiled", "same-observation-deterministic", "later-observation-new-version",
                   "observation-provenance-explicit", "invalid-time-basis-refused"],
        "realTenantAcceptance": False,
    }


def prepare() -> dict:
    source, target = CANDIDATES / SOURCE, CANDIDATES / TARGET
    if target.exists():
        raise ValueError("immutable candidate target already exists")
    helper = builder()
    if helper._tree_hash(source) != BASE_HASH:
        raise ValueError("immutable source tree differs")
    original = yaml.safe_load((source / P02).read_text(encoding="utf-8"))
    mapping = successor_mapping(original)
    report = evaluate(mapping)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    manifest = (source / "bundle.yaml").read_text(encoding="utf-8")
    if manifest.count("  version: 1.22.0\n") != 1:
        raise ValueError("source manifest version differs")
    (target / "bundle.yaml").write_text(
        manifest.replace("  version: 1.22.0\n", "  version: 1.23.0\n", 1), encoding="utf-8"
    )
    (target / P02).write_text(yaml.safe_dump(mapping, allow_unicode=True, sort_keys=False), encoding="utf-8")
    evaluations = json.loads((source / "evidence/bundle-evals.json").read_text(encoding="utf-8"))
    evaluations["productObservationVersion"] = report
    evaluations["inheritedObjectMappings"] = {
        "sourceTreeHash": BASE_HASH, "unchanged": False,
        "changedMapping": str(P02), "objectEvaluationsRerun": True,
    }
    (target / "evidence/bundle-evals.json").write_text(
        json.dumps(evaluations, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    changed = sorted(
        str(path.relative_to(source)) for path in source.rglob("*") if path.is_file()
        and "__pycache__" not in path.parts and path.suffix != ".pyc"
        and path.read_bytes() != (target / path.relative_to(source)).read_bytes()
    )
    expected = ["bundle.yaml", str(P02), "evidence/bundle-evals.json"]
    if helper._tree_hash(source) != BASE_HASH or changed != sorted(expected):
        raise ValueError("unexpected candidate changes")
    return {
        "outcome": "NIUSHOP_PRODUCT_OBSERVATION_CANDIDATE_PREPARED",
        "sourceTreeHash": BASE_HASH,
        "targetTreeHash": helper._tree_hash(target),
        "changedFiles": changed,
        "evaluation": report,
        "published": False,
        "installed": False,
    }


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    print(json.dumps(prepare(), ensure_ascii=False, indent=2))
