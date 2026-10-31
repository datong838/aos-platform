"""Private wire decoding tests; no Port or six-branch authority is claimed yet."""
from copy import deepcopy
from datetime import datetime, time
import json
from pathlib import Path
from uuid import UUID
from unittest import mock

import pytest

from aos_api.asset_registry import terminal_source_reader as reader


UUID_TEXT = "11111111-1111-4111-8111-111111111111"


def empty_packet():
    return {"schema": "aos.reinstall-terminal-source-facts/v13",
            "relations": {name: [] for name in reader._RELATIONS},
            "registry": {name: [] for name in reader._REGISTRY},
            "predecessors": {name: [] for name in reader._PREDECESSOR_RELATIONS}}


def row_for(schema):
    values = {"text": "fixture", "uuid": UUID_TEXT, "bigint": 1, "integer": 1, "smallint": 1,
              "boolean": False, "jsonb": {}, "timestamp with time zone": "2026-10-26T00:00:00+08:00",
              "time without time zone": "12:30:00"}
    return {name: deepcopy(values[kind[:-1]]) for name, kind in schema.columns}


def nonempty_packet():
    packet = empty_packet()
    for group, schemas in (("relations", reader._RELATIONS), ("registry", reader._REGISTRY)):
        for name, schema in schemas.items():
            row = row_for(schema)
            if name == "public.asset_bundle": row["kind"] = "SolutionPack"
            packet[group][name] = [row]
    return packet


def decode(packet, ledger=None):
    return reader._decode_packet(packet, reader._WorkLedger() if ledger is None else ledger)


def test_all_literal_columns_match_frozen_full_plan_and_amendments():
    root = Path(__file__).resolve().parents[4]
    literal = json.loads((root / ".evidence/qyh-m2-terminal-source-implementation-20261025/reader-v13-schema-literal-r374.json").read_text())
    for group, schemas in (("relations", reader._RELATIONS), ("registry", reader._REGISTRY)):
        expected = {item["name"]: item for item in literal[group]}
        assert set(schemas) == set(expected)
        for name, schema in schemas.items():
            assert schema.columns == tuple(tuple(c) for c in expected[name]["columns"])
            assert schema.key == tuple(expected[name]["key"])
            assert schema.cap == expected[name]["cap"]
    assert len(reader._RELATIONS) == 34 and len(reader._REGISTRY) == 3
    assert sum(len(s.columns) for s in (*reader._RELATIONS.values(), *reader._REGISTRY.values())) == 457


def test_empty_and_nonempty_frames_are_only_decoded_facts():
    for packet in (empty_packet(), nonempty_packet()):
        facts = decode(packet)
        assert len(facts.relations) == 34 and len(facts.registry) == 3
        assert not hasattr(facts, "authorized") and not hasattr(facts, "branch")
    facts = decode(nonempty_packet())
    row = facts.relations["public.automation_schedule_binding"][0]
    assert type(row["installation_id"]) is UUID
    assert type(row["effective_from"]) is datetime and row["effective_from"].utcoffset() is not None
    assert type(row["local_time"]) is time and row["local_time"].utcoffset() is None


@pytest.mark.parametrize("mutation", ["version", "root-extra", "family-missing", "family-extra", "row-missing", "row-extra", "not-list"])
def test_exact_wire_shape_refuses_changes(mutation):
    packet = nonempty_packet()
    rows = packet["relations"]["public.bundle_installation"]
    if mutation == "version": packet["schema"] = "aos.reinstall-terminal-source-facts/v2"
    elif mutation == "root-extra": packet["authorized"] = True
    elif mutation == "family-missing": packet["relations"].pop("public.bundle_installation")
    elif mutation == "family-extra": packet["relations"]["public.unregistered"] = []
    elif mutation == "row-missing": rows[0].pop("installation_id")
    elif mutation == "row-extra": rows[0]["approved"] = True
    else: packet["relations"]["public.bundle_installation"] = tuple(rows)
    with pytest.raises(ValueError): decode(packet)


@pytest.mark.parametrize("value", [True, 1.0, "1", -(2 ** 63) - 1, 2 ** 63])
def test_bigint_does_not_coerce_or_overflow(value):
    packet = nonempty_packet(); packet["relations"]["public.bundle_installation"][0]["current_revision"] = value
    with pytest.raises(ValueError): decode(packet)


def test_database_integer_boundaries_and_nullable_are_preserved():
    packet = nonempty_packet(); row = packet["relations"]["public.bundle_installation"][0]
    row["current_revision"] = -(2 ** 63); row["etag_version"] = 2 ** 63 - 1
    row["active_revision"] = None; row["previous_active_revision"] = None
    assert decode(packet).relations["public.bundle_installation"][0]["active_revision"] is None
    row["installation_id"] = None
    with pytest.raises(ValueError): decode(packet)


@pytest.mark.parametrize("column,value", [("installation_id", UUID_TEXT.upper()), ("installation_id", UUID(UUID_TEXT)),
    ("installation_id", "{" + UUID_TEXT + "}"), ("installation_id", UUID_TEXT.replace("-", "")),
    ("org_id", "invalid\x00text"), ("org_id", "\ud800")])
def test_uuid_and_utf8_text_are_exact(column, value):
    if column == "installation_id" and value == UUID_TEXT: value = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
    packet = nonempty_packet(); packet["relations"]["public.bundle_installation"][0][column] = value
    with pytest.raises(ValueError): decode(packet)


@pytest.mark.parametrize("column,value", [("effective_from", "2026-10-26T00:00:00"),
    ("effective_from", "invalid"), ("local_time", "12:30:00+08:00"), ("local_time", "25:00:00"),
    ("approved", 1), ("weekly_day", 2 ** 15)])
def test_temporal_boolean_and_smallint_types(column, value):
    packet = nonempty_packet(); packet["relations"]["public.automation_schedule_binding"][0][column] = value
    with pytest.raises(ValueError): decode(packet)


def test_duplicate_primary_keys_are_rejected_without_sorting_input():
    packet = nonempty_packet(); rows = packet["relations"]["public.extension_runtime_operation"]
    rows.append(deepcopy(rows[0])); rows[-1]["phase"] = "distinct-non-key-value"
    with pytest.raises(ValueError): decode(packet)
    rows[-1]["operation_id"] = "22222222-2222-4222-8222-222222222222"
    assert len(decode(packet).relations["public.extension_runtime_operation"]) == 2


def test_json_copy_preserves_input_and_aliases_are_charged_per_occurrence():
    packet = nonempty_packet(); shared = {"nested": ["月", 3, True, None]}
    packet["relations"]["public.extension_runtime_binding"][0]["package_lock_ref"] = shared
    packet["relations"]["public.extension_runtime_binding"][0]["config_ref"] = shared
    before = deepcopy(packet); ledger = reader._WorkLedger(); facts = decode(packet, ledger)
    assert packet == before and ledger.work_bytes > 0 and ledger.node_visits > 0
    row = facts.relations["public.extension_runtime_binding"][0]
    row["package_lock_ref"]["nested"].append("owned-copy")
    assert row["config_ref"]["nested"] == shared["nested"] and packet == before


@pytest.mark.parametrize("value", [float("nan"), float("inf"), b"bytes", {1: "non-text-key"}])
def test_non_json_values_are_rejected(value):
    packet = nonempty_packet(); packet["relations"]["public.extension_runtime_binding"][0]["config_ref"] = value
    with pytest.raises(ValueError): decode(packet)


def test_json_cycle_is_not_confused_with_legal_aliases():
    value = []; value.append(value)
    packet = nonempty_packet(); packet["relations"]["public.extension_runtime_binding"][0]["config_ref"] = value
    with pytest.raises(ValueError): decode(packet)


def test_json_byte_measurement_matches_compact_unicode_serialization():
    for value in ({"月": ["a\nb\\c\"", True, None, -1, 1.5]}, "", [], {}, "\x01" * 5000):
        ledger = reader._WorkLedger()
        size, nodes = reader._measure_json(value, ledger, reader._MAX_JSON_BYTES)
        assert size == len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode())
        assert nodes >= 1 and ledger.work_bytes == size


def test_depth_single_json_and_work_ledger_cap_plus_one():
    value = {}
    for _ in range(65): value = {"nested": value}
    with pytest.raises(ValueError): reader._measure_json(value, reader._WorkLedger(), reader._MAX_PACKET_BYTES)
    with pytest.raises(ValueError): reader._measure_json("x" * reader._MAX_JSON_BYTES, reader._WorkLedger(), reader._MAX_JSON_BYTES)
    for name, maximum, argument in (("row_visits", reader._MAX_ROW_VISITS, "rows"),
                                    ("work_bytes", reader._MAX_WORK_BYTES, "byte_count"),
                                    ("node_visits", reader._MAX_WORK_NODES, "node_count")):
        ledger = reader._WorkLedger(); ledger._charge(**{argument: maximum})
        assert getattr(ledger, name) == maximum
        with pytest.raises(ValueError): ledger._charge(**{argument: 1})


def test_family_row_budget_and_shared_ledger_are_not_reset():
    packet = empty_packet(); schema = reader._RELATIONS["public.bundle_installation"]
    packet["relations"]["public.bundle_installation"] = [row_for(schema), row_for(schema)]
    with pytest.raises(ValueError): decode(packet)
    ledger = reader._WorkLedger(); ledger._charge(byte_count=reader._MAX_WORK_BYTES - 1)
    with pytest.raises(ValueError): decode(empty_packet(), ledger)


@pytest.mark.parametrize("field,value", [("size", -1), ("size", 8 * 1024 ** 3 + 1), ("size", True), ("kind", "UnknownPack")])
def test_registry_specific_size_and_kind_limits(field, value):
    packet = nonempty_packet(); name = "public.asset_bundle" if field == "kind" else "public.asset_bundle_artifact"
    packet["registry"][name][0][field] = value
    with pytest.raises(ValueError): decode(packet)


def test_error_never_echoes_fact_values():
    packet = nonempty_packet(); marker = "private-looking-fixture-value"
    packet["relations"]["public.bundle_installation"][0]["installation_id"] = marker
    with pytest.raises(ValueError) as caught: decode(packet)
    assert marker not in str(caught.value)


def test_raw_authority_text_has_its_own_utf8_budget_before_semantic_parsing():
    packet = nonempty_packet()
    row = packet["relations"]["public.extension_runtime_uninstall_receipt"][0]
    row["authority_data_text"] = '{"x":"' + "x" * (reader._MAX_JSON_BYTES - 8) + '"}'
    assert len(row["authority_data_text"].encode()) == reader._MAX_JSON_BYTES
    assert decode(packet).relations["public.extension_runtime_uninstall_receipt"][0]["authority_data_text"] == row["authority_data_text"]
    row["authority_data_text"] = '{"x":"' + "月" * (reader._MAX_JSON_BYTES // 3) + '"}'
    assert len(row["authority_data_text"]) < reader._MAX_JSON_BYTES
    assert len(row["authority_data_text"].encode()) > reader._MAX_JSON_BYTES
    with pytest.raises(ValueError): decode(packet)


def test_repeated_scalar_validation_is_charged_to_same_ledger():
    ledger = reader._WorkLedger()
    assert reader._scalar("月", "text!", ledger) == "月"
    assert ledger.work_bytes == 3 and ledger.node_visits == 1


def test_global_row_cap_is_checked_before_packet_walk_or_indexing():
    packet = empty_packet()
    for name in ("public.extension_runtime_operation", "public.extension_runtime_dependency_ref",
                 "public.extension_runtime_resource_lease", "public.extension_runtime_execution_attempt"):
        packet["relations"][name] = [row_for(reader._RELATIONS[name])] * 2048
    packet["relations"]["public.bundle_installation"] = [row_for(reader._RELATIONS["public.bundle_installation"])]
    with mock.patch.object(reader, "_measure_json", side_effect=AssertionError("row cap must precede walk")):
        with pytest.raises(ValueError, match="budget"): decode(packet)


def test_packet_byte_and_json_node_exact_limits_and_cap_plus_one():
    value = "x" * (reader._MAX_PACKET_BYTES - 2)
    assert reader._measure_json(value, reader._WorkLedger(), reader._MAX_PACKET_BYTES)[0] == reader._MAX_PACKET_BYTES
    with pytest.raises(ValueError): reader._measure_json(value + "x", reader._WorkLedger(), reader._MAX_PACKET_BYTES)
    values = [0] * (reader._MAX_JSON_NODES - 1)
    assert reader._measure_json(values, reader._WorkLedger(), reader._MAX_PACKET_BYTES)[1] == reader._MAX_JSON_NODES
    with pytest.raises(ValueError): reader._measure_json(values + [0], reader._WorkLedger(), reader._MAX_PACKET_BYTES)


def source_package_context(*, backend=False, backend_count=1, frontend_only=False, markings=(), claim_count=2, artifact_count=0, artifact_override=None, legacy_content=False, legacy_snapshot=False, composition_id=None):
    from datetime import UTC
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.asset_registry.composition_contracts import RegistrySnapshotCandidate, RegistrySnapshot, StoredCompositionLock
    from aos_api.asset_registry.composition_store import _snapshot_from_json
    from aos_api.asset_registry.resolver import resolve
    from aos_api.tenant_scope import TenantScope
    from tests.asset_registry import test_composition_store as original
    candidate_json = original._snapshot_with_candidate().candidates[0].model_dump(mode="json", by_alias=True, exclude_none=False)
    manifest = candidate_json["manifest"]
    manifest["spec"]["permissions"]["markings"] = list(markings)
    candidate_json["permissions"]["markings"] = list(markings)
    if backend:
        manifest["spec"]["runtime"] = {"apiVersion": "aos.dev/bundle-runtime/v1alpha1", "backend": {
            "entrypoint": "backend/fixture.py:register", "pythonPackage": "fixture",
            "schemaNamespace": "fixture", "profileId": "internal-python-v1", "imageIndex": "artifacts/images.json"}}
        claims = [{"kind": "api", "method": "GET", "path": "/fixture/" + str(i),
                   "operationId": "fixture_" + str(i), "mode": "exclusive"} for i in range(claim_count)]
        manifest["spec"]["contributions"] = claims
        candidate_json["contributions"] = deepcopy(claims)
    elif frontend_only:
        manifest["spec"]["runtime"] = {"apiVersion": "aos.dev/bundle-runtime/v1alpha1", "frontend": {
            "manifest": "frontend/fixture.json", "artifactHash": "sha256:" + "d" * 64}}
    if legacy_content: manifest["spec"]["exports"].pop("knowledge")
    artifacts = [{"relativePath": "file" + str(i) + ".txt", "digest": "sha256:" + "d" * 64,
                  "size": i, "mediaType": "text/plain"} for i in range(artifact_count)]
    if artifact_override is not None: artifacts[0].update(artifact_override)
    content_hash = canonical_sha256({"manifest": manifest, "artifacts": artifacts})
    candidate_json["contentHash"] = content_hash
    candidate_entries = [(candidate_json, manifest, artifacts)]
    for index in range(1, backend_count if backend else 1):
        extra = deepcopy(candidate_json); extra_manifest = extra["manifest"]
        extra["id"] += "." + str(index); extra_manifest["metadata"]["id"] = extra["id"]
        for claim in extra_manifest["spec"]["contributions"]:
            claim["path"] += "/member" + str(index); claim["operationId"] += "_member" + str(index)
        extra["contributions"] = deepcopy(extra_manifest["spec"]["contributions"])
        extra["contentHash"] = canonical_sha256({"manifest": extra_manifest, "artifacts": artifacts})
        candidate_entries.append((extra, extra_manifest, deepcopy(artifacts)))
    candidates = [RegistrySnapshotCandidate.model_validate(entry[0]) for entry in candidate_entries]
    candidate = candidates[0]
    snapshot = RegistrySnapshot.build(candidates=candidates, checked_at=datetime(2026, 10, 26, tzinfo=UTC))
    snapshot_json = snapshot.model_dump(mode="json", by_alias=True, exclude_none=False)
    if legacy_snapshot:
        snapshot_json["candidates"][0]["manifest"]["spec"]["exports"].pop("knowledge")
        snapshot_json["snapshotHash"] = canonical_sha256({"schemaVersion": snapshot_json["schemaVersion"], "candidates": snapshot_json["candidates"]})
        snapshot = _snapshot_from_json(snapshot_json)
    request = original._request()
    if len(candidates) > 1:
        from aos_api.asset_registry.composition_contracts import CompositionRequest
        request_json = request.model_dump(mode="python", by_alias=True)
        request_json["requested"] = [{"publisher": item.publisher, "id": item.id, "version": item.version} for item in candidates]
        request = CompositionRequest.model_validate(request_json)
    payload = resolve(request, snapshot, None)
    diffs = {"permission_diff": payload.permission_diff, "migration_plan": payload.migration_plan,
             "contribution_diff": payload.contribution_diff}
    lock = StoredCompositionLock.model_validate({"compositionId": UUID_TEXT if composition_id is None else composition_id, "revision": 1, "payload": payload,
        "lockHash": canonical_sha256(payload.hash_payload_dump()),
        "permissionDiffHash": canonical_sha256(diffs["permission_diff"].model_dump(mode="json", by_alias=True, exclude_none=False)),
        "migrationPlanHash": canonical_sha256(diffs["migration_plan"].model_dump(mode="json", by_alias=True, exclude_none=False)),
        "contributionDiffHash": canonical_sha256(diffs["contribution_diff"].model_dump(mode="json", by_alias=True, exclude_none=False)),
        "createdAt": datetime(2026, 10, 26, tzinfo=UTC)})
    packet = empty_packet(); scope = TenantScope("org-org", "dev-project")
    packet["relations"]["public.bundle_composition"] = [{"org_id": scope.org_id, "project_id": scope.project_id,
        "composition_pk": lock.composition_id, "composition_id": lock.composition_id,
        "registry_snapshot_json": snapshot_json, "registry_snapshot_hash": snapshot.snapshot_hash}]
    packet["relations"]["public.bundle_composition_lock"] = [{"org_id": scope.org_id, "project_id": scope.project_id,
        "composition_pk": lock.composition_id, "revision": lock.revision, "lock_payload": payload.hash_payload_dump(),
        "lock_hash": lock.lock_hash, "permission_diff_json": diffs["permission_diff"].model_dump(mode="json", by_alias=True, exclude_none=False),
        "permission_diff_hash": lock.permission_diff_hash, "migration_plan_json": diffs["migration_plan"].model_dump(mode="json", by_alias=True, exclude_none=False),
        "migration_plan_hash": lock.migration_plan_hash, "contribution_diff_json": diffs["contribution_diff"].model_dump(mode="json", by_alias=True, exclude_none=False),
        "contribution_diff_hash": lock.contribution_diff_hash}]
    packet["registry"]["public.asset_bundle"] = [{"bundle_pk": UUID_TEXT, "publisher": candidate.publisher,
        "bundle_id": candidate.id, "kind": candidate.kind.value}]
    packet["registry"]["public.asset_bundle_version"] = [{"version_pk": UUID_TEXT, "bundle_pk": UUID_TEXT,
        "version": candidate.version, "manifest_json": manifest, "content_hash": content_hash}]
    packet["registry"]["public.asset_bundle_artifact"] = [{"version_pk": UUID_TEXT,
        "relative_path": item["relativePath"], "digest": item["digest"], "size": item["size"], "media_type": item["mediaType"]} for item in artifacts]
    for index, (extra, extra_manifest, extra_artifacts) in enumerate(candidate_entries[1:], 1):
        pk = str(UUID(int=10000 + index))
        packet["registry"]["public.asset_bundle"].append({"bundle_pk": pk, "publisher": extra["publisher"],
            "bundle_id": extra["id"], "kind": extra["kind"]})
        packet["registry"]["public.asset_bundle_version"].append({"version_pk": pk, "bundle_pk": pk,
            "version": extra["version"], "manifest_json": extra_manifest, "content_hash": extra["contentHash"]})
        packet["registry"]["public.asset_bundle_artifact"].extend({"version_pk": pk,
            "relative_path": item["relativePath"], "digest": item["digest"], "size": item["size"], "media_type": item["mediaType"]}
            for item in extra_artifacts)
    return packet, scope, lock


def verify_packages(packet, scope, lock, ledger=None):
    ledger = reader._WorkLedger() if ledger is None else ledger
    return reader._verify_source_packages(decode(packet, ledger), scope, lock, ledger)


@pytest.mark.parametrize("legacy_content,legacy_snapshot,artifact_count", [(False, False, 0), (True, False, 0), (False, True, 0), (True, True, 0), (False, False, 2)])
def test_source_packages_link_real_resolver_snapshot_and_current_or_legacy_content(legacy_content, legacy_snapshot, artifact_count):
    packet, scope, lock = source_package_context(legacy_content=legacy_content, legacy_snapshot=legacy_snapshot, artifact_count=artifact_count)
    before = deepcopy(packet); result = verify_packages(packet, scope, lock)
    assert len(result) == 1 and result[0].selected == lock.payload.resolved[0]
    assert result[0].manifest.metadata.id == lock.payload.resolved[0].id
    assert result[0].description is None and result[0].claims_hash is None
    assert not hasattr(result[0], "authorized") and packet == before


@pytest.mark.parametrize("mutation", ["tenant", "composition-id", "composition-pk", "revision", "snapshot-hash", "lock-hash", "diff", "candidate-hash", "missing-composition", "missing-lock"])
def test_source_snapshot_and_physical_context_mismatch_is_refused(mutation):
    packet, scope, lock = source_package_context()
    parent = packet["relations"]["public.bundle_composition"][0]; child = packet["relations"]["public.bundle_composition_lock"][0]
    if mutation == "tenant": parent["org_id"] = "dev-org"
    elif mutation == "composition-id": parent["composition_id"] = "22222222-2222-4222-8222-222222222222"
    elif mutation == "composition-pk": child["composition_pk"] = "22222222-2222-4222-8222-222222222222"
    elif mutation == "revision": child["revision"] += 1
    elif mutation == "snapshot-hash": parent["registry_snapshot_hash"] = "sha256:" + "f" * 64
    elif mutation == "lock-hash": child["lock_hash"] = "sha256:" + "f" * 64
    elif mutation == "diff": child["permission_diff_json"]["target"]["roles"] = ["admin"]
    elif mutation == "candidate-hash": parent["registry_snapshot_json"]["candidates"][0]["signatureFingerprint"] = "sha256:" + "f" * 64
    elif mutation == "missing-composition": packet["relations"]["public.bundle_composition"] = []
    else: packet["relations"]["public.bundle_composition_lock"] = []
    with pytest.raises(ValueError): verify_packages(packet, scope, lock)


@pytest.mark.parametrize("mutation", ["missing-bundle", "extra-bundle", "wrong-parent", "version", "hash", "manifest-id", "artifact-version", "artifact-order"])
def test_registry_is_exact_selected_set_and_full_descriptor(mutation):
    packet, scope, lock = source_package_context(artifact_count=2)
    version = packet["registry"]["public.asset_bundle_version"][0]
    if mutation == "missing-bundle": packet["registry"]["public.asset_bundle"] = []
    elif mutation == "extra-bundle":
        extra = deepcopy(packet["registry"]["public.asset_bundle"][0]); extra["bundle_pk"] = "22222222-2222-4222-8222-222222222222"; extra["bundle_id"] = "unexpected"; packet["registry"]["public.asset_bundle"].append(extra)
    elif mutation == "wrong-parent": version["bundle_pk"] = "22222222-2222-4222-8222-222222222222"
    elif mutation == "version": version["version"] = "2.0.0"
    elif mutation == "hash": version["content_hash"] = "sha256:" + "e" * 64
    elif mutation == "manifest-id": version["manifest_json"]["metadata"]["id"] = "unexpected"
    elif mutation == "artifact-version": packet["registry"]["public.asset_bundle_artifact"][0]["version_pk"] = "22222222-2222-4222-8222-222222222222"
    else: packet["registry"]["public.asset_bundle_artifact"].reverse()
    with pytest.raises(ValueError): verify_packages(packet, scope, lock)


def test_backend_claims_use_original_distinct_digest_domains_and_fixed_cap():
    from aos_api.extension_runtime.lifecycle_store import _digest
    from aos_api.extension_runtime.registration import registration_fingerprint
    packet, scope, lock = source_package_context(backend=True, claim_count=2)
    bundle = verify_packages(packet, scope, lock)[0]
    assert bundle.claims_hash == _digest(bundle.description.model_dump(mode="json", by_alias=True))
    assert bundle.registration_fingerprint == registration_fingerprint(bundle.description)
    assert bundle.claims_hash != bundle.registration_fingerprint
    packet, scope, lock = source_package_context(backend=True, claim_count=257)
    with pytest.raises(ValueError) as caught: verify_packages(packet, scope, lock)
    from pydantic import ValidationError
    assert isinstance(caught.value.__context__, ValidationError)
    assert any(error["type"] == "too_long" for error in caught.value.__context__.errors())


def test_source_package_errors_do_not_echo_payload_or_wrong_namespace():
    packet, scope, lock = source_package_context()
    packet["registry"]["public.asset_bundle_version"][0]["manifest_json"]["metadata"]["id"] = "private-looking-fixture"
    with pytest.raises(ValueError) as caught: verify_packages(packet, scope, lock)
    assert "private-looking-fixture" not in str(caught.value)
    class ForeignScope(type(scope)): pass
    with pytest.raises(ValueError): verify_packages(*source_package_context()[:1], ForeignScope(scope.org_id, scope.project_id), lock)


def test_recomputed_selected_hash_still_must_match_original_candidate_projection():
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.asset_registry.composition_contracts import CompositionLockPayload, StoredCompositionLock
    packet, scope, lock = source_package_context()
    body = lock.payload.model_dump(mode="python", by_alias=True, exclude_none=False)
    body["resolved"][0]["signatureFingerprint"] = "sha256:" + "e" * 64
    payload = CompositionLockPayload.model_validate(body)
    changed = lock.model_dump(mode="python", by_alias=True, exclude_none=False)
    changed["payload"] = payload; changed["lockHash"] = canonical_sha256(payload.hash_payload_dump())
    altered = StoredCompositionLock.model_validate(changed)
    row = packet["relations"]["public.bundle_composition_lock"][0]
    row["lock_payload"] = payload.hash_payload_dump(); row["lock_hash"] = altered.lock_hash
    with pytest.raises(ValueError): verify_packages(packet, scope, altered)


def test_missing_candidate_with_recomputed_raw_and_lock_hashes_is_refused():
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.asset_registry.composition_contracts import CompositionLockPayload, StoredCompositionLock
    packet, scope, lock = source_package_context()
    parent = packet["relations"]["public.bundle_composition"][0]
    raw = parent["registry_snapshot_json"]; raw["candidates"] = []
    raw["snapshotHash"] = canonical_sha256({"schemaVersion": raw["schemaVersion"], "candidates": []})
    parent["registry_snapshot_hash"] = raw["snapshotHash"]
    body = lock.payload.model_dump(mode="python", by_alias=True, exclude_none=False)
    body["registrySnapshotHash"] = raw["snapshotHash"]
    payload = CompositionLockPayload.model_validate(body)
    changed = lock.model_dump(mode="python", by_alias=True, exclude_none=False)
    changed["payload"] = payload; changed["lockHash"] = canonical_sha256(payload.hash_payload_dump())
    altered = StoredCompositionLock.model_validate(changed)
    row = packet["relations"]["public.bundle_composition_lock"][0]
    row["lock_payload"] = payload.hash_payload_dump(); row["lock_hash"] = altered.lock_hash
    with pytest.raises(ValueError): verify_packages(packet, scope, altered)


def test_original_backend_registration_accepts_256_claims_within_shared_budget():
    packet, scope, lock = source_package_context(backend=True, claim_count=256)
    ledger = reader._WorkLedger()
    bundle = verify_packages(packet, scope, lock, ledger)[0]
    assert len(bundle.description.contributions) == 256
    assert ledger.node_visits <= reader._MAX_WORK_NODES and ledger.work_bytes <= reader._MAX_WORK_BYTES


def test_bad_model_copy_cannot_bypass_canonical_lock_revalidation():
    packet, scope, lock = source_package_context()
    altered = lock.model_copy(update={"lock_hash": "sha256:" + "f" * 64})
    with pytest.raises(ValueError): verify_packages(packet, scope, altered)


def test_frontend_only_runtime_does_not_create_backend_claims_or_a_business_branch():
    packet, scope, lock = source_package_context(frontend_only=True)
    bundle = verify_packages(packet, scope, lock)[0]
    assert bundle.manifest.spec.runtime.frontend is not None
    assert bundle.manifest.spec.runtime.backend is None and bundle.description is None
    assert not hasattr(bundle, "branch")


@pytest.mark.parametrize("field,value", [("digest", "not-a-digest"), ("relativePath", "../outside.txt"),
    ("relativePath", "x" * 1025), ("mediaType", "not-a-media-type"), ("mediaType", "x/" + "y" * 254)])
def test_self_consistent_descriptor_hash_does_not_skip_original_artifact_field_contract(field, value):
    packet, scope, lock = source_package_context(artifact_count=1, artifact_override={field: value})
    with pytest.raises(ValueError): verify_packages(packet, scope, lock)


def test_source_association_never_invokes_current_release_policy_loader_or_root_file():
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.asset_registry.signature import FileTrustRootProvider
    packet, scope, lock = source_package_context(artifact_count=1)
    with mock.patch.object(ReleasePolicy, "evaluate", side_effect=AssertionError("current policy is not history proof")) as evaluate, \
         mock.patch.object(ReleasePolicy, "snapshot", side_effect=AssertionError("no trust snapshot")) as snapshot, \
         mock.patch.object(ManifestLoader, "load", side_effect=AssertionError("no artifact I/O")) as load, \
         mock.patch.object(FileTrustRootProvider, "_read_roots", side_effect=AssertionError("no configuration I/O")) as roots:
        assert len(verify_packages(packet, scope, lock)) == 1
    assert all(call.call_count == 0 for call in (evaluate, snapshot, load, roots))


class CurrentPermissionResult:
    def __init__(self, *, row=None, rows=None): self.row = row; self.rows = rows
    def fetchone(self): return self.row
    def fetchall(self): return self.rows


class CurrentPermissionConnection:
    def __init__(self, *, roles=("admin", "admin")):
        from types import SimpleNamespace
        from psycopg.pq import TransactionStatus
        self.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        self.scope = {"org_id": "org-org", "project_id": "dev-project"}
        self.roles = list(roles); self.membership_reads = 0; self.calls = []
        self.bearers = {"marking:source-mark", "marking:target-mark"}
        self.member_duplicate = False; self.bearer_duplicate = False; self.failure = None
    def execute(self, query, params=()):
        assert query.lstrip().upper().startswith("SELECT")
        self.calls.append((query, params))
        if self.failure is not None: raise self.failure
        if "current_setting" in query: return CurrentPermissionResult(row=dict(self.scope))
        if "meta_membership" in query:
            index = min(self.membership_reads, len(self.roles) - 1); self.membership_reads += 1
            role = self.roles[index]
            rows = [] if role is None else [{"role": role}]
            return CurrentPermissionResult(rows=rows * (2 if self.member_duplicate else 1))
        if "authz_tuple" in query:
            rows = [{"object_key": params[-1]}] if params[-1] in self.bearers else []
            return CurrentPermissionResult(rows=rows * (2 if self.bearer_duplicate else 1))
        raise AssertionError("unexpected permission query")
    def commit(self): raise AssertionError("permission reader cannot commit")
    def rollback(self): raise AssertionError("permission reader cannot roll back")
    def close(self): raise AssertionError("permission reader cannot replace connection")


def permission_locks():
    _, scope, source = source_package_context(markings=("source-mark",))
    _, _, target = source_package_context(markings=("target-mark",))
    target = target.model_copy(update={"composition_id": "22222222-2222-4222-8222-222222222222"})
    return scope, source, target


def current_permissions(conn, scope, source, target, ledger=None):
    return reader._read_current_permissions(conn, scope=scope, actor="fixture-user", source_lock=source,
        target_lock=target, ledger=reader._WorkLedger() if ledger is None else ledger)


@pytest.mark.parametrize("role", ["admin", "owner", "developer", "asset-installer"])
def test_both_original_current_permissions_are_read_on_same_transaction(monkeypatch, role):
    from aos_api.extension_runtime import ui_current_principal as current
    monkeypatch.setattr(current, "openfga_api_url", lambda: None)
    scope, source, target = permission_locks(); conn = CurrentPermissionConnection(roles=(role, role))
    with mock.patch.object(current, "read_current_ui_principal", wraps=current.read_current_ui_principal) as read:
        principals = current_permissions(conn, scope, source, target)
    assert len(principals) == 2 and all(type(p) is current.CurrentUiPrincipal for p in principals)
    assert [call.kwargs["required_markings"] for call in read.call_args_list] == [("source-mark",), ("target-mark",)]
    assert all(call.kwargs["conn"] is conn and call.kwargs["scope"].key == scope.key and
               call.kwargs["subject"] == "fixture-user" for call in read.call_args_list)
    assert conn.membership_reads == 2
    assert all("FOR SHARE" in q for q, _ in conn.calls if "meta_membership" in q or "authz_tuple" in q)
    assert all(params[-1] == "fixture-user" for q, params in conn.calls if "meta_membership" in q)
    assert all(params[-2] == "user:fixture-user" for q, params in conn.calls if "authz_tuple" in q)


@pytest.mark.parametrize("roles", [("viewer", "admin"), ("admin", "viewer"), ("operator", "operator"),
                                  ("asset-install-approver", "asset-install-approver"), (None, "admin"), ("admin", None)])
def test_current_roles_and_removal_cannot_be_replaced_by_cached_permissions(monkeypatch, roles):
    from aos_api.asset_registry.errors import AssetRegistryError
    from aos_api.extension_runtime import ui_current_principal as current
    monkeypatch.setattr(current, "openfga_api_url", lambda: None)
    scope, source, target = permission_locks(); conn = CurrentPermissionConnection(roles=roles)
    with pytest.raises((ValueError, AssetRegistryError)): current_permissions(conn, scope, source, target)


@pytest.mark.parametrize("mutation", ["scope", "source-bearer", "target-bearer", "duplicate-member", "duplicate-bearer", "idle", "remote"])
def test_current_authority_failure_has_no_fallback_or_transaction_side_effect(monkeypatch, mutation):
    from psycopg.pq import TransactionStatus
    from aos_api.extension_runtime import ui_current_principal as current
    monkeypatch.setattr(current, "openfga_api_url", lambda: "https://example.test" if mutation == "remote" else None)
    scope, source, target = permission_locks(); conn = CurrentPermissionConnection()
    if mutation == "scope": conn.scope["org_id"] = "dev-org"
    elif mutation == "source-bearer": conn.bearers.remove("marking:source-mark")
    elif mutation == "target-bearer": conn.bearers.remove("marking:target-mark")
    elif mutation == "duplicate-member": conn.member_duplicate = True
    elif mutation == "duplicate-bearer": conn.bearer_duplicate = True
    elif mutation == "idle": conn.info.transaction_status = TransactionStatus.IDLE
    with pytest.raises((ValueError, RuntimeError)): current_permissions(conn, scope, source, target)
    if mutation in ("idle", "remote"): assert conn.calls == []


def test_permission_results_are_not_cached_across_checks(monkeypatch):
    from aos_api.asset_registry.errors import AssetRegistryError
    from aos_api.extension_runtime import ui_current_principal as current
    monkeypatch.setattr(current, "openfga_api_url", lambda: None)
    scope, source, target = permission_locks(); conn = CurrentPermissionConnection()
    current_permissions(conn, scope, source, target)
    conn.roles = ["viewer"]
    with pytest.raises(AssetRegistryError): current_permissions(conn, scope, source, target)
    assert conn.membership_reads == 3


@pytest.mark.parametrize("mutation", ["namespace", "scope", "subject", "roles", "markings"])
def test_current_adapter_result_must_be_canonical_and_bound(monkeypatch, mutation):
    from types import SimpleNamespace
    from aos_api.tenant_scope import TenantScope
    from aos_api.extension_runtime import ui_current_principal as current
    scope, source, target = permission_locks(); conn = CurrentPermissionConnection()
    values = dict(scope=scope, subject="fixture-user", roles=("admin",), markings=("source-mark",))
    if mutation == "scope": values["scope"] = TenantScope("dev-org", scope.project_id)
    elif mutation == "subject": values["subject"] = "another-user"
    elif mutation == "roles": values["roles"] = ["admin"]
    elif mutation == "markings": values["markings"] = ["source-mark"]
    result = SimpleNamespace(**values) if mutation == "namespace" else current.CurrentUiPrincipal(**values)
    monkeypatch.setattr(current, "read_current_ui_principal", lambda **kwargs: result)
    with pytest.raises(ValueError): current_permissions(conn, scope, source, target)


def test_permission_sqlstate_propagates_unchanged_without_retry(monkeypatch):
    import psycopg
    from aos_api.extension_runtime import ui_current_principal as current
    monkeypatch.setattr(current, "openfga_api_url", lambda: None)
    scope, source, target = permission_locks(); conn = CurrentPermissionConnection()
    error = psycopg.errors.LockNotAvailable("synthetic locked metadata")
    conn.failure = error
    with pytest.raises(psycopg.errors.LockNotAvailable) as caught: current_permissions(conn, scope, source, target)
    assert caught.value is error and caught.value.sqlstate == "55P03" and len(conn.calls) == 1


@pytest.mark.parametrize("side", ["source", "target"])
def test_admin_current_principal_cannot_bypass_either_lock_marking(monkeypatch, side):
    from aos_api.asset_registry.errors import MarkingAccessDeniedError
    from aos_api.extension_runtime import ui_current_principal as current
    scope, source, target = permission_locks(); conn = CurrentPermissionConnection()
    reads = []
    def read(**kwargs):
        required = kwargs["required_markings"]; reads.append(required)
        markings = () if required == (side + "-mark",) else required
        return current.CurrentUiPrincipal(scope, "fixture-user", ("admin",), markings)
    monkeypatch.setattr(current, "read_current_ui_principal", read)
    with pytest.raises(MarkingAccessDeniedError): current_permissions(conn, scope, source, target)
    assert len(reads) == (1 if side == "source" else 2)


@pytest.mark.parametrize("values", [(), ("admin", "admin"), (" admin",), ("admin\n",), (True,)])
def test_invalid_current_role_facts_are_not_normalized_into_authority(monkeypatch, values):
    from aos_api.extension_runtime import ui_current_principal as current
    scope, source, target = permission_locks(); conn = CurrentPermissionConnection()
    monkeypatch.setattr(current, "read_current_ui_principal", lambda **kwargs:
        current.CurrentUiPrincipal(scope, "fixture-user", values, ("source-mark",)))
    with pytest.raises(ValueError): current_permissions(conn, scope, source, target)


@pytest.mark.parametrize("budget", ["row", "node", "bytes"])
def test_exhausted_shared_permission_budget_refuses_before_sql(monkeypatch, budget):
    from aos_api.extension_runtime import ui_current_principal as current
    monkeypatch.setattr(current, "openfga_api_url", lambda: None)
    scope, source, target = permission_locks(); conn = CurrentPermissionConnection(); ledger = reader._WorkLedger()
    if budget == "row": ledger._charge(rows=reader._MAX_ROW_VISITS)
    elif budget == "node": ledger._charge(node_count=reader._MAX_WORK_NODES)
    else: ledger._charge(byte_count=reader._MAX_WORK_BYTES)
    with pytest.raises(ValueError): current_permissions(conn, scope, source, target, ledger)
    assert not conn.calls


def test_tampered_target_lock_is_revalidated_before_any_current_query(monkeypatch):
    from aos_api.extension_runtime import ui_current_principal as current
    monkeypatch.setattr(current, "openfga_api_url", lambda: None)
    scope, source, target = permission_locks(); conn = CurrentPermissionConnection()
    target = target.model_copy(update={"lock_hash": "sha256:" + "0" * 64})
    with pytest.raises(ValueError): current_permissions(conn, scope, source, target)
    assert not conn.calls


def source_history_context(route="approved", *, backend=False, backend_count=1, installation_pk=None):
    from aos_api.asset_registry import installation_evidence as evidence
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.asset_registry.composition_contracts import InstallationRecord
    from aos_api.asset_registry.installation_store import LockedInstallation
    from aos_api.asset_registry.reinstall_contracts import ReinstallSourceRef
    from tests.asset_registry import test_composition_contracts as original
    packet, scope, lock = source_package_context(backend=backend, backend_count=backend_count)
    value = original._approved_record_payload()
    states = {"approved": ["uninstalled"], "active": ["applied", "active", "uninstalled"],
              "reset": ["applied", "approved", "uninstalled"],
              "two-reset": ["applied", "approved", "applied", "approved", "uninstalled"],
              "reset-active": ["applied", "approved", "applied", "active", "uninstalled"]}[route]
    hashes = {name: getattr(lock, name) for name in
              ("lock_hash", "permission_diff_hash", "migration_plan_hash", "contribution_diff_hash")}
    aliases = {"lock_hash": "lockHash", "permission_diff_hash": "permissionDiffHash",
               "migration_plan_hash": "migrationPlanHash", "contribution_diff_hash": "contributionDiffHash"}
    for name, alias in aliases.items():
        value["current"][alias] = hashes[name]; value["decision"][alias] = hashes[name]
    value["current"]["compositionId"] = lock.composition_id
    for state in states: value = original._append_installation_state(value, state)
    value["activeRevision"] = value["previousActiveRevision"] = None
    for event in value["events"]:
        kinds = [kind for kind, (_, to_state) in evidence._TRANSITIONS.items()
                 if to_state == event["toState"] and event["fromState"] in evidence._ALLOWED_FROM_STATES[kind]]
        if kinds:
            kind = "runtime_preparation" if (backend or route in ("reset", "two-reset")) and event["toState"] == "applied" else kinds[0]
            event["evidence"] = evidence.build_event_evidence(evidence_type=kind,
                installation_id=value["installationId"], from_revision=event["fromRevision"],
                to_revision=event["toRevision"], from_state=event["fromState"], **hashes,
                decision_id=value["decision"]["decisionId"], observed_at=event["createdAt"]).model_dump(mode="python", by_alias=True)
    value["events"][-1]["reason"] = "offline source retirement"
    record = InstallationRecord.model_validate(value)
    native_pk = UUID(UUID_TEXT if installation_pk is None else installation_pk)
    locked = LockedInstallation(scope.org_id, scope.project_id, native_pk, record)
    source = ReinstallSourceRef(installationId=record.installation_id,
        terminalRevision=record.current_revision, lockHash=lock.lock_hash)
    base = {"org_id": scope.org_id, "project_id": scope.project_id, "installation_pk": str(native_pk)}
    packet["relations"]["public.bundle_installation"] = [{**base, "installation_id": record.installation_id,
        "current_revision": record.current_revision, "etag_version": record.etag_version,
        "active_revision": record.active_revision, "previous_active_revision": record.previous_active_revision}]
    packet["relations"]["public.bundle_installation_revision"] = [{**base, "revision": event.to_revision,
        "parent_revision": event.from_revision, "state": event.to_state, "composition_pk": packet["relations"]["public.bundle_composition"][0]["composition_pk"],
        "lock_revision": lock.revision, **hashes, "overlay_revision": record.current.overlay_revision,
        "decision_id": record.current.decision_id if event.to_state not in ("draft", "submitted") else None}
        for event in record.events]
    packet["relations"]["public.bundle_installation_event"] = [{**base, "sequence": event.sequence,
        "from_revision": event.from_revision, "to_revision": event.to_revision,
        "from_state": event.from_state, "to_state": event.to_state, "actor": event.actor,
        "evidence_json": event.evidence.model_dump(mode="json", by_alias=True) if event.evidence is not None else None,
        "evidence_hash": canonical_sha256(event.evidence.model_dump(mode="json", by_alias=True)) if event.evidence is not None else None}
        for event in record.events]
    return packet, scope, source, locked, lock


def verify_history(packet, scope, source, locked, lock):
    ledger = reader._WorkLedger()
    return reader._verify_source_history(decode(packet, ledger), scope=scope, source=source,
        locked_source=locked, source_lock=lock, ledger=ledger)


@pytest.mark.parametrize("route", ["approved", "active", "reset"])
def test_complete_source_histories_use_original_evidence_domains_without_input_mutation(route):
    args = source_history_context(route); before = deepcopy(args)
    result = verify_history(*args)
    assert result == args[3].record and result is not args[3].record
    assert result.events[-1].evidence.type == "uninstall" and not hasattr(result, "authorized")
    assert args == before


@pytest.mark.parametrize("mutation", ["missing-head", "head-id", "head-pk", "head-etag", "head-active",
    "tenant", "missing-revision", "extra-revision", "revision-pk", "parent", "state", "composition",
    "lock-revision", "lock-hash", "permission-hash", "migration-hash", "contribution-hash", "overlay", "decision",
    "missing-event", "extra-event", "event-pk", "event-parent", "event-state", "actor", "outer-hash",
    "missing-proof", "unexpected-proof"])
def test_source_history_rows_must_match_original_complete_record(mutation):
    args = source_history_context("active"); packet = args[0]
    head = packet["relations"]["public.bundle_installation"]
    revisions = packet["relations"]["public.bundle_installation_revision"]
    events = packet["relations"]["public.bundle_installation_event"]
    other = "44444444-4444-4444-8444-444444444444"
    if mutation == "missing-head": head.clear()
    elif mutation == "head-id": head[0]["installation_id"] = other
    elif mutation == "head-pk": head[0]["installation_pk"] = other
    elif mutation == "head-etag": head[0]["etag_version"] += 1
    elif mutation == "head-active": head[0]["active_revision"] = head[0]["previous_active_revision"] = 5
    elif mutation == "tenant": revisions[0]["org_id"] = "dev-org"
    elif mutation == "missing-revision": revisions.pop(1)
    elif mutation == "extra-revision": revisions.append({**revisions[-1], "revision": 7, "parent_revision": 6})
    elif mutation == "revision-pk": revisions[0]["installation_pk"] = other
    elif mutation == "parent": revisions[-1]["parent_revision"] = 1
    elif mutation == "state": revisions[-1]["state"] = "active"
    elif mutation == "composition": revisions[0]["composition_pk"] = other
    elif mutation == "lock-revision": revisions[0]["lock_revision"] += 1
    elif mutation.endswith("hash") and mutation not in ("outer-hash",):
        field = {"lock-hash": "lock_hash", "permission-hash": "permission_diff_hash",
                 "migration-hash": "migration_plan_hash", "contribution-hash": "contribution_diff_hash"}[mutation]
        revisions[0][field] = "sha256:" + "0" * 64
    elif mutation == "overlay": revisions[0]["overlay_revision"] = "different-overlay"
    elif mutation == "decision": revisions[-1]["decision_id"] = other
    elif mutation == "missing-event": events.pop(1)
    elif mutation == "extra-event": events.append({**events[-1], "sequence": 7})
    elif mutation == "event-pk": events[-1]["installation_pk"] = other
    elif mutation == "event-parent": events[-1]["from_revision"] = 1
    elif mutation == "event-state": events[-1]["from_state"] = "approved"
    elif mutation == "actor": events[-1]["actor"] = "unrelated-actor"
    elif mutation == "outer-hash": events[-1]["evidence_hash"] = "sha256:" + "0" * 64
    elif mutation == "missing-proof": events[-1]["evidence_json"] = events[-1]["evidence_hash"] = None
    elif mutation == "unexpected-proof":
        events[0]["evidence_json"] = deepcopy(events[-1]["evidence_json"])
        events[0]["evidence_hash"] = events[-1]["evidence_hash"]
    with pytest.raises(ValueError): verify_history(*args)


def test_source_history_uses_complete_sets_without_inventing_wire_order():
    args = source_history_context("reset")
    args[0]["relations"]["public.bundle_installation_revision"].reverse()
    args[0]["relations"]["public.bundle_installation_event"].reverse()
    assert verify_history(*args) == args[3].record


@pytest.mark.parametrize("mutation", ["source-ref", "locked-scope", "locked-pk", "record-copy", "namespace", "missing-runtime-proof"])
def test_typed_source_objects_cannot_replace_history_integrity(mutation):
    from dataclasses import replace
    from types import SimpleNamespace
    args = list(source_history_context("active")); source, locked = args[2:4]
    if mutation == "source-ref": args[2] = source.model_copy(update={"terminal_revision": 4})
    elif mutation == "locked-scope": args[3] = replace(locked, org_id="dev-org")
    elif mutation == "locked-pk": args[3] = replace(locked, installation_pk=UUID(int=42))
    elif mutation == "record-copy": args[3] = replace(locked, record=locked.record.model_copy(update={"state": "active"}))
    elif mutation == "namespace": args[3] = SimpleNamespace(org_id=locked.org_id,
        project_id=locked.project_id, installation_pk=locked.installation_pk, record=locked.record)
    elif mutation == "missing-runtime-proof":
        record = deepcopy(locked.record)
        object.__setattr__(record.events[3], "evidence", None)
        args[0]["relations"]["public.bundle_installation_event"][3]["evidence_json"] = None
        args[0]["relations"]["public.bundle_installation_event"][3]["evidence_hash"] = None
        args[3] = replace(locked, record=record)
    with pytest.raises(ValueError): verify_history(*args)


@pytest.mark.parametrize("mutation", ["inner-context", "target-state", "approval-actor", "bool-revision"])
def test_self_consistent_record_and_wire_cannot_replace_evidence_context(mutation):
    from dataclasses import replace
    from aos_api.asset_registry import installation_evidence as evidence
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args = list(source_history_context("active")); record = deepcopy(args[3].record)
    if mutation == "approval-actor":
        object.__setattr__(record.decision, "actor", "another-reviewer")
    elif mutation == "bool-revision":
        object.__setattr__(record.events[1], "from_revision", True)
    else:
        event = record.events[-1] if mutation == "inner-context" else record.events[-2]
        proof = evidence.build_event_evidence(evidence_type="uninstall" if mutation == "inner-context" else "preparation_reset",
            installation_id=record.installation_id, from_revision=event.from_revision,
            to_revision=event.to_revision, from_state=event.from_state,
            **{name: getattr(record.current, name) for name in ("lock_hash", "permission_diff_hash", "migration_plan_hash", "contribution_diff_hash")},
            decision_id="44444444-4444-4444-8444-444444444444" if mutation == "inner-context" else record.decision.decision_id,
            observed_at=event.created_at)
        object.__setattr__(event, "evidence", proof)
        row = args[0]["relations"]["public.bundle_installation_event"][event.sequence - 1]
        row["evidence_json"] = proof.model_dump(mode="json", by_alias=True)
        row["evidence_hash"] = canonical_sha256(row["evidence_json"])
    args[3] = replace(args[3], record=record)
    with pytest.raises(ValueError): verify_history(*args)


def test_history_validation_never_calls_original_mutating_transition():
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    with mock.patch.object(PostgresInstallationStore, "_append_transition", side_effect=AssertionError("read-only facts")) as append:
        result = verify_history(*source_history_context("reset"))
    assert result.state == "uninstalled" and append.call_count == 0


def preparation_resource_context(*, two_generations=False, uncommitted=None, member_count=1, route=None):
    from datetime import UTC
    from aos_api.extension_runtime.lifecycle_store import _digest
    from aos_api.extension_runtime.contracts import RegistrationDescription
    args = source_history_context(route or ("two-reset" if two_generations else "reset"), backend=True, backend_count=member_count)
    packet, scope, source, locked, lock = args
    base = {"org_id": scope.org_id, "project_id": scope.project_id}
    timestamp = datetime(2026, 8, 3, 1, tzinfo=UTC).isoformat()
    selected = lock.payload.resolved[0]
    manifest = packet["registry"]["public.asset_bundle_version"][0]["manifest_json"]
    description = RegistrationDescription(contributions=manifest["spec"]["contributions"])
    claims_hash = _digest(description.model_dump(mode="json", by_alias=True))
    operations = packet["relations"]["public.extension_runtime_operation"]
    resources = packet["relations"]["public.extension_runtime_resource_lease"]
    events = packet["relations"]["public.extension_runtime_event"]
    def add_operation(index, installation_event=None):
        op_id, generation, resource_id = (str(UUID(int=index + n)) for n in (100, 200, 300))
        container = format(index + 1, "064x")
        payloads = [("accepted", {"kind": "runtime-apply"}), ("validating", {"previousPhase": "accepted"}),
                    ("preparing", {"previousPhase": "validating"})]
        partial = uncommitted is not None and installation_event is None
        claimed = None if partial and uncommitted == "unclaimed" else timestamp
        created_container = None if partial else container
        if not partial:
            payloads.extend([("resource_created", {"resourceId": resource_id, "containerId": container}),
                ("resource_registered", {"resourceId": resource_id, "containerId": container,
                    "packageHash": selected.content_hash, "claimsHash": claims_hash}),
                ("registered", {"previousPhase": "preparing"})])
            expected_revision = len(payloads)
            payloads.append(("committing", {"previousPhase": "registered"}))
            proof = {"installationId": source.installation_id, "installationRevision": installation_event.to_revision,
                "evidenceRef": installation_event.evidence.evidence_ref, "evidenceHash": installation_event.evidence.evidence_hash,
                "lockHash": lock.lock_hash, "generation": generation,
                "resources": [{"resourceId": resource_id, "containerId": container,
                    "packageHash": selected.content_hash, "claimsHash": claims_hash}], "expectedRevision": expected_revision}
            payloads.extend([("preparation_committed", proof), ("succeeded", {"previousPhase": "committing"})])
        payloads.append(("resource_intent_cancelled" if claimed is None else "resource_released", {"resourceId": resource_id}))
        if partial: payloads.append(("preparation_failed", {"phase": "preparing", "failureCode": "PREPARATION_STOPPED"}))
        op = row_for(reader._RELATIONS["public.extension_runtime_operation"])
        op.update(**base, operation_id=op_id, installation_id=source.installation_id, kind="runtime-apply",
            requested_by="operator", approved_by=None, approval_ref=None, expected_binding_revision=None,
            expected_installation_etag=installation_event.from_revision if installation_event is not None else 3,
            phase="preparing" if partial else "succeeded", status="failed" if partial else "succeeded",
            failure_code="PREPARATION_STOPPED" if partial else None, revision=len(payloads),
            deadline=timestamp, created_at=timestamp,request_hash="sha256:"+"a"*64,idempotency_key=f"prepare-{index}")
        operations.append(op)
        resource = row_for(reader._RELATIONS["public.extension_runtime_resource_lease"])
        resource.update(**base, operation_id=op_id, resource_id=resource_id, generation=generation,
            package_id=selected.id, package_hash=selected.content_hash, container_id=created_container,
            engine_context="isolated-fixture", resource_name="retained-fixture-" + str(index),
            create_claimed_at=claimed, expires_at=timestamp, observed_release=True, cleanup_state="released")
        resources.append(resource)
        for sequence, (kind, payload) in enumerate(payloads, 1):
            events.append({**base, "operation_id": op_id, "sequence": sequence,
                "event_id": str(UUID(int=index * 100 + sequence + 1000)), "type": kind,
                "payload": payload, "payload_hash": _digest(payload), "occurred_at": timestamp})
    prepared = [event for event in locked.record.events if event.evidence is not None and event.evidence.type == "runtime_preparation"]
    for index, event in enumerate(prepared): add_operation(index, event)
    if uncommitted is not None: add_operation(50)
    if member_count > 1:
        for op_index, operation in enumerate(operations):
            group = [event for event in events if event["operation_id"] == operation["operation_id"]]
            proof_event = next((event for event in group if event["type"] == "preparation_committed"), None)
            if proof_event is None: continue
            prototype = next(row for row in resources if row["operation_id"] == operation["operation_id"])
            additions = []; releases = []
            for member_index, member in enumerate(lock.payload.resolved[1:], 1):
                extra = deepcopy(prototype)
                extra["resource_id"] = str(UUID(int=1000000 + op_index * 100 + member_index))
                extra["package_id"] = member.id; extra["package_hash"] = member.content_hash
                extra["container_id"] = format(1000 + op_index * 100 + member_index, "064x")
                extra["resource_name"] += "-" + str(member_index)
                resources.append(extra)
                manifest = next(row["manifest_json"] for row in packet["registry"]["public.asset_bundle_version"]
                                if row["manifest_json"]["metadata"]["id"] == member.id)
                description = RegistrationDescription(contributions=manifest["spec"]["contributions"])
                item = {"resourceId": extra["resource_id"], "containerId": extra["container_id"],
                    "packageHash": extra["package_hash"], "claimsHash": _digest(description.model_dump(mode="json", by_alias=True))}
                proof_event["payload"]["resources"].append(item)
                additions.extend([("resource_created", {"resourceId": item["resourceId"], "containerId": item["containerId"]}),
                                  ("resource_registered", item)])
                releases.append(("resource_released", {"resourceId": item["resourceId"]}))
            entries = [(event["type"], event["payload"]) for event in group]
            registered_index = next(index for index, (kind, _) in enumerate(entries) if kind == "registered")
            entries[registered_index:registered_index] = additions
            proof_event["payload"]["expectedRevision"] = next(index + 1 for index, (kind, _) in enumerate(entries) if kind == "registered")
            entries.extend(releases)
            events[:] = [event for event in events if event["operation_id"] != operation["operation_id"]]
            for sequence, (kind, payload) in enumerate(entries, 1):
                events.append({**base, "operation_id": operation["operation_id"], "sequence": sequence,
                    "event_id": str(UUID(int=2000000 + op_index * 1000 + sequence)), "type": kind,
                    "payload": payload, "payload_hash": _digest(payload), "occurred_at": timestamp})
            operation["revision"] = len(entries)
    return args


def verify_preparation_resources(*args):
    packet, scope, source, locked, lock = args; ledger = reader._WorkLedger()
    return reader._verify_preparation_resources(decode(packet, ledger), scope=scope, source=source,
        locked_source=locked, source_lock=lock, ledger=ledger)


@pytest.mark.parametrize("two_generations,uncommitted", [(False, None), (True, None), (True, "unclaimed"), (True, "claimed")])
@pytest.mark.parametrize("member_count", [1, 2])
def test_all_historical_preparations_and_partial_resources_are_linked(two_generations, uncommitted, member_count):
    args = preparation_resource_context(two_generations=two_generations, uncommitted=uncommitted, member_count=member_count)
    before = deepcopy(args); result = verify_preparation_resources(*args)
    assert len(result.preparations) == (2 if two_generations else 1)
    assert len(result.resources) == len(args[0]["relations"]["public.extension_runtime_resource_lease"])
    assert not hasattr(result, "authorized") and args == before


@pytest.mark.parametrize("mutation", ["missing-old-proof", "missing-old-resource", "extra-proof-resource", "duplicate-proof-resource",
    "claims", "package", "generation", "proof-generation", "proof-installation", "proof-lock", "proof-evidence",
    "proof-revision", "expected-revision", "bool-revision", "outer-hash", "resource-parent", "resource-tenant",
    "event-parent", "operation-installation", "missing-event", "event-gap", "missing-registration", "missing-creation",
    "release-unknown", "missing-release", "wrong-container", "wrong-registration", "proof-extra-key", "wrong-kind"])
def test_preparation_full_set_and_original_claim_proofs_reject_tampering(mutation):
    from aos_api.extension_runtime.lifecycle_store import _digest
    args = preparation_resource_context(two_generations=True); packet = args[0]
    operations = packet["relations"]["public.extension_runtime_operation"]
    resources = packet["relations"]["public.extension_runtime_resource_lease"]
    events = packet["relations"]["public.extension_runtime_event"]
    commit = next(event for event in events if event["type"] == "preparation_committed")
    proof = commit["payload"]; other = "44444444-4444-4444-8444-444444444444"
    if mutation == "missing-old-proof": events.remove(commit)
    elif mutation == "missing-old-resource": resources.pop(0)
    elif mutation == "extra-proof-resource": proof["resources"].append({**proof["resources"][0], "resourceId": other})
    elif mutation == "duplicate-proof-resource": proof["resources"] *= 2
    elif mutation == "claims": proof["resources"][0]["claimsHash"] = "sha256:" + "0" * 64
    elif mutation == "package": resources[0]["package_hash"] = "sha256:" + "0" * 64
    elif mutation == "generation": resources[0]["generation"] = other
    elif mutation == "proof-generation": proof["generation"] = other
    elif mutation == "proof-installation": proof["installationId"] = other
    elif mutation == "proof-lock": proof["lockHash"] = "sha256:" + "0" * 64
    elif mutation == "proof-evidence": proof["evidenceHash"] = "sha256:" + "0" * 64
    elif mutation == "proof-revision": proof["installationRevision"] = 6
    elif mutation == "expected-revision": proof["expectedRevision"] += 1
    elif mutation == "bool-revision": proof["installationRevision"] = True
    elif mutation == "resource-parent": resources[0]["operation_id"] = other
    elif mutation == "resource-tenant": resources[0]["org_id"] = "dev-org"
    elif mutation == "event-parent": events[0]["operation_id"] = other
    elif mutation == "operation-installation": operations[0]["installation_id"] = other
    elif mutation == "missing-event": events.pop(0)
    elif mutation == "event-gap": events[0]["sequence"] = 25
    elif mutation in ("missing-registration", "missing-creation", "missing-release"):
        kind = {"missing-registration": "resource_registered", "missing-creation": "resource_created", "missing-release": "resource_released"}[mutation]
        next(event for event in events if event["type"] == kind)["type"] = "unknown_fixture_event"
    elif mutation == "release-unknown": resources[0]["observed_release"] = False
    elif mutation == "wrong-container": resources[0]["container_id"] = "f" * 64
    elif mutation == "wrong-registration":
        event = next(event for event in events if event["type"] == "resource_registered")
        event["payload"]["claimsHash"] = "sha256:" + "0" * 64; event["payload_hash"] = _digest(event["payload"])
    elif mutation == "proof-extra-key": proof["approved"] = True
    elif mutation == "wrong-kind": operations[0]["kind"] = "runtime-verify"
    commit["payload_hash"] = _digest(proof)
    if mutation == "outer-hash": commit["payload_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError): verify_preparation_resources(*args)


def test_missing_signed_member_is_rejected_even_when_remaining_proof_is_self_consistent():
    from aos_api.extension_runtime.lifecycle_store import _digest
    args = preparation_resource_context(member_count=2); packet = args[0]
    resources = packet["relations"]["public.extension_runtime_resource_lease"]
    omitted = resources.pop()["resource_id"]
    events = packet["relations"]["public.extension_runtime_event"]
    events[:] = [event for event in events if event["payload"].get("resourceId") != omitted]
    proof = next(event["payload"] for event in events if event["type"] == "preparation_committed")
    proof["resources"] = [item for item in proof["resources"] if item["resourceId"] != omitted]
    proof["expectedRevision"] = next(index + 1 for index, event in enumerate(events) if event["type"] == "registered")
    for index, event in enumerate(events, 1):
        event["sequence"] = index; event["payload_hash"] = _digest(event["payload"])
    packet["relations"]["public.extension_runtime_operation"][0]["revision"] = len(events)
    with pytest.raises(ValueError): verify_preparation_resources(*args)


@pytest.mark.parametrize("mutation", ["remove-whole-old-operation", "duplicate-generation", "fingerprint-domain"])
def test_old_installation_links_and_claims_hash_domain_remain_required(mutation):
    from aos_api.extension_runtime.lifecycle_store import _digest
    from aos_api.extension_runtime.contracts import RegistrationDescription
    from aos_api.extension_runtime.registration import registration_fingerprint
    args = preparation_resource_context(two_generations=True); packet = args[0]
    operations = packet["relations"]["public.extension_runtime_operation"]
    resources = packet["relations"]["public.extension_runtime_resource_lease"]
    events = packet["relations"]["public.extension_runtime_event"]
    proofs = [event for event in events if event["type"] == "preparation_committed"]
    if mutation == "remove-whole-old-operation":
        omitted = operations.pop(0)["operation_id"]
        resources[:] = [row for row in resources if row["operation_id"] != omitted]
        events[:] = [row for row in events if row["operation_id"] != omitted]
    elif mutation == "duplicate-generation":
        resources[1]["generation"] = resources[0]["generation"]
        proofs[1]["payload"]["generation"] = resources[0]["generation"]
        proofs[1]["payload_hash"] = _digest(proofs[1]["payload"])
    else:
        manifest = packet["registry"]["public.asset_bundle_version"][0]["manifest_json"]
        fingerprint = registration_fingerprint(RegistrationDescription(contributions=manifest["spec"]["contributions"]))
        assert fingerprint != proofs[0]["payload"]["resources"][0]["claimsHash"]
        proofs[0]["payload"]["resources"][0]["claimsHash"] = fingerprint
        registered = next(event for event in events if event["type"] == "resource_registered")
        registered["payload"]["claimsHash"] = fingerprint
        for event in (proofs[0], registered): event["payload_hash"] = _digest(event["payload"])
    with pytest.raises(ValueError): verify_preparation_resources(*args)


def test_failed_cleanup_retains_committed_historical_proof():
    args = preparation_resource_context(two_generations=True)
    row = args[0]["relations"]["public.extension_runtime_operation"][0]
    row["status"] = "failed"; row["failure_code"] = "PREPARED_RUNTIME_RELEASED"
    assert len(verify_preparation_resources(*args).preparations) == 2


def test_preparation_stopped_before_any_resource_intent_is_preserved_as_facts():
    args = preparation_resource_context(uncommitted="unclaimed"); packet = args[0]
    resources = packet["relations"]["public.extension_runtime_resource_lease"]
    partial = resources.pop()["operation_id"]
    events = packet["relations"]["public.extension_runtime_event"]
    events[:] = [event for event in events if not (event["operation_id"] == partial and event["type"] == "resource_intent_cancelled")]
    sequence = 0
    for event in events:
        if event["operation_id"] == partial:
            sequence += 1; event["sequence"] = sequence
    packet["relations"]["public.extension_runtime_operation"][-1]["revision"] = sequence
    result = verify_preparation_resources(*args)
    assert len(result.preparations) == 1 and len(result.operations) == 2


def test_preparation_fact_reader_never_calls_original_writers():
    from contextlib import ExitStack
    from aos_api.extension_runtime import preparation_commit, verification_commit, preparation_reset, committed_cleanup
    from aos_api.extension_runtime.reconciler import ResourceJournal
    from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore
    targets = [(preparation_commit, "commit_prepared"), (verification_commit, "commit_verified"),
        (preparation_reset, "reset_preparation"), (committed_cleanup, "settle_committed_cleanup"),
        (ResourceJournal, "record_cleanup"), (ResourceJournal, "begin_recovery"),
        (RuntimeOperationStore, "_event")]
    with ExitStack() as stack:
        writers = [stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("no writes")))
                   for owner, name in targets]
        result = verify_preparation_resources(*preparation_resource_context(two_generations=True, member_count=2))
    assert len(result.preparations) == 2 and all(writer.call_count == 0 for writer in writers)


def runtime_notification_context(mode="pending", *, route=None, uncommitted=None):
    args = preparation_resource_context(two_generations=route is None, member_count=2, route=route,uncommitted=uncommitted)
    packet = args[0]; base = {"org_id": args[1].org_id, "project_id": args[1].project_id}
    for index, event in enumerate(packet["relations"]["public.extension_runtime_event"]):
        delivered = mode == "delivered" or (mode == "mixed" and index % 2 == 0)
        packet["relations"]["public.extension_runtime_outbox"].append({**base,
            "event_id": event["event_id"], "consumer_id": "runtime-reconciler", "attempt": 1 if delivered else 0,
            "next_attempt": event["occurred_at"], "claim_until": None,
            "delivered_at": event["occurred_at"] if delivered else None})
    return args


def verify_runtime_notifications(*args):
    packet, scope, source, locked, lock = args; ledger = reader._WorkLedger()
    return reader._verify_runtime_notifications(decode(packet, ledger), scope=scope, source=source,
        locked_source=locked, source_lock=lock, ledger=ledger)


@pytest.mark.parametrize("mode", ["pending", "delivered", "mixed"])
def test_terminal_old_accepted_notifications_are_ack_only_facts(mode):
    args = runtime_notification_context(mode); before = deepcopy(args)
    result = verify_runtime_notifications(*args)
    assert len(result.pending_event_ids) + len(result.delivered_event_ids) == len(args[0]["relations"]["public.extension_runtime_event"])
    if mode != "delivered": assert result.pending_event_ids
    if mode != "pending": assert result.delivered_event_ids
    assert len(result.preparation_facts.preparations) == 2 and not hasattr(result, "authorized") and args == before


@pytest.mark.parametrize("mutation", ["unknown-consumer", "unknown-delivered", "missing", "duplicate", "foreign-event",
    "foreign-tenant", "negative-attempt", "zero-delivered", "claim-future", "claim-past", "claim-delivered",
    "nonterminal-extra-operation", "unknown-kind-extra-operation", "bad-phase-extra-operation"])
def test_runtime_outbox_unknowns_and_claims_do_not_become_safe_by_status_or_ttl(mutation):
    from aos_api.extension_runtime.lifecycle_store import _digest
    args = runtime_notification_context(); packet = args[0]
    rows = packet["relations"]["public.extension_runtime_outbox"]; first = rows[0]
    if mutation in ("unknown-consumer", "unknown-delivered"):
        first["consumer_id"] = "unclassified-consumer"
        if mutation == "unknown-delivered": first["attempt"] = 1; first["delivered_at"] = first["next_attempt"]
    elif mutation == "missing": rows.pop()
    elif mutation == "duplicate": rows.append(deepcopy(first))
    elif mutation == "foreign-event": first["event_id"] = str(UUID(int=42))
    elif mutation == "foreign-tenant": first["org_id"] = "dev-org"
    elif mutation == "negative-attempt": first["attempt"] = -1
    elif mutation == "zero-delivered": first["delivered_at"] = first["next_attempt"]
    elif mutation.startswith("claim-"):
        first["attempt"] = 1; first["claim_until"] = "2000-01-01T00:00:00+00:00" if mutation == "claim-past" else "2099-01-01T00:00:00+00:00"
        if mutation == "claim-delivered": first["delivered_at"] = first["next_attempt"]
    else:
        operation = deepcopy(packet["relations"]["public.extension_runtime_operation"][0])
        operation.update(operation_id=str(UUID(int=555)), kind="configure", status="accepted", phase="accepted", revision=1)
        if mutation == "unknown-kind-extra-operation": operation.update(kind="unclassified-kind", status="failed")
        if mutation == "bad-phase-extra-operation": operation.update(status="failed", phase="unclassified-phase")
        packet["relations"]["public.extension_runtime_operation"].append(operation)
        event = deepcopy(packet["relations"]["public.extension_runtime_event"][0])
        event.update(operation_id=operation["operation_id"], event_id=str(UUID(int=556)), sequence=1, type="accepted", payload={"kind": operation["kind"]})
        event["payload_hash"] = _digest(event["payload"]); packet["relations"]["public.extension_runtime_event"].append(event)
        rows.append({**first, "event_id": event["event_id"]})
    with pytest.raises(ValueError): verify_runtime_notifications(*args)


@pytest.mark.parametrize("kind", ["runtime-apply", "runtime-verify", "enable", "configure", "disable"])
@pytest.mark.parametrize("status", ["succeeded", "failed", "cancelled"])
def test_original_five_consumers_ack_terminal_status_without_executing_again(monkeypatch, kind, status):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from datetime import UTC
    from aos_api.tenant_scope import TenantScope
    from aos_api.extension_runtime.outbox_store import OutboxLease
    from aos_api.extension_runtime import preparation_consumer as preparation
    from aos_api.extension_runtime import owned_control_consumer as owned
    from aos_api.extension_runtime import configuration_consumer as configuration
    from aos_api.extension_runtime import disable_consumer as disable
    scope = {"org_id": "org-org", "project_id": "dev-project"}
    installation = UUID(UUID_TEXT); lease = OutboxLease(UUID(int=600), UUID(int=601), 1,
        "accepted", 1, datetime(2026, 10, 26, tzinfo=UTC))
    phase = "succeeded" if status == "succeeded" else "accepted"
    ack = mock.Mock(); retry = mock.Mock(side_effect=AssertionError("terminal must ACK"))
    forbidden = mock.Mock(side_effect=AssertionError("terminal cannot execute"))
    outbox = SimpleNamespace(claim=lambda *args, **kwargs: lease, ack=ack, retry=retry)
    if kind in ("runtime-apply", "runtime-verify", "enable"):
        module = preparation if kind == "runtime-apply" else owned
        cls = preparation.PreparationConsumer if kind == "runtime-apply" else owned.OwnedControlConsumer
        consumer = object.__new__(cls)  # Method-only characterization; not a production composition.
        consumer.scope=scope; consumer.connect=forbidden; consumer.host_lease=None; consumer.installation=installation
        consumer.outbox=outbox; consumer._claim=lambda:lease; consumer._current=lambda conn, operation:(status, phase, 1)
        if kind == "runtime-apply":
            consumer.rehydrate=False; consumer._job=None; consumer._start_owned=forbidden
        else:
            consumer.kind=kind; consumer.job=SimpleNamespace(verify=forbidden, enable=forbidden)
        async def immediate(function, *args, **kwargs): return function(*args, **kwargs)
        async def settled(awaitable): return await awaitable
        monkeypatch.setattr(module.asyncio, "to_thread", immediate)
        monkeypatch.setattr(module, "_settled", settled)
        monkeypatch.setattr(module, "consumer_connection", lambda *args, **kwargs:nullcontext(object()))
        coroutine=consumer._run()
        try:
            with pytest.raises(StopIteration) as completed: coroutine.send(None)
            result=completed.value.value
        finally: coroutine.close()
    elif kind == "configure":
        consumer=object.__new__(configuration.ConfigurationConsumer)
        consumer._connection=lambda scope:nullcontext(object()); consumer._current=lambda conn, scope, operation:(status, phase, 1)
        consumer.outbox=outbox; consumer.authorize=forbidden; consumer.check_drained=forbidden
        monkeypatch.setattr(configuration, "begin_configuration", forbidden)
        monkeypatch.setattr(configuration, "commit_configuration", forbidden)
        result=consumer.run_once(**scope)
    else:
        consumer=object.__new__(disable.RuntimeDisableConsumer)
        claimed=disable.ClaimedDisableDelivery(TenantScope(**scope),lease,installation)
        consumer.claim_once=lambda **kwargs:claimed; consumer._connection=lambda scope:nullcontext(object())
        consumer._current=lambda conn, scope, operation:(installation,status,phase,1)
        consumer.executor=SimpleNamespace(execute=forbidden); consumer.outbox=outbox
        result=consumer.run_once(**scope)
    assert result.operation_status==status and result.delivery_status=="acknowledged"
    assert ack.call_count==1 and ack.call_args.kwargs["lease"] is lease
    assert retry.call_count==0 and forbidden.call_count==0


@pytest.mark.parametrize("mode", ["pending", "delivered"])
@pytest.mark.parametrize("kind", ["abort_prepare", "uninstall-execute"])
def test_original_path_name_alone_does_not_prove_an_audited_consumer(kind, mode):
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=runtime_notification_context(mode); packet=args[0]
    operation=deepcopy(packet["relations"]["public.extension_runtime_operation"][0])
    operation.update(operation_id=str(UUID(int=700)),kind=kind,status="failed",phase="accepted",revision=1)
    packet["relations"]["public.extension_runtime_operation"].append(operation)
    event=deepcopy(packet["relations"]["public.extension_runtime_event"][0])
    event.update(operation_id=operation["operation_id"],event_id=str(UUID(int=701)),type="accepted",sequence=1,payload={"kind":kind})
    event["payload_hash"]=_digest(event["payload"]);packet["relations"]["public.extension_runtime_event"].append(event)
    row=deepcopy(packet["relations"]["public.extension_runtime_outbox"][0]);row["event_id"]=event["event_id"]
    packet["relations"]["public.extension_runtime_outbox"].append(row)
    with pytest.raises(ValueError):verify_runtime_notifications(*args)


def attempt_dependency_context(*, kind="signed_read", state="succeeded", reason=None, error=None, heartbeat=False, direction=None, dependency_kind="data", route="active",uncommitted=None):
    from datetime import timedelta
    args=runtime_notification_context(route=route,uncommitted=uncommitted);packet,scope,source,locked,lock=args
    base={"org_id":scope.org_id,"project_id":scope.project_id}
    proof_event=max((row for row in packet["relations"]["public.extension_runtime_event"] if row["type"]=="preparation_committed"),
        key=lambda row:row["payload"]["installationRevision"])
    proof=proof_event["payload"];generation=proof["generation"]
    binding=row_for(reader._RELATIONS["public.extension_runtime_binding"])
    binding.update(**base,installation_id=source.installation_id,generation=generation,
        installation_revision=source.terminal_revision-1,package_lock_ref={"lockHash":lock.lock_hash},profile_ref="internal-python-v1",
        config_ref=None,execution_epoch=3,desired_state="uninstalled",observed_state="stopped",enabled=False,
        operation_fence=True,resource_handle_ref={"preparationOperationId":proof_event["operation_id"],"resources":deepcopy(proof["resources"])},revision=10)
    packet["relations"]["public.extension_runtime_binding"]=[binding]
    accepted=locked.record.created_at;completed=accepted+timedelta(seconds=20)
    attempt=row_for(reader._RELATIONS["public.extension_runtime_execution_attempt"])
    attempt.update(**base,attempt_id=str(UUID(int=900)),installation_id=source.installation_id,generation=generation,
        execution_epoch=1,operation_kind=kind,operation_key="products.read",idempotency_key="read-once:1",
        request_hash="sha256:"+"a"*64,state=state,lease_until=(accepted+timedelta(seconds=30)).isoformat(),
        revision=3 if heartbeat else 2,accepted_at=accepted.isoformat(),heartbeat_at=(accepted+timedelta(seconds=10)).isoformat() if heartbeat else None,
        completed_at=completed.isoformat(),terminal_reason_code=reason,terminal_error_type=error)
    packet["relations"]["public.extension_runtime_execution_attempt"]=[attempt]
    events=packet["relations"]["public.extension_runtime_execution_attempt_event"]
    for sequence in range(1,attempt["revision"]+1):
        terminal=sequence==attempt["revision"]
        events.append({**base,"attempt_id":attempt["attempt_id"],"sequence":sequence,"revision":sequence,
            "event_id":str(UUID(int=910+sequence)),"type":"attempt_"+state if terminal else "attempt_accepted" if sequence==1 else "attempt_heartbeat",
            "state":state if terminal else "running","occurred_at":(accepted+timedelta(seconds=sequence)).isoformat(),
            "terminal_reason_code":reason if terminal else None,"terminal_error_type":error if terminal else None})
    if direction is not None:
        source_pair=(source.installation_id,generation); other=(str(UUID(int=950)),str(UUID(int=951)))
        consumer,provider=(source_pair,other) if direction=="outgoing" else (other,source_pair) if direction=="incoming" else (source_pair,source_pair)
        packet["relations"]["public.extension_runtime_dependency_ref"]=[{**base,
            "consumer_installation":consumer[0],"consumer_generation":consumer[1],
            "provider_installation":provider[0],"provider_generation":provider[1],"kind":dependency_kind,"active":False,"revision":1}]
    return args


def verify_attempt_dependencies(*args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    return reader._verify_attempt_dependencies(decode(packet,ledger),scope=scope,source=source,
        locked_source=locked,source_lock=lock,ledger=ledger)


@pytest.mark.parametrize("kind", ["signed_read","recoverable_store"])
@pytest.mark.parametrize("state,reason,error", [("succeeded",None,None),("failed",None,None),
    ("failed","READ_FAILED",None),("failed","RECOVERABLE_EXECUTION_EXCEPTION","ValueError"),
    ("abandoned",None,None),("abandoned","ATTEMPT_LEASE_EXPIRED",None)])
@pytest.mark.parametrize("heartbeat", [False,True])
def test_terminal_attempts_keep_valid_nullable_historical_reason_shapes(kind,state,reason,error,heartbeat):
    args=attempt_dependency_context(kind=kind,state=state,reason=reason,error=error,heartbeat=heartbeat);before=deepcopy(args)
    result=verify_attempt_dependencies(*args)
    assert len(result.attempts)==1 and not hasattr(result,"authorized") and args==before


@pytest.mark.parametrize("direction", ["incoming","outgoing","self"])
@pytest.mark.parametrize("dependency_kind", ["capability","data","reconcile"])
def test_inactive_source_dependencies_are_checked_in_both_directions(direction,dependency_kind):
    result=verify_attempt_dependencies(*attempt_dependency_context(direction=direction,dependency_kind=dependency_kind))
    assert len(result.dependencies)==1


@pytest.mark.parametrize("mutation", ["running-past-lease","future-epoch","fence-epoch","kind","source","generation","tenant",
    "completed-null","revision-gap","missing-event","orphan-event","event-tenant","tail-reason","tail-state","middle-terminal",
    "heartbeat-pointer","raw-error","unknown-reason","success-reason","error-without-reason","abandoned-reason","event-id-duplicate",
    "duplicate-natural-key","active-incoming","active-outgoing","foreign-dependency","dependency-generation","dependency-kind","missing-binding"])
def test_attempt_or_dependency_obligations_cannot_be_hidden_by_ttl_or_partial_history(mutation):
    args=attempt_dependency_context(heartbeat=True,direction="incoming");packet=args[0]
    attempt=packet["relations"]["public.extension_runtime_execution_attempt"][0]
    events=packet["relations"]["public.extension_runtime_execution_attempt_event"]
    dependency=packet["relations"]["public.extension_runtime_dependency_ref"][0]
    if mutation=="running-past-lease":
        attempt.update(state="running",completed_at=None,lease_until="2000-01-01T00:00:00+00:00")
        events[-1].update(state="running",type="attempt_heartbeat")
    elif mutation in ("future-epoch","fence-epoch"):attempt["execution_epoch"]=4 if mutation=="future-epoch" else 3
    elif mutation=="kind":attempt["operation_kind"]="unknown-executor"
    elif mutation=="source":attempt["installation_id"]=str(UUID(int=999))
    elif mutation=="generation":attempt["generation"]=str(UUID(int=999))
    elif mutation=="tenant":attempt["org_id"]="dev-org"
    elif mutation=="completed-null":attempt["completed_at"]=None
    elif mutation=="revision-gap":attempt["revision"]+=1
    elif mutation=="missing-event":events.pop(1)
    elif mutation=="orphan-event":events[-1]["attempt_id"]=str(UUID(int=999))
    elif mutation=="event-tenant":events[-1]["org_id"]="dev-org"
    elif mutation=="tail-reason":events[-1]["terminal_reason_code"]="READ_FAILED"
    elif mutation=="tail-state":events[-1]["state"]="failed"
    elif mutation=="middle-terminal":events[1].update(type="attempt_failed",state="failed")
    elif mutation=="heartbeat-pointer":attempt["heartbeat_at"]=None
    elif mutation in ("raw-error","unknown-reason","error-without-reason"):
        attempt["state"]="failed";events[-1].update(type="attempt_failed",state="failed")
        attempt["terminal_reason_code"]="READ_FAILED" if mutation=="raw-error" else "RAW_PRIVATE_REASON" if mutation=="unknown-reason" else None
        attempt["terminal_error_type"]="private message with spaces" if mutation=="raw-error" else "ValueError" if mutation=="error-without-reason" else None
        for field in ("terminal_reason_code","terminal_error_type"):events[-1][field]=attempt[field]
    elif mutation=="success-reason":attempt["terminal_reason_code"]=events[-1]["terminal_reason_code"]="READ_FAILED"
    elif mutation=="abandoned-reason":
        attempt.update(state="abandoned",terminal_reason_code="READ_FAILED");events[-1].update(type="attempt_abandoned",state="abandoned",terminal_reason_code="READ_FAILED")
    elif mutation=="event-id-duplicate":events[-1]["event_id"]=events[0]["event_id"]
    elif mutation=="duplicate-natural-key":
        packet["relations"]["public.extension_runtime_execution_attempt"].append({**attempt,"attempt_id":str(UUID(int=999))})
    elif mutation in ("active-incoming","active-outgoing"):
        dependency["active"]=True
        if mutation=="active-outgoing":
            dependency["consumer_installation"],dependency["provider_installation"]=dependency["provider_installation"],dependency["consumer_installation"]
            dependency["consumer_generation"],dependency["provider_generation"]=dependency["provider_generation"],dependency["consumer_generation"]
    elif mutation=="foreign-dependency":dependency["provider_installation"]=str(UUID(int=999))
    elif mutation=="dependency-generation":dependency["provider_generation"]=str(UUID(int=999))
    elif mutation=="dependency-kind":dependency["kind"]="unknown-kind"
    elif mutation=="missing-binding":packet["relations"]["public.extension_runtime_binding"].clear()
    with pytest.raises(ValueError):verify_attempt_dependencies(*args)


@pytest.mark.parametrize("state,epoch", [("succeeded",1),("failed",1),("abandoned",1),("running",1),("succeeded",3),("failed",4)])
def test_original_generation_drain_agrees_on_terminal_state_and_fence_without_ttl(state,epoch):
    from types import SimpleNamespace
    from psycopg.pq import TransactionStatus
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    class Result:
        def __init__(self,row):self.row=row
        def fetchone(self):return self.row
    class Connection:
        info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        def __init__(self):self.queries=[]
        def execute(self,query,params=()):
            self.queries.append(query)
            if "current_setting" in query:return Result({"org_id":"org-org","project_id":"dev-project"})
            if "FROM extension_runtime_binding" in query:return Result({"enabled":False,"operation_fence":True,"execution_epoch":3})
            if "execution_epoch>=" in query:return Result({"exists":1} if epoch>=params[-1] else None)
            if "state<>ALL" in query:return Result({"exists":1} if state not in params[-1] else None)
            raise AssertionError("unexpected original drain query")
    conn=Connection();arguments=dict(org_id="org-org",project_id="dev-project",installation_id=UUID(UUID_TEXT),generation=UUID(int=200),fence_epoch=3)
    if epoch>=3:
        with pytest.raises(RuntimeConflict):GenerationDrainReader()(conn,**arguments)
    else:assert GenerationDrainReader()(conn,**arguments) is (state!="running")
    assert not any("lease_until" in query or query.lstrip().upper().startswith(("UPDATE","INSERT","DELETE")) for query in conn.queries)


def test_attempt_fact_reader_does_not_settle_or_abandon_current_work():
    from aos_api.extension_runtime.generation_attempts import PostgresRuntimeAttemptStore
    with mock.patch.object(PostgresRuntimeAttemptStore,"settle",side_effect=AssertionError("no settlement")) as settle, \
         mock.patch.object(PostgresRuntimeAttemptStore,"abandon_expired_reads",side_effect=AssertionError("no recovery")) as abandon:
        result=verify_attempt_dependencies(*attempt_dependency_context(state="failed",reason=None))
    assert len(result.attempts)==1 and settle.call_count==0 and abandon.call_count==0


RECEIPT_REF_COLUMNS=("disable_operation_id","activation_operation_id","unactivated_disable_operation_id",
                     "runtime_enable_operation_id","runtime_disable_operation_id")
RECEIPT_MASKS={"detached":3,"never_enabled":0,"configured_unactivated":4,"enabled_undispatched":24}


def uninstall_receipt_context(kind="never_enabled", *, route="active",uncommitted=None):
    import hashlib
    args=attempt_dependency_context(route=route,uncommitted=uncommitted);packet,scope,source,locked,lock=args
    packet["relations"]["public.extension_runtime_execution_attempt"].clear()
    packet["relations"]["public.extension_runtime_execution_attempt_event"].clear()
    binding=packet["relations"]["public.extension_runtime_binding"][0]
    if kind in ("configured_unactivated","enabled_undispatched"):
        binding["config_ref"]={"configurationId":str(UUID(int=810)),"revision":1,"hash":"sha256:"+"b"*64}
    refs={column:str(UUID(int=820+index)) if RECEIPT_MASKS[kind]&(1<<index) else None
          for index,column in enumerate(RECEIPT_REF_COLUMNS)}
    body={"orgId":scope.org_id,"projectId":scope.project_id,"installationId":source.installation_id,
          "generation":binding["generation"],"installationRevision":source.terminal_revision-1,
          "releasedResourceCount":len(packet["relations"]["public.extension_runtime_resource_lease"]),
          "actor":locked.record.events[-1].actor}
    if kind=="detached":
        body.update(schemaVersion="ar2-runtime-uninstall/v1",bindingFromRevision=binding["revision"]-1,
            bindingToRevision=binding["revision"],disableOperationId=refs["disable_operation_id"],
            activationOperationId=refs["activation_operation_id"],cutoverGroupId=str(UUID(int=830)),
            legacyDispatchCount=9,claimedOccurrenceCount=0,openDispatchAttemptCount=0,runningRuntimeAttemptCount=0)
    else:
        body.update(bindingRevision=binding["revision"],retirementKind=kind,dispatchCount=0,businessExecutionCount=0)
        if kind=="never_enabled":body.update(configurationCount=0,enableCount=0)
        else:
            body.update(configRef=deepcopy(binding["config_ref"]),successfulEnableCount=1 if kind=="enabled_undispatched" else 0,
                disableOperationId=refs["runtime_disable_operation_id"] if kind=="enabled_undispatched" else refs["unactivated_disable_operation_id"])
            if kind=="enabled_undispatched":body["enableOperationId"]=refs["runtime_enable_operation_id"]
    raw=json.dumps(body,ensure_ascii=False)
    packet["relations"]["public.extension_runtime_uninstall_receipt"]=[{"org_id":scope.org_id,"project_id":scope.project_id,
        "receipt_id":str(UUID(int=840)),"installation_id":source.installation_id,"generation":binding["generation"],
        "installation_revision":source.terminal_revision-1,"binding_revision":binding["revision"],"actor":body["actor"],
        "authority_data_text":raw,"content_hash":"sha256:"+hashlib.sha256(raw.encode()).hexdigest(),
        "created_at":locked.record.created_at.isoformat(),"retirement_kind":kind,**refs}]
    return args


def verify_uninstall_receipt(*args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    return reader._read_uninstall_receipt(decode(packet,ledger),scope=scope,source=source,
        locked_source=locked,source_lock=lock,ledger=ledger)


@pytest.mark.parametrize("kind", list(RECEIPT_MASKS))
def test_original_four_receipt_shapes_link_without_claiming_full_branch_authority(kind):
    args=uninstall_receipt_context(kind);before=deepcopy(args);result=verify_uninstall_receipt(*args)
    assert result.receipt["retirement_kind"]==kind and result.authority["installationId"]==args[2].installation_id
    assert not hasattr(result,"authorized") and args==before


@pytest.mark.parametrize("kind", list(RECEIPT_MASKS))
@pytest.mark.parametrize("mask", range(32))
def test_all_five_nullable_receipt_references_follow_original_kind_matrix(kind,mask):
    args=uninstall_receipt_context(kind);row=args[0]["relations"]["public.extension_runtime_uninstall_receipt"][0]
    for index,column in enumerate(RECEIPT_REF_COLUMNS):
        row[column]=(row[column] or str(UUID(int=850+index))) if mask&(1<<index) else None
    if mask==RECEIPT_MASKS[kind]:assert verify_uninstall_receipt(*args).receipt["retirement_kind"]==kind
    else:
        with pytest.raises(ValueError):verify_uninstall_receipt(*args)


@pytest.mark.parametrize("mutation", ["hash","whitespace-hash","tenant","generation","actor","installation-revision","binding-revision",
    "body-tenant","body-generation","body-actor","body-bool-number","body-extra-key","body-missing-key","body-count",
    "body-dispatch","config-ref","unknown-kind","missing-receipt","missing-binding"])
def test_receipt_hash_validity_is_not_context_or_kind_authority(mutation):
    import hashlib
    args=uninstall_receipt_context("configured_unactivated");packet=args[0]
    rows=packet["relations"]["public.extension_runtime_uninstall_receipt"];row=rows[0]
    body=json.loads(row["authority_data_text"])
    if mutation=="hash":row["content_hash"]="sha256:"+"0"*64
    elif mutation=="whitespace-hash":row["authority_data_text"]+=" "
    elif mutation=="tenant":row["org_id"]="dev-org"
    elif mutation=="generation":row["generation"]=str(UUID(int=999))
    elif mutation=="actor":row["actor"]="different-actor"
    elif mutation=="installation-revision":row["installation_revision"]+=1
    elif mutation=="binding-revision":row["binding_revision"]+=1
    elif mutation=="unknown-kind":row["retirement_kind"]="unclassified"
    elif mutation=="missing-receipt":rows.clear()
    elif mutation=="missing-binding":packet["relations"]["public.extension_runtime_binding"].clear()
    else:
        if mutation=="body-tenant":body["orgId"]="dev-org"
        elif mutation=="body-generation":body["generation"]=str(UUID(int=999))
        elif mutation=="body-actor":body["actor"]="different-actor"
        elif mutation=="body-bool-number":body["installationRevision"]=True
        elif mutation=="body-extra-key":body["authorized"]=True
        elif mutation=="body-missing-key":body.pop("releasedResourceCount")
        elif mutation=="body-count":body["releasedResourceCount"]-=1
        elif mutation=="body-dispatch":body["dispatchCount"]=1
        elif mutation=="config-ref":body["configRef"]["hash"]="sha256:"+"0"*64
        row["authority_data_text"]=json.dumps(body,ensure_ascii=False)
        row["content_hash"]="sha256:"+hashlib.sha256(row["authority_data_text"].encode()).hexdigest()
    with pytest.raises(ValueError):verify_uninstall_receipt(*args)


def parse_authority(raw,digest=None,ledger=None):
    import hashlib
    digest="sha256:"+hashlib.sha256(raw.encode()).hexdigest() if digest is None else digest
    return reader._authority_object(raw,digest,reader._WorkLedger() if ledger is None else ledger)


def test_authority_hash_uses_original_utf8_bytes_not_canonical_reserialization():
    raw='{ "操作": "月", "count": 0 }';other='{"count":0,"操作":"月"}'
    assert parse_authority(raw)==parse_authority(other)
    import hashlib
    with pytest.raises(ValueError):parse_authority(other,"sha256:"+hashlib.sha256(raw.encode()).hexdigest())
    packet=json.loads(json.dumps({"authority_data_text":raw},ensure_ascii=False))
    assert packet["authority_data_text"].encode()==raw.encode()


@pytest.mark.parametrize("raw", ['[]','null','{"x":NaN}','{"x":Infinity}','{"x":1e9999}',
    '{"a":1,"a":2}','{"x":{"a":1,"a":2}}','{"x":"\\ud800"}','{"x":1} trailing','{"x":'])
def test_authority_json_rejects_hash_valid_but_invalid_or_ambiguous_text(raw):
    with pytest.raises(ValueError):parse_authority(raw)


@pytest.mark.parametrize("shape", ["depth","nodes","bytes"])
def test_authority_preflight_bounds_before_json_parser(shape):
    raw='['*200+'0'+']'*200 if shape=="depth" else '{"values":['+','.join('0' for _ in range(reader._MAX_JSON_NODES))+']}' if shape=="nodes" else ' '*reader._MAX_JSON_BYTES+'{}'
    with mock.patch.object(reader.json,"loads",side_effect=AssertionError("budget must reject before parser")) as loads:
        with pytest.raises(ValueError):parse_authority(raw)
    assert loads.call_count==0


@pytest.mark.parametrize("prepared", [False,True])
def test_no_binding_and_no_receipt_are_facts_without_choosing_a_business_branch(prepared):
    args=runtime_notification_context() if prepared else source_history_context("approved")
    result=verify_uninstall_receipt(*args)
    assert result.receipt is None and result.authority is None and not hasattr(result,"branch")
    if prepared:assert len(result.context.notifications.preparation_facts.preparations)==2


def test_receipt_context_reuses_revalidated_record_instead_of_unordered_model_copy():
    from dataclasses import replace
    args=list(uninstall_receipt_context("detached"));locked=args[3]
    record=locked.record.model_copy(update={"events":list(reversed(locked.record.events))})
    args[3]=replace(locked,record=record)
    result=verify_uninstall_receipt(*args)
    assert result.receipt["actor"]==locked.record.events[-1].actor


def test_authority_single_json_byte_cap_accepts_exact_limit():
    raw='{"x":"'+'x'*(reader._MAX_JSON_BYTES-8)+'"}'
    assert len(raw.encode())==reader._MAX_JSON_BYTES
    assert len(parse_authority(raw)["x"])==reader._MAX_JSON_BYTES-8


def test_authority_budget_scanner_does_not_parse_braces_or_escaped_quotes_inside_strings():
    values=["\\",'"[{]}"',"line\n月",'escape\\\"[[]]',"{["*100]
    body={"values":values,"nested":{"empty":[],"count":42}}
    assert parse_authority(json.dumps(body,ensure_ascii=False))==body


def test_authority_decode_error_does_not_expose_raw_text_or_secret_fixture():
    raw='{"private":"PRIVATE_FIXTURE_VALUE",invalid}'
    with pytest.raises(ValueError) as caught:parse_authority(raw)
    assert str(caught.value)=="invalid terminal facts" and caught.value.__suppress_context__


def configuration_history_context():
    from aos_api.extension_runtime.configuration_contracts import ConfigurationDocument
    from aos_api.extension_runtime.configuration_store import _content_hash
    from aos_api.tenant_scope import TenantScope
    packet=empty_packet();scope=TenantScope("org-org","dev-project")
    installation=UUID(int=900);generation=UUID(int=901)
    def reference(identity):
        return dict(authority="test.configuration",id=identity,revision=1,hash="sha256:"+"a"*64)
    document=ConfigurationDocument.model_validate_json(json.dumps(dict(schemaVersion=1,
        roleRefs=[reference("role")],dataRefs=[reference("data")],budgetRef=reference("budget"),policyRef=reference("policy"))))
    rows=[]
    for identity,count in ((UUID(int=902),3),(UUID(int=903),1)):
        previous=None
        for revision in range(1,count+1):
            payload=document.model_dump(mode="json")
            digest=_content_hash((*scope.key,installation,generation),identity,revision,previous,"fixture-actor",payload)
            rows.append(dict(org_id=scope.org_id,project_id=scope.project_id,installation_id=str(installation),
                generation=str(generation),configuration_id=str(identity),revision=revision,payload=payload,
                content_hash=digest,previous_hash=previous,request_hash="sha256:"+"c"*64,
                idempotency_key=f"configuration-{identity}-{revision}",actor="fixture-actor",
                created_at="2026-10-26T00:00:00+08:00"))
            previous=digest
    packet["relations"]["public.extension_runtime_configuration"]=rows
    pointer=dict(configurationId=rows[0]["configuration_id"],revision=1,hash=rows[0]["content_hash"])
    return packet,scope,str(installation),generation,pointer


def verify_configuration_history(args,ledger=None):
    packet,scope,installation,generation,pointer=args
    ledger=ledger or reader._WorkLedger()
    return reader._configuration_history(decode(packet,ledger),scope=scope,installation_id=installation,
        generation=generation,binding_ref=pointer,ledger=ledger)


def test_configuration_history_retains_staged_successors_and_unapplied_identity():
    args=configuration_history_context();before=deepcopy(args)
    result=verify_configuration_history(args)
    assert len(result.versions)==4 and result.current.model_dump(mode="json")==args[-1]
    assert args==before and not hasattr(result,"authorized")
    with pytest.raises(TypeError):result.versions["new"]=None


def test_configuration_history_order_is_not_row_order_and_pointer_need_not_be_latest():
    args=configuration_history_context()
    args[0]["relations"]["public.extension_runtime_configuration"].reverse()
    assert verify_configuration_history(args).current.revision==1


@pytest.mark.parametrize("empty", [False,True])
def test_configuration_history_can_have_no_applied_pointer(empty):
    args=list(configuration_history_context());args[-1]=None
    if empty:args[0]["relations"]["public.extension_runtime_configuration"].clear()
    result=verify_configuration_history(args)
    assert result.current is None and len(result.versions)==(0 if empty else 4)


@pytest.mark.parametrize("fault", ["missing_first","missing_middle","previous_first","previous_later",
    "scope","installation","generation","actor_empty","actor_space","actor_control","request_hash",
    "idempotency_duplicate","idempotency_empty","idempotency_space","idempotency_control",
    "payload_hash","payload_schema","payload_duplicate","payload_uri","pointer_hash","pointer_missing",
    "pointer_bool","pointer_extra","pointer_uuid","bool_revision","zero_revision","duplicate_version"])
def test_configuration_history_rejects_incomplete_or_tampered_facts(fault):
    args=list(configuration_history_context());rows=args[0]["relations"]["public.extension_runtime_configuration"]
    if fault=="missing_first":rows.pop(0)
    elif fault=="missing_middle":rows.pop(1)
    elif fault=="previous_first":rows[0]["previous_hash"]="sha256:"+"d"*64
    elif fault=="previous_later":rows[1]["previous_hash"]="sha256:"+"d"*64
    elif fault=="scope":rows[-1]["org_id"]="dev-org"
    elif fault=="installation":rows[-1]["installation_id"]=str(UUID(int=999))
    elif fault=="generation":rows[-1]["generation"]=str(UUID(int=999))
    elif fault.startswith("actor_"):rows[-1]["actor"]={"actor_empty":"","actor_space":" padded ","actor_control":"a\nb"}[fault]
    elif fault=="request_hash":rows[-1]["request_hash"]="invalid"
    elif fault=="idempotency_duplicate":rows[-1]["idempotency_key"]=rows[0]["idempotency_key"]
    elif fault.startswith("idempotency_"):rows[-1]["idempotency_key"]={"idempotency_empty":"","idempotency_space":" padded ","idempotency_control":"a\nb"}[fault]
    elif fault=="payload_hash":rows[-1]["payload"]["budgetRef"]["revision"]=2
    elif fault=="payload_schema":rows[-1]["payload"]["schemaVersion"]=True
    elif fault=="payload_duplicate":rows[-1]["payload"]["roleRefs"]*=2
    elif fault=="payload_uri":rows[-1]["payload"]["budgetRef"]["id"]="secret://PRIVATE_FIXTURE_VALUE"
    elif fault=="pointer_hash":args[-1]["hash"]="sha256:"+"d"*64
    elif fault=="pointer_missing":args[-1]["configurationId"]=str(UUID(int=999))
    elif fault=="pointer_bool":args[-1]["revision"]=True
    elif fault=="pointer_extra":args[-1]["extra"]=1
    elif fault=="pointer_uuid":args[-1]["configurationId"]="INVALID"
    elif fault=="bool_revision":rows[0]["revision"]=True
    elif fault=="zero_revision":rows[0]["revision"]=0
    elif fault=="duplicate_version":rows.append(deepcopy(rows[0]))
    with pytest.raises(ValueError):verify_configuration_history(args)


def test_configuration_history_decode_failure_hides_payload():
    args=configuration_history_context();rows=args[0]["relations"]["public.extension_runtime_configuration"]
    rows[-1]["payload"]["budgetRef"]["id"]="secret://PRIVATE_FIXTURE_VALUE"
    with pytest.raises(ValueError) as caught:verify_configuration_history(args)
    assert str(caught.value)=="invalid terminal facts" and caught.value.__suppress_context__


def test_configuration_history_reserves_work_before_original_document_parser():
    from aos_api.extension_runtime import configuration_store
    args=configuration_history_context();ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    ledger.work_bytes=reader._MAX_WORK_BYTES
    with mock.patch.object(configuration_store,"_decode",side_effect=AssertionError("parser must not run")) as parser:
        with pytest.raises(ValueError):
            reader._configuration_history(facts,scope=args[1],installation_id=args[2],generation=args[3],
                binding_ref=args[4],ledger=ledger)
        assert parser.call_count==0


def test_configuration_history_uses_original_decoder_for_every_staged_version():
    from aos_api.extension_runtime import configuration_store
    args=configuration_history_context()
    with mock.patch.object(configuration_store,"_decode",wraps=configuration_store._decode) as parser:
        result=verify_configuration_history(args)
    assert parser.call_count==len(result.versions)==4


def test_configuration_request_hash_without_original_cas_operands_is_only_a_shape_fact():
    args=configuration_history_context()
    for row in args[0]["relations"]["public.extension_runtime_configuration"]:
        row["request_hash"]="sha256:"+"f"*64
    assert len(verify_configuration_history(args).versions)==4


def runtime_verification_context(*, route="active", retirement_kind="never_enabled",uncommitted=None):
    from datetime import timedelta
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=uninstall_receipt_context(retirement_kind,route=route,uncommitted=uncommitted);packet,scope,source,locked,lock=args
    event=next(item for item in locked.record.events if item.evidence is not None and item.evidence.type=="verification")
    operation=deepcopy(packet["relations"]["public.extension_runtime_operation"][0])
    operation.update(operation_id=str(UUID(int=980)),kind="runtime-verify",expected_installation_etag=event.from_revision,
        expected_binding_revision=None,requested_by=event.actor,status="succeeded",phase="succeeded",revision=5,
        failure_code=None,idempotency_key="verification-once",request_hash="sha256:"+"e"*64)
    packet["relations"]["public.extension_runtime_operation"].append(operation)
    binding=packet["relations"]["public.extension_runtime_binding"][0]
    preparation=next(item for item in packet["relations"]["public.extension_runtime_event"]
        if item["type"]=="preparation_committed" and item["payload"]["generation"]==binding["generation"])
    payload=dict(installationId=source.installation_id,installationRevision=event.to_revision,
        generation=binding["generation"],preparationOperationId=preparation["operation_id"],
        evidenceHash=event.evidence.evidence_hash,healthCheckedAt=event.evidence.observed_at.isoformat(),enabled=False)
    entries=[("accepted",{"kind":"runtime-verify"}),("validating",{"previousPhase":"accepted"}),
        ("committing",{"previousPhase":"validating"}),("verification_committed",payload),
        ("succeeded",{"previousPhase":"committing"})]
    # now() is the transaction start, not the clock_timestamp() health observation.
    occurred=(event.evidence.observed_at-timedelta(seconds=30)).isoformat()
    for sequence,(kind,body) in enumerate(entries,1):
        identity=str(UUID(int=990+sequence))
        packet["relations"]["public.extension_runtime_event"].append(dict(org_id=scope.org_id,project_id=scope.project_id,
            operation_id=operation["operation_id"],sequence=sequence,event_id=identity,type=kind,payload=body,
            payload_hash=_digest(body),occurred_at=occurred))
        packet["relations"]["public.extension_runtime_outbox"].append(dict(org_id=scope.org_id,project_id=scope.project_id,
            event_id=identity,consumer_id="runtime-reconciler",attempt=0,next_attempt=occurred,claim_until=None,delivered_at=None))
    return args


def verify_runtime_graph(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    return reader._verified_runtime_graph(decode(packet,ledger),scope=scope,source=source,
        locked_source=locked,source_lock=lock,ledger=ledger)


def test_original_runtime_verification_links_record_preparation_and_binding_without_time_reinterpretation():
    args=runtime_verification_context();before=deepcopy(args);result=verify_runtime_graph(args)
    assert result.verification_operation==UUID(int=980)
    assert result.preparation.operation_id==UUID(int=100)
    assert result.configurations.current is None and args==before and not hasattr(result,"authorized")


@pytest.mark.parametrize("fault",["missing","actor","etag","binding_target","request_hash","failed",
    "installation","generation","revision","revision_bool","evidence","preparation","enabled_int","enabled_true",
    "extra","health_naive","health_old","health_future","profile","handle_extra","handle_operation",
    "handle_resource","accepted","transition","proof_kind"])
def test_runtime_verification_rejects_unlinked_or_tampered_producer_facts(fault):
    from datetime import timedelta
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=runtime_verification_context();packet=args[0]
    operation=packet["relations"]["public.extension_runtime_operation"][-1]
    events=[row for row in packet["relations"]["public.extension_runtime_event"] if row["operation_id"]==operation["operation_id"]]
    proof=events[3];body=proof["payload"];binding=packet["relations"]["public.extension_runtime_binding"][0]
    if fault=="missing":proof["type"]="unknown"
    elif fault=="actor":operation["requested_by"]="another-actor"
    elif fault=="etag":operation["expected_installation_etag"]+=1
    elif fault=="binding_target":operation["expected_binding_revision"]=1
    elif fault=="request_hash":operation["request_hash"]="invalid"
    elif fault=="failed":operation["status"]="failed"
    elif fault=="installation":body["installationId"]=str(UUID(int=9999))
    elif fault=="generation":body["generation"]=str(UUID(int=9999))
    elif fault=="revision":body["installationRevision"]+=1
    elif fault=="revision_bool":body["installationRevision"]=True
    elif fault=="evidence":body["evidenceHash"]="sha256:"+"d"*64
    elif fault=="preparation":body["preparationOperationId"]=str(UUID(int=9999))
    elif fault=="enabled_int":body["enabled"]=0
    elif fault=="enabled_true":body["enabled"]=True
    elif fault=="extra":body["extra"]=True
    elif fault=="health_naive":body["healthCheckedAt"]="2026-08-03T01:00:00"
    elif fault in ("health_old","health_future"):
        value=datetime.fromisoformat(body["healthCheckedAt"])+timedelta(seconds=-4 if fault=="health_old" else 1)
        body["healthCheckedAt"]=value.isoformat()
    elif fault=="profile":binding["profile_ref"]="unknown-profile"
    elif fault=="handle_extra":binding["resource_handle_ref"]["extra"]=True
    elif fault=="handle_operation":binding["resource_handle_ref"]["preparationOperationId"]=str(UUID(int=9999))
    elif fault=="handle_resource":binding["resource_handle_ref"]["resources"].pop()
    elif fault=="accepted":events[0]["payload"]["kind"]="runtime-apply"
    elif fault=="transition":events[1]["payload"]["previousPhase"]="committing"
    elif fault=="proof_kind":operation["kind"]="runtime-apply"
    for row in events:row["payload_hash"]=_digest(row["payload"])
    with pytest.raises(ValueError):verify_runtime_graph(args)


def test_runtime_verification_uses_current_preparation_and_keeps_reset_old_generation():
    args=runtime_verification_context(route="reset-active");result=verify_runtime_graph(args)
    assert result.preparation.operation_id==UUID(int=101)
    assert len(result.receipt.context.notifications.preparation_facts.preparations)==2


@pytest.mark.parametrize("age",[0,3])
def test_runtime_verification_original_clock_health_boundary(age):
    from datetime import timedelta
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=runtime_verification_context();event=next(row for row in args[0]["relations"]["public.extension_runtime_event"] if row["type"]=="verification_committed")
    value=datetime.fromisoformat(event["payload"]["healthCheckedAt"])-timedelta(seconds=age)
    event["payload"]["healthCheckedAt"]=value.isoformat();event["payload_hash"]=_digest(event["payload"])
    assert verify_runtime_graph(args).verification_operation==UUID(int=980)


def test_runtime_verification_cannot_reuse_old_reset_generation_resource_handle():
    args=runtime_verification_context(route="reset-active")
    old=next(row for row in args[0]["relations"]["public.extension_runtime_event"] if row["type"]=="preparation_committed")
    args[0]["relations"]["public.extension_runtime_binding"][0]["resource_handle_ref"]={
        "preparationOperationId":old["operation_id"],"resources":deepcopy(old["payload"]["resources"])}
    with pytest.raises(ValueError):verify_runtime_graph(args)


def test_runtime_verification_integrates_configuration_history_with_the_same_work_ledger():
    args=runtime_verification_context()
    with mock.patch.object(reader,"_configuration_history",wraps=reader._configuration_history) as checked:
        result=verify_runtime_graph(args)
    assert checked.call_count==1 and checked.call_args.kwargs["generation"]==result.preparation.generation
    assert type(checked.call_args.kwargs["ledger"]) is reader._WorkLedger


def test_runtime_verification_rejects_successful_operation_without_its_own_proof():
    args=runtime_verification_context();packet=args[0]
    extra=deepcopy(packet["relations"]["public.extension_runtime_operation"][-1])
    extra.update(operation_id=str(UUID(int=1990)),revision=1,idempotency_key="other-verification")
    packet["relations"]["public.extension_runtime_operation"].append(extra)
    event=deepcopy(next(row for row in packet["relations"]["public.extension_runtime_event"] if row["operation_id"]==str(UUID(int=980)) and row["sequence"]==1))
    event.update(operation_id=extra["operation_id"],event_id=str(UUID(int=1991)))
    packet["relations"]["public.extension_runtime_event"].append(event)
    outbox=deepcopy(packet["relations"]["public.extension_runtime_outbox"][0]);outbox["event_id"]=event["event_id"]
    packet["relations"]["public.extension_runtime_outbox"].append(outbox)
    with pytest.raises(ValueError):verify_runtime_graph(args)


def add_control_operation(args,kind,identity,binding_revision,epoch,*,outcome="succeeded",cancel_phase="accepted",disable_id=None):
    from aos_api.extension_runtime.lifecycle_store import _digest,_request_hash
    packet,scope,source,locked,lock=args;binding=packet["relations"]["public.extension_runtime_binding"][0]
    target=dict(generation=binding["generation"],bindingRevision=binding_revision)
    target_key="bindingTarget" if kind=="disable" else "configurationTarget"
    if kind!="disable":target["configRef"]=deepcopy(binding["config_ref"])
    operation=deepcopy(packet["relations"]["public.extension_runtime_operation"][-1])
    operation.update(operation_id=str(UUID(int=identity)),kind=kind,expected_installation_etag=binding["installation_revision"],
        expected_binding_revision=binding_revision,requested_by="control-actor",failure_code=None,
        idempotency_key=f"control-{identity}",deadline="2026-08-03T12:00:00+08:00")
    operation["request_hash"]=_request_hash(kind=kind,actor=operation["requested_by"],etag=operation["expected_installation_etag"],
        deadline=datetime.fromisoformat(operation["deadline"]),**{"binding_target" if kind=="disable" else "configuration_target":target})
    entries=[("accepted",{"kind":kind,target_key:target})]
    if outcome=="cancelled":
        if cancel_phase=="validating":entries.append(("validating",{"previousPhase":"accepted"}))
        entries.append(("cancelled_for_disable",dict(previousPhase=cancel_phase,disableOperationId=str(UUID(int=disable_id)),actor="control-actor")))
        operation.update(status="cancelled",phase=cancel_phase)
    elif outcome=="stale":
        entries.append(("disable_target_stale",dict(installationId=source.installation_id,generation=binding["generation"],
            acceptedBindingRevision=binding_revision,currentBindingRevision=binding_revision+3,failureCode="DISABLE_TARGET_STALE")))
        operation.update(status="failed",phase="accepted",failure_code="DISABLE_TARGET_STALE")
    else:
        phases={"configure":["validating","fencing","committing"],"enable":["validating","committing"],
                "disable":["fencing","draining","committing"]}[kind]
        previous="accepted"
        for phase in phases:entries.append((phase,{"previousPhase":previous}));previous=phase
        body=dict(installationId=source.installation_id,generation=binding["generation"],
            bindingRevision=binding_revision+(1 if kind=="enable" else 2),executionEpoch=epoch)
        if kind=="configure":body.update(configRef=deepcopy(binding["config_ref"]),enabled=False,observedState="unknown")
        elif kind=="enable":body.update(configRef=deepcopy(binding["config_ref"]),
            preparationOperationId=binding["resource_handle_ref"]["preparationOperationId"],healthCheckedAt="2026-08-03T01:00:00+00:00")
        else:body.update(resourcesRetained=True)
        entries += [({"configure":"configuration_committed","enable":"enabled_committed","disable":"disabled_committed"}[kind],body),
                    ("succeeded",{"previousPhase":"committing"})]
        operation.update(status="succeeded",phase="succeeded")
    operation["revision"]=len(entries)
    packet["relations"]["public.extension_runtime_operation"].append(operation)
    for sequence,(kind_,payload) in enumerate(entries,1):
        event_id=str(UUID(int=identity*100+sequence))
        packet["relations"]["public.extension_runtime_event"].append(dict(org_id=scope.org_id,project_id=scope.project_id,
            operation_id=operation["operation_id"],sequence=sequence,event_id=event_id,type=kind_,payload=payload,
            payload_hash=_digest(payload),occurred_at="2026-08-03T00:00:00+00:00"))
        packet["relations"]["public.extension_runtime_outbox"].append(dict(org_id=scope.org_id,project_id=scope.project_id,
            event_id=event_id,consumer_id="runtime-reconciler",attempt=0,next_attempt="2026-08-03T00:00:00+00:00",
            claim_until=None,delivered_at=None))
    return operation


def control_history_context(retirement_kind="enabled_undispatched"):
    import hashlib
    from aos_api.extension_runtime.configuration_store import _content_hash
    args=runtime_verification_context(retirement_kind=retirement_kind);packet,scope,source,locked,lock=args
    binding=packet["relations"]["public.extension_runtime_binding"][0]
    rows=configuration_history_context()[0]["relations"]["public.extension_runtime_configuration"]
    previous={}
    for row in rows:
        row.update(installation_id=source.installation_id,generation=binding["generation"])
        row["previous_hash"]=previous.get(row["configuration_id"])
        row["content_hash"]=_content_hash((*scope.key,UUID(source.installation_id),UUID(binding["generation"])),
            UUID(row["configuration_id"]),row["revision"],row["previous_hash"],row["actor"],row["payload"])
        previous[row["configuration_id"]]=row["content_hash"]
    packet["relations"]["public.extension_runtime_configuration"]=rows
    binding["config_ref"]=dict(configurationId=rows[0]["configuration_id"],revision=1,hash=rows[0]["content_hash"])
    configure=add_control_operation(args,"configure",3000,1,2)
    enabled=retirement_kind=="enabled_undispatched"
    if enabled:enable=add_control_operation(args,"enable",3001,3,3)
    disable=add_control_operation(args,"disable",3002,4 if enabled else 3,4 if enabled else 3)
    receipt=packet["relations"]["public.extension_runtime_uninstall_receipt"][0]
    if enabled:receipt.update(runtime_enable_operation_id=enable["operation_id"],runtime_disable_operation_id=disable["operation_id"])
    else:receipt.update(unactivated_disable_operation_id=disable["operation_id"])
    body=json.loads(receipt["authority_data_text"])
    body.update(configRef=deepcopy(binding["config_ref"]),disableOperationId=disable["operation_id"])
    if enabled:body["enableOperationId"]=enable["operation_id"]
    receipt["authority_data_text"]=json.dumps(body);receipt["content_hash"]="sha256:"+hashlib.sha256(receipt["authority_data_text"].encode()).hexdigest()
    return args


def verify_control_history(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    return reader._control_history(decode(packet,ledger),scope=scope,source=source,
        locked_source=locked,source_lock=lock,ledger=ledger)


def test_original_control_targets_and_commits_link_all_three_kinds_with_staged_successors():
    args=control_history_context();before=deepcopy(args);result=verify_control_history(args)
    assert len(result.targets)==len(result.commits)==3 and args==before
    assert len(result.graph.configurations.versions)==4 and not hasattr(result,"authorized")


@pytest.mark.parametrize("kind",["configure","enable"])
@pytest.mark.parametrize("phase",["accepted","validating"])
def test_original_effect_free_cancellation_retains_disable_cause(kind,phase):
    args=control_history_context();add_control_operation(args,kind,3010,4,4,outcome="cancelled",cancel_phase=phase,disable_id=3002)
    result=verify_control_history(args)
    assert result.cancelled==(UUID(int=3010),) and len(result.commits)==3


def test_original_stale_disable_target_is_a_failed_receipt_without_binding_effect():
    args=control_history_context();add_control_operation(args,"disable",3011,1,1,outcome="stale")
    result=verify_control_history(args)
    assert result.stale==(UUID(int=3011),) and len(result.commits)==3


@pytest.mark.parametrize("fault",["accepted_extra","accepted_kind","target_extra","target_generation","target_revision_bool",
    "target_revision","target_config","target_config_bool","request_hash","request_actor","etag","expected_binding",
    "commit_kind","commit_extra","commit_generation","commit_revision","commit_revision_bool","commit_epoch_zero",
    "commit_epoch_bool","commit_config","commit_enabled_int","commit_observed","commit_prepare","commit_health_naive",
    "commit_retained_int","phase_previous","phase_order","status","failure_code","idempotency_duplicate"])
def test_control_history_rejects_tampering_even_with_rehashed_event_payloads(fault):
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=control_history_context();packet=args[0]
    operations=packet["relations"]["public.extension_runtime_operation"]
    chosen=3001 if fault in ("commit_prepare","commit_health_naive") else 3002 if fault=="commit_retained_int" else 3000
    op=next(row for row in operations if row["operation_id"]==str(UUID(int=chosen)))
    events=[row for row in packet["relations"]["public.extension_runtime_event"] if row["operation_id"]==op["operation_id"]]
    accepted=events[0]["payload"];target=accepted["bindingTarget" if op["kind"]=="disable" else "configurationTarget"]
    commit=next(row for row in events if row["type"].endswith("_committed"));body=commit["payload"]
    if fault=="accepted_extra":accepted["extra"]=1
    elif fault=="accepted_kind":accepted["kind"]="enable"
    elif fault=="target_extra":target["extra"]=1
    elif fault=="target_generation":target["generation"]=str(UUID(int=9999))
    elif fault=="target_revision_bool":target["bindingRevision"]=True
    elif fault=="target_revision":target["bindingRevision"]+=1
    elif fault=="target_config":target["configRef"]["hash"]="sha256:"+"d"*64
    elif fault=="target_config_bool":target["configRef"]["revision"]=True
    elif fault=="request_hash":op["request_hash"]="sha256:"+"d"*64
    elif fault=="request_actor":op["requested_by"]="another"
    elif fault=="etag":op["expected_installation_etag"]+=1
    elif fault=="expected_binding":op["expected_binding_revision"]+=1
    elif fault=="commit_kind":commit["type"]="enabled_committed"
    elif fault=="commit_extra":body["extra"]=1
    elif fault=="commit_generation":body["generation"]=str(UUID(int=9999))
    elif fault=="commit_revision":body["bindingRevision"]+=1
    elif fault=="commit_revision_bool":body["bindingRevision"]=True
    elif fault=="commit_epoch_zero":body["executionEpoch"]=0
    elif fault=="commit_epoch_bool":body["executionEpoch"]=True
    elif fault=="commit_config":body["configRef"]["hash"]="sha256:"+"d"*64
    elif fault=="commit_enabled_int":body["enabled"]=0
    elif fault=="commit_observed":body["observedState"]="ready"
    elif fault=="commit_prepare":body["preparationOperationId"]=str(UUID(int=9999))
    elif fault=="commit_health_naive":body["healthCheckedAt"]="2026-08-03T01:00:00"
    elif fault=="commit_retained_int":body["resourcesRetained"]=1
    elif fault=="phase_previous":events[1]["payload"]["previousPhase"]="committing"
    elif fault=="phase_order":events[1]["type"]="committing"
    elif fault=="status":op["status"]="failed"
    elif fault=="failure_code":op["failure_code"]="unproven"
    elif fault=="idempotency_duplicate":
        add_control_operation(args,"configure",3020,7,5)["idempotency_key"]=op["idempotency_key"]
    for row in events:row["payload_hash"]=_digest(row["payload"])
    with pytest.raises(ValueError):verify_control_history(args)


def test_control_request_hash_keeps_original_utc_offset_normalization():
    from datetime import UTC
    args=control_history_context()
    for op in args[0]["relations"]["public.extension_runtime_operation"]:
        if op["kind"] in {"configure","enable","disable"}:
            op["deadline"]=datetime.fromisoformat(op["deadline"]).astimezone(UTC).isoformat()
    assert len(verify_control_history(args).commits)==3


@pytest.mark.parametrize("fault",["unknown_cause","other_actor","other_target","wrong_previous","extra","failed_positive"])
def test_cancelled_positive_operation_requires_original_exact_disable_cause(fault):
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=control_history_context();op=add_control_operation(args,"enable",3010,4,4,outcome="cancelled",disable_id=3002)
    event=next(row for row in args[0]["relations"]["public.extension_runtime_event"] if row["operation_id"]==op["operation_id"] and row["type"]=="cancelled_for_disable")
    body=event["payload"]
    if fault=="unknown_cause":body["disableOperationId"]=str(UUID(int=9999))
    elif fault=="other_actor":body["actor"]="another-actor"
    elif fault=="other_target":body["disableOperationId"]=str(UUID(int=3000))
    elif fault=="wrong_previous":body["previousPhase"]="validating"
    elif fault=="extra":body["extra"]=1
    elif fault=="failed_positive":op.update(status="failed",failure_code="unproven")
    event["payload_hash"]=_digest(body)
    with pytest.raises(ValueError):verify_control_history(args)


@pytest.mark.parametrize("fault",["equal","older","future","bool","reason","extra"])
def test_stale_disable_failure_requires_a_strictly_newer_current_version(fault):
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=control_history_context();op=add_control_operation(args,"disable",3011,1,1,outcome="stale")
    event=next(row for row in args[0]["relations"]["public.extension_runtime_event"] if row["operation_id"]==op["operation_id"] and row["type"]=="disable_target_stale")
    body=event["payload"]
    if fault in {"equal","older","future","bool"}:body["currentBindingRevision"]={"equal":1,"older":0,"future":100,"bool":True}[fault]
    elif fault=="reason":body["failureCode"]="unproven"
    else:body["extra"]=1
    event["payload_hash"]=_digest(body)
    with pytest.raises(ValueError):verify_control_history(args)


def terminal_binding_versions(args,revision,epoch):
    import hashlib
    packet=args[0];packet["relations"]["public.extension_runtime_binding"][0].update(revision=revision,execution_epoch=epoch)
    row=packet["relations"]["public.extension_runtime_uninstall_receipt"][0];row["binding_revision"]=revision
    body=json.loads(row["authority_data_text"]);body["bindingRevision"]=revision
    row["authority_data_text"]=json.dumps(body);row["content_hash"]="sha256:"+hashlib.sha256(row["authority_data_text"].encode()).hexdigest()
    return args


def replace_successful_controls(args,specs):
    packet=args[0];operations=packet["relations"]["public.extension_runtime_operation"]
    removed={row["operation_id"] for row in operations if row["kind"] in {"configure","enable","disable"}}
    operations[:]=[row for row in operations if row["operation_id"] not in removed]
    events=packet["relations"]["public.extension_runtime_event"]
    event_ids={row["event_id"] for row in events if row["operation_id"] in removed}
    events[:]=[row for row in events if row["event_id"] not in event_ids]
    outbox=packet["relations"]["public.extension_runtime_outbox"]
    outbox[:]=[row for row in outbox if row["event_id"] not in event_ids]
    for spec in specs:add_control_operation(args,*spec)
    return args


def verify_control_timeline(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    return reader._control_timeline(decode(packet,ledger),scope=scope,source=source,
        locked_source=locked,source_lock=lock,ledger=ledger)


def test_control_timeline_original_enabled_configure_disable_then_uninstall_versions():
    args=terminal_binding_versions(control_history_context(),7,4);result=verify_control_timeline(args)
    assert result.before_uninstall_revision==6 and result.execution_epoch==4
    assert result.cleanup_revision is None and not hasattr(result,"authorized")


def test_control_timeline_never_enabled_requires_ready_cleanup_revision_before_uninstall():
    args=terminal_binding_versions(runtime_verification_context(),3,1);result=verify_control_timeline(args)
    assert result.cleanup_revision==2 and result.before_uninstall_revision==2 and result.execution_epoch==1


def test_control_timeline_cleanup_before_disable_preserves_the_extra_fence_epoch():
    args=replace_successful_controls(control_history_context(),[("configure",3000,1,2),("enable",3001,3,3),("disable",3002,5,5)])
    result=verify_control_timeline(terminal_binding_versions(args,8,5))
    assert result.cleanup_revision==5 and result.before_uninstall_revision==7 and result.execution_epoch==5


def test_control_timeline_multiple_configurations_do_not_require_latest_staged_payload():
    args=replace_successful_controls(control_history_context(),[("configure",3000,1,2),("configure",3015,3,3),
        ("enable",3001,5,4),("disable",3002,6,5)])
    result=verify_control_timeline(terminal_binding_versions(args,9,5))
    assert result.before_uninstall_revision==8 and result.execution_epoch==5


@pytest.mark.parametrize("revision,epoch",[(6,4),(8,4),(7,3),(7,5),(10,3)])
def test_control_timeline_rejects_unexplained_final_revisions_or_epochs(revision,epoch):
    with pytest.raises(ValueError):verify_control_timeline(terminal_binding_versions(control_history_context(),revision,epoch))


def test_control_timeline_rejects_a_ready_binding_without_its_necessary_cleanup_version():
    with pytest.raises(ValueError):verify_control_timeline(terminal_binding_versions(runtime_verification_context(),2,1))


def test_control_timeline_cannot_fill_a_gap_with_cleanup_before_later_successful_enable():
    args=replace_successful_controls(control_history_context(),[("configure",3000,2,2),("enable",3001,4,3),("disable",3002,5,4)])
    with pytest.raises(ValueError):verify_control_timeline(terminal_binding_versions(args,8,4))


def test_control_timeline_configured_unactivated_preserves_original_fence_and_commit_versions():
    result=verify_control_timeline(terminal_binding_versions(control_history_context("configured_unactivated"),6,3))
    assert result.before_uninstall_revision==5 and result.execution_epoch==3 and result.cleanup_revision is None


def test_control_timeline_ready_cleanup_then_configuration_and_disable_is_reachable_without_enable():
    args=replace_successful_controls(control_history_context("configured_unactivated"),[("configure",3000,2,2),("disable",3002,4,3)])
    result=verify_control_timeline(terminal_binding_versions(args,7,3))
    assert result.cleanup_revision==2 and result.before_uninstall_revision==6


def test_control_timeline_old_reset_generation_does_not_add_current_binding_cleanup_versions():
    args=runtime_verification_context(route="reset-active")
    result=verify_control_timeline(terminal_binding_versions(args,3,1))
    assert result.cleanup_revision==2 and len(result.versions)==2


def test_control_timeline_stale_receipt_and_shuffled_rows_use_sequence_not_input_order():
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=replace_successful_controls(control_history_context("configured_unactivated"),[("configure",3000,2,2),("disable",3002,4,3)])
    terminal_binding_versions(args,7,3)
    op=add_control_operation(args,"disable",3011,1,1,outcome="stale")
    event=next(row for row in args[0]["relations"]["public.extension_runtime_event"] if row["operation_id"]==op["operation_id"] and row["type"]=="disable_target_stale")
    event["payload"]["currentBindingRevision"]=2;event["payload_hash"]=_digest(event["payload"])
    for rows in args[0]["relations"].values():rows.reverse()
    result=verify_control_timeline(args)
    assert result.cleanup_revision==2 and result.history.stale==(UUID(int=3011),)


def test_control_timeline_rejects_enable_on_a_different_valid_staged_configuration():
    from aos_api.extension_runtime.lifecycle_store import _digest,_request_hash
    args=terminal_binding_versions(control_history_context(),7,4);packet=args[0]
    staged=packet["relations"]["public.extension_runtime_configuration"][1]
    ref=dict(configurationId=staged["configuration_id"],revision=staged["revision"],hash=staged["content_hash"])
    op=next(row for row in packet["relations"]["public.extension_runtime_operation"] if row["kind"]=="enable")
    events=[row for row in packet["relations"]["public.extension_runtime_event"] if row["operation_id"]==op["operation_id"]]
    target=events[0]["payload"]["configurationTarget"];target["configRef"]=deepcopy(ref)
    next(row for row in events if row["type"]=="enabled_committed")["payload"]["configRef"]=deepcopy(ref)
    op["request_hash"]=_request_hash(kind="enable",actor=op["requested_by"],etag=op["expected_installation_etag"],
        deadline=datetime.fromisoformat(op["deadline"]),configuration_target=target)
    for row in events:row["payload_hash"]=_digest(row["payload"])
    assert len(verify_control_history(args).commits)==3
    with pytest.raises(ValueError):verify_control_timeline(args)


NONDISPATCH_EMPTY_FAMILIES=("extension_operation_dispatch_binding","extension_dispatch_cutover_operation",
    "extension_dispatch_lifecycle_operation","automation_schedule_binding","automation_occurrence",
    "automation_occurrence_dispatch_attempt","automation_occurrence_outbox","extension_dispatch_claim_gate",
    "extension_runtime_execution_attempt","extension_runtime_execution_attempt_event","extension_dispatch_cutover_receipt",
    "extension_dispatch_lifecycle_event","extension_dispatch_lifecycle_receipt","extension_dispatch_configuration_refresh_receipt",
    "extension_dispatch_successor_registration_receipt","extension_event_control_dispatch_receipt","extension_dispatch_cutover_event",
    "extension_dispatch_cutover_approval_refresh_receipt","extension_dispatch_registration_receipt","extension_dispatch_withdrawal_receipt","ecommerce_growth_runtime_command_receipt")


def nondispatch_context(kind):
    if kind=="never_enabled":return terminal_binding_versions(runtime_verification_context(),3,1)
    return terminal_binding_versions(control_history_context(kind),6 if kind=="configured_unactivated" else 7,
        3 if kind=="configured_unactivated" else 4)


def verify_nondispatch_source(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    return reader._nondispatch_runtime_source(decode(packet,ledger),scope=scope,source=source,
        locked_source=locked,source_lock=lock,ledger=ledger)


@pytest.mark.parametrize("kind",["never_enabled","configured_unactivated","enabled_undispatched"])
def test_three_nondispatch_sources_require_full_nonempty_graphs_and_actual_empty_obligations(kind):
    args=nondispatch_context(kind);before=deepcopy(args);result=verify_nondispatch_source(args)
    assert result.kind==kind and result.timeline.before_uninstall_revision==args[0]["relations"]["public.extension_runtime_binding"][0]["revision"]-1
    assert not hasattr(result,"authorized") and args==before


@pytest.mark.parametrize("family",NONDISPATCH_EMPTY_FAMILIES)
def test_each_nondispatch_obligation_family_is_explicitly_empty_before_graph_work(family):
    args=nondispatch_context("enabled_undispatched");name="public."+family
    row=row_for(reader._RELATIONS[name]);row.update(org_id=args[1].org_id,project_id=args[1].project_id)
    args[0]["relations"][name].append(row)
    with mock.patch.object(reader,"_control_timeline",side_effect=AssertionError("nonempty obligation must be rejected first")) as timeline:
        with pytest.raises(ValueError):verify_nondispatch_source(args)
        assert timeline.call_count==0


@pytest.mark.parametrize("kind,column",[("configured_unactivated","unactivated_disable_operation_id"),
    ("enabled_undispatched","runtime_disable_operation_id"),("enabled_undispatched","runtime_enable_operation_id")])
def test_retirement_references_must_name_actual_matching_final_control_proofs(kind,column):
    import hashlib
    args=nondispatch_context(kind);row=args[0]["relations"]["public.extension_runtime_uninstall_receipt"][0]
    row[column]=str(UUID(int=9999));body=json.loads(row["authority_data_text"])
    body["enableOperationId" if column=="runtime_enable_operation_id" else "disableOperationId"]=row[column]
    row["authority_data_text"]=json.dumps(body);row["content_hash"]="sha256:"+hashlib.sha256(row["authority_data_text"].encode()).hexdigest()
    assert verify_control_timeline(args).before_uninstall_revision>1
    with pytest.raises(ValueError):verify_nondispatch_source(args)


@pytest.mark.parametrize("kind",["configured_unactivated","enabled_undispatched"])
def test_nondispatch_retirement_cannot_use_an_older_disable_proof(kind):
    import hashlib
    args=nondispatch_context(kind);binding=args[0]["relations"]["public.extension_runtime_binding"][0]
    before=binding["revision"]-1;epoch=binding["execution_epoch"]
    add_control_operation(args,"disable",3030,before,epoch+1)
    terminal_binding_versions(args,before+3,epoch+1)
    assert verify_control_timeline(args).before_uninstall_revision==before+2
    with pytest.raises(ValueError):verify_nondispatch_source(args)


def test_nondispatch_configured_keeps_a_legitimate_cancelled_enable_with_its_disable():
    args=nondispatch_context("configured_unactivated")
    add_control_operation(args,"enable",3010,3,3,outcome="cancelled",disable_id=3002)
    assert verify_nondispatch_source(args).kind=="configured_unactivated"


@pytest.mark.parametrize("partial",["unclaimed","claimed"])
def test_nondispatch_never_keeps_released_uncommitted_failed_preparation(partial):
    args=terminal_binding_versions(runtime_verification_context(uncommitted=partial),3,1)
    assert verify_nondispatch_source(args).kind=="never_enabled"


def add_abandoned_verification(args,phase="accepted"):
    from aos_api.extension_runtime.lifecycle_store import _digest
    packet,scope,source,locked,lock=args
    reset=next(event for event in locked.record.events if event.evidence is not None and event.evidence.type=="preparation_reset")
    operation=deepcopy(next((row for row in packet["relations"]["public.extension_runtime_operation"] if row["kind"]=="runtime-verify"),
        packet["relations"]["public.extension_runtime_operation"][0]))
    operation.update(operation_id=str(UUID(int=985)),expected_installation_etag=reset.from_revision,
        kind="runtime-verify",expected_binding_revision=None,idempotency_key="abandoned-before-reset",status="failed",phase=phase,failure_code="PREPARATION_OWNER_LOST")
    entries=[("accepted",{"kind":"runtime-verify"})]
    if phase=="validating":entries.append(("validating",{"previousPhase":"accepted"}))
    entries.append(("verification_abandoned",dict(phase=phase,installationRevision=reset.from_revision)))
    operation["revision"]=len(entries);packet["relations"]["public.extension_runtime_operation"].append(operation)
    for sequence,(kind,body) in enumerate(entries,1):
        identity=str(UUID(int=1985+sequence))
        packet["relations"]["public.extension_runtime_event"].append(dict(org_id=scope.org_id,project_id=scope.project_id,
            operation_id=operation["operation_id"],sequence=sequence,event_id=identity,type=kind,payload=body,
            payload_hash=_digest(body),occurred_at=reset.created_at.isoformat()))
        packet["relations"]["public.extension_runtime_outbox"].append(dict(org_id=scope.org_id,project_id=scope.project_id,
            event_id=identity,consumer_id="runtime-reconciler",attempt=0,next_attempt=reset.created_at.isoformat(),claim_until=None,delivered_at=None))
    return operation


@pytest.mark.parametrize("phase",["accepted","validating"])
def test_nondispatch_keeps_old_abandoned_verification_only_with_original_reset(phase):
    args=terminal_binding_versions(runtime_verification_context(route="reset-active"),3,1)
    add_abandoned_verification(args,phase)
    assert verify_nondispatch_source(args).kind=="never_enabled"


@pytest.mark.parametrize("fault",["reason","phase","revision_bool","reset_revision","etag","extra"])
def test_abandoned_verification_cannot_be_a_bare_failed_label(fault):
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=terminal_binding_versions(runtime_verification_context(route="reset-active"),3,1);op=add_abandoned_verification(args)
    event=next(row for row in args[0]["relations"]["public.extension_runtime_event"] if row["operation_id"]==op["operation_id"] and row["type"]=="verification_abandoned")
    if fault=="reason":op["failure_code"]="unknown"
    elif fault=="phase":event["payload"]["phase"]="committing"
    elif fault=="revision_bool":event["payload"]["installationRevision"]=True
    elif fault=="reset_revision":event["payload"]["installationRevision"]+=1
    elif fault=="etag":op["expected_installation_etag"]+=1
    elif fault=="extra":event["payload"]["extra"]=1
    event["payload_hash"]=_digest(event["payload"])
    with pytest.raises(ValueError):verify_nondispatch_source(args)


def multi_enable_nondispatch_context(different_config):
    import hashlib
    args=replace_successful_controls(nondispatch_context("enabled_undispatched"),[]);packet=args[0]
    binding=packet["relations"]["public.extension_runtime_binding"][0]
    add_control_operation(args,"configure",3000,1,2)
    add_control_operation(args,"enable",3016,3,3)
    if different_config:
        staged=packet["relations"]["public.extension_runtime_configuration"][1]
        binding["config_ref"]=dict(configurationId=staged["configuration_id"],revision=staged["revision"],hash=staged["content_hash"])
        add_control_operation(args,"configure",3015,4,4)
    else:add_control_operation(args,"disable",3017,4,4)
    add_control_operation(args,"enable",3001,6,5);add_control_operation(args,"disable",3002,7,6)
    row=packet["relations"]["public.extension_runtime_uninstall_receipt"][0];body=json.loads(row["authority_data_text"])
    body["configRef"]=deepcopy(binding["config_ref"]);row["authority_data_text"]=json.dumps(body)
    row["content_hash"]="sha256:"+hashlib.sha256(row["authority_data_text"].encode()).hexdigest()
    return terminal_binding_versions(args,10,6)


def test_enabled_branch_keeps_older_successful_enable_for_a_different_configuration():
    args=multi_enable_nondispatch_context(True);result=verify_nondispatch_source(args)
    assert len([commit for commit in result.timeline.history.commits.values() if commit.kind=="enable"])==2
    assert result.kind=="enabled_undispatched"


def test_enabled_branch_rejects_two_successful_enable_proofs_for_the_current_configuration():
    args=multi_enable_nondispatch_context(False)
    assert verify_control_timeline(args).before_uninstall_revision==9
    with pytest.raises(ValueError):verify_nondispatch_source(args)


@pytest.mark.parametrize("fault",["reason","phase","etag","request_hash","idempotency","checkpoint","proof_extra"])
def test_failed_uncommitted_preparation_needs_its_real_terminal_producer(fault):
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=terminal_binding_versions(runtime_verification_context(uncommitted="claimed"),3,1)
    op=next(row for row in args[0]["relations"]["public.extension_runtime_operation"] if row["kind"]=="runtime-apply" and row["status"]=="failed")
    events=sorted([row for row in args[0]["relations"]["public.extension_runtime_event"] if row["operation_id"]==op["operation_id"]],key=lambda row:row["sequence"])
    if fault=="reason":op["failure_code"]="unproven"
    elif fault=="phase":op["phase"]="registered"
    elif fault=="etag":op["expected_installation_etag"]+=1
    elif fault=="request_hash":op["request_hash"]="invalid"
    elif fault=="idempotency":op["idempotency_key"]="private://PRIVATE_FIXTURE_VALUE\n"
    elif fault=="checkpoint":events[1]["payload"]["previousPhase"]="committing"
    elif fault=="proof_extra":events[-1]["payload"]["extra"]=True
    for event in events:event["payload_hash"]=_digest(event["payload"])
    with pytest.raises(ValueError) as caught:verify_nondispatch_source(args)
    assert "PRIVATE_FIXTURE_VALUE" not in str(caught.value)


def test_failed_uncertain_preparation_is_kept_after_exact_settlement_and_release():
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=terminal_binding_versions(runtime_verification_context(uncommitted="claimed"),3,1);packet=args[0]
    op=next(row for row in packet["relations"]["public.extension_runtime_operation"] if row["kind"]=="runtime-apply" and row["status"]=="failed")
    events=sorted([row for row in packet["relations"]["public.extension_runtime_event"] if row["operation_id"]==op["operation_id"]],key=lambda row:row["sequence"])
    release=next(row for row in events if row["type"]=="resource_released")
    uncertain=deepcopy(release);uncertain.update(event_id=str(UUID(int=9990)),type="resource_uncertain")
    events.insert(events.index(release),uncertain);packet["relations"]["public.extension_runtime_event"].append(uncertain)
    op.update(failure_code="RESOURCE_CLEANUP_UNCERTAIN",revision=len(events))
    events[-1].update(type="failed_preparation_settled",payload={"phase":op["phase"]})
    for sequence,event in enumerate(events,1):event.update(sequence=sequence,payload_hash=_digest(event["payload"]))
    outbox=deepcopy(packet["relations"]["public.extension_runtime_outbox"][0]);outbox["event_id"]=uncertain["event_id"]
    packet["relations"]["public.extension_runtime_outbox"].append(outbox)
    assert verify_nondispatch_source(args).kind=="never_enabled"


def test_fixed_nondispatch_family_partition_is_exhaustive_and_disjoint():
    assert len(reader._NONDISPATCH_EMPTY)==21 and len(reader._NONDISPATCH_LINKED)==13
    assert not reader._NONDISPATCH_EMPTY&reader._NONDISPATCH_LINKED
    assert reader._NONDISPATCH_EMPTY|reader._NONDISPATCH_LINKED==set(reader._RELATIONS)


class ContentPredicateConnection:
    def __init__(self,row=None,*,idle=False,error=None):
        from types import SimpleNamespace
        from psycopg.pq import TransactionStatus
        self.info=SimpleNamespace(transaction_status=TransactionStatus.IDLE if idle else TransactionStatus.INTRANS)
        self.row={"eligible":True} if row is None else row
        self.error=error;self.queries=[]
    def execute(self,statement,parameters):
        self.queries.append((statement,parameters))
        if self.error is not None:raise self.error
        return self
    def fetchone(self):return self.row
    def fetchall(self):return [self.row]


def verify_unbound_source(args,conn=None):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    conn=conn if conn is not None else ContentPredicateConnection()
    return reader._unbound_runtime_source(conn,decode(packet,ledger),scope=scope,source=source,
        locked_source=locked,source_lock=lock,ledger=ledger)


def test_active_content_source_uses_original_sql_and_canonical_lock_json_on_the_same_connection():
    from aos_api.asset_registry.legacy_runtime_boundary import legacy_content_predicate
    args=source_history_context("active");before=deepcopy(args);conn=ContentPredicateConnection()
    result=verify_unbound_source(args,conn)
    assert result.kind=="content" and args==before and not hasattr(result,"authorized")
    assert len(conn.queries)==1
    statement,parameters=conn.queries[0]
    predicate=legacy_content_predicate('composition_lock').replace('JOIN asset_bundle boundary_bundle','JOIN public.asset_bundle boundary_bundle').replace('JOIN asset_bundle_version boundary_version','JOIN public.asset_bundle_version boundary_version')
    assert predicate in statement and 'public.bundle_composition_lock AS composition_lock' in statement
    assert 'pg_catalog.current_setting' in statement and 'WHERE eligible' not in statement and 'LIMIT' not in statement
    assert parameters==(UUID(args[-1].composition_id),args[-1].revision,args[-1].lock_hash)


@pytest.mark.parametrize("backend",[False,True])
def test_approved_source_is_explicit_and_does_not_query_the_content_predicate(backend):
    args=source_history_context("approved",backend=backend);conn=ContentPredicateConnection(error=AssertionError("approved must not query eligibility"))
    result=verify_unbound_source(args,conn)
    assert result.kind=="approved" and not conn.queries


def test_approved_source_keeps_all_released_reset_preparation_history():
    args=runtime_notification_context(route="reset");result=verify_unbound_source(args)
    assert result.kind=="approved" and len(result.context.context.notifications.preparation_facts.preparations)==1


@pytest.mark.parametrize("partial",["unclaimed","claimed"])
def test_approved_source_keeps_complete_failed_uncommitted_preparation(partial):
    args=runtime_notification_context(route="approved",uncommitted=partial)
    assert verify_unbound_source(args).kind=="approved"


@pytest.mark.parametrize("row",[{"eligible":False},{"eligible":None},{"eligible":1},{"eligible":"true"},{"other":True},{"eligible":True,"extra":1}])
def test_active_content_requires_the_single_exact_true_sql_observation(row):
    with pytest.raises(ValueError):verify_unbound_source(source_history_context("active"),ContentPredicateConnection(row))


def test_active_content_missing_sql_row_is_not_default_eligibility():
    conn=ContentPredicateConnection();conn.row=None
    with pytest.raises(ValueError):verify_unbound_source(source_history_context("active"),conn)
    assert len(conn.queries)==1


def test_content_sql_failure_is_not_retried_or_replaced_with_python_inference():
    conn=ContentPredicateConnection(error=RuntimeError("predicate unavailable"))
    with pytest.raises(RuntimeError,match="predicate unavailable"):verify_unbound_source(source_history_context("active"),conn)
    assert len(conn.queries)==1


@pytest.mark.parametrize("route",["approved","active"])
def test_unbound_source_requires_original_intrans_connection_before_queries(route):
    conn=ContentPredicateConnection(idle=True)
    with pytest.raises(RuntimeError):verify_unbound_source(source_history_context(route),conn)
    assert conn.queries==[]


def test_active_runtime_manifest_is_not_eligible_content_even_if_fake_sql_would_say_true():
    conn=ContentPredicateConnection();args=source_history_context("active",backend=True)
    with pytest.raises(ValueError):verify_unbound_source(args,conn)
    assert conn.queries==[]


@pytest.mark.parametrize("family",NONDISPATCH_EMPTY_FAMILIES)
def test_unbound_sources_also_reject_each_nonempty_dispatch_or_business_obligation(family):
    args=source_history_context("approved");name="public."+family
    row=row_for(reader._RELATIONS[name]);row.update(org_id=args[1].org_id,project_id=args[1].project_id)
    args[0]["relations"][name].append(row)
    conn=ContentPredicateConnection()
    with pytest.raises(ValueError):verify_unbound_source(args,conn)
    assert not conn.queries


def test_unbound_source_does_not_reinterpret_a_runtime_retirement_with_a_binding():
    with pytest.raises(ValueError):verify_unbound_source(nondispatch_context("never_enabled"))


def test_unbound_preparation_classification_reuses_the_already_verified_contents():
    args=runtime_notification_context(route="reset");conn=ContentPredicateConnection()
    with mock.patch.object(reader,"_verify_source_packages",wraps=reader._verify_source_packages) as packages:
        result=verify_unbound_source(args,conn)
    assert len(result.context.context.notifications.preparation_facts.contents)==2
    assert packages.call_count==1 and not conn.queries


@pytest.mark.parametrize("phase",["accepted","validating"])
def test_approved_source_keeps_old_abandoned_verify_only_with_permanent_preparation_reset(phase):
    args=runtime_notification_context(route="reset");add_abandoned_verification(args,phase)
    conn=ContentPredicateConnection(error=AssertionError("approved must not query SQL predicate"))
    assert verify_unbound_source(args,conn).kind=="approved" and not conn.queries


def test_approved_source_failed_label_does_not_replace_preparation_failure_evidence():
    args=runtime_notification_context(route="approved",uncommitted="claimed")
    op=args[0]["relations"]["public.extension_runtime_operation"][0];op["failure_code"]="unknown_failure"
    with pytest.raises(ValueError):verify_unbound_source(args)


def test_content_sql_preserves_original_single_tuple_row_support():
    assert verify_unbound_source(source_history_context("active"),ContentPredicateConnection((True,))).kind=="content"


@pytest.mark.parametrize("family",["extension_runtime_binding","extension_runtime_configuration","extension_runtime_uninstall_receipt","extension_runtime_dependency_ref"])
def test_unbound_sources_reject_bound_state_even_with_an_approved_history(family):
    args=source_history_context("approved");name="public."+family;row=row_for(reader._RELATIONS[name])
    row.update(org_id=args[1].org_id,project_id=args[1].project_id);args[0]["relations"][name].append(row)
    with pytest.raises(ValueError):verify_unbound_source(args)


def test_content_sql_does_not_run_when_the_shared_validation_budget_is_exhausted():
    conn=ContentPredicateConnection();ledger=reader._WorkLedger();ledger.work_bytes=reader._MAX_WORK_BYTES
    with pytest.raises(ValueError):reader._read_legacy_content(conn,source_history_context("active")[-1],ledger)
    assert not conn.queries


def cutover_event_packet():
    packet=empty_packet();packet["schema"]="aos.reinstall-terminal-source-facts/v13"
    packet["relations"]["public.extension_dispatch_cutover_event"]=[dict(org_id="org-org",project_id="dev-project",
        cutover_operation_id=str(UUID(int=4000)),sequence=1,event_id=str(UUID(int=4001)),event_type="CUTOVER_PREPARED",
        payload={"cutoverOperationId":str(UUID(int=4000)),"phase":"prepare"},payload_hash="sha256:"+"a"*64,
        occurred_at="2026-10-26T00:00:00+08:00")]
    return packet


@pytest.mark.parametrize("event_type",["CUTOVER_PREPARED","CUTOVER_CLAIMS_PAUSED","CUTOVER_VALIDATED","CUTOVER_RESUMED"])
def test_v4_carries_the_actual_cutover_event_fields_for_later_parent_verification(event_type):
    packet=cutover_event_packet();packet["relations"]["public.extension_dispatch_cutover_event"][0]["event_type"]=event_type
    row=decode(packet).relations["public.extension_dispatch_cutover_event"][0]
    assert row["event_type"]==event_type and type(row["event_id"]) is UUID and row["sequence"]==1


def test_v3_wire_is_not_silently_accepted_without_cutover_events():
    packet=empty_packet();packet["schema"]="aos.reinstall-terminal-source-facts/v3"
    packet["relations"].pop("public.extension_dispatch_cutover_event",None)
    with pytest.raises(ValueError):decode(packet)


def test_v4_cutover_events_keep_the_full_tenant_operation_sequence_primary_key():
    packet=cutover_event_packet();rows=packet["relations"]["public.extension_dispatch_cutover_event"]
    second=deepcopy(rows[0]);second["cutover_operation_id"]=str(UUID(int=4010));second["event_id"]=str(UUID(int=4011));rows.append(second)
    assert len(decode(packet).relations["public.extension_dispatch_cutover_event"])==2
    rows.append(deepcopy(rows[0]))
    with pytest.raises(ValueError):decode(packet)


@pytest.mark.parametrize("field,value",[("sequence",True),("sequence",2**63),("cutover_operation_id","INVALID"),
    ("event_id",None),("event_type",False),("payload",None),("payload_hash",7),("occurred_at","2026-10-26T00:00:00")])
def test_v4_cutover_event_scalars_follow_original_ddl_types(field,value):
    packet=cutover_event_packet();packet["relations"]["public.extension_dispatch_cutover_event"][0][field]=value
    with pytest.raises(ValueError):decode(packet)


def test_v4_literal_preserves_every_prior_column_key_and_cap_without_rewriting_v3():
    import hashlib
    root=Path(__file__).resolve().parents[4]/".evidence/qyh-m2-terminal-source-implementation-20261025"
    old_path=root/"reader-v3-schema-literal-r47.json";old=json.loads(old_path.read_text())
    new=json.loads((root/"reader-v4-schema-literal-r113.json").read_text())
    assert new["priorLiteralSHA256"]==hashlib.sha256(old_path.read_bytes()).hexdigest()
    assert new["relations"][:-1]==old["relations"] and new["registry"]==old["registry"]
    assert new["relations"][-1]["rank"]==173 and len(new["relations"][-1]["columns"])==9


def test_v4_packet_requires_cutover_event_family_even_when_it_is_empty():
    packet=empty_packet();packet["relations"].pop("public.extension_dispatch_cutover_event")
    with pytest.raises(ValueError):decode(packet)


def test_v5_carries_the_original_independent_cutover_approval_refresh_table():
    assert reader._SCHEMA_VERSION=='aos.reinstall-terminal-source-facts/v13'
    assert 'public.extension_dispatch_cutover_approval_refresh_receipt' in reader._RELATIONS
    assert 'public.extension_dispatch_cutover_approval_refresh_receipt' in reader._NONDISPATCH_EMPTY


def test_old_v4_or_missing_approval_family_cannot_claim_complete_source_input():
    packet=empty_packet();packet['schema']='aos.reinstall-terminal-source-facts/v4'
    packet['relations'].pop('public.extension_dispatch_cutover_approval_refresh_receipt')
    with pytest.raises(ValueError):decode(packet)
    packet['schema']='aos.reinstall-terminal-source-facts/v13'
    with pytest.raises(ValueError):decode(packet)


def test_v5_literal_preserves_all_v4_columns_and_adds_only_the_original_approval_refresh_family():
    import hashlib
    root=Path(__file__).resolve().parents[4]/'.evidence/qyh-m2-terminal-source-implementation-20261025'
    prior=root/'reader-v4-schema-literal-r113.json';old=json.loads(prior.read_text());new=json.loads((root/'reader-v5-schema-literal-r146.json').read_text())
    assert new['priorLiteralSHA256']==hashlib.sha256(prior.read_bytes()).hexdigest()
    assert new['relations'][:-1]==old['relations'] and new['registry']==old['registry']
    assert new['relations'][-1]['rank']==174 and len(new['relations'][-1]['columns'])==13
    assert reader._RELATIONS['public.extension_dispatch_cutover_approval_refresh_receipt'].columns==tuple(tuple(x) for x in new['relations'][-1]['columns'])


def add_preparation_renewal(args,kind="runtime_lease_renewed",payload=None):
    from aos_api.extension_runtime.lifecycle_store import _digest
    packet=args[0];binding=packet["relations"]["public.extension_runtime_binding"][0]
    operation_id=binding["resource_handle_ref"]["preparationOperationId"]
    operation=next(row for row in packet["relations"]["public.extension_runtime_operation"] if row["operation_id"]==operation_id)
    group=sorted([row for row in packet["relations"]["public.extension_runtime_event"] if row["operation_id"]==operation_id],key=lambda row:row["sequence"])
    body=dict(generation=binding["generation"],expiresAt="2026-08-03T01:03:00+00:00")
    if kind=="runtime_lease_rehydrated":body["bindingRevision"]=4
    else:body["healthCheckedAt"]="2026-08-03T01:00:00+00:00"
    if kind=="runtime_inflight_lease_renewed":body.update(executionEpoch=3,attemptId=str(UUID(int=900)))
    if payload is not None:body=deepcopy(payload)
    index=next(i for i,event in enumerate(group) if event["type"] in {"resource_released","resource_uncertain","resource_intent_cancelled"})
    event=deepcopy(group[0]);event.update(event_id=str(UUID(int=7000000+len(group))),type=kind,payload=body,payload_hash=_digest(body))
    group.insert(index,event);packet["relations"]["public.extension_runtime_event"].append(event)
    for sequence,item in enumerate(group,1):item["sequence"]=sequence
    operation["revision"]=len(group)
    outbox=deepcopy(packet["relations"]["public.extension_runtime_outbox"][0]);outbox["event_id"]=event["event_id"]
    packet["relations"]["public.extension_runtime_outbox"].append(outbox)
    for row in packet["relations"]["public.extension_runtime_resource_lease"]:
        if row["operation_id"]==operation_id:row["expires_at"]=body["expiresAt"]
    return event


def test_normal_renewal_is_retained_in_a_never_enabled_terminal_history():
    args=nondispatch_context("never_enabled");add_preparation_renewal(args)
    assert verify_nondispatch_source(args).kind=="never_enabled"


def test_rehydration_is_retained_for_an_original_enabled_ready_binding_version():
    args=nondispatch_context("enabled_undispatched");add_preparation_renewal(args,"runtime_lease_rehydrated")
    assert verify_nondispatch_source(args).kind=="enabled_undispatched"


def test_renewal_uses_the_last_atomic_expiry_without_inventing_monotonicity():
    args=nondispatch_context("never_enabled")
    for expiry in ("2026-08-03T01:10:00+00:00","2026-08-03T01:04:00+00:00"):
        add_preparation_renewal(args,payload=dict(generation=args[0]["relations"]["public.extension_runtime_binding"][0]["generation"],
            expiresAt=expiry,healthCheckedAt="2026-08-03T01:00:00+00:00"))
    assert verify_nondispatch_source(args).kind=="never_enabled"


@pytest.mark.parametrize("fault",["generation","extra","expiry_equal","expiry_naive","health_naive","missing_health",
    "resource_expiry","after_release","unknown_kind","rehydrate_bool","rehydrate_disabled_version","rehydrate_missing_version"])
def test_renewal_event_is_not_a_blanket_checkpoint_exemption(fault):
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=nondispatch_context("enabled_undispatched")
    rehydrate=fault.startswith("rehydrate_")
    event=add_preparation_renewal(args,"runtime_lease_rehydrated" if rehydrate else "runtime_lease_renewed")
    body=event["payload"]
    if fault=="generation":body["generation"]=str(UUID(int=9999))
    elif fault=="extra":body["extra"]=1
    elif fault=="expiry_equal":body["expiresAt"]=body["healthCheckedAt"]
    elif fault=="expiry_naive":body["expiresAt"]="2026-08-03T01:03:00"
    elif fault=="health_naive":body["healthCheckedAt"]="2026-08-03T01:00:00"
    elif fault=="missing_health":body.pop("healthCheckedAt")
    elif fault=="resource_expiry":args[0]["relations"]["public.extension_runtime_resource_lease"][0]["expires_at"]="2026-08-03T01:01:00+00:00"
    elif fault=="unknown_kind":event["type"]="unclassified_renewal"
    elif fault=="rehydrate_bool":body["bindingRevision"]=True
    elif fault=="rehydrate_disabled_version":body["bindingRevision"]=3
    elif fault=="rehydrate_missing_version":body["bindingRevision"]=900
    elif fault=="after_release":
        group=sorted([row for row in args[0]["relations"]["public.extension_runtime_event"] if row["operation_id"]==event["operation_id"]],key=lambda row:row["sequence"])
        group.remove(event);group.append(event)
        for sequence,row in enumerate(group,1):row["sequence"]=sequence
    event["payload_hash"]=_digest(body)
    with pytest.raises(ValueError):verify_nondispatch_source(args)


def verify_preparation_terminals_with_timeline(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    timeline=reader._control_timeline(decode(packet,ledger),scope=scope,source=source,
        locked_source=locked,source_lock=lock,ledger=ledger)
    prepared=timeline.history.graph.receipt.context.notifications.preparation_facts
    reader._preparation_terminal_history(prepared,ledger,timeline=timeline)
    return timeline


def inflight_renewal_context():
    args=nondispatch_context("enabled_undispatched");other=attempt_dependency_context(kind="recoverable_store")
    for family in ("public.extension_runtime_execution_attempt","public.extension_runtime_execution_attempt_event"):
        args[0]["relations"][family]=deepcopy(other[0]["relations"][family])
    args[0]["relations"]["public.extension_runtime_execution_attempt"][0]["execution_epoch"]=3
    add_preparation_renewal(args,"runtime_inflight_lease_renewed")
    return args


def test_inflight_renewal_requires_original_recoverable_store_attempt_and_cannot_enter_nondispatch_branch():
    args=inflight_renewal_context();timeline=verify_preparation_terminals_with_timeline(args)
    assert len(timeline.history.graph.receipt.context.attempts)==1
    with pytest.raises(ValueError):verify_nondispatch_source(args)


@pytest.mark.parametrize("fault",["missing_attempt","signed_read","wrong_attempt","wrong_epoch","bool_epoch"])
def test_inflight_renewal_does_not_invent_a_missing_or_different_business_attempt(fault):
    from aos_api.extension_runtime.lifecycle_store import _digest
    args=inflight_renewal_context();packet=args[0]
    event=next(row for row in packet["relations"]["public.extension_runtime_event"] if row["type"]=="runtime_inflight_lease_renewed")
    if fault=="missing_attempt":
        packet["relations"]["public.extension_runtime_execution_attempt"].clear()
        packet["relations"]["public.extension_runtime_execution_attempt_event"].clear()
    elif fault=="signed_read":packet["relations"]["public.extension_runtime_execution_attempt"][0]["operation_kind"]="signed_read"
    elif fault=="wrong_attempt":event["payload"]["attemptId"]=str(UUID(int=9999))
    elif fault=="wrong_epoch":event["payload"]["executionEpoch"]=2
    elif fault=="bool_epoch":event["payload"]["executionEpoch"]=True
    event["payload_hash"]=_digest(event["payload"])
    with pytest.raises(ValueError):verify_preparation_terminals_with_timeline(args)


def test_a_renewal_cannot_be_ignored_without_a_validated_binding_timeline():
    args=nondispatch_context("never_enabled");add_preparation_renewal(args);timeline=verify_control_timeline(args)
    prepared=timeline.history.graph.receipt.context.notifications.preparation_facts
    with pytest.raises(ValueError):reader._preparation_terminal_history(prepared,reader._WorkLedger())


def detached_lifecycle_context(*,legacy_fence=False,cleanup_before_disable=False,refresh_ref=None):
    import hashlib
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    args=control_history_context();packet,scope,source,locked,lock=args
    replace_successful_controls(args,[("configure",3000,1,2),("enable",3001,3,3),
        ("disable",3002,7 if cleanup_before_disable else 6,5 if cleanup_before_disable else 4)])
    terminal_binding_versions(args,10 if cleanup_before_disable else 9,5 if cleanup_before_disable else 4)
    binding=packet["relations"]["public.extension_runtime_binding"][0]
    receipt=deepcopy(uninstall_receipt_context("detached")[0]["relations"]["public.extension_runtime_uninstall_receipt"][0])
    receipt.update(disable_operation_id=str(UUID(int=3002)),activation_operation_id=str(UUID(int=4000)),binding_revision=binding["revision"])
    authority=json.loads(receipt["authority_data_text"])
    authority.update(bindingFromRevision=binding["revision"]-1,bindingToRevision=binding["revision"],
        disableOperationId=receipt["disable_operation_id"],activationOperationId=receipt["activation_operation_id"],
        cutoverGroupId=str(UUID(int=4002)))
    receipt["authority_data_text"]=json.dumps(authority);receipt["content_hash"]="sha256:"+hashlib.sha256(receipt["authority_data_text"].encode()).hexdigest()
    packet["relations"]["public.extension_runtime_uninstall_receipt"]=[receipt]
    ops=sorted(ECOMMERCE_GROWTH_OPERATIONS);group=str(UUID(int=4002));timestamp="2026-08-03T01:00:00+00:00"
    legacy=[dict(operationId=op,handlerKind="legacy",installationId=None,generation=None,executionEpoch=None,
        operationFence=legacy_fence,revision=1,cutoverGroupId=group,cutoverGroupRevision=1) for op in ops]
    extension=[dict(item,handlerKind="extension",installationId=source.installation_id,generation=binding["generation"],
        executionEpoch=3,operationFence=False,revision=2,cutoverGroupRevision=2) for item in legacy]
    fenced=[dict(item,operationFence=True,revision=3,cutoverGroupRevision=3) for item in extension]
    detached=[dict(item,revision=4,cutoverGroupRevision=4) for item in legacy]
    activation=row_for(reader._RELATIONS["public.extension_dispatch_cutover_operation"])
    activation.update(org_id=scope.org_id,project_id=scope.project_id,cutover_operation_id=receipt["activation_operation_id"],
        kind="activate",status="resumed",cutover_group_id=group,expected_group_revision=1,target_group_revision=2,
        target_installation_id=source.installation_id,target_generation=binding["generation"],target_execution_epoch=3,
        target_runtime_revision=4,operation_ids=ops,old_dispatch_snapshot=legacy,new_dispatch_snapshot=deepcopy(extension),
        request_hash="sha256:"+"b"*64,requested_by="activation-actor",checkpoint={},pending_target_receipt_refs=[],
        policy_ref={},approval_ref={},parent_cutover_operation_id=None,parent_receipt_ref=None,failure_reason=None,
        occurrence_watermark=None,created_at=timestamp,updated_at=timestamp)
    packet["relations"]["public.extension_dispatch_cutover_operation"]=[activation]
    runtime=next(row for row in packet["relations"]["public.extension_runtime_operation"] if row["operation_id"]==receipt["disable_operation_id"])
    digest=canonical_sha256(dict(runtimeOperationId=runtime["operation_id"],runtimeRequestHash=runtime["request_hash"],
        activationOperationId=activation["cutover_operation_id"],activationRequestHash=activation["request_hash"],operationIds=ops))
    lifecycle=dict(org_id=scope.org_id,project_id=scope.project_id,runtime_operation_id=runtime["operation_id"],
        activation_operation_id=activation["cutover_operation_id"],cutover_group_id=group,status="detached",request_hash=digest,
        operation_ids=ops,extension_snapshot=extension,fenced_snapshot=fenced,legacy_snapshot=legacy,fenced_group_revision=3,
        requested_by=runtime["requested_by"],created_at=timestamp,updated_at=timestamp)
    packet["relations"]["public.extension_dispatch_lifecycle_operation"]=[lifecycle]
    for item in detached:
        packet["relations"]["public.extension_operation_dispatch_binding"].append(dict(org_id=scope.org_id,project_id=scope.project_id,
            operation_id=item["operationId"],handler_kind=item["handlerKind"],installation_id=None,generation=None,execution_epoch=None,
            operation_fence=item["operationFence"],revision=item["revision"],cutover_group_id=group,
            cutover_group_revision=item["cutoverGroupRevision"],updated_by=runtime["requested_by"],updated_at=timestamp))
    fence_row=None
    for sequence,phase,snapshot in ((1,"fence",fenced),(2,"detach",detached)):
        body=EcommerceGrowthDisableDependent._authority(scope,runtime,activation,phase=phase,dispatch_snapshot=deepcopy(snapshot),
            request_hash=digest,unknown_attempts=[],fence_receipt=fence_row,configuration_refresh_ref=deepcopy(refresh_ref))
        row=dict(org_id=scope.org_id,project_id=scope.project_id,receipt_id=str(UUID(int=4100+sequence)),
            runtime_operation_id=runtime["operation_id"],phase=phase,request_hash=digest,authority_data=body,
            content_hash=canonical_sha256(body),created_at=timestamp)
        packet["relations"]["public.extension_dispatch_lifecycle_receipt"].append(row)
        event=dict(runtimeOperationId=runtime["operation_id"],phase=phase,receiptId=row["receipt_id"],contentHash=row["content_hash"])
        packet["relations"]["public.extension_dispatch_lifecycle_event"].append(dict(org_id=scope.org_id,project_id=scope.project_id,
            runtime_operation_id=runtime["operation_id"],sequence=sequence,event_type="DISPATCH_DISABLE_FENCED" if sequence==1 else "DISPATCH_DISABLED_DETACHED",
            payload=event,payload_hash=canonical_sha256(event),occurred_at=timestamp))
        if phase=="fence":fence_row=row
    return args


def cutover_prepare_context(registration=None, *, old_revision=1, old_group_revision=1, group_id=None, legacy_fence=None, watermark=None, pending=True, activation_id=4000, idempotency_key=None,registration_ref=None,created_at=None):
    from aos_api.ecommerce_growth_cutover import CutoverPrepareRequest
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=detached_lifecycle_context(legacy_fence=(registration is not None if legacy_fence is None else legacy_fence))
    packet,scope,source,locked,lock=args
    operation=packet['relations']['public.extension_dispatch_cutover_operation'][0]
    operation['cutover_operation_id']=str(UUID(int=activation_id))
    operation['status']='prepared'
    if group_id is not None:operation['cutover_group_id']=group_id
    operation.update(expected_group_revision=old_group_revision,target_group_revision=old_group_revision+1)
    if created_at is not None:operation.update(created_at=created_at,updated_at=created_at)
    for item in operation['old_dispatch_snapshot']:item.update(revision=old_revision,cutoverGroupRevision=old_group_revision,cutoverGroupId=operation['cutover_group_id'])
    for item in operation['new_dispatch_snapshot']:item.update(revision=old_revision+1,cutoverGroupRevision=old_group_revision+1,cutoverGroupId=operation['cutover_group_id'])
    ref=lambda kind,n:dict(resourceType=kind,resourceId=str(UUID(int=n)),revision=1,contentHash='sha256:'+'c'*64)
    key=idempotency_key if idempotency_key is not None else ('activation-prepare' if activation_id==4000 else 'activation-prepare-'+str(activation_id))
    request=CutoverPrepareRequest(cutoverOperationId=operation['cutover_operation_id'],idempotencyKey=key,
        cutoverGroupId=operation['cutover_group_id'],expectedGroupRevision=old_group_revision,targetInstallationId=source.installation_id,
        targetGeneration=operation['target_generation'],targetExecutionEpoch=3,targetRuntimeRevision=4,
        policyRef=ref('ActionPolicy',4200),approvalRef=ref('ActionApprovalEvent',4201),checkpoint={'cursor':'x'},
        occurrenceWatermark=watermark,pendingTargetReceiptRefs=[ref('TargetReceipt',4202)] if pending else [],
        registrationReceiptRef=registration_ref if registration_ref is not None else ref(registration,4203) if registration else None)
    wire=request.model_dump(mode='json',by_alias=True)
    operation.update(idempotency_key=request.idempotency_key,request_hash=request.request_hash(),checkpoint=wire['checkpoint'],
        policy_ref=wire['policyRef'],approval_ref=wire['approvalRef'],pending_target_receipt_refs=wire['pendingTargetReceiptRefs'],
        occurrence_watermark=wire['occurrenceWatermark'])
    body=dict(schemaVersion='aos.ecommerce.dispatch-cutover-prepare/v1',tenant=dict(orgId=scope.org_id,projectId=scope.project_id),
        cutoverOperationId=operation['cutover_operation_id'],status='prepared',cutoverGroupId=operation['cutover_group_id'],
        expectedGroupRevision=old_group_revision,targetGroupRevision=old_group_revision+1,targetInstallationId=source.installation_id,
        targetGeneration=operation['target_generation'],targetExecutionEpoch=3,targetRuntimeRevision=4,
        operationIds=operation['operation_ids'],oldDispatchSnapshot=deepcopy(operation['old_dispatch_snapshot']),
        newDispatchSnapshot=deepcopy(operation['new_dispatch_snapshot']),checkpoint=wire['checkpoint'],
        occurrenceWatermark=wire['occurrenceWatermark'],pendingTargetReceiptRefs=wire['pendingTargetReceiptRefs'],
        policyRef=wire['policyRef'],approvalRef=wire['approvalRef'],requestHash=request.request_hash(),
        requestedBy=operation['requested_by'],createdAt=operation['created_at'])
    if registration:body['registrationReceiptRef']=wire['registrationReceiptRef']
    row=dict(org_id=scope.org_id,project_id=scope.project_id,receipt_id=str(UUID(int=activation_id+204)),
        cutover_operation_id=operation['cutover_operation_id'],phase='prepare',request_hash=request.request_hash(),
        authority_data=body,content_hash=canonical_sha256(body),created_at=operation['created_at'])
    packet['relations']['public.extension_dispatch_cutover_receipt']=[row]
    payload=dict(cutoverOperationId=operation['cutover_operation_id'],cutoverGroupId=operation['cutover_group_id'],
        expectedGroupRevision=old_group_revision,targetGroupRevision=old_group_revision+1,receiptId=row['receipt_id'],contentHash=row['content_hash'])
    packet['relations']['public.extension_dispatch_cutover_event']=[dict(org_id=scope.org_id,project_id=scope.project_id,
        cutover_operation_id=operation['cutover_operation_id'],sequence=1,event_id=str(UUID(int=activation_id+205)),
        event_type='CUTOVER_PREPARED',payload=payload,payload_hash=canonical_sha256(payload),occurred_at=operation['created_at'])]
    return args


def verify_cutover_prepare(args):
    packet,scope,*_=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    return reader._cutover_prepare_receipt(facts,facts.relations['public.extension_dispatch_cutover_operation'][0],
        scope=scope,ledger=ledger)


@pytest.mark.parametrize('registration,old_revision',[(None,1),(None,7),('FirstDispatchRegistrationReceipt',1),
    ('SuccessorDispatchRegistrationReceipt',7)])
@pytest.mark.parametrize('watermark',[None,'2026-08-03T08:00:00+08:00'])
def test_original_cutover_prepare_request_snapshot_receipt_and_first_event(registration,old_revision,watermark):
    result=verify_cutover_prepare(cutover_prepare_context(registration,old_revision=old_revision,watermark=watermark))
    assert result.receipt.status=='prepared' and result.request.request_hash()==result.receipt.request_hash
    assert len(result.old_snapshot)==len(result.new_snapshot)==9
    assert not hasattr(result,'authorized') and not hasattr(result,'kind')


def rehash_cutover_prepare(args):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    relations=args[0]['relations'];row=relations['public.extension_dispatch_cutover_receipt'][0]
    row['content_hash']=canonical_sha256(row['authority_data'])
    event=relations['public.extension_dispatch_cutover_event'][0]
    event['payload']['contentHash']=row['content_hash'];event['payload_hash']=canonical_sha256(event['payload'])


@pytest.mark.parametrize('defect',['missing-receipt','missing-event','schema','body-extra','body-bool','event-extra',
    'event-bool','event-type','event-time','event-receipt','event-hash','receipt-hash','request-hash','receipt-request',
    'parent','actor','body-snapshot-bool','body-ref-extra','old-handler','new-revision','new-epoch','new-fence',
    'snapshot-order','target-group','registration-null','missing-target'])
def test_cutover_prepare_rejects_rehashed_provenance_drift(defect):
    args=cutover_prepare_context();relations=args[0]['relations']
    operation=relations['public.extension_dispatch_cutover_operation'][0]
    row=relations['public.extension_dispatch_cutover_receipt'][0];body=row['authority_data']
    event=relations['public.extension_dispatch_cutover_event'][0]
    if defect=='schema':body['schemaVersion']='unrecognized'
    elif defect=='body-extra':body['eligible']=True
    elif defect=='body-bool':body['expectedGroupRevision']=True
    elif defect=='event-extra':event['payload']['eligible']=True
    elif defect=='event-bool':event['payload']['expectedGroupRevision']=True
    elif defect=='event-type':event['event_type']='CUTOVER_RESUMED'
    elif defect=='event-time':event['occurred_at']='2026-08-03T01:00:01+00:00'
    elif defect=='event-receipt':event['payload']['receiptId']=str(UUID(int=999))
    elif defect=='request-hash':operation['request_hash']='sha256:'+'0'*64;body['requestHash']=operation['request_hash']
    elif defect=='receipt-request':row['request_hash']='sha256:'+'0'*64
    elif defect=='parent':operation['parent_cutover_operation_id']=str(UUID(int=999))
    elif defect=='actor':operation['requested_by']=' activation-actor';body['requestedBy']=operation['requested_by']
    elif defect=='body-snapshot-bool':body['oldDispatchSnapshot'][0]['operationFence']=0
    elif defect=='body-ref-extra':body['policyRef']['extra']=True
    elif defect=='old-handler':operation['old_dispatch_snapshot'][0].update(handlerKind='extension',
        installationId=operation['target_installation_id'],generation=operation['target_generation'],executionEpoch=3)
    elif defect=='new-revision':operation['new_dispatch_snapshot'][0]['revision']=7
    elif defect=='new-epoch':operation['new_dispatch_snapshot'][0]['executionEpoch']=7
    elif defect=='new-fence':operation['new_dispatch_snapshot'][0]['operationFence']=True
    elif defect=='snapshot-order':operation['new_dispatch_snapshot'].reverse()
    elif defect=='target-group':operation['target_group_revision']=7;body['targetGroupRevision']=7
    elif defect=='registration-null':body['registrationReceiptRef']=None
    elif defect=='missing-target':body.pop('targetGeneration')
    if defect in {'old-handler','new-revision','new-epoch','new-fence','snapshot-order'}:
        body['oldDispatchSnapshot']=deepcopy(operation['old_dispatch_snapshot'])
        body['newDispatchSnapshot']=deepcopy(operation['new_dispatch_snapshot'])
    rehash_cutover_prepare(args)
    if defect=='missing-receipt':relations['public.extension_dispatch_cutover_receipt']=[]
    elif defect=='missing-event':relations['public.extension_dispatch_cutover_event']=[]
    elif defect=='receipt-hash':row['content_hash']='sha256:'+'0'*64
    elif defect=='event-hash':event['payload_hash']='sha256:'+'0'*64
    with pytest.raises(ValueError):verify_cutover_prepare(args)


def test_first_registration_prepare_retains_revision_one_constraint():
    with pytest.raises(ValueError):verify_cutover_prepare(cutover_prepare_context('FirstDispatchRegistrationReceipt',old_revision=7))


def cutover_forward_context(count=4, *, pause_busy=False, unknown=False, resume_busy=False, pending=False, same_time=False, registration=None,activation_id=4000,registration_ref=None,created_at=None,old_revision=1,old_group_revision=1,group_id=None,legacy_fence=None,idempotency_key=None):
    from datetime import timedelta
    from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverStore, CutoverCommitRequest, CutoverFinalizeRequest
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=cutover_prepare_context(registration,pending=pending,activation_id=activation_id,registration_ref=registration_ref,created_at=created_at,old_revision=old_revision,old_group_revision=old_group_revision,group_id=group_id,legacy_fence=legacy_fence,idempotency_key=idempotency_key);relations=args[0]['relations'];operation=relations['public.extension_dispatch_cutover_operation'][0]
    prepare=verify_cutover_prepare(args).receipt;scope=args[1]
    refs=lambda kind,r:dict(resourceType=kind,resourceId=str(r.receipt_id),revision=1,contentHash=r.content_hash)
    commit_request=CutoverCommitRequest(cutoverOperationId=prepare.cutover_operation_id,idempotencyKey='commit-once',
        prepareReceiptRef=refs('CutoverPrepareReceipt',prepare))
    commit=None
    for n,phase in enumerate(('pause','commit','validate','resume')[:count],2):
        facts=dict(occurrenceWatermark='2026-08-03T08:00:00+08:00',claimedOccurrences=[],claimedAttempts=[],unknownAttempts=[],runningRuntimeAttempts=[])
        if unknown:
            facts['unknownAttempts']=[dict(attemptId=str(UUID(int=4401)),occurrenceId=str(UUID(int=4402)),
                targetIdempotencyKey='prior-attempt',resolvedAt='2026-08-03T01:00:00+00:00')]
        if (phase=='pause' and pause_busy) or (phase=='resume' and resume_busy):
            facts['claimedOccurrences']=[dict(occurrenceId=str(UUID(int=4402)),claimOwner='worker',claimUntil='2026-08-03T01:00:30+00:00')]
            facts['claimedAttempts']=[dict(attemptId=str(UUID(int=4403)),occurrenceId=str(UUID(int=4402)),targetIdempotencyKey='claimed',
                claimOwner='worker',claimUntil='2026-08-03T01:00:30+00:00')]
            facts['runningRuntimeAttempts']=[dict(attemptId=str(UUID(int=4404)),operationKey='run',idempotencyKey='running',
                acceptedAt='2026-08-03T01:00:00+00:00',leaseUntil='2026-08-03T01:00:30+00:00')]
        created=datetime.fromisoformat(operation['created_at'])+timedelta(seconds=0 if same_time else n)
        if phase in {'pause','commit'}:
            request=commit_request
            body=EcommerceGrowthCutoverStore._phase_authority(scope,request,prepare,phase=phase,
                status='draining' if phase=='pause' else 'committed',dispatch_snapshot=list(prepare.old_dispatch_snapshot if phase=='pause' else prepare.new_dispatch_snapshot),
                facts=facts,actor='phase-actor',created_at=created)
        else:
            request=CutoverFinalizeRequest(cutoverOperationId=prepare.cutover_operation_id,idempotencyKey='finalize-'+phase,
                commitReceiptRef=refs('CutoverCommitReceipt',commit))
            body=EcommerceGrowthCutoverStore._finalize_authority(scope,request,prepare,phase=phase,
                status='validated' if phase=='validate' else 'resumed',runtime_revision=4+(1 if phase=='validate' else 2),
                claim_paused=phase!='resume',facts=facts,actor='finalize-actor',created_at=created)
        body=deepcopy(body)
        row=dict(org_id=scope.org_id,project_id=scope.project_id,receipt_id=str(UUID(int=activation_id+300+n)),
            cutover_operation_id=operation['cutover_operation_id'],phase=phase,request_hash=request.request_hash(),
            authority_data=body,content_hash=canonical_sha256(body),created_at=created.isoformat())
        event_body=dict(cutoverOperationId=operation['cutover_operation_id'],phase=phase,receiptId=row['receipt_id'],contentHash=row['content_hash'])
        event=dict(org_id=scope.org_id,project_id=scope.project_id,cutover_operation_id=operation['cutover_operation_id'],sequence=n,
            event_id=str(UUID(int=activation_id+350+n)),event_type={'pause':'CUTOVER_CLAIMS_PAUSED','commit':'CUTOVER_COMMITTED','validate':'CUTOVER_VALIDATED','resume':'CUTOVER_RESUMED'}[phase],
            payload=event_body,payload_hash=canonical_sha256(event_body),occurred_at=created.isoformat())
        relations['public.extension_dispatch_cutover_receipt'].append(row);relations['public.extension_dispatch_cutover_event'].append(event)
        if phase=='commit':
            # Fixture uses the original immutable row to build the subsequent exact reference.
            class Commit:pass
            commit=Commit();commit.receipt_id=UUID(row['receipt_id']);commit.content_hash=row['content_hash']
    operation['status']=('prepared','draining','committed','validated','resumed')[count]
    return args


def verify_cutover_forward(args):
    packet,scope,*_=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    return reader._cutover_forward_receipts(facts,facts.relations['public.extension_dispatch_cutover_operation'][0],scope=scope,ledger=ledger)


@pytest.mark.parametrize('count',range(5))
@pytest.mark.parametrize('unknown',[False,True])
def test_cutover_forward_preserves_every_prefix_and_original_unknown_facts(count,unknown):
    graph=verify_cutover_forward(cutover_forward_context(count,pause_busy=True,unknown=unknown,resume_busy=True))
    assert tuple(graph.receipts)==('pause','commit','validate','resume')[:count]
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind')
    if count==4:
        assert graph.receipts['validate'].request_hash!=graph.receipts['resume'].request_hash
        assert len(graph.receipts['resume'].running_runtime_attempts)==1


def rehash_forward_row(args,phase):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    relations=args[0]['relations'];row=next(r for r in relations['public.extension_dispatch_cutover_receipt'] if r['phase']==phase)
    row['content_hash']=canonical_sha256(row['authority_data'])
    event=next(e for e in relations['public.extension_dispatch_cutover_event'] if e['payload'].get('phase')==phase)
    event['payload']['contentHash']=row['content_hash'];event['payload_hash']=canonical_sha256(event['payload'])


def test_cutover_pause_can_retain_pending_targets_but_commit_cannot():
    graph=verify_cutover_forward(cutover_forward_context(1,pending=True))
    assert len(graph.receipts['pause'].pending_target_receipt_refs)==1
    with pytest.raises(ValueError):verify_cutover_forward(cutover_forward_context(2,pending=True))


def test_cutover_forward_allows_equal_permanent_phase_timestamps():
    graph=verify_cutover_forward(cutover_forward_context(same_time=True))
    assert graph.receipts['resume'].created_at==graph.prepared.receipt.created_at


@pytest.mark.parametrize('field,key,value',[
    ('unknownAttempts','resolvedAt','2026-08-03 01:00:00+00:00'),
    ('claimedOccurrences','claimUntil','2026-08-03T01:00:30Z'),
    ('claimedAttempts','claimUntil','2026-08-03T01:00:30.1+00:00'),
    ('runningRuntimeAttempts','acceptedAt','2026-08-03 01:00:00+00:00'),
    ('runningRuntimeAttempts','leaseUntil','2026-08-03T01:00:30Z'),
    (None,'occurrenceWatermark','2026-08-03T00:00:00Z')])
def test_cutover_forward_permanent_snapshot_times_use_original_producer_isoformat(field,key,value):
    args=cutover_forward_context(1,pause_busy=True,unknown=True)
    body=args[0]['relations']['public.extension_dispatch_cutover_receipt'][-1]['authority_data']
    if field is None:body[key]=value
    else:body[field][0][key]=value
    rehash_forward_row(args,'pause')
    with pytest.raises(ValueError):verify_cutover_forward(args)


@pytest.mark.parametrize('phase',['pause','commit','validate','resume'])
@pytest.mark.parametrize('defect',['schema','extra','actor','claim-bool','snapshot-bool','parent','event-type','event-time','event-extra','request-hash'])
def test_cutover_forward_rejects_rehashed_phase_and_parent_drift(phase,defect):
    from aos_api.ecommerce_growth_cutover import CutoverCommitRequest,CutoverFinalizeRequest
    args=cutover_forward_context();relations=args[0]['relations']
    row=next(r for r in relations['public.extension_dispatch_cutover_receipt'] if r['phase']==phase);body=row['authority_data']
    event=next(e for e in relations['public.extension_dispatch_cutover_event'] if e['payload'].get('phase')==phase)
    if defect=='schema':body['schemaVersion']='wrong'
    elif defect=='extra':body['eligible']=True
    elif defect=='actor':body['requestedBy']=' bad '
    elif defect=='claim-bool':body['claimPaused']=0 if phase=='resume' else 1
    elif defect=='snapshot-bool':body['dispatchSnapshot'][0]['operationFence']=0
    elif defect=='parent':
        key='prepareReceiptRef' if phase in {'pause','commit'} else 'commitReceiptRef'
        body[key]['resourceId']=str(UUID(int=999))
        request=(CutoverCommitRequest(cutoverOperationId=body['cutoverOperationId'],idempotencyKey=body['commitIdempotencyKey'],prepareReceiptRef=body[key])
            if phase in {'pause','commit'} else CutoverFinalizeRequest(cutoverOperationId=body['cutoverOperationId'],idempotencyKey=body['finalizeIdempotencyKey'],commitReceiptRef=body[key]))
        body['requestHash']=row['request_hash']=request.request_hash()
    elif defect=='event-type':event['event_type']='CUTOVER_FENCED'
    elif defect=='event-time':event['occurred_at']='2026-08-03T00:59:59+00:00'
    elif defect=='event-extra':event['payload']['eligible']=True
    elif defect=='request-hash':body['requestHash']=row['request_hash']='sha256:'+'0'*64
    rehash_forward_row(args,phase)
    with pytest.raises(ValueError):verify_cutover_forward(args)


@pytest.mark.parametrize('phase',['pause','commit','validate'])
@pytest.mark.parametrize('family',['receipt','event'])
def test_cutover_forward_rejects_missing_prefix_members(phase,family):
    args=cutover_forward_context();name='public.extension_dispatch_cutover_'+family
    args[0]['relations'][name]=[r for r in args[0]['relations'][name] if (r.get('phase') if family=='receipt' else r['payload'].get('phase'))!=phase]
    with pytest.raises(ValueError):verify_cutover_forward(args)


@pytest.mark.parametrize('phase',['commit','validate'])
@pytest.mark.parametrize('field',['claimedOccurrences','claimedAttempts','runningRuntimeAttempts'])
def test_cutover_forward_retains_original_commit_validate_drained_requirement(phase,field):
    args=cutover_forward_context(pause_busy=True);rows=args[0]['relations']['public.extension_dispatch_cutover_receipt']
    pause=next(r for r in rows if r['phase']=='pause');row=next(r for r in rows if r['phase']==phase)
    row['authority_data'][field]=deepcopy(pause['authority_data'][field]);rehash_forward_row(args,phase)
    with pytest.raises(ValueError):verify_cutover_forward(args)


@pytest.mark.parametrize('defect',['unknown-extra','unknown-naive','unknown-duplicate','unknown-order','unknown-key-type','target-bool','target-gap'])
def test_cutover_forward_rejects_invalid_permanent_execution_fact_shapes(defect):
    args=cutover_forward_context(unknown=True);row=args[0]['relations']['public.extension_dispatch_cutover_receipt'][-1];body=row['authority_data'];item=body['unknownAttempts'][0]
    if defect=='unknown-extra':item['extra']=True
    elif defect=='unknown-naive':item['resolvedAt']='2026-08-03T01:00:00'
    elif defect=='unknown-duplicate':body['unknownAttempts'].append(deepcopy(item))
    elif defect=='unknown-order':body['unknownAttempts'].append(dict(item,attemptId=str(UUID(int=1))))
    elif defect=='unknown-key-type':item['targetIdempotencyKey']=7
    elif defect=='target-bool':body['targetRuntimeRevision']=True
    elif defect=='target-gap':body['targetRuntimeRevision']=99
    rehash_forward_row(args,'resume')
    with pytest.raises(ValueError):verify_cutover_forward(args)


def cutover_approval_context(*,count=4,offset=3.5,registration=None):
    from datetime import timedelta
    from aos_api.ecommerce_growth_cutover import CutoverApprovalRefreshRequest
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=cutover_forward_context(count,registration=registration);relations=args[0]['relations'];operation=relations['public.extension_dispatch_cutover_operation'][0]
    prepare=verify_cutover_prepare(args).receipt;scope=args[1]
    parent=dict(resourceType='CutoverPrepareReceipt',resourceId=str(prepare.receipt_id),revision=1,contentHash=prepare.content_hash)
    old=prepare.approval_ref.model_dump(mode='json',by_alias=True)
    new=dict(old,resourceId=str(UUID(int=4500)),revision=2)
    request=CutoverApprovalRefreshRequest(cutoverOperationId=prepare.cutover_operation_id,idempotencyKey='refresh-approval',prepareReceiptRef=parent,approvalRef=new)
    created=datetime.fromisoformat(operation['created_at'])+timedelta(seconds=offset)
    body=dict(schemaVersion='aos.ecommerce.dispatch-cutover-approval-refresh/v1',tenant=dict(orgId=scope.org_id,projectId=scope.project_id),
        receiptId=str(UUID(int=4501)),cutoverOperationId=operation['cutover_operation_id'],status='approval_refreshed',
        prepareReceiptRef=parent,oldApprovalRef=old,newApprovalRef=new,requestHash=request.request_hash(),refreshedBy='refresh-actor',createdAt=created.isoformat())
    row=dict(org_id=scope.org_id,project_id=scope.project_id,receipt_id=body['receiptId'],cutover_operation_id=operation['cutover_operation_id'],
        idempotency_key=request.idempotency_key,request_hash=request.request_hash(),prepare_receipt_ref=deepcopy(parent),
        old_approval_ref=deepcopy(old),new_approval_ref=deepcopy(new),authority_data=body,content_hash=canonical_sha256(body),
        refreshed_by='refresh-actor',created_at=created.isoformat())
    relations['public.extension_dispatch_cutover_approval_refresh_receipt']=[row]
    return args


@pytest.mark.parametrize('count,offset',[(0,0.5),(1,2.5),(2,3.5),(3,4.5),(4,4.5)])
def test_cutover_forward_retains_original_independent_approval_refresh_without_an_invented_event(count,offset):
    args=cutover_approval_context(count=count,offset=offset);graph=verify_cutover_forward(args)
    assert graph.approval_refresh.new_approval_ref.revision==2
    assert graph.approval_refresh.old_approval_ref==graph.prepared.receipt.approval_ref
    assert len(args[0]['relations']['public.extension_dispatch_cutover_event'])==count+1


def test_cutover_forward_no_approval_refresh_retains_original_prepare_authority():
    graph=verify_cutover_forward(cutover_forward_context())
    assert graph.approval_refresh is None


@pytest.mark.parametrize('defect',['body-request-hash','schema','extra','old-ref','same-ref','parent-id','parent-hash',
    'parent-revision','parent-bool','new-type','new-extra','actor','early','after-resume','duplicate','row-scope','row-request-hash','hash'])
def test_cutover_approval_rejects_rehashed_parent_and_request_drift(defect):
    from aos_api.ecommerce_growth_cutover import CutoverApprovalRefreshRequest
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=cutover_approval_context();relations=args[0]['relations'];row=relations['public.extension_dispatch_cutover_approval_refresh_receipt'][0];body=row['authority_data']
    if defect=='body-request-hash':body['requestHash']='sha256:'+'0'*64
    elif defect=='schema':body['schemaVersion']='wrong'
    elif defect=='extra':body['eligible']=True
    elif defect=='old-ref':body['oldApprovalRef']['resourceId']=str(UUID(int=999));row['old_approval_ref']=deepcopy(body['oldApprovalRef'])
    elif defect=='same-ref':body['newApprovalRef']=deepcopy(body['oldApprovalRef']);row['new_approval_ref']=deepcopy(body['newApprovalRef'])
    elif defect=='parent-id':body['prepareReceiptRef']['resourceId']=str(UUID(int=999));row['prepare_receipt_ref']=deepcopy(body['prepareReceiptRef'])
    elif defect=='parent-hash':body['prepareReceiptRef']['contentHash']='sha256:'+'0'*64;row['prepare_receipt_ref']=deepcopy(body['prepareReceiptRef'])
    elif defect=='parent-revision':body['prepareReceiptRef']['revision']=2;row['prepare_receipt_ref']=deepcopy(body['prepareReceiptRef'])
    elif defect=='parent-bool':body['prepareReceiptRef']['revision']=True;row['prepare_receipt_ref']=deepcopy(body['prepareReceiptRef'])
    elif defect=='new-type':body['newApprovalRef']['resourceType']='NotApproval';row['new_approval_ref']=deepcopy(body['newApprovalRef'])
    elif defect=='new-extra':body['newApprovalRef']['extra']=True;row['new_approval_ref']=deepcopy(body['newApprovalRef'])
    elif defect=='actor':body['refreshedBy']=row['refreshed_by']=' bad '
    elif defect=='early':body['createdAt']=row['created_at']='2026-08-03T00:59:59+00:00'
    elif defect=='after-resume':body['createdAt']=row['created_at']='2026-08-03T01:00:06+00:00'
    elif defect=='row-scope':row['org_id']='dev-org'
    if defect in {'same-ref','parent-id','parent-hash','parent-revision'}:
        request=CutoverApprovalRefreshRequest(cutoverOperationId=body['cutoverOperationId'],idempotencyKey=row['idempotency_key'],prepareReceiptRef=body['prepareReceiptRef'],approvalRef=body['newApprovalRef'])
        body['requestHash']=row['request_hash']=request.request_hash()
    row['content_hash']=canonical_sha256(body)
    if defect=='duplicate':relations['public.extension_dispatch_cutover_approval_refresh_receipt'].append(dict(deepcopy(row),receipt_id=str(UUID(int=4502))))
    elif defect=='row-request-hash':row['request_hash']='sha256:'+'0'*64
    elif defect=='hash':row['content_hash']='sha256:'+'0'*64
    with pytest.raises(ValueError):verify_cutover_forward(args)


def cutover_rollback_context(*,parent_count=3,complete=True,registration=None,refresh=False,unknown=True):
    from datetime import timedelta
    from aos_api.ecommerce_growth_cutover import CutoverRollbackRequest,CutoverExactRef,EcommerceGrowthCutoverStore
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=(cutover_approval_context(count=parent_count,offset=parent_count+1.5,registration=registration) if refresh
        else cutover_forward_context(parent_count,registration=registration))
    relations=args[0]['relations'];parent=relations['public.extension_dispatch_cutover_operation'][0]
    parent.update(status='validated' if parent_count==3 else 'committed',updated_at=relations['public.extension_dispatch_cutover_receipt'][-1]['created_at'])
    parent_graph=verify_cutover_forward(args);prepare=parent_graph.prepared.receipt;commit=parent_graph.receipts['commit'];scope=args[1]
    commit_ref=dict(resourceType='CutoverCommitReceipt',resourceId=str(commit.receipt_id),revision=1,contentHash=commit.content_hash)
    approval=dict(resourceType='ActionApprovalEvent',resourceId=str(UUID(int=4601)),revision=1,contentHash='sha256:'+'e'*64)
    request=CutoverRollbackRequest(rollbackOperationId=UUID(int=4600),activationOperationId=prepare.cutover_operation_id,
        idempotencyKey='rollback-once',commitReceiptRef=commit_ref,approvalRef=approval,failureReason='validation_failed')
    created=datetime.fromisoformat(parent['created_at'])+timedelta(seconds=10)
    fenced=[dict(item,operationFence=True,revision=item['revision']+1,cutoverGroupRevision=item['cutoverGroupRevision']+1) for item in parent['new_dispatch_snapshot']]
    restored=[dict(item,revision=item['revision']+3,cutoverGroupRevision=item['cutoverGroupRevision']+3) for item in parent['old_dispatch_snapshot']]
    rollback=dict(deepcopy(parent),cutover_operation_id=str(request.rollback_operation_id),kind='rollback',idempotency_key=request.idempotency_key,
        request_hash=request.request_hash(),status='rolled_back' if complete else 'draining',expected_group_revision=parent['target_group_revision'],
        target_group_revision=parent['target_group_revision']+1,old_dispatch_snapshot=deepcopy(parent['new_dispatch_snapshot']),
        new_dispatch_snapshot=deepcopy(fenced),parent_cutover_operation_id=parent['cutover_operation_id'],parent_receipt_ref=deepcopy(commit_ref),
        failure_reason=request.failure_reason,approval_ref=deepcopy(approval),pending_target_receipt_refs=[],created_at=created.isoformat(),
        updated_at=(created+timedelta(seconds=0.5) if complete else created).isoformat())
    relations['public.extension_dispatch_cutover_operation'].append(rollback)
    drain=None
    for sequence,phase in enumerate(('fence','drain','rollback') if complete else ('fence',),1):
        facts=dict(occurrenceWatermark=None,claimedOccurrences=[],claimedAttempts=[],unknownAttempts=[],runningRuntimeAttempts=[])
        if unknown:facts['unknownAttempts']=[dict(attemptId=str(UUID(int=4602)),occurrenceId=str(UUID(int=4603)),targetIdempotencyKey='unknown-kept',resolvedAt=created.isoformat())]
        if phase=='fence':facts['claimedOccurrences']=[dict(occurrenceId=str(UUID(int=4603)),claimOwner='worker',claimUntil=(created+timedelta(seconds=30)).isoformat())]
        at=created if phase=='fence' else created+timedelta(seconds=1)
        body=EcommerceGrowthCutoverStore._rollback_authority(scope,request,prepare,phase=phase,status='rolled_back' if phase=='rollback' else 'draining',
            dispatch_snapshot=deepcopy(restored if phase=='rollback' else fenced),facts=facts,actor=rollback['requested_by'],created_at=at,drain_receipt_ref=drain if phase=='rollback' else None)
        row=dict(org_id=scope.org_id,project_id=scope.project_id,receipt_id=str(UUID(int=4610+sequence)),cutover_operation_id=rollback['cutover_operation_id'],
            phase=phase,request_hash=request.request_hash(),authority_data=deepcopy(body),content_hash=canonical_sha256(body),created_at=at.isoformat())
        payload=dict(cutoverOperationId=rollback['cutover_operation_id'],phase=phase,receiptId=row['receipt_id'],contentHash=row['content_hash'])
        event=dict(org_id=scope.org_id,project_id=scope.project_id,cutover_operation_id=rollback['cutover_operation_id'],sequence=sequence,event_id=str(UUID(int=4620+sequence)),
            event_type={'fence':'CUTOVER_FENCED','drain':'CUTOVER_DRAINED','rollback':'CUTOVER_ROLLED_BACK'}[phase],payload=payload,payload_hash=canonical_sha256(payload),occurred_at=at.isoformat())
        relations['public.extension_dispatch_cutover_receipt'].append(row);relations['public.extension_dispatch_cutover_event'].append(event)
        if phase=='drain':drain=CutoverExactRef(resourceType='CutoverDrainReceipt',resourceId=row['receipt_id'],revision=1,contentHash=row['content_hash'])
    return args


def verify_cutover_rollback(args):
    packet,scope,*_=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    return reader._cutover_rollback_receipts(facts,facts.relations['public.extension_dispatch_cutover_operation'][1],scope=scope,ledger=ledger)


@pytest.mark.parametrize('parent_count',[2,3])
@pytest.mark.parametrize('complete',[False,True])
@pytest.mark.parametrize('registration',[None,'FirstDispatchRegistrationReceipt'])
@pytest.mark.parametrize('refresh',[False,True])
def test_original_independent_rollback_receipts_keep_parent_runtime_and_legacy_fence(parent_count,complete,registration,refresh):
    args=cutover_rollback_context(parent_count=parent_count,complete=complete,registration=registration,refresh=refresh)
    graph=verify_cutover_rollback(args)
    assert tuple(graph.receipts)==(('fence','drain','rollback') if complete else ('fence',))
    assert len(graph.receipts['fence'].claimed_occurrences)==1 and len(graph.receipts['fence'].unknown_attempts)==1
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind')
    if complete:
        assert graph.receipts['rollback'].dispatch_snapshot[0]['operationFence'] is (registration is not None)
        assert graph.receipts['rollback'].unknown_attempts==graph.receipts['drain'].unknown_attempts


def rehash_rollback_phase(args,phase):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    relations=args[0]['relations'];identity=str(UUID(int=4600))
    row=next(r for r in relations['public.extension_dispatch_cutover_receipt'] if r['cutover_operation_id']==identity and r['phase']==phase)
    row['content_hash']=canonical_sha256(row['authority_data'])
    event=next(e for e in relations['public.extension_dispatch_cutover_event'] if e['cutover_operation_id']==identity and e['payload']['phase']==phase)
    event['payload']['contentHash']=row['content_hash'];event['payload_hash']=canonical_sha256(event['payload'])


@pytest.mark.parametrize('defect',['parent-id','parent-resumed','parent-status','parent-ref','target-generation','target-epoch','target-runtime','group',
    'old-snapshot','fenced-snapshot','fenced-bool','checkpoint','policy','pending','request-hash','actor','failure-reason','drain-missing','rollback-missing',
    'extra-phase','status','schema','body-extra','body-request','restore-revision','restore-fence','drain-ref','drain-ref-bool','event-type','event-extra','event-time',
    'fence-time','drain-time','drain-facts','drain-claimed','scope'])
def test_cutover_rollback_rejects_rehashed_parent_snapshot_phase_and_atomicity_drift(defect):
    args=cutover_rollback_context(refresh=True);relations=args[0]['relations'];parent,op=relations['public.extension_dispatch_cutover_operation']
    rows=[r for r in relations['public.extension_dispatch_cutover_receipt'] if r['cutover_operation_id']==op['cutover_operation_id']]
    fence,drain,final=rows;body=final['authority_data'];event=relations['public.extension_dispatch_cutover_event'][-1]
    if defect=='parent-id':op['parent_cutover_operation_id']=str(UUID(int=999))
    elif defect=='parent-resumed':parent['status']='resumed'
    elif defect=='parent-status':parent['status']='committed'
    elif defect=='parent-ref':op['parent_receipt_ref']['resourceId']=str(UUID(int=999))
    elif defect=='target-generation':op['target_generation']=str(UUID(int=999))
    elif defect=='target-epoch':op['target_execution_epoch']+=1
    elif defect=='target-runtime':op['target_runtime_revision']+=1
    elif defect=='group':op['cutover_group_id']=str(UUID(int=999))
    elif defect=='old-snapshot':op['old_dispatch_snapshot'][0]['revision']+=1
    elif defect=='fenced-snapshot':op['new_dispatch_snapshot'][0]['revision']+=1
    elif defect=='fenced-bool':op['new_dispatch_snapshot'][0]['operationFence']=1
    elif defect=='checkpoint':op['checkpoint']={'different':True}
    elif defect=='policy':op['policy_ref']['resourceId']=str(UUID(int=999))
    elif defect=='pending':op['pending_target_receipt_refs']=[{}]
    elif defect=='request-hash':op['request_hash']='sha256:'+'0'*64
    elif defect=='actor':op['requested_by']=' bad '
    elif defect=='failure-reason':op['failure_reason']='other_reason'
    elif defect=='extra-phase':final['phase']='prepare'
    elif defect=='status':op['status']='draining'
    elif defect=='schema':body['schemaVersion']='wrong'
    elif defect=='body-extra':body['eligible']=True
    elif defect=='body-request':body['requestHash']='sha256:'+'0'*64
    elif defect=='restore-revision':body['dispatchSnapshot'][0]['revision']+=1
    elif defect=='restore-fence':body['dispatchSnapshot'][0]['operationFence']=True
    elif defect=='drain-ref':body['drainReceiptRef']['resourceId']=str(UUID(int=999))
    elif defect=='drain-ref-bool':body['drainReceiptRef']['revision']=True
    elif defect=='event-type':event['event_type']='CUTOVER_RESUMED'
    elif defect=='event-extra':event['payload']['extra']=True
    elif defect=='event-time':event['occurred_at']='2026-08-03T01:00:30+00:00'
    elif defect=='fence-time':fence['authority_data']['createdAt']=fence['created_at']='2026-08-03T01:00:09+00:00';relations['public.extension_dispatch_cutover_event'][-3]['occurred_at']=fence['created_at']
    elif defect=='drain-time':drain['authority_data']['createdAt']=drain['created_at']='2026-08-03T01:00:10.500000+00:00';relations['public.extension_dispatch_cutover_event'][-2]['occurred_at']=drain['created_at']
    elif defect=='drain-facts':drain['authority_data']['unknownAttempts']=[]
    elif defect=='drain-claimed':drain['authority_data']['claimedOccurrences']=deepcopy(fence['authority_data']['claimedOccurrences'])
    elif defect=='scope':op['org_id']='dev-org'
    if defect!='extra-phase':
        for phase in ('fence','drain','rollback'):rehash_rollback_phase(args,phase)
    if defect in {'drain-time','drain-facts','drain-claimed'}:
        body['drainReceiptRef']['contentHash']=drain['content_hash'];rehash_rollback_phase(args,'rollback')
    if defect in {'drain-missing','rollback-missing'}:
        phase=defect.split('-')[0];relations['public.extension_dispatch_cutover_receipt'].remove(next(r for r in rows if r['phase']==phase))
    with pytest.raises(ValueError):verify_cutover_rollback(args)


def test_activate_parent_cannot_carry_a_rollback_failure_reason():
    args=cutover_prepare_context();args[0]['relations']['public.extension_dispatch_cutover_operation'][0]['failure_reason']='unexpected'
    with pytest.raises(ValueError):verify_cutover_prepare(args)


def test_rollback_inherited_policy_json_cannot_equate_boolean_with_integer():
    args=cutover_rollback_context()
    args[0]['relations']['public.extension_dispatch_cutover_operation'][1]['policy_ref']['revision']=True
    with pytest.raises(ValueError):verify_cutover_rollback(args)


def verify_cutover_history(args):
    packet,scope,source,*_=args;ledger=reader._WorkLedger()
    return reader._cutover_history(decode(packet,ledger),scope=scope,source=source,ledger=ledger)


@pytest.mark.parametrize('count',range(5))
def test_all_cutover_history_consumes_the_original_activation_status_prefix(count):
    graph=verify_cutover_history(cutover_forward_context(count))
    assert len(graph.activations)==1 and not graph.rollbacks
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind')


@pytest.mark.parametrize('complete',[False,True])
def test_all_cutover_history_links_independent_rollback_and_approval_without_losing_parent(complete):
    graph=verify_cutover_history(cutover_rollback_context(complete=complete,refresh=True))
    assert len(graph.activations)==len(graph.rollbacks)==1
    assert graph.rollback_by_parent[UUID(int=4000)]==UUID(int=4600)


def test_all_cutover_history_can_be_empty_without_granting_a_branch():
    graph=verify_cutover_history(source_history_context('approved'))
    assert not graph.activations and not graph.rollbacks


def test_all_cutover_history_consumes_multiple_legitimate_prepared_candidates_in_the_same_tenant():
    args=cutover_forward_context(0);other=cutover_prepare_context(activation_id=5000)
    other[0]['relations']['public.extension_dispatch_cutover_operation'][0]['status']='prepared'
    for name in ('public.extension_dispatch_cutover_operation','public.extension_dispatch_cutover_event','public.extension_dispatch_cutover_receipt'):
        args[0]['relations'][name].extend(deepcopy(other[0]['relations'][name]))
    graph=verify_cutover_history(args)
    assert set(graph.activations)=={UUID(int=4000),UUID(int=5000)}


@pytest.mark.parametrize('collision',['request-key','event-id'])
def test_cutover_global_uniqueness_cannot_be_replaced_by_individually_valid_parent_graphs(collision):
    args=cutover_forward_context(0);other=cutover_prepare_context(activation_id=5000,
        idempotency_key='activation-prepare' if collision=='request-key' else None)
    other[0]['relations']['public.extension_dispatch_cutover_operation'][0]['status']='prepared'
    if collision=='event-id':
        other[0]['relations']['public.extension_dispatch_cutover_event'][0]['event_id']=args[0]['relations']['public.extension_dispatch_cutover_event'][0]['event_id']
    assert verify_cutover_prepare(args).receipt.status=='prepared'
    assert verify_cutover_prepare(other).receipt.status=='prepared'
    for name in ('public.extension_dispatch_cutover_operation','public.extension_dispatch_cutover_event','public.extension_dispatch_cutover_receipt'):
        args[0]['relations'][name].extend(deepcopy(other[0]['relations'][name]))
    with pytest.raises(ValueError):verify_cutover_history(args)


@pytest.mark.parametrize('defect',['op-scope','target','status-lag','status-ahead','committing','fencing','needs_attention','unknown-kind',
    'orphan-event','orphan-receipt','orphan-refresh','refresh-on-rollback','extra-event','extra-phase','duplicate-phase','duplicate-event-id',
    'duplicate-key','duplicate-child','receipt-scope','event-scope','refresh-scope'])
def test_all_cutover_history_rejects_unconsumed_orphan_reserved_or_cross_scope_records(defect):
    args=cutover_rollback_context(refresh=True);relations=args[0]['relations'];parent,child=relations['public.extension_dispatch_cutover_operation']
    events=relations['public.extension_dispatch_cutover_event'];rows=relations['public.extension_dispatch_cutover_receipt'];refresh=relations['public.extension_dispatch_cutover_approval_refresh_receipt'][0]
    if defect=='op-scope':parent['org_id']='dev-org'
    elif defect=='target':parent['target_installation_id']=str(UUID(int=999))
    elif defect=='status-lag':parent['status']='draining'
    elif defect=='status-ahead':parent['status']='resumed'
    elif defect in {'committing','fencing','needs_attention'}:parent['status']=defect
    elif defect=='unknown-kind':parent['kind']='unexpected'
    elif defect=='orphan-event':events[0]['cutover_operation_id']=str(UUID(int=999))
    elif defect=='orphan-receipt':rows[0]['cutover_operation_id']=str(UUID(int=999))
    elif defect=='orphan-refresh':refresh['cutover_operation_id']=str(UUID(int=999))
    elif defect=='refresh-on-rollback':refresh['cutover_operation_id']=child['cutover_operation_id']
    elif defect=='extra-event':events.append(dict(deepcopy(events[0]),sequence=99,event_id=str(UUID(int=999)),event_type='CUTOVER_NEEDS_ATTENTION'))
    elif defect=='extra-phase':rows.append(dict(deepcopy(rows[0]),phase='unexpected',receipt_id=str(UUID(int=999))))
    elif defect=='duplicate-phase':rows.append(dict(deepcopy(rows[0]),receipt_id=str(UUID(int=999))))
    elif defect=='duplicate-event-id':events[-1]['event_id']=events[0]['event_id']
    elif defect=='duplicate-key':child['idempotency_key']=parent['idempotency_key']
    elif defect=='duplicate-child':relations['public.extension_dispatch_cutover_operation'].append(dict(deepcopy(child),cutover_operation_id=str(UUID(int=999)),idempotency_key='second-child'))
    elif defect=='receipt-scope':rows[0]['org_id']='dev-org'
    elif defect=='event-scope':events[0]['org_id']='dev-org'
    elif defect=='refresh-scope':refresh['org_id']='dev-org'
    with pytest.raises(ValueError):verify_cutover_history(args)


def primary_refresh_context(count=2, *, skip_staged=False, registration=None,registration_ref=None,created_at=None,old_revision=1,old_group_revision=1,group_id=None,legacy_fence=None,idempotency_key=None):
    from datetime import timedelta
    from aos_api.ecommerce_dispatch_configuration_contracts import DispatchConfigurationRefreshRequest
    from aos_api.ecommerce_dispatch_configuration_receipt import receipt_body
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=cutover_forward_context(registration=registration,registration_ref=registration_ref,created_at=created_at,old_revision=old_revision,old_group_revision=old_group_revision,group_id=group_id,legacy_fence=legacy_fence,idempotency_key=idempotency_key);packet,scope,source,locked,lock=args;relations=packet['relations']
    root=verify_cutover_forward(args);resume=root.receipts['resume'];binding=relations['public.extension_runtime_binding'][0]
    configs=sorted([r for r in relations['public.extension_runtime_configuration'] if r['configuration_id']==binding['config_ref']['configurationId']],key=lambda r:r['revision'])
    config_ref=lambda r:dict(configurationId=r['configuration_id'],revision=r['revision'],hash=r['content_hash'])
    source_cfg=config_ref(configs[0]);binding['config_ref']=deepcopy(source_cfg)
    replace_successful_controls(args,[]);add_control_operation(args,'configure',3000,1,2);add_control_operation(args,'enable',3001,3,3)
    install=next(r for r in relations['public.bundle_installation_revision'] if r['revision']==binding['installation_revision'])
    install_ref=dict(installationId=source.installation_id,revision=install['revision'],lockHash=install['lock_hash'],overlayRevision=install['overlay_revision'])
    previous=None;authority=dict(resourceType='CutoverResumeReceipt',resourceId=str(resume.receipt_id),revision=1,contentHash=resume.content_hash)
    runtime=6;epoch=3;group=root.prepared.receipt.target_group_revision
    for number in range(1,count+1):
        target_cfg=config_ref(configs[2 if skip_staged else number]);binding['config_ref']=deepcopy(target_cfg)
        configure=add_control_operation(args,'configure',4700+number*2,runtime,epoch+1)
        enable=add_control_operation(args,'enable',4701+number*2,runtime+2,epoch+2)
        request=DispatchConfigurationRefreshRequest(orgId=scope.org_id,projectId=scope.project_id,installationRef=install_ref,
            generation=binding['generation'],cutoverGroupId=str(root.prepared.receipt.cutover_group_id),expectedGroupRevision=group,
            sourceAuthorityRef=authority,sourceRuntimeRevision=runtime,sourceExecutionEpoch=epoch,sourceConfigurationRef=source_cfg,
            targetRuntimeRevision=runtime+3,targetExecutionEpoch=epoch+2,targetConfigurationRef=target_cfg,
            configureOperationId=configure['operation_id'],configureOperationRevision=configure['revision'],
            enableOperationId=enable['operation_id'],enableOperationRevision=enable['revision'],operationIds=tuple(sorted(root.prepared.receipt.operation_ids)),
            approvalRef=dict(resourceType='ActionApprovalEvent',resourceId=str(UUID(int=4800+number)),revision=1,contentHash='sha256:'+'d'*64),
            idempotencyKey=('refresh-' if idempotency_key is None else idempotency_key+'-refresh-')+str(number),externalEffectsAllowed=False,resumeBusinessRuns=False)
        created=max(datetime.fromisoformat('2026-08-03T01:00:20.250000+00:00')+timedelta(seconds=number),resume.created_at+timedelta(seconds=number))
        row=dict(org_id=scope.org_id,project_id=scope.project_id,cutover_group_id=str(root.prepared.receipt.cutover_group_id),
            receipt_id=str(UUID(int=4810+number)),revision=number,activation_operation_id=str(root.prepared.receipt.cutover_operation_id),
            activation_resume_receipt_id=str(resume.receipt_id),installation_id=source.installation_id,generation=binding['generation'],
            previous_receipt_id=None if previous is None else previous['receipt_id'],previous_hash=None if previous is None else previous['content_hash'],
            actor='control-actor',idempotency_key=request.idempotency_key,request=request.wire(),request_hash=request.request_hash(),created_at=created)
        row['body']=receipt_body(row);row['content_hash']=canonical_sha256(row['body']);row['created_at']=created.isoformat()
        relations['public.extension_dispatch_configuration_refresh_receipt'].append(row)
        authority=dict(resourceType='DispatchConfigurationRefreshReceipt',resourceId=row['receipt_id'],revision=number,contentHash=row['content_hash'])
        previous=row;runtime+=3;epoch+=2;group+=1;source_cfg=target_cfg
    add_control_operation(args,'disable',3002,runtime,epoch+1)
    terminal_binding_versions(args,runtime+3,epoch+1)
    receipt=relations['public.extension_runtime_uninstall_receipt'][0];body=json.loads(receipt['authority_data_text'])
    body.pop('bindingRevision',None)
    receipt['activation_operation_id']=str(root.prepared.receipt.cutover_operation_id)
    body.update(bindingFromRevision=runtime+2,bindingToRevision=runtime+3,activationOperationId=receipt['activation_operation_id'],cutoverGroupId=str(root.prepared.receipt.cutover_group_id))
    import hashlib
    receipt['authority_data_text']=json.dumps(body);receipt['content_hash']='sha256:'+hashlib.sha256(receipt['authority_data_text'].encode()).hexdigest()
    return args


def verify_primary_refresh(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    cutovers=reader._cutover_history(facts,scope=scope,source=source,ledger=ledger)
    controls=reader._control_history(facts,scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger)
    return reader._primary_refresh_history(facts,cutovers,controls,activation_id=UUID(int=4000),scope=scope,source=source,ledger=ledger)


@pytest.mark.parametrize('count',[0,1,2])
def test_primary_refresh_continues_original_resume_through_every_original_control_and_receipt(count):
    graph=verify_primary_refresh(primary_refresh_context(count))
    assert graph.runtime_revision==6+3*count and graph.execution_epoch==3+2*count
    assert graph.group_revision==2+count and len(graph.receipt_ids)==count
    assert all(row['revision']==2+count and row['executionEpoch']==3+2*count for row in graph.dispatch_snapshot)
    assert not graph.remaining_receipt_ids and not hasattr(graph,'authorized') and not hasattr(graph,'kind')


def test_primary_refresh_can_skip_an_unapplied_staged_configuration_version():
    graph=verify_primary_refresh(primary_refresh_context(1,skip_staged=True))
    assert graph.configuration.revision==3


def rehash_refresh_row(row):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.ecommerce_dispatch_configuration_receipt import receipt_body
    row['request_hash']=canonical_sha256(row['request'])
    raw=dict(row,created_at=datetime.fromisoformat(row['created_at']));row['body']=receipt_body(raw)
    row['content_hash']=canonical_sha256(row['body'])


@pytest.mark.parametrize('defect',['missing-first','missing-last-parent','root','resume','previous-hash','source-runtime','source-epoch','source-config',
    'group','target-runtime','target-epoch','target-config','configure-id','configure-revision','enable-id','enable-revision',
    'installation-lock','installation-overlay','actor','time','duplicate-key','body-extra','body-revision-bool','body-request','scope','generation'])
def test_primary_refresh_rejects_rehashed_chain_control_and_current_installation_drift(defect):
    args=primary_refresh_context();rows=args[0]['relations']['public.extension_dispatch_configuration_refresh_receipt'];row=rows[-1];req=row['request']
    if defect=='root':row['activation_operation_id']=str(UUID(int=999))
    elif defect=='resume':row['activation_resume_receipt_id']=str(UUID(int=999))
    elif defect=='previous-hash':row['previous_hash']='sha256:'+'e'*64;req['sourceAuthorityRef']['contentHash']=row['previous_hash']
    elif defect=='source-runtime':req['sourceRuntimeRevision']+=1
    elif defect=='source-epoch':req['sourceExecutionEpoch']+=1
    elif defect=='source-config':req['sourceConfigurationRef']=deepcopy(req['targetConfigurationRef']);req['targetConfigurationRef']['revision']+=1
    elif defect=='group':req['expectedGroupRevision']+=1
    elif defect=='target-runtime':req['targetRuntimeRevision']+=1
    elif defect=='target-epoch':req['targetExecutionEpoch']+=1
    elif defect=='target-config':req['targetConfigurationRef']['hash']='sha256:'+'e'*64
    elif defect=='configure-id':req['configureOperationId']=str(UUID(int=999))
    elif defect=='configure-revision':req['configureOperationRevision']+=1
    elif defect=='enable-id':req['enableOperationId']=str(UUID(int=999))
    elif defect=='enable-revision':req['enableOperationRevision']+=1
    elif defect=='installation-lock':req['installationRef']['lockHash']='sha256:'+'e'*64
    elif defect=='installation-overlay':req['installationRef']['overlayRevision']='other'
    elif defect=='actor':row['actor']='other-actor'
    elif defect=='time':row['created_at']='2026-08-03T01:00:01.250000+00:00'
    elif defect=='duplicate-key':row['idempotency_key']=req['idempotencyKey']=rows[0]['idempotency_key']
    elif defect=='scope':row['org_id']=req['orgId']='dev-org'
    elif defect=='generation':row['generation']=req['generation']=str(UUID(int=999))
    rehash_refresh_row(row)
    if defect=='body-extra':row['body']['eligible']=True
    elif defect=='body-revision-bool':row['body']['revision']=True
    elif defect=='body-request':row['body']['requestHash']='sha256:'+'e'*64
    elif defect=='missing-first':rows.pop(0)
    elif defect=='missing-last-parent':row['previous_receipt_id']=req['sourceAuthorityRef']['resourceId']=str(UUID(int=999));rehash_refresh_row(row)
    with pytest.raises(ValueError):verify_primary_refresh(args)


def test_primary_refresh_does_not_silently_consume_another_group_without_proof():
    args=primary_refresh_context(1);row=deepcopy(args[0]['relations']['public.extension_dispatch_configuration_refresh_receipt'][0])
    row.update(cutover_group_id=str(UUID(int=4900)),receipt_id=str(UUID(int=4901)))
    args[0]['relations']['public.extension_dispatch_configuration_refresh_receipt'].append(row)
    graph=verify_primary_refresh(args)
    assert graph.remaining_receipt_ids==(UUID(int=4901),)


def test_primary_refresh_rechecks_actual_body_bytes_after_original_decoder_boolean_equality():
    from aos_api.ecommerce_dispatch_configuration_receipt import decode_receipt
    args=primary_refresh_context(1);row=args[0]['relations']['public.extension_dispatch_configuration_refresh_receipt'][0]
    row['body']['revision']=True
    # Original decoder compares reconstructed body dictionaries: True equals 1.
    # Keep its old integer-body hash to isolate why raw-body hashing is required.
    original=decode_receipt(dict(row,created_at=datetime.fromisoformat(row['created_at'])))
    assert original['ref']['revision']==1
    with pytest.raises(ValueError):verify_primary_refresh(args)


def shift_final_disable_for_join_fixture(args):
    from aos_api.extension_runtime.lifecycle_store import _digest,_request_hash
    relations=args[0]['relations'];binding=relations['public.extension_runtime_binding'][0]
    operation=next(o for o in relations['public.extension_runtime_operation'] if o['operation_id']==str(UUID(int=3002)))
    operation['expected_binding_revision']+=1
    events=[e for e in relations['public.extension_runtime_event'] if e['operation_id']==operation['operation_id']]
    events[0]['payload']['bindingTarget']['bindingRevision']+=1
    operation['request_hash']=_request_hash(kind='disable',actor=operation['requested_by'],etag=operation['expected_installation_etag'],
        deadline=datetime.fromisoformat(operation['deadline']),binding_target=events[0]['payload']['bindingTarget'])
    proof=next(e for e in events if e['type']=='disabled_committed');proof['payload']['bindingRevision']+=1;proof['payload']['executionEpoch']+=1
    for event in events:event['payload_hash']=_digest(event['payload'])
    binding['revision']+=1;binding['execution_epoch']+=1
    row=relations['public.extension_runtime_uninstall_receipt'][0];row['binding_revision']+=1;body=json.loads(row['authority_data_text'])
    body['bindingFromRevision']+=1;body['bindingToRevision']+=1
    import hashlib
    row['authority_data_text']=json.dumps(body);row['content_hash']='sha256:'+hashlib.sha256(row['authority_data_text'].encode()).hexdigest()


def rebuild_lifecycle_pair_for_join_fixture(args,refresh_ref):
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from datetime import timedelta
    relations=args[0]['relations'];life=relations['public.extension_dispatch_lifecycle_operation'][0]
    runtime=next(o for o in relations['public.extension_runtime_operation'] if o['operation_id']==life['runtime_operation_id'])
    activation=next(o for o in relations['public.extension_dispatch_cutover_operation'] if o['cutover_operation_id']==life['activation_operation_id'])
    basis=dict(runtimeOperationId=runtime['operation_id'],runtimeRequestHash=runtime['request_hash'],activationOperationId=activation['cutover_operation_id'],
        activationRequestHash=activation['request_hash'],operationIds=activation['operation_ids'])
    life['request_hash']=canonical_sha256(basis)
    start=datetime.fromisoformat(life['created_at']);life['updated_at']=(start+timedelta(seconds=1)).isoformat()
    relations['public.extension_dispatch_lifecycle_receipt']=[];relations['public.extension_dispatch_lifecycle_event']=[]
    current=[dict(item,revision=held['revision']+1,cutoverGroupRevision=life['fenced_group_revision']+1) for item,held in zip(life['legacy_snapshot'],life['fenced_snapshot'])]
    written_operations={item['operationId'] for item in current}
    relations['public.extension_operation_dispatch_binding']=[r for r in relations['public.extension_operation_dispatch_binding'] if r['operation_id'] not in written_operations]
    for item in current:
        relations['public.extension_operation_dispatch_binding'].append(dict(org_id=args[1].org_id,project_id=args[1].project_id,
            operation_id=item['operationId'],handler_kind=item['handlerKind'],installation_id=None,generation=None,execution_epoch=None,
            operation_fence=item['operationFence'],revision=item['revision'],cutover_group_id=item['cutoverGroupId'],cutover_group_revision=item['cutoverGroupRevision'],
            updated_by=runtime['requested_by'],updated_at=(start+timedelta(seconds=2)).isoformat()))
    fence=None
    for sequence,phase,snapshot in ((1,'fence',life['fenced_snapshot']),(2,'detach',current)):
        body=EcommerceGrowthDisableDependent._authority(args[1],runtime,activation,phase=phase,dispatch_snapshot=deepcopy(snapshot),request_hash=life['request_hash'],
            unknown_attempts=[],fence_receipt=fence,configuration_refresh_ref=deepcopy(refresh_ref))
        created=start if phase=='fence' else start+timedelta(seconds=2)
        row=dict(org_id=args[1].org_id,project_id=args[1].project_id,receipt_id=str(UUID(int=4100+sequence)),runtime_operation_id=runtime['operation_id'],
            phase=phase,request_hash=life['request_hash'],authority_data=body,content_hash=canonical_sha256(body),created_at=created.isoformat())
        payload=dict(runtimeOperationId=runtime['operation_id'],phase=phase,receiptId=row['receipt_id'],contentHash=row['content_hash'])
        relations['public.extension_dispatch_lifecycle_receipt'].append(row)
        relations['public.extension_dispatch_lifecycle_event'].append(dict(org_id=args[1].org_id,project_id=args[1].project_id,runtime_operation_id=runtime['operation_id'],sequence=sequence,
            event_type='DISPATCH_DISABLE_FENCED' if sequence==1 else 'DISPATCH_DISABLED_DETACHED',payload=payload,payload_hash=canonical_sha256(payload),occurred_at=created.isoformat()))
        if phase=='fence':fence=row


def detached_refresh_context(count=2,*,snapshot_count=None,shift_disable=False,registration=None,registration_ref=None,created_at=None,old_revision=1,old_group_revision=1,group_id=None,legacy_fence=None,idempotency_key=None):
    args=primary_refresh_context(count,registration=registration,registration_ref=registration_ref,created_at=created_at,old_revision=old_revision,old_group_revision=old_group_revision,group_id=group_id,legacy_fence=legacy_fence,idempotency_key=idempotency_key);relations=args[0]['relations']
    if shift_disable:shift_final_disable_for_join_fixture(args)
    actual=count if snapshot_count is None else snapshot_count
    activation=relations['public.extension_dispatch_cutover_operation'][0]
    extension=[dict(item,executionEpoch=3+2*actual,revision=item['revision']+actual,cutoverGroupRevision=item['cutoverGroupRevision']+actual)
        for item in activation['new_dispatch_snapshot']]
    life=relations['public.extension_dispatch_lifecycle_operation'][0]
    life.update(activation_operation_id=activation['cutover_operation_id'],cutover_group_id=activation['cutover_group_id'],extension_snapshot=extension,fenced_snapshot=[dict(item,operationFence=True,revision=item['revision']+1,
        cutoverGroupRevision=item['cutoverGroupRevision']+1) for item in extension],legacy_snapshot=deepcopy(activation['old_dispatch_snapshot']),
        fenced_group_revision=activation['target_group_revision']+1+actual,created_at='2026-08-03T01:01:00+00:00')
    from datetime import timedelta
    times=[datetime.fromisoformat(r['created_at']) for r in relations['public.extension_dispatch_cutover_receipt']+relations['public.extension_dispatch_configuration_refresh_receipt']]
    life['created_at']=max(datetime.fromisoformat(life['created_at']),max(times)+timedelta(seconds=2)).isoformat()
    refresh=relations['public.extension_dispatch_configuration_refresh_receipt'][-1] if count else None
    ref=None if refresh is None else dict(resourceType='DispatchConfigurationRefreshReceipt',resourceId=refresh['receipt_id'],revision=refresh['revision'],contentHash=refresh['content_hash'])
    rebuild_lifecycle_pair_for_join_fixture(args,ref)
    return args


def verify_detached_refresh(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    return reader._detached_refresh_history(decode(packet,ledger),scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger)


@pytest.mark.parametrize('count',[0,1,2])
def test_detached_refresh_joins_full_cutover_controls_latest_authority_and_both_lifecycle_receipts(count):
    graph=verify_detached_refresh(detached_refresh_context(count))
    assert len(graph.refresh.receipt_ids)==count and len(graph.cutovers.activations)==1
    assert len(graph.lifecycle.primary_dispatch)==9
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind')


def test_detached_no_refresh_does_not_pretend_an_extra_version_is_already_a_proven_cleanup_timeline():
    graph=verify_detached_refresh(detached_refresh_context(0,shift_disable=True))
    assert graph.refresh.runtime_revision==6
    # This join retains the extra B version; its actual cleanup cause is still a later gate.
    assert graph.lifecycle.history.commits[UUID(int=3002)].from_revision==7
    assert not hasattr(graph,'timeline')


@pytest.mark.parametrize('count',[0,2])
@pytest.mark.parametrize('registration',['FirstDispatchRegistrationReceipt','SuccessorDispatchRegistrationReceipt'])
def test_detached_refresh_join_preserves_original_fenced_legacy_registration_snapshots(count,registration):
    graph=verify_detached_refresh(detached_refresh_context(count,registration=registration))
    assert graph.lifecycle.primary_dispatch[0]['operationFence'] is True
    # Registration reference origin is a later obligation; this join grants no branch.
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind')


@pytest.mark.parametrize('defect',['missing-ref','stale-ref','wrong-id','wrong-hash','wrong-revision','phantom-no-refresh',
    'snapshot-old','snapshot-one-behind','parent-time','missing-C-resume','wrong-C-request','refresh-disable-gap'])
def test_detached_refresh_rejects_self_consistent_but_unlinked_lifecycle_authority(defect):
    count=0 if defect=='phantom-no-refresh' else 2
    args=detached_refresh_context(count,snapshot_count=0 if defect=='snapshot-old' else 1 if defect=='snapshot-one-behind' else None,
        shift_disable=defect=='refresh-disable-gap')
    relations=args[0]['relations'];last=relations['public.extension_dispatch_configuration_refresh_receipt'][-1] if count else None
    ref=None if last is None else dict(resourceType='DispatchConfigurationRefreshReceipt',resourceId=last['receipt_id'],revision=last['revision'],contentHash=last['content_hash'])
    if defect=='missing-ref':ref=None
    elif defect=='stale-ref':first=relations['public.extension_dispatch_configuration_refresh_receipt'][0];ref=dict(resourceType='DispatchConfigurationRefreshReceipt',resourceId=first['receipt_id'],revision=1,contentHash=first['content_hash'])
    elif defect=='wrong-id':ref['resourceId']=str(UUID(int=999))
    elif defect=='wrong-hash':ref['contentHash']='sha256:'+'e'*64
    elif defect=='wrong-revision':ref['revision']+=1
    elif defect=='phantom-no-refresh':ref=dict(resourceType='DispatchConfigurationRefreshReceipt',resourceId=str(UUID(int=999)),revision=1,contentHash='sha256:'+'e'*64)
    elif defect=='parent-time':relations['public.extension_dispatch_lifecycle_operation'][0]['created_at']='2026-08-03T01:00:01+00:00'
    elif defect=='missing-C-resume':relations['public.extension_dispatch_cutover_receipt']=[r for r in relations['public.extension_dispatch_cutover_receipt'] if r['phase']!='resume']
    elif defect=='wrong-C-request':relations['public.extension_dispatch_cutover_operation'][0]['request_hash']='sha256:'+'e'*64
    rebuild_lifecycle_pair_for_join_fixture(args,ref)
    with pytest.raises(ValueError):verify_detached_refresh(args)


def verify_detached_control_timeline(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    return reader._detached_control_timeline(decode(packet,ledger),scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger)


@pytest.mark.parametrize('count',[0,1,2])
@pytest.mark.parametrize('registration',[None,'FirstDispatchRegistrationReceipt','SuccessorDispatchRegistrationReceipt'])
def test_detached_single_binding_timeline_includes_both_cutover_steps_without_advancing_epoch(count,registration):
    graph=verify_detached_control_timeline(detached_refresh_context(count,registration=registration));timeline=graph.timeline
    assert timeline.before_uninstall_revision==8+3*count and timeline.execution_epoch==4+2*count
    assert timeline.cleanup_revision is None
    assert timeline.versions[5].execution_epoch==timeline.versions[6].execution_epoch==3
    assert timeline.versions[5].enabled is False and timeline.versions[5].observed_state=='ready'
    assert timeline.versions[6].enabled is True and timeline.versions[6].observed_state=='ready'
    assert set(timeline.versions)==set(range(1,timeline.before_uninstall_revision+1))
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind')


def test_detached_timeline_derives_the_one_extra_cleanup_fence_after_the_last_resume():
    graph=verify_detached_control_timeline(detached_refresh_context(0,shift_disable=True))
    assert graph.timeline.cleanup_revision==7 and graph.timeline.execution_epoch==5
    assert graph.timeline.before_uninstall_revision==9


@pytest.mark.parametrize('count',[0,1,2])
def test_original_nondispatch_kernel_still_rejects_unexplained_cutover_binding_gaps(count):
    with pytest.raises(ValueError):verify_control_timeline(detached_refresh_context(count))


def test_detached_timeline_does_not_accept_a_client_style_allow_extra_versions_flag():
    controls=verify_control_history(detached_refresh_context())
    with pytest.raises(ValueError):reader._derive_control_timeline(controls,reader._WorkLedger(),detached={'allow':True})


def test_detached_timeline_requires_the_exact_controls_object_from_its_verified_join():
    args=detached_refresh_context();joined=verify_detached_refresh(args);other=verify_control_history(args)
    with pytest.raises(ValueError):reader._derive_control_timeline(other,reader._WorkLedger(),detached=joined)


def test_two_individually_valid_cutover_roots_cannot_claim_the_same_binding_transitions():
    args=detached_refresh_context(0);other=cutover_forward_context(activation_id=5000)
    for name in ('public.extension_dispatch_cutover_operation','public.extension_dispatch_cutover_receipt','public.extension_dispatch_cutover_event'):
        args[0]['relations'][name].extend(deepcopy(other[0]['relations'][name]))
    assert len(verify_detached_refresh(args).cutovers.activations)==2
    with pytest.raises(ValueError):verify_detached_control_timeline(args)


def test_v6_includes_the_original_first_registration_receipt_source():
    assert reader._SCHEMA_VERSION=='aos.reinstall-terminal-source-facts/v13'
    assert 'public.extension_dispatch_registration_receipt' in reader._RELATIONS
    assert 'public.extension_dispatch_registration_receipt' in reader._NONDISPATCH_EMPTY


def test_v5_and_a_missing_first_registration_family_cannot_claim_current_complete_input():
    packet=empty_packet();packet['schema']='aos.reinstall-terminal-source-facts/v5'
    packet['relations'].pop('public.extension_dispatch_registration_receipt')
    with pytest.raises(ValueError):decode(packet)
    packet['schema']='aos.reinstall-terminal-source-facts/v13'
    with pytest.raises(ValueError):decode(packet)


def test_v6_preserves_all_prior_columns_and_adds_only_original_a0v026_receipt_fields():
    import hashlib
    root=Path(__file__).resolve().parents[4]/'.evidence/qyh-m2-terminal-source-implementation-20261025'
    prior=root/'reader-v5-schema-literal-r146.json';old=json.loads(prior.read_text());new=json.loads((root/'reader-v6-schema-literal-r189.json').read_text())
    assert new['priorLiteralSHA256']==hashlib.sha256(prior.read_bytes()).hexdigest()
    assert new['relations'][:-1]==old['relations'] and new['registry']==old['registry']
    item=new['relations'][-1];assert item['rank']==175 and len(item['columns'])==11
    actual=reader._RELATIONS[item['name']]
    assert actual.columns==tuple(tuple(c) for c in item['columns']) and actual.key==tuple(item['key']) and actual.cap==2048


def registration_origin_context(kind='FirstDispatchRegistrationReceipt',*,count=0,defect=None,old_revision=1,old_group_revision=1,group_id=None,predecessor_ref=None,dispatch_snapshot=None,registration_time=None,cutover_time=None,idempotency_key=None):
    from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest,preview_registration
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    from aos_api.asset_registry.canonical_json import canonical_sha256
    preliminary=detached_refresh_context(count,registration=kind,old_revision=old_revision,old_group_revision=old_group_revision,group_id=group_id,created_at=cutover_time,idempotency_key=idempotency_key);packet,scope,source,locked,lock=preliminary
    rel=packet['relations'];binding=rel['public.extension_runtime_binding'][0]
    installed=next(r for r in rel['public.bundle_installation_revision'] if r['revision']==binding['installation_revision'])
    configuration=next(r for r in rel['public.extension_runtime_configuration'] if r['configuration_id']==binding['config_ref']['configurationId'] and r['revision']==1)
    request=FirstDispatchRegistrationRequest(schemaVersion='aos.ecommerce.first-dispatch-registration/v1',
        installationRef=dict(installationId=source.installation_id,revision=installed['revision'],lockHash=installed['lock_hash'],overlayRevision=installed['overlay_revision']),
        generation=binding['generation'],bindingRevision=4,executionEpoch=3,configRef=dict(configurationId=configuration['configuration_id'],revision=1,hash=configuration['content_hash']),
        groupId=group_id if group_id is not None else str(UUID(int=4002)),idempotencyKey='registration-origin')
    material=request.model_dump(mode='json',by_alias=True);snapshot=preview_registration(request)['proposedDispatchSnapshot']
    if dispatch_snapshot is not None:snapshot=deepcopy(dispatch_snapshot)
    if kind=='SuccessorDispatchRegistrationReceipt':
        successor=SuccessorDispatchRegistrationRequest(schemaVersion='aos.ecommerce.successor-dispatch-registration/v1',registration=request,
            expectedGroupRevision=old_group_revision,predecessorDetachReceiptRef=predecessor_ref if predecessor_ref is not None else dict(resourceType='DispatchDisableDetachReceipt',resourceId=str(UUID(int=5100)),revision=1,contentHash='sha256:'+'d'*64))
        material=successor.model_dump(mode='json',by_alias=True)
    body=dict(schemaVersion='aos.ecommerce.first-dispatch-registration-receipt/v1' if kind=='FirstDispatchRegistrationReceipt' else 'aos.ecommerce.successor-dispatch-registration-receipt/v1',
        tenant=dict(orgId=scope.org_id,projectId=scope.project_id),receiptId=str(UUID(int=4203)),installationId=source.installation_id,generation=binding['generation'],groupId=request.groupId,
        requestHash=canonical_sha256(material),idempotencyKey=request.idempotencyKey,actor='registration-actor',request=material,
        dispatchSnapshot=snapshot,executable=False,createdAt=registration_time if registration_time is not None else '2026-08-03T01:00:01.0001+00:00')
    row=dict(org_id=scope.org_id,project_id=scope.project_id,receipt_id=body['receiptId'],installation_id=source.installation_id,generation=body['generation'],group_id=request.groupId,
        idempotency_key=request.idempotencyKey,request_hash=body['requestHash'],payload=body,created_at='2026-08-03T01:00:01.000200+00:00')
    if registration_time is not None:
        from datetime import timedelta
        row['created_at']=(datetime.fromisoformat(registration_time)+timedelta(microseconds=100)).isoformat()
    registration=body['request'] if kind=='FirstDispatchRegistrationReceipt' else body['request']['registration']
    if defect=='binding':registration['bindingRevision']+=1
    elif defect=='epoch':registration['executionEpoch']+=1
    elif defect=='configuration':registration['configRef']['hash']='sha256:'+'e'*64
    elif defect=='overlay':registration['installationRef']['overlayRevision']='other'
    elif defect=='lock':registration['installationRef']['lockHash']='sha256:'+'e'*64
    elif defect=='installation-revision':registration['installationRef']['revision']+=1
    elif defect=='snapshot-bool':body['dispatchSnapshot'][0]['revision']=True
    elif defect=='snapshot-order':body['dispatchSnapshot'].reverse()
    elif defect=='actor':body['actor']=' bad '
    elif defect=='extra':body['eligible']=True
    elif defect=='body-after-row':body['createdAt']='2026-08-03T01:00:02+00:00'
    elif defect=='row-after-prepare':row['created_at']='2026-08-03T01:00:04+00:00'
    elif defect=='naive-time':body['createdAt']='2026-08-03T01:00:01'
    elif defect=='target':body['installationId']=row['installation_id']=str(UUID(int=999))
    elif defect=='body-id':body['receiptId']=str(UUID(int=999))
    elif defect=='request-extra':registration['extra']=True
    row['request_hash']=body['requestHash']=canonical_sha256(body['request'])
    if defect=='request-hash':row['request_hash']=body['requestHash']='sha256:'+'e'*64
    row['content_hash']=canonical_sha256(body)
    ref=dict(resourceType=kind,resourceId=row['receipt_id'],revision=1,contentHash=row['content_hash'])
    if defect=='ref-hash':ref['contentHash']='sha256:'+'e'*64
    args=detached_refresh_context(count,registration=kind,registration_ref=ref,created_at=cutover_time if cutover_time is not None else '2026-08-03T01:00:03+00:00',old_revision=old_revision,old_group_revision=old_group_revision,group_id=group_id,idempotency_key=idempotency_key)
    family='public.extension_dispatch_registration_receipt' if kind=='FirstDispatchRegistrationReceipt' else 'public.extension_dispatch_successor_registration_receipt'
    if defect!='missing':args[0]['relations'][family]=[row]
    return args


def verify_registration_history(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    controls=reader._control_history(facts,scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger)
    cutovers=reader._cutover_history(facts,scope=scope,source=source,ledger=ledger)
    return reader._registration_history(facts,cutovers,controls,scope=scope,source=source,ledger=ledger)


@pytest.mark.parametrize('kind',['FirstDispatchRegistrationReceipt','SuccessorDispatchRegistrationReceipt'])
@pytest.mark.parametrize('count',[0,2])
def test_registration_origin_uses_real_stored_receipt_and_original_control_configuration_pins(kind,count):
    graph=verify_registration_history(registration_origin_context(kind,count=count))
    assert graph.origins[UUID(int=4000)].bindingRevision==4
    assert not graph.unconsumed and not graph.pending_control_roots
    assert len(graph.pending_predecessors)==int(kind=='SuccessorDispatchRegistrationReceipt')
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind')


def test_legacy_cutover_without_registration_does_not_invent_a_new_origin_reference():
    graph=verify_registration_history(detached_refresh_context(0))
    assert not graph.origins and not graph.unconsumed and not graph.pending_predecessors


@pytest.mark.parametrize('kind',['FirstDispatchRegistrationReceipt','SuccessorDispatchRegistrationReceipt'])
@pytest.mark.parametrize('defect',['missing','binding','epoch','configuration','overlay','lock','installation-revision','snapshot-bool','snapshot-order',
    'actor','extra','body-after-row','row-after-prepare','naive-time','target','body-id','request-extra','request-hash','ref-hash'])
def test_registration_origin_rejects_rehashed_record_target_snapshot_pin_and_time_drift(kind,defect):
    with pytest.raises(ValueError):verify_registration_history(registration_origin_context(kind,defect=defect))


def test_unconsumed_registration_receipt_is_preserved_for_formal_withdrawal_resolution():
    args=registration_origin_context();legacy=detached_refresh_context(0)
    legacy[0]['relations']['public.extension_dispatch_registration_receipt']=args[0]['relations']['public.extension_dispatch_registration_receipt']
    graph=verify_registration_history(legacy)
    assert graph.unconsumed==(('FirstDispatchRegistrationReceipt',UUID(int=4203)),)
    assert not graph.origins


def verify_detached_registration(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    return reader._detached_registration_history(decode(packet,ledger),scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger)


@pytest.mark.parametrize('kind',['FirstDispatchRegistrationReceipt','SuccessorDispatchRegistrationReceipt'])
@pytest.mark.parametrize('count',[0,2])
def test_detached_registration_uses_one_joined_control_timeline_and_origin_graph(kind,count):
    graph=verify_detached_registration(registration_origin_context(kind,count=count))
    assert graph.control.timeline.before_uninstall_revision==8+3*count
    assert len(graph.registrations.origins)==1
    assert len(graph.registrations.pending_predecessors)==int(kind=='SuccessorDispatchRegistrationReceipt')
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind')


def test_detached_registration_cannot_substitute_a_typed_first_reference_for_its_stored_parent():
    with pytest.raises(ValueError):verify_detached_registration(detached_refresh_context(0,registration='FirstDispatchRegistrationReceipt'))


@pytest.mark.parametrize('collision',['group','key'])
def test_individually_valid_first_receipts_still_obey_original_table_uniqueness(collision):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.ecommerce_growth_registration_receipt import decode_registration_receipt
    args=registration_origin_context();rows=args[0]['relations']['public.extension_dispatch_registration_receipt'];other=deepcopy(rows[0])
    other['receipt_id']=other['payload']['receiptId']=str(UUID(int=5201))
    body=other['payload'];request=body['request']
    if collision=='group':other['idempotency_key']=body['idempotencyKey']=request['idempotencyKey']='registration-other-key'
    else:
        other['group_id']=body['groupId']=request['groupId']=str(UUID(int=5202))
        for item in body['dispatchSnapshot']:item['cutoverGroupId']=other['group_id']
    other['request_hash']=body['requestHash']=canonical_sha256(request);other['content_hash']=canonical_sha256(body)
    assert decode_registration_receipt(rows[0],scope=args[1])['executable'] is False
    assert decode_registration_receipt(other,scope=args[1])['executable'] is False
    rows.append(other)
    with pytest.raises(ValueError):verify_registration_history(args)


def verify_detached_lifecycle_receipts(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    return reader._detached_lifecycle_receipts(decode(packet,ledger),scope=scope,source=source,
        locked_source=locked,source_lock=lock,ledger=ledger)


@pytest.mark.parametrize("legacy_fence",[False,True])
@pytest.mark.parametrize("cleanup",[False,True])
def test_detached_lifecycle_receipts_preserve_original_legacy_fence_and_extended_epoch(legacy_fence,cleanup):
    args=detached_lifecycle_context(legacy_fence=legacy_fence,cleanup_before_disable=cleanup);before=deepcopy(args)
    result=verify_detached_lifecycle_receipts(args)
    assert result.fence.phase=="fence" and result.detach.phase=="detach" and args==before
    assert not hasattr(result,"authorized") and not hasattr(result,"kind")


def test_lifecycle_receipts_retain_a_typed_refresh_reference_for_later_full_resolution():
    ref=dict(resourceType="DispatchConfigurationRefreshReceipt",resourceId=str(UUID(int=9001)),revision=1,contentHash="sha256:"+"c"*64)
    result=verify_detached_lifecycle_receipts(detached_lifecycle_context(refresh_ref=ref))
    assert result.fence.configuration_refresh_ref.resource_id==ref["resourceId"]
    # This slice does not claim that the referenced refresh history is present.
    assert result.detach.configuration_refresh_ref==result.fence.configuration_refresh_ref


@pytest.mark.parametrize("fault",["missing_lifecycle","status","actor","runtime_parent","activation_parent","group","request_hash",
    "activation_generation","activation_installation","activation_status","missing_fence","missing_event","event_type","event_parent",
    "event_hash","receipt_hash","receipt_time","authority_extra","runtime_hash","fence_ref","refresh_bool",
    "snapshot_missing","snapshot_duplicate","snapshot_bool_revision","snapshot_extra","fenced_delta","legacy_uuid",
    "current_missing","current_revision","claim_gate"])
def test_lifecycle_source_pairs_reject_incomplete_or_tampered_receipt_causes(fault):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=detached_lifecycle_context();packet=args[0]
    lifecycle=packet["relations"]["public.extension_dispatch_lifecycle_operation"][0]
    activation=packet["relations"]["public.extension_dispatch_cutover_operation"][0]
    receipts=packet["relations"]["public.extension_dispatch_lifecycle_receipt"];events=packet["relations"]["public.extension_dispatch_lifecycle_event"]
    if fault=="missing_lifecycle":packet["relations"]["public.extension_dispatch_lifecycle_operation"].clear()
    elif fault=="status":lifecycle["status"]="fenced"
    elif fault=="actor":lifecycle["requested_by"]="another-actor"
    elif fault=="runtime_parent":lifecycle["runtime_operation_id"]=str(UUID(int=9999))
    elif fault=="activation_parent":lifecycle["activation_operation_id"]=str(UUID(int=9999))
    elif fault=="group":lifecycle["cutover_group_id"]=str(UUID(int=9999))
    elif fault=="request_hash":lifecycle["request_hash"]="sha256:"+"d"*64
    elif fault=="activation_generation":activation["target_generation"]=str(UUID(int=9999))
    elif fault=="activation_installation":activation["target_installation_id"]=str(UUID(int=9999))
    elif fault=="activation_status":activation["status"]="committed"
    elif fault=="missing_fence":receipts.pop(0)
    elif fault=="missing_event":events.pop()
    elif fault=="event_type":events[-1]["event_type"]="DISPATCH_DISABLE_FENCED"
    elif fault=="event_parent":events[-1]["runtime_operation_id"]=str(UUID(int=9999))
    elif fault=="event_hash":events[-1]["payload_hash"]="sha256:"+"d"*64
    elif fault=="receipt_hash":receipts[-1]["content_hash"]="sha256:"+"d"*64
    elif fault=="receipt_time":receipts[-1]["created_at"]="2026-08-03T01:01:00+00:00"
    elif fault in {"authority_extra","runtime_hash","fence_ref","refresh_bool"}:
        body=receipts[-1]["authority_data"]
        if fault=="authority_extra":body["extra"]=1
        elif fault=="runtime_hash":body["runtimeRequestHash"]="sha256:"+"d"*64
        elif fault=="fence_ref":body["fenceReceiptRef"]["resourceId"]=str(UUID(int=9999))
        else:body["configurationRefreshRef"]=dict(resourceType="DispatchConfigurationRefreshReceipt",resourceId=str(UUID(int=9001)),revision=True,contentHash="sha256:"+"c"*64)
        receipts[-1]["content_hash"]=canonical_sha256(body);events[-1]["payload"]["contentHash"]=receipts[-1]["content_hash"]
        events[-1]["payload_hash"]=canonical_sha256(events[-1]["payload"])
    elif fault=="snapshot_missing":lifecycle["extension_snapshot"].pop()
    elif fault=="snapshot_duplicate":lifecycle["extension_snapshot"][0]=deepcopy(lifecycle["extension_snapshot"][1])
    elif fault=="snapshot_bool_revision":lifecycle["extension_snapshot"][0]["revision"]=True
    elif fault=="snapshot_extra":lifecycle["extension_snapshot"][0]["extra"]=1
    elif fault=="fenced_delta":lifecycle["fenced_snapshot"][0]["revision"]+=1
    elif fault=="legacy_uuid":lifecycle["legacy_snapshot"][0]["installationId"]=str(UUID(int=9999))
    elif fault=="current_missing":packet["relations"]["public.extension_operation_dispatch_binding"].pop()
    elif fault=="current_revision":packet["relations"]["public.extension_operation_dispatch_binding"][0]["revision"]+=1
    elif fault=="claim_gate":
        row=row_for(reader._RELATIONS["public.extension_dispatch_claim_gate"]);row.update(org_id=args[1].org_id,project_id=args[1].project_id,cutover_group_id=lifecycle["cutover_group_id"])
        packet["relations"]["public.extension_dispatch_claim_gate"].append(row)
    with pytest.raises(ValueError):verify_detached_lifecycle_receipts(args)


@pytest.mark.parametrize("fault",["snapshot_integer_fence","fence_ref_bool_revision"])
def test_rehashed_lifecycle_authority_cannot_use_python_bool_int_equality(fault):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=detached_lifecycle_context();packet=args[0]
    receipt=packet["relations"]["public.extension_dispatch_lifecycle_receipt"][-1]
    event=packet["relations"]["public.extension_dispatch_lifecycle_event"][-1]
    if fault=="snapshot_integer_fence":receipt["authority_data"]["dispatchSnapshot"][0]["operationFence"]=0
    else:receipt["authority_data"]["fenceReceiptRef"]["revision"]=True
    receipt["content_hash"]=canonical_sha256(receipt["authority_data"])
    event["payload"]["contentHash"]=receipt["content_hash"];event["payload_hash"]=canonical_sha256(event["payload"])
    with pytest.raises(ValueError):verify_detached_lifecycle_receipts(args)


def test_v7_carries_original_withdrawal_table_without_fabricated_installation_columns():
    assert reader._SCHEMA_VERSION=='aos.reinstall-terminal-source-facts/v13'
    schema=reader._RELATIONS['public.extension_dispatch_withdrawal_receipt']
    assert schema.columns==(('org_id','text!'),('project_id','text!'),('receipt_id','uuid!'),('registration_receipt_id','uuid!'),('idempotency_key','text!'),('request_hash','text!'),('payload','jsonb!'),('content_hash','text!'),('created_at','timestamp with time zone!'))
    assert schema.key==('org_id','project_id','receipt_id') and schema.cap==2048
    assert 'public.extension_dispatch_withdrawal_receipt' in reader._NONDISPATCH_EMPTY


def test_v7_preserves_v6_literal_bytes_lineage_and_requires_explicit_withdrawal_family():
    import hashlib
    root=Path(__file__).resolve().parents[4]/'.evidence/qyh-m2-terminal-source-implementation-20261025'
    prior=root/'reader-v6-schema-literal-r189.json';old=json.loads(prior.read_text());new=json.loads((root/'reader-v7-schema-literal-r203.json').read_text())
    assert new['priorLiteralSHA256']==hashlib.sha256(prior.read_bytes()).hexdigest()
    assert new['relations'][:-1]==old['relations'] and new['registry']==old['registry']
    assert new['relations'][-1]['rank']==176 and len(new['relations'][-1]['columns'])==9
    packet=empty_packet();packet['schema']='aos.reinstall-terminal-source-facts/v6'
    with pytest.raises(ValueError):decode(packet)
    packet['schema']='aos.reinstall-terminal-source-facts/v13';packet['relations'].pop('public.extension_dispatch_withdrawal_receipt',None)
    with pytest.raises(ValueError):decode(packet)


def withdrawal_origin_context(defect=None,*,count=0,idempotency_key=None):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.ecommerce_growth_registration_withdrawal import RegistrationWithdrawalRequest
    args=registration_origin_context(count=count,idempotency_key=idempotency_key);rel=args[0]['relations']
    parent=deepcopy(rel['public.extension_dispatch_registration_receipt'][0])
    origin=parent['payload'];request=origin['request']
    parent['receipt_id']=origin['receiptId']=str(UUID(int=5401))
    parent['group_id']=origin['groupId']=request['groupId']=str(UUID(int=5402))
    parent['idempotency_key']=origin['idempotencyKey']=request['idempotencyKey']='registration-prior-withdrawn'
    for item in origin['dispatchSnapshot']:item['cutoverGroupId']=parent['group_id']
    parent['request_hash']=origin['requestHash']=canonical_sha256(request);parent['content_hash']=canonical_sha256(origin)
    rel['public.extension_dispatch_registration_receipt'].append(parent)
    ref=dict(resourceType='FirstDispatchRegistrationReceipt',resourceId=parent['receipt_id'],revision=1,contentHash=parent['content_hash'])
    req=RegistrationWithdrawalRequest(registrationReceiptRef=ref,expectedInstallationEtag=request['installationRef']['revision'],idempotencyKey='pristine-withdrawal')
    body=dict(schemaVersion='aos.ecommerce.first-dispatch-withdrawal-receipt/v1',tenant=deepcopy(origin['tenant']),receiptId=str(UUID(int=5403)),
        registrationReceiptRef=deepcopy(ref),installationId=origin['installationId'],generation=origin['generation'],groupId=origin['groupId'],
        idempotencyKey=req.idempotencyKey,requestHash=req.request_hash(),actor='withdrawal-actor',request=req.model_dump(mode='json'),
        oldDispatchSnapshot=deepcopy(origin['dispatchSnapshot']),releasedOperationCount=9,executable=False,createdAt='2026-08-03T01:00:02.0001+00:00')
    row=dict(org_id=args[1].org_id,project_id=args[1].project_id,receipt_id=body['receiptId'],registration_receipt_id=origin['receiptId'],
        idempotency_key=body['idempotencyKey'],request_hash=body['requestHash'],payload=body,created_at='2026-08-03T01:00:02.000200+00:00')
    if defect=='missing-parent':rel['public.extension_dispatch_registration_receipt'].remove(parent)
    elif defect=='foreign-scope':row['org_id']='foreign'
    elif defect=='wrong-parent-id':row['registration_receipt_id']=str(UUID(int=5499))
    elif defect=='ref-hash':body['registrationReceiptRef']['contentHash']='sha256:'+'e'*64
    elif defect=='target':body['installationId']=str(UUID(int=5499))
    elif defect=='generation':body['generation']=str(UUID(int=5499))
    elif defect=='group':body['groupId']=str(UUID(int=5499))
    elif defect=='bool-etag':body['request']['expectedInstallationEtag']=True
    elif defect=='float-etag':body['request']['expectedInstallationEtag']=3.0
    elif defect=='extra':body['eligible']=True
    elif defect=='actor':body['actor']=' bad '
    elif defect=='bool-snapshot':body['oldDispatchSnapshot'][0]['revision']=True
    elif defect=='float-snapshot':body['oldDispatchSnapshot'][0]['revision']=1.0
    elif defect=='snapshot-order':body['oldDispatchSnapshot'].reverse()
    elif defect=='wrong-count':body['releasedOperationCount']=8
    elif defect=='executable':body['executable']=True
    elif defect=='body-after-row':body['createdAt']='2026-08-03T01:00:03+00:00'
    elif defect=='before-parent':body['createdAt']='2026-08-03T01:00:01+00:00'
    elif defect=='naive-time':body['createdAt']='2026-08-03T01:00:02'
    elif defect in ('consumed-parent','legacy-cutover'):
        parent=rel['public.extension_dispatch_registration_receipt'][0];origin=parent['payload']
        newref=dict(resourceType='FirstDispatchRegistrationReceipt',resourceId=origin['receiptId'],revision=1,contentHash=parent['content_hash'])
        body['registrationReceiptRef']=deepcopy(newref);body['request']['registrationReceiptRef']=deepcopy(newref)
        row['registration_receipt_id']=origin['receiptId'];body['groupId']=origin['groupId'];body['oldDispatchSnapshot']=deepcopy(origin['dispatchSnapshot'])
        if defect=='legacy-cutover':
            other=detached_refresh_context(0)
            for family in ('public.extension_dispatch_cutover_operation','public.extension_dispatch_cutover_receipt','public.extension_dispatch_cutover_event'):
                rel[family]=deepcopy(other[0]['relations'][family])
    row['request_hash']=body['requestHash']=canonical_sha256(body['request'])
    if defect=='request-hash':row['request_hash']=body['requestHash']='sha256:'+'e'*64
    row['content_hash']=canonical_sha256(body)
    if defect=='content-hash':row['content_hash']='sha256:'+'e'*64
    rel['public.extension_dispatch_withdrawal_receipt']=[row]
    if defect in ('duplicate-key','duplicate-parent'):
        other=deepcopy(row);other['receipt_id']=other['payload']['receiptId']=str(UUID(int=5404))
        if defect=='duplicate-parent':other['idempotency_key']=other['payload']['idempotencyKey']=other['payload']['request']['idempotencyKey']='other-withdrawal'
        else:
            # Isolate the key UNIQUE rule with a different, independently valid parent.
            second=deepcopy(parent);ob=second['payload'];orq=ob['request']
            second['receipt_id']=ob['receiptId']=str(UUID(int=5411));second['group_id']=ob['groupId']=orq['groupId']=str(UUID(int=5412))
            second['idempotency_key']=ob['idempotencyKey']=orq['idempotencyKey']='another-original-registration'
            for item in ob['dispatchSnapshot']:item['cutoverGroupId']=second['group_id']
            second['request_hash']=ob['requestHash']=canonical_sha256(orq);second['content_hash']=canonical_sha256(ob)
            rel['public.extension_dispatch_registration_receipt'].append(second)
            sr=dict(resourceType='FirstDispatchRegistrationReceipt',resourceId=second['receipt_id'],revision=1,contentHash=second['content_hash'])
            other['registration_receipt_id']=second['receipt_id'];other['payload']['registrationReceiptRef']=deepcopy(sr)
            other['payload']['request']['registrationReceiptRef']=deepcopy(sr);other['payload']['groupId']=second['group_id']
            other['payload']['oldDispatchSnapshot']=deepcopy(ob['dispatchSnapshot'])
        other['request_hash']=other['payload']['requestHash']=canonical_sha256(other['payload']['request']);other['content_hash']=canonical_sha256(other['payload'])
        rel['public.extension_dispatch_withdrawal_receipt'].append(other)
    return args


def verify_withdrawal_history(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    cutovers=reader._cutover_history(facts,scope=scope,source=source,ledger=ledger)
    return reader._withdrawal_history(facts,cutovers,scope=scope,source=source,ledger=ledger)


def test_withdrawal_history_resolves_actual_first_parent_but_preserves_unproved_pristine_dependencies_and_cas():
    args=withdrawal_origin_context();before=deepcopy(args[0]);graph=verify_withdrawal_history(args)
    assert graph.withdrawn_origins==(UUID(int=5401),)
    assert graph.receipts[UUID(int=5403)]['registration_receipt_id']==UUID(int=5401)
    assert graph.pending_dependency_origins==(UUID(int=5401),)
    assert graph.pending_installation_etags[UUID(int=5403)]==args[0]['relations']['public.extension_dispatch_registration_receipt'][1]['payload']['request']['installationRef']['revision']
    assert verify_registration_history(args).unconsumed==(('FirstDispatchRegistrationReceipt',UUID(int=5401)),)
    assert args[0]==before and not hasattr(graph,'authorized') and not hasattr(graph,'kind')


def test_empty_withdrawal_history_does_not_invent_retirement():
    graph=verify_withdrawal_history(registration_origin_context())
    assert not graph.receipts and not graph.withdrawn_origins and not graph.pending_dependency_origins and not graph.pending_installation_etags


@pytest.mark.parametrize('defect',['missing-parent','foreign-scope','wrong-parent-id','ref-hash','target','generation','group','bool-etag','float-etag',
    'extra','actor','bool-snapshot','float-snapshot','snapshot-order','wrong-count','executable','body-after-row','before-parent','naive-time',
    'consumed-parent','legacy-cutover','request-hash','content-hash','duplicate-key','duplicate-parent'])
def test_withdrawal_history_rejects_rehashed_invalid_origin_projection_shape_and_history(defect):
    with pytest.raises(ValueError):verify_withdrawal_history(withdrawal_origin_context(defect))


def test_detached_registration_joins_withdrawal_from_same_facts_without_erasing_unresolved_admission():
    graph=verify_detached_registration(withdrawal_origin_context())
    assert graph.withdrawals.withdrawn_origins==(UUID(int=5401),)
    assert graph.withdrawals.pending_dependency_origins==(UUID(int=5401),)
    assert graph.registrations.unconsumed==(('FirstDispatchRegistrationReceipt',UUID(int=5401)),)
    assert graph.control.timeline.before_uninstall_revision==8


@pytest.mark.parametrize('defect',['duplicate-key','duplicate-parent'])
def test_withdrawal_uniqueness_corruptions_are_individually_valid_original_receipts(defect):
    from aos_api.ecommerce_growth_withdrawal_receipt import decode_withdrawal_receipt
    args=withdrawal_origin_context(defect);rel=args[0]['relations'];parents={r['receipt_id']:r for r in rel['public.extension_dispatch_registration_receipt']}
    for row in rel['public.extension_dispatch_withdrawal_receipt']:
        assert decode_withdrawal_receipt(row,registration_row=parents[row['registration_receipt_id']],scope=args[1])['executable'] is False
    with pytest.raises(ValueError):verify_withdrawal_history(args)



def test_v8_carries_original_runtime_command_journal_including_historical_dispatch_independence():
    assert reader._SCHEMA_VERSION=='aos.reinstall-terminal-source-facts/v13'
    schema=reader._RELATIONS['public.ecommerce_growth_runtime_command_receipt']
    assert schema.columns==(('org_id','text!'),('project_id','text!'),('operation_id','text!'),('idempotency_key','text!'),('request_hash','text!'),('dispatch_revision','bigint!'),('installation_id','uuid!'),('generation','uuid!'),('execution_epoch','bigint!'),('cutover_group_id','uuid!'),('cutover_group_revision','bigint!'),('runtime_revision','bigint!'),('response','jsonb!'),('target_receipt_ref','jsonb!'),('actor','text!'),('occurred_at','timestamp with time zone!'))
    assert schema.key==('org_id','project_id','operation_id','idempotency_key') and schema.cap==2048
    assert 'public.ecommerce_growth_runtime_command_receipt' in reader._NONDISPATCH_EMPTY


def test_v8_literal_preserves_v7_bytes_lineage_and_requires_command_receipt_family():
    import hashlib
    root=Path(__file__).resolve().parents[4]/'.evidence/qyh-m2-terminal-source-implementation-20261025'
    prior=root/'reader-v7-schema-literal-r203.json';old=json.loads(prior.read_text());new=json.loads((root/'reader-v8-schema-literal-r213.json').read_text())
    assert new['priorLiteralSHA256']==hashlib.sha256(prior.read_bytes()).hexdigest()
    assert new['relations'][:-1]==old['relations'] and new['registry']==old['registry']
    assert new['relations'][-1]['rank']==177 and len(new['relations'][-1]['columns'])==16
    packet=empty_packet();packet['schema']='aos.reinstall-terminal-source-facts/v7'
    with pytest.raises(ValueError):decode(packet)
    packet['schema']='aos.reinstall-terminal-source-facts/v13';packet['relations'].pop('public.ecommerce_growth_runtime_command_receipt',None)
    with pytest.raises(ValueError):decode(packet)


COMMAND_OPERATIONS=(
    'ecommerce_growth_investigation_describe','ecommerce_growth_case_put','ecommerce_growth_schedule_put',
    'ecommerce_growth_schedule_trigger','ecommerce_growth_data_fulfill','ecommerce_growth_analysis_advance',
    'ecommerce_growth_review_advance','ecommerce_growth_content_generate','ecommerce_growth_content_review','ecommerce_growth_event_control')


def command_history_context(operation='ecommerce_growth_analysis_advance',defect=None):
    args=withdrawal_origin_context();rel=args[0]['relations']
    target=dict(resourceType='AnalysisReceipt',resourceId='historical-analysis-target',revision=1,contentHash='sha256:'+'c'*64)
    row=dict(org_id=args[1].org_id,project_id=args[1].project_id,operation_id=operation,idempotency_key='command-key',request_hash='sha256:'+'a'*64,
        dispatch_revision=2,installation_id=args[2].installation_id,generation=str(UUID(int=5800)),execution_epoch=3,
        cutover_group_id=str(UUID(int=5801)),cutover_group_revision=2,runtime_revision=6,response=dict(targetReceiptRef=deepcopy(target),requestHash='sha256:'+'a'*64,status='done'),
        target_receipt_ref=target,actor='command-actor',occurred_at='2026-08-03T02:00:00+00:00')
    if defect=='operation':row['operation_id']='invented-operation'
    elif defect=='scope':row['project_id']='foreign'
    elif defect=='key-blank':row['idempotency_key']=' '
    elif defect=='key-pad':row['idempotency_key']=' padded '
    elif defect=='key-long':row['idempotency_key']='x'*201
    elif defect=='actor-blank':row['actor']=' '
    elif defect=='actor-pad':row['actor']=' padded '
    elif defect=='actor-long':row['actor']='x'*241
    elif defect=='request-hash':row['request_hash']='invalid'
    elif defect in ('dispatch_revision','execution_epoch','cutover_group_revision','runtime_revision'):row[defect]=0
    elif defect=='target-extra':target['allowed']=True
    elif defect=='target-bool':target['revision']=True
    elif defect=='target-float':target['revision']=1.0
    elif defect=='target-missing':target.pop('resourceType')
    elif defect=='target-empty':target['resourceId']=' '
    elif defect=='target-hash':target['contentHash']='invalid'
    elif defect=='target-receipt-empty':target['receiptId']=''
    elif defect=='response-empty':row['response']={}
    elif defect=='response-nested':row['response']=dict(wrapper=dict(targetReceiptRef=deepcopy(target)))
    elif defect=='response-ref-drift':row['response']['targetReceiptRef']['revision']=2
    elif defect=='response-request-hash':row['response']['requestHash']='sha256:'+'b'*64
    elif defect=='naive-time':row['occurred_at']='2026-08-03T02:00:00'
    elif defect=='historical-other-installation':row['installation_id']=str(UUID(int=5900))
    elif defect=='late-caller-time':row['occurred_at']='2099-01-01T00:00:00+00:00'
    if defect and defect.startswith('target-'):
        row['response']['targetReceiptRef']=deepcopy(target)
    rel['public.ecommerce_growth_runtime_command_receipt']=[row]
    if defect=='duplicate-key':rel['public.ecommerce_growth_runtime_command_receipt'].append(deepcopy(row))
    return args


def verify_command_history(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    return reader._runtime_command_history(decode(packet,ledger),scope=scope,ledger=ledger)


@pytest.mark.parametrize('operation',COMMAND_OPERATIONS)
def test_command_history_retains_all_original_nine_and_tenth_operations_as_unresolved_actual_parents(operation):
    args=command_history_context(operation);before=deepcopy(args[0]);graph=verify_command_history(args);key=(operation,'command-key')
    assert set(graph.records)=={key} and key in graph.pending_dispatch_sources and key in graph.pending_target_refs
    assert graph.pending_target_refs[key]['resourceId']=='historical-analysis-target'
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind') and args[0]==before


@pytest.mark.parametrize('defect',['operation','scope','key-blank','key-pad','key-long','actor-blank','actor-pad','actor-long','request-hash',
    'dispatch_revision','execution_epoch','cutover_group_revision','runtime_revision','target-extra','target-bool','target-float','target-missing',
    'target-empty','target-hash','target-receipt-empty','response-empty','response-nested','response-ref-drift','response-request-hash','naive-time','duplicate-key'])
def test_command_history_reuses_original_target_response_contract_and_rejects_invalid_stored_shapes(defect):
    with pytest.raises(ValueError):verify_command_history(command_history_context(defect=defect))


@pytest.mark.parametrize('defect',['historical-other-installation','late-caller-time'])
def test_command_history_does_not_invent_current_dispatch_fk_or_database_insertion_clock(defect):
    graph=verify_command_history(command_history_context(defect=defect))
    assert len(graph.records)==1 and len(graph.pending_dispatch_sources)==1 and len(graph.pending_target_refs)==1


def test_command_history_empty_family_does_not_invent_an_execution_receipt():
    graph=verify_command_history(withdrawal_origin_context())
    assert not graph.records and not graph.pending_dispatch_sources and not graph.pending_target_refs


@pytest.mark.parametrize('defect',['historical-other-installation','late-caller-time'])
def test_withdrawal_dependency_observation_covers_same_tenant_operation_across_installations_and_times(defect):
    graph=verify_withdrawal_history(command_history_context(defect=defect))
    assert graph.observed_current_dependencies[UUID(int=5401)]==(('command','ecommerce_growth_analysis_advance','command-key'),)
    assert graph.pending_dependency_origins==(UUID(int=5401),)


def test_tenth_command_remains_explicit_but_is_not_invented_as_one_of_the_original_nine_withdrawal_dependencies():
    args=command_history_context('ecommerce_growth_event_control');graph=verify_withdrawal_history(args)
    assert graph.observed_current_dependencies[UUID(int=5401)]==()
    assert len(verify_command_history(args).pending_target_refs)==1
    assert graph.pending_dependency_origins==(UUID(int=5401),)


def test_disabled_unapproved_foreign_installation_schedule_is_still_observed_by_original_operation_predicate():
    args=withdrawal_origin_context();schema=reader._RELATIONS['public.automation_schedule_binding'];row=row_for(schema)
    row.update(org_id=args[1].org_id,project_id=args[1].project_id,operation_id='ecommerce_growth_analysis_advance',
        policy_id='historical-policy',policy_revision=2,installation_id=str(UUID(int=5999)),approved=False,enabled=False)
    args[0]['relations']['public.automation_schedule_binding']=[row]
    graph=verify_withdrawal_history(args)
    assert graph.observed_current_dependencies[UUID(int=5401)]==(('schedule','ecommerce_growth_analysis_advance','historical-policy',2),)
    assert graph.pending_dependency_origins==(UUID(int=5401),)


@pytest.mark.parametrize('bound',['below-origin','after-terminal'])
def test_withdrawal_etag_must_be_within_original_monotonic_installation_revision_bounds(bound):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=withdrawal_origin_context();rel=args[0]['relations'];parent=rel['public.extension_dispatch_registration_receipt'][1]
    minimum=parent['payload']['request']['installationRef']['revision'];assert minimum>1
    row=rel['public.extension_dispatch_withdrawal_receipt'][0];body=row['payload']
    body['request']['expectedInstallationEtag']=minimum-1 if bound=='below-origin' else args[2].terminal_revision+1
    row['request_hash']=body['requestHash']=canonical_sha256(body['request']);row['content_hash']=canonical_sha256(body)
    with pytest.raises(ValueError):verify_withdrawal_history(args)


def test_original_withdrawal_contract_can_run_at_terminal_installation_etag_and_does_not_imply_cas_provenance():
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=withdrawal_origin_context();row=args[0]['relations']['public.extension_dispatch_withdrawal_receipt'][0];body=row['payload']
    body['request']['expectedInstallationEtag']=args[2].terminal_revision
    row['request_hash']=body['requestHash']=canonical_sha256(body['request']);row['content_hash']=canonical_sha256(body)
    graph=verify_withdrawal_history(args)
    assert graph.pending_installation_etags[UUID(int=5403)]==args[2].terminal_revision


def test_detached_registration_includes_command_history_and_withdrawal_observation_from_one_input():
    graph=verify_detached_registration(command_history_context())
    key=('ecommerce_growth_analysis_advance','command-key')
    assert key in graph.commands.records and key in graph.commands.pending_dispatch_sources and key in graph.commands.pending_target_refs
    assert graph.withdrawals.observed_current_dependencies[UUID(int=5401)]==(('command',*key),)
    assert graph.withdrawals.pending_dependency_origins==(UUID(int=5401),)
    assert graph.registrations.unconsumed==(('FirstDispatchRegistrationReceipt',UUID(int=5401)),)


def test_detached_registration_rejects_invalid_runtime_receipt_response_instead_of_ignoring_the_new_family():
    with pytest.raises(ValueError):verify_detached_registration(command_history_context(defect='response-ref-drift'))


def test_detached_registration_preserves_tenth_runtime_receipt_with_unresolved_source_and_target():
    graph=verify_detached_registration(command_history_context('ecommerce_growth_event_control'))
    assert ('ecommerce_growth_event_control','command-key') in graph.commands.pending_target_refs
    assert not graph.withdrawals.observed_current_dependencies[UUID(int=5401)]


@pytest.mark.parametrize('padding',['\t','\u00a0'])
def test_command_history_preserves_native_sql_btrim_semantics_instead_of_imposing_python_strip_on_history(padding):
    args=command_history_context();row=args[0]['relations']['public.ecommerce_growth_runtime_command_receipt'][0]
    row['idempotency_key']=padding+'command-key'+padding;row['actor']=padding+'command-actor'+padding
    graph=verify_command_history(args)
    assert ('ecommerce_growth_analysis_advance',row['idempotency_key']) in graph.records



def test_v9_requires_a_distinct_actual_table_predecessor_partition_with_one_shared_packet_budget():
    assert reader._SCHEMA_VERSION=='aos.reinstall-terminal-source-facts/v13'
    assert len(reader._PREDECESSOR_RELATIONS)==32
    assert reader._RELATIONS['public.extension_runtime_binding'].cap==1
    assert reader._PREDECESSOR_RELATIONS['public.extension_runtime_binding'].cap==2048
    assert reader._MAX_PACKET_ROWS==8192 and reader._MAX_PACKET_BYTES==8*1024*1024
    packet=empty_packet();facts=decode(packet)
    assert len(facts.predecessors)==32 and not any(facts.predecessors.values())


def test_v9_predecessor_literal_preserves_all_v8_native_columns_and_only_expands_old_binding_set_cap():
    import hashlib
    root=Path(__file__).resolve().parents[4]/'.evidence/qyh-m2-terminal-source-implementation-20261025'
    prior=root/'reader-v8-schema-literal-r213.json';old=json.loads(prior.read_text());new=json.loads((root/'reader-v9-schema-literal-r225.json').read_text())
    assert new['priorLiteralSHA256']==hashlib.sha256(prior.read_bytes()).hexdigest()
    assert new['relations']==old['relations'] and new['registry']==old['registry']
    original={x['name']:x for x in old['relations']};expected={x['name']:x for x in new['predecessors']}
    assert set(expected) < set(reader._PREDECESSOR_RELATIONS)
    for name in expected:
        schema=reader._PREDECESSOR_RELATIONS[name]
        item=expected[name];assert item['columns']==original[name]['columns'] and item['key']==original[name]['key']
        assert schema.columns==tuple(tuple(c) for c in item['columns'])
        expected_key=tuple(item['key']) if not name.endswith('configuration_refresh_receipt') else ('org_id','project_id','cutover_group_id','activation_operation_id','revision')
        assert schema.key==expected_key
        assert schema.cap==item['cap']==(2048 if name=='public.extension_runtime_binding' else original[name]['cap'])


def test_v8_or_omitted_predecessor_partition_is_never_invented_as_empty_complete_source():
    packet=empty_packet();packet['schema']='aos.reinstall-terminal-source-facts/v8'
    with pytest.raises(ValueError):decode(packet)
    packet['schema']='aos.reinstall-terminal-source-facts/v13';packet.pop('predecessors',None)
    with pytest.raises(ValueError):decode(packet)


PREDECESSOR_FAMILIES=tuple('public.'+name for name in (
    'extension_runtime_binding','extension_runtime_operation','extension_runtime_event','extension_runtime_outbox',
    'extension_runtime_configuration','extension_runtime_dependency_ref','extension_runtime_resource_lease',
    'extension_runtime_execution_attempt','extension_runtime_execution_attempt_event','extension_operation_dispatch_binding',
    'extension_dispatch_claim_gate','extension_dispatch_cutover_operation','extension_dispatch_cutover_receipt',
    'extension_dispatch_cutover_event','extension_dispatch_cutover_approval_refresh_receipt','extension_dispatch_configuration_refresh_receipt',
    'extension_dispatch_lifecycle_operation','extension_dispatch_lifecycle_receipt','extension_dispatch_lifecycle_event',
    'automation_occurrence','automation_occurrence_dispatch_attempt'))


def add_predecessor_binding(packet,scope=None):
    packet['predecessors']={name:[] for name in reader._PREDECESSOR_RELATIONS}
    row=row_for(reader._RELATIONS['public.extension_runtime_binding'])
    if scope:row.update(org_id=scope.org_id,project_id=scope.project_id)
    row.update(installation_id=str(UUID(int=7000)),generation=str(UUID(int=7001)),desired_state='disabled',observed_state='unknown',enabled=False,operation_fence=True)
    packet['predecessors']['public.extension_runtime_binding']=[row]
    return row


@pytest.mark.parametrize('family',PREDECESSOR_FAMILIES)
def test_v9_every_predecessor_family_is_mandatory_even_when_empty(family):
    packet=empty_packet();packet['predecessors']={name:[] for name in reader._PREDECESSOR_RELATIONS};packet['predecessors'].pop(family)
    with pytest.raises(ValueError):decode(packet)


def test_v9_predecessor_bindings_are_separate_bounded_owned_rows_not_current_source_bindings():
    packet=empty_packet();row=add_predecessor_binding(packet);second=deepcopy(row);second['installation_id']=str(UUID(int=7002))
    packet['predecessors']['public.extension_runtime_binding'].append(second)
    shared={'nested':['old']};row['package_lock_ref']=shared;row['config_ref']=shared;before=deepcopy(packet)
    facts=decode(packet);rows=facts.predecessors['public.extension_runtime_binding'];assert len(rows)==2
    assert not facts.relations['public.extension_runtime_binding']
    rows[0]['package_lock_ref']['nested'].append('owned')
    assert rows[0]['config_ref']==shared and packet==before


@pytest.mark.parametrize('defect',['duplicate','column-extra','column-missing','uuid','bool','time','family-extra'])
def test_v9_predecessor_decode_preserves_native_primary_key_column_and_scalar_guards(defect):
    packet=empty_packet();row=add_predecessor_binding(packet)
    if defect=='duplicate':packet['predecessors']['public.extension_runtime_binding'].append(deepcopy(row))
    elif defect=='column-extra':row['authorized']=True
    elif defect=='column-missing':row.pop('generation')
    elif defect=='uuid':row['installation_id']='invalid'
    elif defect=='bool':row['enabled']=1
    elif defect=='time':
        value=row_for(reader._RELATIONS['public.extension_runtime_event']);value['occurred_at']='2026-10-26T00:00:00'
        packet['predecessors']['public.extension_runtime_event']=[value]
    else:packet['predecessors']['public.invented_table']=[]
    with pytest.raises(ValueError):decode(packet)


def test_v9_predecessor_rows_share_the_original_whole_packet_row_limit(monkeypatch):
    packet=empty_packet();add_predecessor_binding(packet)
    row=row_for(reader._RELATIONS['public.extension_runtime_operation']);second=deepcopy(row);second['operation_id']=str(UUID(int=7003))
    packet['relations']['public.extension_runtime_operation']=[row,second]
    monkeypatch.setattr(reader,'_MAX_PACKET_ROWS',2)
    with pytest.raises(ValueError,match='budget'):decode(packet)


def test_detached_registration_explicitly_retains_unconsumed_predecessor_input_without_granting_parent_qualification():
    args=registration_origin_context();before=add_predecessor_binding(args[0],args[1]);graph=verify_detached_registration(args)
    rows=graph.pending_predecessor_input['public.extension_runtime_binding']
    assert rows[0]['installation_id']==UUID(before['installation_id'])
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind')


def test_detached_registration_does_not_ignore_foreign_tenant_predecessor_rows():
    args=registration_origin_context();row=add_predecessor_binding(args[0],args[1]);row['org_id']='foreign'
    with pytest.raises(ValueError):verify_detached_registration(args)


@pytest.mark.parametrize('branch',['nondispatch','unbound'])
def test_existing_terminal_slices_cannot_ignore_unconsumed_nonempty_predecessor_input(branch):
    args=nondispatch_context('never_enabled') if branch=='nondispatch' else source_history_context()
    add_predecessor_binding(args[0],args[1])
    with pytest.raises(ValueError):
        verify_nondispatch_source(args) if branch=='nondispatch' else verify_unbound_source(args)


def test_v9_predecessor_binding_capacity_does_not_expand_current_source_single_binding_limit():
    packet=empty_packet();first=add_predecessor_binding(packet);second=deepcopy(first);second['installation_id']=str(UUID(int=7004))
    packet['predecessors']['public.extension_runtime_binding'].append(second)
    assert len(decode(packet).predecessors['public.extension_runtime_binding'])==2
    packet['relations']['public.extension_runtime_binding']=[deepcopy(first),deepcopy(second)]
    with pytest.raises(ValueError):decode(packet)


def test_source_selection_checks_predecessor_tenant_without_claiming_parent_qualification():
    packet,scope,source,locked,lock=source_history_context();row=add_predecessor_binding(packet,scope)
    ledger=reader._WorkLedger();facts=decode(packet,ledger)
    assert reader._source_selection(facts,scope,lock,ledger)[0].lock_hash==lock.lock_hash
    row['project_id']='foreign';ledger=reader._WorkLedger();facts=decode(packet,ledger)
    with pytest.raises(ValueError):reader._source_selection(facts,scope,lock,ledger)


def lifecycle_pair_inputs(*,legacy_fence=False,cleanup=False,refresh_ref=None):
    args=detached_lifecycle_context(legacy_fence=legacy_fence,cleanup_before_disable=cleanup,refresh_ref=refresh_ref)
    ledger=reader._WorkLedger();facts=decode(args[0],ledger);rel=facts.relations
    lifecycle=rel['public.extension_dispatch_lifecycle_operation'][0]
    runtime=next(r for r in rel['public.extension_runtime_operation'] if r['operation_id']==lifecycle['runtime_operation_id'])
    activation=next(r for r in rel['public.extension_dispatch_cutover_operation'] if r['cutover_operation_id']==lifecycle['activation_operation_id'])
    fenced=reader._snapshot9(lifecycle['fenced_snapshot'],lifecycle['cutover_group_id'],ledger)
    detached=tuple(dict(old,revision=held['revision']+1,cutoverGroupRevision=lifecycle['fenced_group_revision']+1) for old,held in zip(lifecycle['legacy_snapshot'],fenced))
    return dict(receipts=list(map(dict,rel['public.extension_dispatch_lifecycle_receipt'])),events=list(map(dict,rel['public.extension_dispatch_lifecycle_event'])),
        scope=args[1],runtime=dict(runtime),activation=dict(activation),lifecycle=dict(lifecycle),fenced=fenced,detached=detached,ledger=ledger)


@pytest.mark.parametrize('legacy_fence',[False,True])
@pytest.mark.parametrize('cleanup',[False,True])
def test_shared_lifecycle_pair_uses_original_builders_without_requiring_any_installation_terminal_record(legacy_fence,cleanup):
    pair=reader._lifecycle_receipt_pair(**lifecycle_pair_inputs(legacy_fence=legacy_fence,cleanup=cleanup))
    assert pair.fence.phase=='fence' and pair.detach.phase=='detach'
    assert not hasattr(pair,'authorized') and not hasattr(pair,'kind')


def test_shared_lifecycle_pair_preserves_refresh_as_unresolved_exact_reference():
    ref=dict(resourceType='DispatchConfigurationRefreshReceipt',resourceId=str(UUID(int=9001)),revision=1,contentHash='sha256:'+'c'*64)
    pair=reader._lifecycle_receipt_pair(**lifecycle_pair_inputs(refresh_ref=ref))
    assert pair.fence.configuration_refresh_ref.resource_id==ref['resourceId']
    assert pair.detach.configuration_refresh_ref==pair.fence.configuration_refresh_ref


@pytest.mark.parametrize('defect',['receipt-scope','event-scope','runtime-scope','activation-scope','lifecycle-scope','runtime-parent','activation-parent',
    'actor','status','runtime-hash','activation-hash','receipt-missing','event-missing','event-type','event-time','receipt-extra'])
def test_shared_lifecycle_pair_rejects_projection_scope_parent_and_original_builder_drift(defect):
    args=lifecycle_pair_inputs()
    if defect=='receipt-scope':args['receipts'][0]['org_id']='foreign'
    elif defect=='event-scope':args['events'][0]['project_id']='foreign'
    elif defect in ('runtime-scope','activation-scope','lifecycle-scope'):args[defect.split('-')[0]]['org_id']='foreign'
    elif defect=='runtime-parent':args['runtime']['operation_id']=UUID(int=9999)
    elif defect=='activation-parent':args['activation']['cutover_operation_id']=UUID(int=9999)
    elif defect=='actor':args['lifecycle']['requested_by']='different'
    elif defect=='status':args['lifecycle']['status']='fenced'
    elif defect=='runtime-hash':args['runtime']['request_hash']='sha256:'+'d'*64
    elif defect=='activation-hash':args['activation']['request_hash']='sha256:'+'d'*64
    elif defect=='receipt-missing':args['receipts'].pop()
    elif defect=='event-missing':args['events'].pop()
    elif defect=='event-type':args['events'][1]['event_type']='DISPATCH_DISABLE_FENCED'
    elif defect=='event-time':
        from datetime import timedelta
        args['events'][1]['occurred_at']+=timedelta(microseconds=1)
    elif defect=='receipt-extra':args['receipts'][1]['authority_data']['authorized']=True
    with pytest.raises(ValueError):reader._lifecycle_receipt_pair(**args)



def test_current_terminal_lifecycle_calls_the_single_shared_pair_kernel_once(monkeypatch):
    original=reader._lifecycle_receipt_pair;calls=[]
    def capture(*args,**kwargs):
        calls.append(kwargs['runtime']['operation_id'])
        return original(*args,**kwargs)
    monkeypatch.setattr(reader,'_lifecycle_receipt_pair',capture)
    graph=verify_detached_lifecycle_receipts(detached_lifecycle_context())
    assert calls==[graph.lifecycle['runtime_operation_id']]


def test_shared_lifecycle_pair_work_budget_refuses_before_original_builder_allocation(monkeypatch):
    args=lifecycle_pair_inputs();ledger=args['ledger'];ledger._charge(rows=reader._MAX_ROW_VISITS-ledger.row_visits)
    calls=[]
    def forbidden(*a,**k):
        calls.append(True)
        raise AssertionError('builder must not run after exhausted work budget')
    monkeypatch.setattr(reader.EcommerceGrowthDisableDependent,'_authority',forbidden)
    with pytest.raises(ValueError):reader._lifecycle_receipt_pair(**args)
    assert not calls


@pytest.mark.parametrize('count',range(5))
def test_shared_cutover_history_accepts_actual_installation_uuid_without_fabricated_terminal_source(count):
    args=cutover_forward_context(count);ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    graph=reader._cutover_history_for_installation(facts,scope=args[1],installation_id=UUID(args[2].installation_id),ledger=ledger)
    assert len(graph.activations[UUID(int=4000)].receipts)==count
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind')


def test_shared_cutover_history_preserves_original_rollback_parent_join():
    args=cutover_rollback_context();ledger=reader._WorkLedger()
    graph=reader._cutover_history_for_installation(decode(args[0],ledger),scope=args[1],installation_id=UUID(args[2].installation_id),ledger=ledger)
    assert len(graph.activations)==1 and len(graph.rollbacks)==1 and len(graph.rollback_by_parent)==1


@pytest.mark.parametrize('value',[UUID_TEXT,None,1,True,UUID(int=9999)])
def test_shared_cutover_history_requires_exact_real_target_uuid_and_matching_rows(value):
    args=cutover_forward_context();ledger=reader._WorkLedger()
    with pytest.raises(ValueError):reader._cutover_history_for_installation(decode(args[0],ledger),scope=args[1],installation_id=value,ledger=ledger)


def test_current_cutover_history_delegates_once_to_the_shared_actual_installation_kernel(monkeypatch):
    args=cutover_forward_context();original=reader._cutover_history_for_installation;calls=[]
    def capture(*a,**k):calls.append(k['installation_id']);return original(*a,**k)
    monkeypatch.setattr(reader,'_cutover_history_for_installation',capture)
    ledger=reader._WorkLedger();reader._cutover_history(decode(args[0],ledger),scope=args[1],source=args[2],ledger=ledger)
    assert calls==[UUID(args[2].installation_id)]


PREDECESSOR_C_FAMILIES=('public.extension_dispatch_cutover_operation','public.extension_dispatch_cutover_receipt',
    'public.extension_dispatch_cutover_event','public.extension_dispatch_cutover_approval_refresh_receipt')


def predecessor_cutover_context(count=4):
    args=cutover_forward_context(count)
    for family in PREDECESSOR_C_FAMILIES:
        args[0]['predecessors'][family]=args[0]['relations'][family]
        args[0]['relations'][family]=[]
    return args


def verify_predecessor_cutovers(args):
    ledger=reader._WorkLedger()
    return reader._predecessor_cutover_history(decode(args[0],ledger),scope=args[1],ledger=ledger)


def test_predecessor_cutovers_read_real_native_rows_without_current_source_cutover_substitution():
    args=predecessor_cutover_context();before=deepcopy(args[0]);graph=verify_predecessor_cutovers(args)
    installation=UUID(args[2].installation_id)
    assert graph.operation_installations[UUID(int=4000)]==installation
    assert len(graph.histories[installation].activations[UUID(int=4000)].receipts)==4
    assert args[0]==before and not hasattr(graph,'authorized') and not hasattr(graph,'kind')


@pytest.mark.parametrize('defect',['scope','orphan-receipt','orphan-event','missing-event','unknown-status','duplicate-event-id'])
def test_predecessor_cutovers_reject_incomplete_or_cross_tenant_native_parent_history(defect):
    args=predecessor_cutover_context();p=args[0]['predecessors'];op=p[PREDECESSOR_C_FAMILIES[0]][0]
    if defect=='scope':op['project_id']='foreign'
    elif defect=='orphan-receipt':p[PREDECESSOR_C_FAMILIES[1]][0]['cutover_operation_id']=str(UUID(int=9999))
    elif defect=='orphan-event':p[PREDECESSOR_C_FAMILIES[2]][0]['cutover_operation_id']=str(UUID(int=9999))
    elif defect=='missing-event':p[PREDECESSOR_C_FAMILIES[2]].pop()
    elif defect=='unknown-status':op['status']='needs_attention'
    else:p[PREDECESSOR_C_FAMILIES[2]][1]['event_id']=p[PREDECESSOR_C_FAMILIES[2]][0]['event_id']
    with pytest.raises(ValueError):verify_predecessor_cutovers(args)


def test_empty_predecessor_cutover_input_does_not_invent_an_old_root():
    graph=verify_predecessor_cutovers(registration_origin_context())
    assert not graph.histories and not graph.operation_installations


def original_second_installation_prepared_cutover(key='distinct-old-root'):
    from tests.asset_registry import test_composition_contracts as original
    # Rebuild every original record component from one constructor identity.
    with mock.patch.object(original,'INSTALLATION_ID',str(UUID(int=8000))):
        return cutover_prepare_context(activation_id=5000,idempotency_key=key)


def test_predecessor_cutovers_partition_two_normally_constructed_installations_using_actual_native_targets():
    args=predecessor_cutover_context();other=original_second_installation_prepared_cutover()
    assert args[2].installation_id!=other[2].installation_id
    for family in PREDECESSOR_C_FAMILIES:args[0]['predecessors'][family].extend(deepcopy(other[0]['relations'][family]))
    graph=verify_predecessor_cutovers(args)
    assert set(graph.histories)=={UUID(args[2].installation_id),UUID(other[2].installation_id)}
    assert graph.operation_installations[UUID(int=5000)]==UUID(other[2].installation_id)
    assert not graph.histories[UUID(other[2].installation_id)].activations[UUID(int=5000)].receipts


def test_predecessor_cutover_idempotency_is_tenant_wide_not_reset_per_installation():
    args=predecessor_cutover_context();key=args[0]['predecessors'][PREDECESSOR_C_FAMILIES[0]][0]['idempotency_key']
    other=original_second_installation_prepared_cutover(key)
    isolated=deepcopy(other[0])
    for family in PREDECESSOR_C_FAMILIES:isolated['predecessors'][family]=isolated['relations'][family];isolated['relations'][family]=[]
    assert len(verify_predecessor_cutovers((isolated,*other[1:])).histories)==1
    for family in PREDECESSOR_C_FAMILIES:args[0]['predecessors'][family].extend(deepcopy(other[0]['relations'][family]))
    with pytest.raises(ValueError):verify_predecessor_cutovers(args)


def test_detached_registration_exposes_actual_predecessor_cutovers_but_keeps_remaining_old_parent_input_pending():
    args=registration_origin_context();other=original_second_installation_prepared_cutover()
    for family in PREDECESSOR_C_FAMILIES:args[0]['predecessors'][family]=deepcopy(other[0]['relations'][family])
    graph=verify_detached_registration(args)
    assert UUID(other[2].installation_id) in graph.predecessor_cutovers.histories
    assert graph.pending_predecessor_input['public.extension_dispatch_cutover_operation']



def test_original_prepare_fixture_does_not_claim_resumed_without_native_followup_receipts():
    args=cutover_prepare_context()
    assert args[0]['relations']['public.extension_dispatch_cutover_operation'][0]['status']=='prepared'
    ledger=reader._WorkLedger();graph=reader._cutover_history(decode(args[0],ledger),scope=args[1],source=args[2],ledger=ledger)
    assert not graph.activations[UUID(int=4000)].receipts


def predecessor_lifecycle_context(count=0,defect=None,context=None):
    args=detached_refresh_context(count) if context is None else context;rel=args[0]['relations'];life=rel['public.extension_dispatch_lifecycle_operation'][0]
    runtime=next(r for r in rel['public.extension_runtime_operation'] if r['operation_id']==life['runtime_operation_id'])
    event=next(r for r in rel['public.extension_runtime_event'] if r['operation_id']==runtime['operation_id'] and r['type']=='disabled_committed')
    binding=rel['public.extension_runtime_binding'][0]
    binding.update(desired_state='disabled',observed_state='unknown',enabled=False,operation_fence=True,
        revision=event['payload']['bindingRevision'],execution_epoch=event['payload']['executionEpoch'])
    if defect=='no-root':rel['public.extension_dispatch_cutover_operation'].clear();rel['public.extension_dispatch_cutover_receipt'].clear();rel['public.extension_dispatch_cutover_event'].clear()
    elif defect=='no-disable':rel['public.extension_runtime_operation'].remove(runtime)
    elif defect=='disable-kind':runtime['kind']='enable'
    elif defect=='disable-status':runtime['status']='running'
    elif defect=='disable-phase':runtime['phase']='failed'
    elif defect=='disable-target':runtime['installation_id']=str(UUID(int=999))
    elif defect=='no-binding':rel['public.extension_runtime_binding'].clear()
    elif defect=='binding-generation':binding['generation']=str(UUID(int=999))
    elif defect=='binding-enabled':binding['enabled']=True
    elif defect=='binding-fence':binding['operation_fence']=False
    elif defect=='binding-desired':binding['desired_state']='uninstalled'
    elif defect=='binding-observed':binding['observed_state']='stopped'
    elif defect=='binding-epoch':binding['execution_epoch']=1
    elif defect=='life-status':life['status']='fenced'
    elif defect=='life-root':life['activation_operation_id']=str(UUID(int=999))
    elif defect=='life-group':life['cutover_group_id']=str(UUID(int=999))
    elif defect=='missing-receipt':rel['public.extension_dispatch_lifecycle_receipt'].pop()
    elif defect=='missing-event':rel['public.extension_dispatch_lifecycle_event'].pop()
    elif defect=='event-hash':rel['public.extension_dispatch_lifecycle_event'][1]['payload_hash']='sha256:'+'d'*64
    elif defect=='resource-unreleased':rel['public.extension_runtime_resource_lease'][0].update(cleanup_state='retained',observed_release=False)
    elif defect=='resource-observation':rel['public.extension_runtime_resource_lease'][0]['observed_release']=False
    elif defect=='resource-orphan':rel['public.extension_runtime_resource_lease'][0]['operation_id']=str(UUID(int=999))
    elif defect=='zero-resources':rel['public.extension_runtime_resource_lease']=[]
    elif defect=='unlinked-no-refresh':
        life['extension_snapshot'][0]['revision']+=1;life['fenced_snapshot'][0]['revision']+=1
        rebuild_lifecycle_pair_for_join_fixture(args,None)
    elif defect=='running-expired':
        row=row_for(reader._RELATIONS['public.extension_runtime_execution_attempt']);row.update(org_id=args[1].org_id,project_id=args[1].project_id,
            installation_id=args[2].installation_id,generation=binding['generation'],state='running',lease_until='2000-01-01T00:01:00+00:00',accepted_at='2000-01-01T00:00:00+00:00')
        rel['public.extension_runtime_execution_attempt']=[row]
    elif defect in ('claimed-occurrence','unknown-expired','claimed-attempt','attempt-orphan'):
        occurrence=row_for(reader._RELATIONS['public.automation_occurrence']);occurrence.update(org_id=args[1].org_id,project_id=args[1].project_id,
            installation_id=args[2].installation_id,generation=binding['generation'],status='claimed' if defect=='claimed-occurrence' else 'pending')
        rel['public.automation_occurrence']=[occurrence]
        if defect!='claimed-occurrence':
            attempt=row_for(reader._RELATIONS['public.automation_occurrence_dispatch_attempt']);attempt.update(org_id=args[1].org_id,project_id=args[1].project_id,
                occurrence_id=occurrence['occurrence_id'] if defect!='attempt-orphan' else str(UUID(int=999)),status='claimed' if defect=='claimed-attempt' else 'unknown',
                claim_until='2000-01-01T00:01:00+00:00',claimed_at='2000-01-01T00:00:00+00:00',resolved_at=None)
            rel['public.automation_occurrence_dispatch_attempt']=[attempt]
    elif defect=='claim-gate':
        row=row_for(reader._RELATIONS['public.extension_dispatch_claim_gate']);row.update(org_id=args[1].org_id,project_id=args[1].project_id,
            cutover_group_id=life['cutover_group_id'],cutover_operation_id=life['activation_operation_id'],claim_paused=False)
        rel['public.extension_dispatch_claim_gate']=[row]
    packet=empty_packet()
    for family in PREDECESSOR_FAMILIES:packet['predecessors'][family]=deepcopy(rel[family])
    return (packet,*args[1:])


def verify_predecessor_lifecycles(args):
    ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    cutovers=reader._predecessor_cutover_history(facts,scope=args[1],ledger=ledger)
    return reader._predecessor_lifecycle_history(facts,cutovers,scope=args[1],ledger=ledger)


@pytest.mark.parametrize('count',[0,2])
def test_actual_predecessor_lifecycle_uses_resumed_native_root_pair_and_disabled_binding_without_uninstall_record(count):
    args=predecessor_lifecycle_context(count);before=deepcopy(args[0]);graph=verify_predecessor_lifecycles(args)
    assert len(graph.pairs)==1 and len(graph.by_detach)==1 and len(graph.bindings)==1
    identity=next(iter(graph.pairs));assert graph.bindings[identity]['desired_state']=='disabled'
    assert graph.pairs[identity].detach.receipt_id in graph.by_detach
    assert graph.pending_control_operations==(identity,)
    assert len(graph.pending_refresh_refs)==int(count>0)
    assert not graph.pending_cutover_operations and args[0]==before
    assert not hasattr(graph,'authorized') and not hasattr(graph,'kind')


def test_original_predecessor_not_exists_unreleased_predicate_does_not_invent_a_positive_resource_count_requirement():
    graph=verify_predecessor_lifecycles(predecessor_lifecycle_context(defect='zero-resources'))
    assert len(graph.pairs)==1


@pytest.mark.parametrize('defect',['no-root','no-disable','disable-kind','disable-status','disable-phase','disable-target','no-binding','binding-generation',
    'binding-enabled','binding-fence','binding-desired','binding-observed','binding-epoch','life-status','life-root','life-group',
    'missing-receipt','missing-event','event-hash','resource-unreleased','resource-observation','resource-orphan','unlinked-no-refresh',
    'running-expired','claimed-occurrence','unknown-expired','claimed-attempt','attempt-orphan','claim-gate'])
def test_actual_predecessor_lifecycle_rejects_wrong_or_undrained_native_cause_without_ttl_inference(defect):
    with pytest.raises(ValueError):verify_predecessor_lifecycles(predecessor_lifecycle_context(defect=defect))


def test_predecessor_lifecycle_cannot_consume_a_cutover_graph_from_another_decoded_snapshot():
    args=predecessor_lifecycle_context();ledger=reader._WorkLedger();first=decode(args[0],ledger);second=decode(args[0],ledger)
    graph=reader._predecessor_cutover_history(first,scope=args[1],ledger=ledger)
    with pytest.raises(ValueError):reader._predecessor_lifecycle_history(second,graph,scope=args[1],ledger=ledger)


@pytest.mark.parametrize('defect',[None,'scalar','json-bool'])
def test_same_native_pk_across_source_and_predecessor_partitions_must_have_identical_native_values(defect):
    packet=empty_packet();scope=reader.TenantScope('org-a','project-a');row=add_predecessor_binding(packet,scope)
    row['package_lock_ref']={'revision':1};packet['relations']['public.extension_runtime_binding']=[deepcopy(row)]
    if defect=='scalar':packet['relations']['public.extension_runtime_binding'][0]['revision']+=1
    elif defect=='json-bool':packet['relations']['public.extension_runtime_binding'][0]['package_lock_ref']['revision']=True
    ledger=reader._WorkLedger();facts=decode(packet,ledger)
    if defect:
        with pytest.raises(ValueError):reader._check_predecessor_scope(facts,scope,ledger)
    else:reader._check_predecessor_scope(facts,scope,ledger)


def test_detached_registration_keeps_prepared_old_roots_pending_and_reuses_one_actual_cutover_graph():
    args=registration_origin_context();other=original_second_installation_prepared_cutover()
    for family in PREDECESSOR_C_FAMILIES:args[0]['predecessors'][family]=deepcopy(other[0]['relations'][family])
    graph=verify_detached_registration(args)
    assert graph.predecessor_lifecycles.cutovers is graph.predecessor_cutovers
    assert not graph.predecessor_lifecycles.pairs and graph.predecessor_lifecycles.pending_cutover_operations==(UUID(int=5000),)
    assert graph.pending_predecessor_input['public.extension_dispatch_cutover_operation']


def test_same_native_pk_overlap_preserves_nullable_json_values_without_synthetic_defaults():
    packet=empty_packet();scope=reader.TenantScope('org-a','project-a');row=add_predecessor_binding(packet,scope)
    row['config_ref']=None;packet['relations']['public.extension_runtime_binding']=[deepcopy(row)]
    ledger=reader._WorkLedger();facts=decode(packet,ledger);reader._check_predecessor_scope(facts,scope,ledger)
    assert facts.predecessors['public.extension_runtime_binding'][0]['config_ref'] is None


def actual_successor_handover_context(old_count=0,new_count=0,defect=None,complete_old=False,old_withdrawal=False,old_member_count=None):
    from uuid import UUID as NativeUUID
    from functools import partial
    from contextlib import nullcontext
    from tests.asset_registry import test_composition_contracts as original
    def old_uuid(*a,**k):
        if 'int' in k:k={**k,'int':k['int']+100000}
        return NativeUUID(*a,**k)
    source_constructor=source_history_context
    package_constructor=source_package_context;preparation_constructor=preparation_resource_context
    def old_packages(**kwargs):
        kwargs['composition_id']=str(NativeUUID(int=88000))
        with mock.patch(__name__+'.UUID',new=NativeUUID):return package_constructor(**kwargs)
    def old_preparations(**kwargs):
        kwargs['member_count']=old_member_count
        return preparation_constructor(**kwargs)
    package_scope=mock.patch(__name__+'.source_package_context',new=old_packages) if old_member_count is not None else nullcontext()
    preparation_scope=mock.patch(__name__+'.preparation_resource_context',new=old_preparations) if old_member_count is not None else nullcontext()
    native_scope=mock.patch(__name__+'.source_history_context',new=partial(source_constructor,installation_pk=str(NativeUUID(int=18000)))) if complete_old else nullcontext()
    with mock.patch(__name__+'.UUID',new=old_uuid),mock.patch.object(original,'INSTALLATION_ID',str(NativeUUID(int=8000))),native_scope,package_scope,preparation_scope:
        old=(withdrawal_origin_context(count=old_count,idempotency_key='old-activation') if old_withdrawal else
            registration_origin_context('FirstDispatchRegistrationReceipt',count=old_count,idempotency_key='old-activation'))
    if complete_old:
        complete=old_installation_record_context('active',original=old)
        old_source=old[0]
    old=predecessor_lifecycle_context(old_count,context=old)
    if complete_old:
        for family in _OLD_INSTALLATION_FAMILIES:old[0]['predecessors'][family]=deepcopy(complete[0]['predecessors'][family])
        for family in _OLD_REGISTRATION_FAMILIES+('public.automation_schedule_binding','public.ecommerce_growth_runtime_command_receipt'):
            old[0]['predecessors'][family]=deepcopy(old_source['relations'][family])
    parent=verify_predecessor_lifecycles(old);identity=next(iter(parent.pairs));pair=parent.pairs[identity]
    snapshot=list(map(dict,pair.detach.dispatch_snapshot));ref=dict(resourceType='DispatchDisableDetachReceipt',resourceId=str(pair.detach.receipt_id),revision=1,contentHash=pair.detach.content_hash)
    registration_time='2026-08-03T01:02:01.0001+00:00'
    if defect=='ref-hash':ref['contentHash']='sha256:'+'e'*64
    elif defect=='missing-id':ref['resourceId']=str(NativeUUID(int=999))
    elif defect=='snapshot-revision':
        for item in snapshot:item['revision']+=1
    elif defect=='group-revision':
        for item in snapshot:item['cutoverGroupRevision']+=1
    elif defect=='group':
        for item in snapshot:item['cutoverGroupId']=str(NativeUUID(int=999))
    elif defect=='before-detach':registration_time='2026-08-03T01:01:01.999900+00:00'
    from contextlib import nullcontext
    constructor_scope=mock.patch.object(original,'INSTALLATION_ID',str(next(iter(parent.bindings.values()))['installation_id'])) if defect=='same-installation' else nullcontext()
    with constructor_scope:
        args=registration_origin_context('SuccessorDispatchRegistrationReceipt',count=new_count,old_revision=snapshot[0]['revision'],old_group_revision=snapshot[0]['cutoverGroupRevision'],
        group_id=snapshot[0]['cutoverGroupId'],predecessor_ref=ref,dispatch_snapshot=snapshot,
        registration_time=registration_time,cutover_time='2026-08-03T01:02:03+00:00')
    args[0]['predecessors']=deepcopy(old[0]['predecessors'])
    # One shared mutable table image; historical predecessor values stay in its immutable L receipts.
    args[0]['predecessors']['public.extension_operation_dispatch_binding']=deepcopy(args[0]['relations']['public.extension_operation_dispatch_binding'])
    if old_member_count is not None:
        assert complete_old
        for family,schema in reader._REGISTRY.items():
            merged={}
            for row in args[0]['registry'][family]+old_source['registry'][family]:
                key=tuple(row[k] for k in schema.key)
                assert key not in merged or merged[key]==row, 'conflicting native Registry row'
                merged[key]=deepcopy(row)
            args[0]['registry'][family]=list(merged.values())
    return args


@pytest.mark.parametrize('old_count,new_count',[(0,0),(2,0),(0,2)])
def test_normally_constructed_successor_fixture_joins_two_installations_with_actual_starting_snapshot_and_unique_native_ids(old_count,new_count):
    args=actual_successor_handover_context(old_count,new_count);graph=verify_detached_registration(args)
    assert len(graph.predecessor_lifecycles.by_detach)==1
    assert len(graph.predecessor_lifecycles.pending_refresh_refs)==int(old_count>0)
    assert len(graph.registrations.pending_predecessors)==1
    old_binding=next(iter(graph.predecessor_lifecycles.bindings.values()))
    assert old_binding['installation_id']!=UUID(args[2].installation_id)
    assert graph.control.timeline.before_uninstall_revision==8+3*new_count



def test_v10_candidate_represents_both_actual_activation_refresh_chains_without_dropping_old_history():
    args=actual_successor_handover_context(2,2);before=deepcopy(args[0]);graph=verify_detached_registration(args)
    current=args[0]['relations']['public.extension_dispatch_configuration_refresh_receipt']
    prior=args[0]['predecessors']['public.extension_dispatch_configuration_refresh_receipt']
    assert [r['revision'] for r in current]==[1,2]==[r['revision'] for r in prior]
    assert {r['activation_operation_id'] for r in current}.isdisjoint({r['activation_operation_id'] for r in prior})
    assert {r['idempotency_key'] for r in current}.isdisjoint({r['idempotency_key'] for r in prior})
    assert len(graph.successor_handover.matched)==1 and graph.predecessor_lifecycles.pending_refresh_refs
    assert args[0]==before and not hasattr(graph,'authorized')


def verify_successor_handover(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    control=reader._control_history(facts,scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger)
    cutovers=reader._cutover_history(facts,scope=scope,source=source,ledger=ledger)
    registrations=reader._registration_history(facts,cutovers,control,scope=scope,source=source,ledger=ledger)
    old=reader._predecessor_cutover_history(facts,scope=scope,ledger=ledger)
    lifecycles=reader._predecessor_lifecycle_history(facts,old,scope=scope,ledger=ledger)
    return reader._successor_predecessor_history(facts,registrations,lifecycles,scope=scope,source=source,ledger=ledger)


@pytest.mark.parametrize('old_count,new_count',[(0,0),(2,0),(0,2)])
def test_successor_actual_detach_ref_hash_snapshot_group_distinct_installation_and_time_are_joined(old_count,new_count):
    args=actual_successor_handover_context(old_count,new_count);before=deepcopy(args[0]);graph=verify_successor_handover(args)
    assert len(graph.matched)==1 and not graph.pending_refs and not graph.unused_detach_receipts
    assert len(graph.pending_old_registration_refs)==1
    assert len(graph.predecessors.pending_control_operations)==1
    assert len(graph.predecessors.pending_refresh_refs)==int(old_count>0)
    assert len(graph.registrations.pending_predecessors)==1
    assert args[0]==before and not hasattr(graph,'kind') and not hasattr(graph,'authorized')


@pytest.mark.parametrize('defect',['ref-hash','snapshot-revision','group-revision','group','before-detach','same-installation'])
def test_successor_join_rejects_normally_rehashed_new_current_chain_with_wrong_old_handover(defect):
    with pytest.raises(ValueError):verify_successor_handover(actual_successor_handover_context(defect=defect))


def test_successor_missing_exact_detach_parent_stays_explicit_pending_and_cannot_claim_a_match():
    graph=verify_successor_handover(actual_successor_handover_context(defect='missing-id'))
    assert not graph.matched and len(graph.pending_refs)==1 and len(graph.unused_detach_receipts)==1


def test_typed_legacy_successor_reference_with_no_old_native_rows_never_counts_as_an_actual_match():
    graph=verify_successor_handover(registration_origin_context('SuccessorDispatchRegistrationReceipt'))
    assert not graph.matched and len(graph.pending_refs)==1


def test_first_registration_does_not_invent_a_successor_handover():
    graph=verify_successor_handover(registration_origin_context())
    assert not graph.matched and not graph.pending_refs


def test_main_detached_wrapper_joins_actual_handover_with_the_same_old_and_new_graphs():
    graph=verify_detached_registration(actual_successor_handover_context())
    assert graph.successor_handover.registrations is graph.registrations
    assert graph.successor_handover.predecessors is graph.predecessor_lifecycles
    assert len(graph.successor_handover.matched)==1 and not graph.successor_handover.pending_refs
    assert graph.predecessor_lifecycles.pending_control_operations
    assert graph.successor_handover.pending_old_registration_refs


def test_v10_literal_changes_only_native_activation_key_preserving_v9_archive_and_all_columns_caps():
    import hashlib
    root=Path(__file__).resolve().parents[4]/'.evidence/qyh-m2-terminal-source-implementation-20261025'
    old_path=root/'reader-v9-schema-literal-r225.json';old=json.loads(old_path.read_text())
    new=json.loads((root/'reader-v10-schema-literal-r265.json').read_text())
    assert new['priorLiteralSHA256']==hashlib.sha256(old_path.read_bytes()).hexdigest()
    assert new['registry']==old['registry'] and new['baseSpecSHA256']==old['baseSpecSHA256']
    for group in ['relations','predecessors']:
        expected=deepcopy(old[group])
        for row in expected:
            if row['name'].endswith('configuration_refresh_receipt'):
                row['key']=['org_id','project_id','cutover_group_id','activation_operation_id','revision']
        assert new[group]==expected
    packet=empty_packet();packet['schema']='aos.reinstall-terminal-source-facts/v9'
    with pytest.raises(ValueError):decode(packet)


@pytest.mark.parametrize('collision',['receipt','idempotency'])
def test_v10_cross_partition_refresh_native_unique_collision_cannot_hide_behind_new_primary_key(collision):
    packet=empty_packet();family='public.extension_dispatch_configuration_refresh_receipt'
    one=row_for(reader._RELATIONS[family]);one.update(org_id='org-org',project_id='dev-project');two=deepcopy(one)
    two['activation_operation_id']=str(UUID(int=999))
    if collision=='receipt':two['idempotency_key']='different-key'
    else:two['receipt_id']=str(UUID(int=998))
    packet['relations'][family]=[one];packet['predecessors'][family]=[two]
    ledger=reader._WorkLedger();facts=decode(packet,ledger)
    with pytest.raises(ValueError):reader._check_predecessor_scope(facts,reader.TenantScope('org-org','dev-project'),ledger)


def test_v10_same_actual_refresh_row_in_two_partitions_preserves_shared_native_identity():
    packet=empty_packet();family='public.extension_dispatch_configuration_refresh_receipt'
    row=row_for(reader._RELATIONS[family]);row.update(org_id='org-org',project_id='dev-project');packet['relations'][family]=[row];packet['predecessors'][family]=[deepcopy(row)]
    ledger=reader._WorkLedger();facts=decode(packet,ledger)
    reader._check_predecessor_scope(facts,reader.TenantScope('org-org','dev-project'),ledger)


def verify_predecessor_refreshes(args):
    ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    cutovers=reader._predecessor_cutover_history(facts,scope=args[1],ledger=ledger)
    lifecycle=reader._predecessor_lifecycle_history(facts,cutovers,scope=args[1],ledger=ledger)
    return reader._predecessor_refresh_history(facts,lifecycle,scope=args[1],ledger=ledger)


@pytest.mark.parametrize('count',[0,1,2])
def test_predecessor_refresh_receipts_use_actual_old_resumed_chain_and_detach_snapshot(count):
    args=actual_successor_handover_context(count,2);before=deepcopy(args[0]);graph=verify_predecessor_refreshes(args)
    assert len(graph.detached)==1
    assert len(next(iter(graph.chains.values())).steps)==count
    assert bool(graph.pending_control_operations)==bool(count)
    assert bool(graph.pending_installation_refs)==bool(count)
    assert args[0]==before and not hasattr(graph,'authorized') and not hasattr(graph,'kind')
    assert len(graph.lifecycle.pending_refresh_refs)==int(count>0)


def test_main_wrapper_preserves_same_actual_predecessor_refresh_parent_and_remaining_obligations():
    graph=verify_detached_registration(actual_successor_handover_context(2,2))
    assert graph.predecessor_refreshes.lifecycle is graph.predecessor_lifecycles
    assert graph.predecessor_refreshes.pending_control_operations
    assert graph.successor_handover.pending_old_registration_refs


def test_current_refresh_path_calls_shared_receipt_chain_once_without_skipping_control_proofs(monkeypatch):
    args=primary_refresh_context();original=reader._refresh_receipt_chain;calls=[]
    def capture(*a,**k):calls.append(a[1]);return original(*a,**k)
    monkeypatch.setattr(reader,'_refresh_receipt_chain',capture)
    result=verify_primary_refresh(args)
    assert len(calls)==1 and len(result.receipt_ids)==2


def rehash_original_refresh_row(row):
    from aos_api.ecommerce_dispatch_configuration_receipt import receipt_body
    from aos_api.asset_registry.canonical_json import canonical_sha256
    row['request_hash']=canonical_sha256(row['request'])
    native=dict(row,created_at=datetime.fromisoformat(row['created_at']))
    row['body']=receipt_body(native);row['content_hash']=canonical_sha256(row['body'])


@pytest.mark.parametrize('defect',['root','resume-hash','source-runtime','source-epoch','source-group','row-time','configuration-missing','detach-ref-hash'])
def test_old_refresh_rejects_rehashed_wrong_native_parents_and_incomplete_actual_configuration(defect):
    args=actual_successor_handover_context(1,0);p=args[0]['predecessors'];row=p['public.extension_dispatch_configuration_refresh_receipt'][0]
    if defect=='root':row['activation_operation_id']=str(UUID(int=999))
    elif defect=='resume-hash':row['request']['sourceAuthorityRef']['contentHash']='sha256:'+'e'*64
    elif defect=='source-runtime':row['request']['sourceRuntimeRevision']+=1
    elif defect=='source-epoch':row['request']['sourceExecutionEpoch']+=1
    elif defect=='source-group':row['request']['expectedGroupRevision']+=1
    elif defect=='row-time':row['created_at']='2026-08-03T00:00:01+00:00'
    elif defect=='configuration-missing':p['public.extension_runtime_configuration']=[]
    elif defect=='detach-ref-hash':row['actor']='different-actor'
    rehash_original_refresh_row(row)
    with pytest.raises(ValueError):verify_predecessor_refreshes(args)


@pytest.mark.parametrize('defect',['gap','parent-id','parent-hash','cross-root','backward-time'])
def test_old_refresh_history_must_follow_its_exact_actual_predecessor_not_just_a_typed_ref(defect):
    args=actual_successor_handover_context(2,0);rows=args[0]['predecessors']['public.extension_dispatch_configuration_refresh_receipt'];row=rows[1]
    if defect=='gap':rows.pop(0)
    elif defect=='parent-id':row['previous_receipt_id']=row['request']['sourceAuthorityRef']['resourceId']=str(UUID(int=999))
    elif defect=='parent-hash':row['previous_hash']=row['request']['sourceAuthorityRef']['contentHash']='sha256:'+'e'*64
    elif defect=='cross-root':row['activation_resume_receipt_id']=str(UUID(int=999))
    else:row['created_at']=rows[0]['created_at'][:19]+'.000001+00:00'
    rehash_original_refresh_row(row)
    with pytest.raises(ValueError):verify_predecessor_refreshes(args)


def test_old_refresh_graph_cannot_be_joined_to_an_equal_but_different_fact_partition():
    args=actual_successor_handover_context(1,0);ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    cutovers=reader._predecessor_cutover_history(facts,scope=args[1],ledger=ledger)
    old=reader._predecessor_lifecycle_history(facts,cutovers,scope=args[1],ledger=ledger)
    other=decode(deepcopy(args[0]),ledger)
    with pytest.raises(ValueError):reader._predecessor_refresh_history(other,old,scope=args[1],ledger=ledger)


def test_unused_actual_old_refresh_chain_remains_visible_without_a_lifecycle_or_admission_claim():
    args=actual_successor_handover_context(2,0)
    for family in ('extension_dispatch_lifecycle_operation','extension_dispatch_lifecycle_receipt','extension_dispatch_lifecycle_event'):
        args[0]['predecessors']['public.'+family]=[]
    graph=verify_predecessor_refreshes(args)
    assert not graph.detached and len(graph.remaining_receipt_ids)==2
    assert len(graph.chains)==1 and not hasattr(graph,'authorized')


def verify_predecessor_controls(args):
    ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    cutovers=reader._predecessor_cutover_history(facts,scope=args[1],ledger=ledger)
    lifecycle=reader._predecessor_lifecycle_history(facts,cutovers,scope=args[1],ledger=ledger)
    refresh=reader._predecessor_refresh_history(facts,lifecycle,scope=args[1],ledger=ledger)
    return reader._predecessor_control_history(facts,refresh,scope=args[1],ledger=ledger)


@pytest.mark.parametrize('count',[0,1,2])
def test_actual_old_control_commits_join_refresh_targets_and_disable_without_fake_terminal(count):
    args=actual_successor_handover_context(count,2);before=deepcopy(args[0]);graph=verify_predecessor_controls(args)
    assert len(graph.histories)==1 and len(graph.linked_disables)==1
    assert len(next(iter(graph.linked_refresh_operations.values())))==2*count
    assert graph.pending_preparations and graph.pending_timeline
    assert args[0]==before and not hasattr(graph,'authorized') and not hasattr(graph,'kind')
    assert graph.refreshes.lifecycle.pending_control_operations


def test_main_old_control_graph_uses_the_same_old_refresh_parent_and_preserves_unproved_origins():
    graph=verify_detached_registration(actual_successor_handover_context(2,2))
    assert graph.predecessor_controls.refreshes is graph.predecessor_refreshes
    assert graph.predecessor_controls.pending_preparations
    assert graph.successor_handover.pending_old_registration_refs


def test_current_control_history_delegates_once_to_the_same_original_commit_kernel(monkeypatch):
    original=reader._control_commit_history;calls=[]
    def capture(*a,**k):calls.append(k['installation_id']);return original(*a,**k)
    monkeypatch.setattr(reader,'_control_commit_history',capture)
    verify_primary_refresh(primary_refresh_context(1))
    assert len(calls)==1


@pytest.mark.parametrize('defect',['request-hash','phase','event-hash','sequence','missing-event','accepted-target','commit-payload','actor','prepare-parent','commit-epoch'])
def test_old_actual_control_producers_reject_rehashed_or_partial_native_event_proofs(defect):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=actual_successor_handover_context(1,0);p=args[0]['predecessors']
    refresh=p['public.extension_dispatch_configuration_refresh_receipt'][0]
    identity=refresh['request']['enableOperationId'];op=next(r for r in p['public.extension_runtime_operation'] if r['operation_id']==identity)
    events=sorted([r for r in p['public.extension_runtime_event'] if r['operation_id']==identity],key=lambda r:r['sequence'])
    if defect=='request-hash':op['request_hash']='sha256:'+'e'*64
    elif defect=='phase':op['phase']='accepted'
    elif defect=='event-hash':events[-2]['payload_hash']='sha256:'+'e'*64
    elif defect=='sequence':events[-2]['sequence']=99
    elif defect=='missing-event':p['public.extension_runtime_event'].remove(events[1])
    elif defect=='accepted-target':events[0]['payload']['configurationTarget']['bindingRevision']+=1
    elif defect=='commit-payload':events[-2]['payload']['bindingRevision']+=1
    elif defect=='actor':op['requested_by']='different-actor'
    elif defect=='prepare-parent':events[-2]['payload']['preparationOperationId']=str(UUID(int=999))
    else:events[-2]['payload']['executionEpoch']+=1
    if defect in ('accepted-target','commit-payload','prepare-parent','commit-epoch'):
        for row in events:row['payload_hash']=canonical_sha256(row['payload'])
    with pytest.raises(ValueError):verify_predecessor_controls(args)


def test_old_control_join_refuses_an_equal_but_different_parent_fact_instance():
    args=actual_successor_handover_context();ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    cutovers=reader._predecessor_cutover_history(facts,scope=args[1],ledger=ledger)
    lifecycle=reader._predecessor_lifecycle_history(facts,cutovers,scope=args[1],ledger=ledger)
    refresh=reader._predecessor_refresh_history(facts,lifecycle,scope=args[1],ledger=ledger)
    with pytest.raises(ValueError):reader._predecessor_control_history(decode(deepcopy(args[0]),ledger),refresh,scope=args[1],ledger=ledger)


def test_old_preparation_may_precede_current_binding_but_cannot_reference_a_future_installation_version():
    from aos_api.asset_registry.canonical_json import canonical_sha256
    args=actual_successor_handover_context(1,0);p=args[0]['predecessors'];binding=p['public.extension_runtime_binding'][0]
    preparation=next(r for r in p['public.extension_runtime_event'] if r['type']=='preparation_committed')
    assert preparation['payload']['installationRevision']<binding['installation_revision']
    assert verify_predecessor_controls(args).pending_preparations
    preparation['payload']['installationRevision']=binding['installation_revision']+1
    preparation['payload_hash']=canonical_sha256(preparation['payload'])
    with pytest.raises(ValueError):verify_predecessor_controls(args)


def verify_old_binding_timeline(args):
    ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    cutovers=reader._predecessor_cutover_history(facts,scope=args[1],ledger=ledger)
    life=reader._predecessor_lifecycle_history(facts,cutovers,scope=args[1],ledger=ledger)
    refresh=reader._predecessor_refresh_history(facts,life,scope=args[1],ledger=ledger)
    controls=reader._predecessor_control_history(facts,refresh,scope=args[1],ledger=ledger)
    return reader._predecessor_binding_timeline(facts,controls,scope=args[1],ledger=ledger)


@pytest.mark.parametrize('count',[0,1,2])
def test_actual_old_binding_timeline_ends_at_disable_commit_not_an_invented_uninstall(count):
    args=actual_successor_handover_context(count,2);before=deepcopy(args[0]);graph=verify_old_binding_timeline(args)
    assert len(graph.timelines)==1 and graph.pending_remaining_operations and graph.pending_preparations
    binding=args[0]['predecessors']['public.extension_runtime_binding'][0]
    timeline=next(iter(graph.timelines.values()))
    assert timeline.revision==binding['revision'] and timeline.execution_epoch==binding['execution_epoch']
    assert timeline.versions[timeline.revision].enabled is False
    assert args[0]==before and not hasattr(graph,'authorized') and not hasattr(graph,'kind')
    remaining=set(map(str,graph.pending_remaining_operations))
    assert {r['kind'] for r in args[0]['predecessors']['public.extension_runtime_operation'] if r['operation_id'] in remaining}=={'runtime-apply','runtime-verify'}


def test_main_old_binding_timeline_uses_same_parent_graph_and_never_clears_preparation_obligations():
    graph=verify_detached_registration(actual_successor_handover_context(2,2))
    assert graph.predecessor_timeline.controls is graph.predecessor_controls
    assert graph.predecessor_timeline.pending_preparations


def test_current_control_timeline_calls_original_shared_binding_kernel_once(monkeypatch):
    original=reader._binding_step_timeline;calls=[]
    def capture(*a,**k):calls.append(k['expected_revision']);return original(*a,**k)
    monkeypatch.setattr(reader,'_binding_step_timeline',capture)
    args=detached_refresh_context(1);packet,scope,source,locked,lock=args;ledger=reader._WorkLedger()
    reader._detached_control_timeline(decode(packet,ledger),scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger)
    assert len(calls)==1


@pytest.mark.parametrize('defect',['duplicate','gap','epoch'])
def test_shared_binding_kernel_rejects_unreachable_steps_without_synthesizing_cas_versions(defect):
    from dataclasses import replace
    args=control_history_context();history=verify_control_history(args);steps=list(history.commits.values())
    if defect=='duplicate':steps.append(steps[0])
    elif defect=='gap':steps[1]=replace(steps[1],from_revision=steps[1].from_revision+4)
    else:steps[1]=replace(steps[1],execution_epoch=steps[1].execution_epoch+1)
    binding=history.graph.receipt.context.binding
    with pytest.raises(ValueError):reader._binding_step_timeline(steps,expected_revision=binding['revision']-1,
        execution_epoch=binding['execution_epoch'],configuration=history.graph.configurations.current,ledger=reader._WorkLedger())


def test_zero_retained_old_resources_does_not_invent_a_missing_runtime_cleanup_requirement():
    args=actual_successor_handover_context();args[0]['predecessors']['public.extension_runtime_resource_lease']=[]
    assert len(verify_old_binding_timeline(args).timelines)==1


def test_old_binding_timeline_refuses_a_parent_from_another_equal_fact_snapshot():
    args=actual_successor_handover_context();ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    cutovers=reader._predecessor_cutover_history(facts,scope=args[1],ledger=ledger)
    life=reader._predecessor_lifecycle_history(facts,cutovers,scope=args[1],ledger=ledger)
    refresh=reader._predecessor_refresh_history(facts,life,scope=args[1],ledger=ledger)
    controls=reader._predecessor_control_history(facts,refresh,scope=args[1],ledger=ledger)
    with pytest.raises(ValueError):reader._predecessor_binding_timeline(decode(deepcopy(args[0]),ledger),controls,scope=args[1],ledger=ledger)


_OLD_INSTALLATION_FAMILIES = (
    'public.bundle_installation', 'public.bundle_installation_revision',
    'public.bundle_installation_event', 'public.bundle_composition',
    'public.bundle_composition_lock', 'public.bundle_installation_decision',
)


def test_v11_old_installation_projection_exact_literal_and_v10_archive_preserved():
    import hashlib
    root=Path(__file__).resolve().parents[4]/'.evidence/qyh-m2-terminal-source-implementation-20261025'
    prior=root/'reader-v10-schema-literal-r265.json'
    old=json.loads(prior.read_text());new=json.loads((root/'reader-v11-schema-literal-r305.json').read_text())
    assert new['priorLiteralSHA256']==hashlib.sha256(prior.read_bytes()).hexdigest()
    assert new['relations']==old['relations'] and new['registry']==old['registry']
    assert new['predecessors'][:len(old['predecessors'])]==old['predecessors']
    expected={row['name']:row for row in new['predecessors']}
    assert set(expected) < set(reader._PREDECESSOR_RELATIONS)
    for name in expected:
        schema=reader._PREDECESSOR_RELATIONS[name]
        item=expected[name]
        assert schema.columns==tuple(map(tuple,item['columns']))+((('created_at','timestamp with time zone!'),) if name=='public.bundle_composition_lock' else ())
        assert schema.key==tuple(item['key']) and schema.cap==item['cap']
    assert reader._SCHEMA_VERSION=='aos.reinstall-terminal-source-facts/v13'
    packet=empty_packet();packet['schema']='aos.reinstall-terminal-source-facts/v10'
    with pytest.raises(ValueError):decode(packet)


@pytest.mark.parametrize('family',_OLD_INSTALLATION_FAMILIES)
@pytest.mark.parametrize('defect',['missing-family','missing-column','extra-column','wrong-tenant','duplicate-pk'])
def test_v11_old_installation_facts_are_required_typed_scoped_and_unique(family,defect):
    packet=empty_packet()
    schema=reader._PREDECESSOR_RELATIONS[family]
    row=row_for(schema);packet['predecessors'][family]=[row]
    if defect=='missing-family':packet['predecessors'].pop(family)
    elif defect=='missing-column':row.pop(schema.columns[-1][0])
    elif defect=='extra-column':row['authorized']=True
    elif defect=='wrong-tenant':row['org_id']='foreign'
    else:packet['predecessors'][family].append(deepcopy(row))
    with pytest.raises(ValueError):
        facts=decode(packet);reader._check_predecessor_scope(facts,reader.TenantScope('fixture','fixture'),reader._WorkLedger())


@pytest.mark.parametrize('family',_OLD_INSTALLATION_FAMILIES)
def test_v11_old_installation_projection_retains_actual_rows_without_authority(family):
    packet=empty_packet();row=row_for(reader._PREDECESSOR_RELATIONS[family])
    packet['predecessors'][family]=[row]
    facts=decode(packet);reader._check_predecessor_scope(facts,reader.TenantScope('fixture','fixture'),reader._WorkLedger())
    assert len(facts.predecessors[family])==1 and not hasattr(facts,'authorized')
    assert packet['predecessors'][family]==[row]


@pytest.mark.parametrize('family',_OLD_INSTALLATION_FAMILIES[:5])
def test_v11_old_and_current_same_native_key_cannot_disagree_on_shared_columns(family):
    packet=empty_packet();row=row_for(reader._RELATIONS[family]);old=row_for(reader._PREDECESSOR_RELATIONS[family]);old.update(deepcopy(row))
    packet['relations'][family]=[row];packet['predecessors'][family]=[old]
    facts=decode(packet);reader._check_predecessor_scope(facts,reader.TenantScope('fixture','fixture'),reader._WorkLedger())
    key=reader._RELATIONS[family].key
    column,kind=next((n,k) for n,k in reader._RELATIONS[family].columns if n not in key)
    if kind.startswith('uuid'):old[column]=str(UUID(int=45678))
    elif kind.startswith('bigint'):old[column]=2
    elif kind.startswith('jsonb'):old[column]={'different':True}
    else:old[column]='different'
    with pytest.raises(ValueError):reader._check_predecessor_scope(decode(packet),reader.TenantScope('fixture','fixture'),reader._WorkLedger())


@pytest.mark.parametrize('family',['public.bundle_installation','public.bundle_installation_revision','public.bundle_installation_event','public.bundle_installation_decision'])
def test_v11_old_installation_time_and_nullable_reason_come_from_actual_projection(family):
    packet=empty_packet();row=row_for(reader._PREDECESSOR_RELATIONS[family]);packet['predecessors'][family]=[row]
    if 'reason' in row:row['reason']=None
    assert decode(packet).predecessors[family][0]['created_at'].utcoffset() is not None
    row['created_at']='2026-10-26T00:00:00'
    with pytest.raises(ValueError):decode(packet)


def test_v11_ancestor_rows_do_not_expand_current_caps_or_reset_packet_budget(monkeypatch):
    packet=empty_packet()
    for family in _OLD_INSTALLATION_FAMILIES:
        assert reader._PREDECESSOR_RELATIONS[family].cap==2048
        packet['predecessors'][family]=[row_for(reader._PREDECESSOR_RELATIONS[family])]
    assert all(reader._RELATIONS[x].cap==1 for x in ('public.bundle_installation','public.bundle_composition','public.bundle_composition_lock'))
    monkeypatch.setattr(reader,'_MAX_PACKET_ROWS',5)
    with pytest.raises(ValueError,match='budget'):decode(packet)



def old_installation_record_context(state='applied', *, original=None):
    from aos_api.asset_registry.composition_contracts import InstallationRecord
    original=source_history_context('active',backend=True) if original is None else original
    old_packet,scope,_,locked,lock=original;record=locked.record
    event=next(e for e in record.events if e.to_state==state)
    events=[e for e in record.events if e.to_revision<=event.to_revision]
    current=record.current.model_dump(mode='python',by_alias=True)
    current.update(revision=event.to_revision,parentRevision=event.from_revision,state=state,createdAt=event.created_at)
    body=record.model_dump(mode='python',by_alias=True)
    body.update(state=state,currentRevision=event.to_revision,etagVersion=event.to_revision,
        activeRevision=event.to_revision if state=='active' else None,previousActiveRevision=None,
        updatedAt=event.created_at,current=current,events=[e.model_dump(mode='python',by_alias=True) for e in events])
    expected=InstallationRecord.model_validate(body)
    packet=empty_packet();packet['registry']=deepcopy(old_packet['registry'])
    prior=packet['predecessors']
    for name in ('public.bundle_composition','public.bundle_composition_lock'):
        prior[name]=deepcopy(old_packet['relations'][name])
    for row in prior['public.bundle_composition_lock']:row['created_at']=lock.created_at.isoformat()
    head=deepcopy(old_packet['relations']['public.bundle_installation'][0]);head.update(
        current_revision=expected.current_revision,etag_version=expected.etag_version,
        active_revision=expected.active_revision,previous_active_revision=expected.previous_active_revision,
        display_name=expected.display_name,created_at=expected.created_at.isoformat(),updated_at=expected.updated_at.isoformat())
    prior['public.bundle_installation']=[head]
    times={e.sequence:e for e in events}
    prior['public.bundle_installation_revision']=[dict(row,requested_by=expected.current.requested_by,
        created_at=times[row['revision']].created_at.isoformat()) for row in old_packet['relations']['public.bundle_installation_revision']
        if row['revision']<=expected.current_revision]
    prior['public.bundle_installation_event']=[dict(row,reason=times[row['sequence']].reason,
        created_at=times[row['sequence']].created_at.isoformat()) for row in old_packet['relations']['public.bundle_installation_event']
        if row['sequence']<=expected.current_revision]
    decision=expected.decision
    prior['public.bundle_installation_decision']=[dict(org_id=scope.org_id,project_id=scope.project_id,
        installation_pk=str(locked.installation_pk),decision_id=decision.decision_id,
        submitted_revision=decision.submitted_revision,decision=decision.decision,actor=decision.actor,
        lock_hash=decision.lock_hash,permission_diff_hash=decision.permission_diff_hash,
        migration_plan_hash=decision.migration_plan_hash,contribution_diff_hash=decision.contribution_diff_hash,
        reason=decision.reason,created_at=decision.created_at.isoformat())]
    return packet,scope,expected,locked.installation_pk,lock


def verify_old_installation_record(args,ledger=None):
    packet,scope,expected,pk,lock=args
    ledger=reader._WorkLedger() if ledger is None else ledger
    return reader._predecessor_installation_record(decode(packet,ledger),scope=scope,
        installation_id=UUID(expected.installation_id),source_lock=lock,ledger=ledger)


@pytest.mark.parametrize('state',['approved','applied','active','uninstalled'])
def test_old_installation_record_uses_actual_state_and_original_contract_without_fake_terminal(state):
    args=old_installation_record_context(state);before=deepcopy(args[0])
    result=verify_old_installation_record(args)
    assert type(result) is reader.LockedInstallation
    assert result.record==args[2] and result.installation_pk==args[3]
    assert result.record.state==state and args[0]==before
    assert not hasattr(result,'authorized')


@pytest.mark.parametrize('fault',['missing-head','duplicate-id','missing-revision','missing-event','event-pk',
    'event-time','event-actor','decision-pk','decision-time','decision-hash','decision-actor','revision-actor',
    'revision-time','revision-parent','lock-hash','lock-payload','snapshot','composition-id'])
def test_old_installation_record_rejects_wrong_original_parent_evidence_or_lock(fault):
    args=list(old_installation_record_context());p=args[0]['predecessors']
    if fault=='missing-head':p['public.bundle_installation']=[]
    elif fault=='duplicate-id':
        row=deepcopy(p['public.bundle_installation'][0]);row['installation_pk']=str(UUID(int=444))
        p['public.bundle_installation'].append(row)
    elif fault=='missing-revision':p['public.bundle_installation_revision'].pop(0)
    elif fault=='missing-event':p['public.bundle_installation_event'].pop(0)
    elif fault=='event-pk':p['public.bundle_installation_event'][-1]['installation_pk']=str(UUID(int=444))
    elif fault=='event-time':p['public.bundle_installation_event'][-1]['created_at']='2026-10-26T00:00:00+00:00'
    elif fault=='event-actor':p['public.bundle_installation_event'][2]['actor']='wrong-approver'
    elif fault=='decision-pk':p['public.bundle_installation_decision'][0]['installation_pk']=str(UUID(int=444))
    elif fault=='decision-time':p['public.bundle_installation_decision'][0]['created_at']='2026-10-26T00:00:00+00:00'
    elif fault=='decision-hash':p['public.bundle_installation_decision'][0]['lock_hash']='sha256:'+'e'*64
    elif fault=='decision-actor':p['public.bundle_installation_decision'][0]['actor']=args[2].current.requested_by
    elif fault=='revision-actor':p['public.bundle_installation_revision'][-1]['requested_by']='wrong-requester'
    elif fault=='revision-time':p['public.bundle_installation_revision'][-1]['created_at']='2026-10-26T00:00:00+00:00'
    elif fault=='revision-parent':p['public.bundle_installation_revision'][-1]['parent_revision']=1
    elif fault=='lock-hash':p['public.bundle_composition_lock'][0]['lock_hash']='sha256:'+'e'*64
    elif fault=='lock-payload':p['public.bundle_composition_lock'][0]['lock_payload']['registrySnapshotHash']='sha256:'+'e'*64
    elif fault=='snapshot':p['public.bundle_composition'][0]['registry_snapshot_hash']='sha256:'+'e'*64
    else:p['public.bundle_composition'][0]['composition_id']=str(UUID(int=444))
    with pytest.raises(ValueError,match='invalid terminal facts'):verify_old_installation_record(args)


def test_old_installation_record_uses_shared_history_kernel_with_projected_context_and_budget():
    args=old_installation_record_context();ledger=reader._WorkLedger()
    with mock.patch.object(reader,'_verify_installation_history_rows',wraps=reader._verify_installation_history_rows) as shared:
        result=verify_old_installation_record(args,ledger)
    assert shared.call_count==1 and shared.call_args.kwargs['projected_context'] is True
    assert shared.call_args.kwargs['ledger'] is ledger and result.record.state=='applied'
    with pytest.raises(ValueError,match='budget'):
        with mock.patch.object(reader,'_MAX_ROW_VISITS',1):verify_old_installation_record(args)


def test_current_source_history_keeps_original_terminal_requirement_and_shared_kernel_context():
    args=source_history_context('active')
    with mock.patch.object(reader,'_verify_installation_history_rows',wraps=reader._verify_installation_history_rows) as shared:
        assert verify_history(*args).state=='uninstalled'
    assert shared.call_count==1 and shared.call_args.kwargs['projected_context'] is False



def test_old_installation_record_never_constructs_a_terminal_reference_or_calls_current_wrapper():
    args=old_installation_record_context('active')
    with mock.patch.object(reader,'ReinstallSourceRef',side_effect=AssertionError('no fake terminal ref')), \
         mock.patch.object(reader,'_verify_source_history',side_effect=AssertionError('no borrowed current source')):
        assert verify_old_installation_record(args).record.state=='active'


def test_old_installation_record_preserves_other_installation_input_without_qualifying_it():
    args=old_installation_record_context();packet=args[0]
    other=deepcopy(packet['predecessors']['public.bundle_installation'][0])
    other.update(installation_pk=str(UUID(int=555)),installation_id=str(UUID(int=556)))
    packet['predecessors']['public.bundle_installation'].append(other);before=deepcopy(packet)
    assert verify_old_installation_record(args).installation_pk==args[3]
    assert packet==before and len(packet['predecessors']['public.bundle_installation'])==2


def test_old_installation_record_same_lock_selection_kernel_checks_actual_rows():
    args=old_installation_record_context()
    with mock.patch.object(reader,'_check_composition_lock_rows',wraps=reader._check_composition_lock_rows) as shared:
        verify_old_installation_record(args)
    assert shared.call_count==1
    assert shared.call_args.args[0]['composition_pk']==UUID(args[0]['predecessors']['public.bundle_composition'][0]['composition_pk'])



def old_preparation_resources_context(*, two_generations=False,member_count=1,uncommitted=None):
    current=preparation_resource_context(two_generations=two_generations,member_count=member_count,
        uncommitted=uncommitted,route='reset-active' if two_generations else 'active')
    args=old_installation_record_context('active',original=current)
    for family in ('public.extension_runtime_operation','public.extension_runtime_event','public.extension_runtime_resource_lease'):
        args[0]['predecessors'][family]=deepcopy(current[0]['relations'][family])
    return args


def verify_old_preparation_resources(args,ledger=None):
    packet,scope,expected,_,lock=args;ledger=reader._WorkLedger() if ledger is None else ledger
    return reader._predecessor_preparation_resources(decode(packet,ledger),scope=scope,
        installation_id=UUID(expected.installation_id),source_lock=lock,ledger=ledger)


@pytest.mark.parametrize('two_generations,uncommitted',[(False,None),(True,None),(True,'unclaimed'),(True,'claimed')])
@pytest.mark.parametrize('member_count',[1,2])
def test_old_preparation_resources_preserve_complete_original_generation_and_package_sets(two_generations,uncommitted,member_count):
    args=old_preparation_resources_context(two_generations=two_generations,member_count=member_count,uncommitted=uncommitted)
    before=deepcopy(args[0]);result=verify_old_preparation_resources(args)
    assert result.record.state=='active' and result.record==args[2]
    assert len(result.preparations)==(2 if two_generations else 1)
    assert len(result.resources)==len(args[0]['predecessors']['public.extension_runtime_resource_lease'])
    assert len(result.contents)==member_count and args[0]==before
    assert not hasattr(result,'authorized') and not hasattr(result,'branch')


@pytest.mark.parametrize('fault',['missing-resource','extra-resource','generation','claims','proof-set','proof-lock',
    'proof-evidence','resource-parent','event-hash','event-gap','missing-registration','release-unknown',
    'missing-version','descriptor','extra-artifact'])
def test_old_preparation_resources_refuse_wrong_set_or_self_inconsistent_source_proof(fault):
    args=old_preparation_resources_context(two_generations=True,member_count=2);packet=args[0];prior=packet['predecessors']
    resources=prior['public.extension_runtime_resource_lease'];events=prior['public.extension_runtime_event']
    proof=next(e for e in events if e['type']=='preparation_committed')
    if fault=='missing-resource':resources.pop(0)
    elif fault=='extra-resource':
        extra=deepcopy(resources[0]);extra['resource_id']=str(UUID(int=999111));resources.append(extra)
    elif fault=='generation':resources[0]['generation']=str(UUID(int=999111))
    elif fault=='claims':proof['payload']['resources'][0]['claimsHash']='sha256:'+'e'*64
    elif fault=='proof-set':proof['payload']['resources'].pop()
    elif fault=='proof-lock':proof['payload']['lockHash']='sha256:'+'e'*64
    elif fault=='proof-evidence':proof['payload']['evidenceHash']='sha256:'+'e'*64
    elif fault=='resource-parent':resources[0]['operation_id']=str(UUID(int=999111))
    elif fault=='event-hash':events[0]['payload_hash']='sha256:'+'e'*64
    elif fault=='event-gap':events.pop(0)
    elif fault=='missing-registration':
        event=next(e for e in events if e['type']=='resource_registered');event['type']='resource_uncertain';event['payload']={'resourceId':event['payload']['resourceId']};event['payload_hash']=reader._digest(event['payload'])
    elif fault=='release-unknown':resources[0]['observed_release']=False
    elif fault=='missing-version':packet['registry']['public.asset_bundle_version'].pop()
    elif fault=='descriptor':packet['registry']['public.asset_bundle_version'][0]['content_hash']='sha256:'+'e'*64
    else:
        # Supply an actual descriptor artifact on the selected version, then break its descriptor body.
        version=packet['registry']['public.asset_bundle_version'][0]
        packet['registry']['public.asset_bundle_artifact'].append(dict(version_pk=version['version_pk'],relative_path='extra.py',digest='sha256:'+'e'*64,size=1,media_type='text/plain'))
    if fault in {'claims','proof-set','proof-lock','proof-evidence'}:proof['payload_hash']=reader._digest(proof['payload'])
    with pytest.raises(ValueError):verify_old_preparation_resources(args)


def test_old_preparation_resources_share_original_resource_kernel_and_same_ledger():
    args=old_preparation_resources_context(two_generations=True);ledger=reader._WorkLedger()
    with mock.patch.object(reader,'_preparation_resources_from_rows',wraps=reader._preparation_resources_from_rows) as shared:
        result=verify_old_preparation_resources(args,ledger)
    assert shared.call_count==1 and shared.call_args.kwargs['ledger'] is ledger
    assert shared.call_args.args[0] is result.record and result.record.state=='active'
    with pytest.raises(ValueError,match='budget'):
        with mock.patch.object(reader,'_MAX_ROW_VISITS',1):verify_old_preparation_resources(args)


def test_old_preparation_resources_preserve_unselected_registry_and_other_installation_input_as_unqualified():
    args=old_preparation_resources_context();packet=args[0]
    unrelated=deepcopy(packet['registry']['public.asset_bundle'][0]);unrelated.update(bundle_pk=str(UUID(int=999777)),bundle_id='other-installation-package')
    packet['registry']['public.asset_bundle'].append(unrelated);before=deepcopy(packet)
    result=verify_old_preparation_resources(args)
    assert len(result.contents)==1 and packet==before and not hasattr(result,'authorized')


def test_current_preparation_resources_keep_original_source_package_and_resource_kernel_calls():
    args=preparation_resource_context(two_generations=True)
    with mock.patch.object(reader,'_preparation_resources_from_rows',wraps=reader._preparation_resources_from_rows) as shared:
        result=verify_preparation_resources(*args)
    assert shared.call_count==1 and result.record.state=='uninstalled'



def old_runtime_verification_context(route='active'):
    original=runtime_verification_context(route=route)
    args=old_installation_record_context('active',original=original)
    for family in ('public.extension_runtime_operation','public.extension_runtime_event','public.extension_runtime_resource_lease',
        'public.extension_runtime_binding','public.extension_runtime_configuration','public.extension_runtime_outbox',
        'public.extension_runtime_execution_attempt','public.extension_runtime_execution_attempt_event','public.extension_runtime_dependency_ref'):
        args[0]['predecessors'][family]=deepcopy(original[0]['relations'][family])
    return args


def verify_old_runtime_verification(args,ledger=None):
    packet,scope,expected,_,lock=args;ledger=reader._WorkLedger() if ledger is None else ledger
    generation=UUID(packet['predecessors']['public.extension_runtime_binding'][0]['generation']) if packet['predecessors']['public.extension_runtime_binding'] else UUID(int=200)
    return reader._predecessor_runtime_verification(decode(packet,ledger),scope=scope,
        installation_id=UUID(expected.installation_id),generation=generation,source_lock=lock,ledger=ledger)


@pytest.mark.parametrize('route',['active','reset-active'])
def test_old_runtime_verification_uses_real_preparation_binding_and_history_without_uninstall_wrapper(route):
    args=old_runtime_verification_context(route);before=deepcopy(args[0])
    with mock.patch.object(reader,'_read_uninstall_receipt',side_effect=AssertionError('no fake receipt')):
        result=verify_old_runtime_verification(args)
    assert result.verification_operation==UUID(int=980) and result.preparations.record.state=='active'
    assert result.preparation.operation_id in result.preparations.operations
    assert result.configurations.current is None and args[0]==before
    assert dict(result.binding)==decode(args[0]).predecessors['public.extension_runtime_binding'][0]
    assert not hasattr(result,'authorized') and not hasattr(result,'receipt')


@pytest.mark.parametrize('fault',['missing-binding','profile','package-lock','binding-revision','handle','generation',
    'actor','etag','status','kind','request-hash','event-order','accepted','evidence','preparation','installation',
    'revision','enabled','extra','health-naive','health-old','health-future','missing-proof','configuration'])
def test_old_runtime_verification_rejects_unlinked_original_producer_or_binding(fault):
    args=old_runtime_verification_context();p=args[0]['predecessors'];binding=p['public.extension_runtime_binding'][0]
    op=next(o for o in p['public.extension_runtime_operation'] if o['kind']=='runtime-verify')
    events=[e for e in p['public.extension_runtime_event'] if e['operation_id']==op['operation_id']]
    proof=next(e for e in events if e['type']=='verification_committed');body=proof['payload']
    if fault=='missing-binding':p['public.extension_runtime_binding']=[]
    elif fault=='profile':binding['profile_ref']='other-profile'
    elif fault=='package-lock':binding['package_lock_ref']['lockHash']='sha256:'+'e'*64
    elif fault=='binding-revision':binding['installation_revision']+=1
    elif fault=='handle':binding['resource_handle_ref']['resources'].pop()
    elif fault=='generation':binding['generation']=str(UUID(int=999111))
    elif fault=='actor':op['requested_by']='other-actor'
    elif fault=='etag':op['expected_installation_etag']+=1
    elif fault=='status':op['status']='failed'
    elif fault=='kind':op['kind']='runtime-apply'
    elif fault=='request-hash':op['request_hash']='invalid'
    elif fault=='event-order':events[1]['type']='committing'
    elif fault=='accepted':events[0]['payload']['kind']='other-kind';events[0]['payload_hash']=reader._digest(events[0]['payload'])
    elif fault=='evidence':body['evidenceHash']='sha256:'+'e'*64
    elif fault=='preparation':body['preparationOperationId']=str(UUID(int=999111))
    elif fault=='installation':body['installationId']=str(UUID(int=999111))
    elif fault=='revision':body['installationRevision']+=1
    elif fault=='enabled':body['enabled']=True
    elif fault=='extra':body['authorized']=True
    elif fault.startswith('health-'):
        from datetime import timedelta
        observed=datetime.fromisoformat(body['healthCheckedAt'])
        body['healthCheckedAt']=(observed+timedelta(seconds=1) if fault=='health-future' else observed-timedelta(seconds=4)).isoformat()
        if fault=='health-naive':body['healthCheckedAt']=observed.replace(tzinfo=None).isoformat()
    elif fault=='missing-proof':proof['type']='verification_missing'
    else:binding['config_ref']={'configurationId':str(UUID(int=999111)),'revision':1,'hash':'sha256:'+'e'*64}
    proof['payload_hash']=reader._digest(proof['payload'])
    with pytest.raises(ValueError):verify_old_runtime_verification(args)


@pytest.mark.parametrize('seconds',[0,3])
def test_old_runtime_verification_uses_original_health_window_not_transaction_event_time(seconds):
    from datetime import timedelta
    args=old_runtime_verification_context();rows=args[0]['predecessors']['public.extension_runtime_event']
    proof=next(e for e in rows if e['type']=='verification_committed')
    observed=datetime.fromisoformat(proof['payload']['healthCheckedAt'])
    proof['payload']['healthCheckedAt']=(observed-timedelta(seconds=seconds)).isoformat()
    proof['payload_hash']=reader._digest(proof['payload'])
    assert (observed-datetime.fromisoformat(proof['occurred_at'])).total_seconds()==30
    assert verify_old_runtime_verification(args).preparations.record.state=='active'


def test_old_runtime_verification_shares_proof_kernel_and_original_configuration_decoder_context():
    args=old_runtime_verification_context();ledger=reader._WorkLedger()
    with mock.patch.object(reader,'_runtime_verification_proof',wraps=reader._runtime_verification_proof) as proof:
        result=verify_old_runtime_verification(args,ledger)
    assert proof.call_count==1 and proof.call_args.kwargs['ledger'] is ledger
    assert proof.call_args.args[0] is result.preparations and proof.call_args.args[1] is result.binding


def test_current_runtime_verification_keeps_original_receipt_graph_and_same_proof_kernel():
    args=runtime_verification_context()
    with mock.patch.object(reader,'_runtime_verification_proof',wraps=reader._runtime_verification_proof) as proof:
        result=verify_runtime_graph(args)
    assert proof.call_count==1 and result.receipt.receipt['retirement_kind']=='never_enabled'



def old_runtime_protocol_context(mode='pending', *, kind='signed_read',state='succeeded',reason=None,error=None,heartbeat=False,direction=None,dependency_kind='data'):
    args=old_runtime_verification_context();p=args[0]['predecessors']
    original=attempt_dependency_context(kind=kind,state=state,reason=reason,error=error,heartbeat=heartbeat,direction=direction,dependency_kind=dependency_kind)
    for family in ('public.extension_runtime_execution_attempt','public.extension_runtime_execution_attempt_event','public.extension_runtime_dependency_ref'):
        p[family]=deepcopy(original[0]['relations'][family])
    for index,row in enumerate(p['public.extension_runtime_outbox']):
        delivered=mode=='delivered' or (mode=='mixed' and index%2==0)
        row['attempt']=1 if delivered else 0;row['delivered_at']=row['next_attempt'] if delivered else None
    return args


def verify_old_runtime_protocol(args,ledger=None):
    packet,scope,expected,_,lock=args;ledger=reader._WorkLedger() if ledger is None else ledger
    facts=decode(packet,ledger);generation=facts.predecessors['public.extension_runtime_binding'][0]['generation']
    verification=reader._predecessor_runtime_verification(facts,scope=scope,installation_id=UUID(expected.installation_id),generation=generation,source_lock=lock,ledger=ledger)
    return reader._predecessor_runtime_protocol(facts,verification,scope=scope,ledger=ledger)


@pytest.mark.parametrize('mode',['pending','delivered','mixed'])
def test_old_runtime_protocol_keeps_complete_notification_coverage_without_ack_or_execution(mode):
    args=old_runtime_protocol_context(mode);before=deepcopy(args[0]);result=verify_old_runtime_protocol(args)
    context=result.context
    assert len(context.notifications.pending_event_ids)+len(context.notifications.delivered_event_ids)==len(args[0]['predecessors']['public.extension_runtime_event'])
    if mode!='delivered':assert context.notifications.pending_event_ids
    if mode!='pending':assert context.notifications.delivered_event_ids
    assert context.binding is result.verification.binding and len(context.attempts)==1
    assert args[0]==before and not hasattr(result,'authorized')


@pytest.mark.parametrize('kind',['signed_read','recoverable_store'])
@pytest.mark.parametrize('state,reason,error,heartbeat',[('succeeded',None,None,False),('failed',None,None,True),('failed','RECOVERABLE_EXECUTION_EXCEPTION','ValueError',False),('abandoned','ATTEMPT_LEASE_EXPIRED',None,True)])
def test_old_runtime_protocol_preserves_original_terminal_attempt_reason_and_heartbeat_shapes(kind,state,reason,error,heartbeat):
    args=old_runtime_protocol_context(kind=kind,state=state,reason=reason,error=error,heartbeat=heartbeat)
    assert len(verify_old_runtime_protocol(args).context.attempts)==1


@pytest.mark.parametrize('direction',['incoming','outgoing','self'])
@pytest.mark.parametrize('dependency_kind',['capability','data','reconcile'])
def test_old_runtime_protocol_requires_both_dependency_directions_and_exact_generation(direction,dependency_kind):
    args=old_runtime_protocol_context(direction=direction,dependency_kind=dependency_kind)
    assert len(verify_old_runtime_protocol(args).context.dependencies)==1
    row=args[0]['predecessors']['public.extension_runtime_dependency_ref'][0];row['active']=True
    with pytest.raises(ValueError):verify_old_runtime_protocol(args)


@pytest.mark.parametrize('fault',['unknown-consumer','unknown-delivered','missing-outbox','claim-past','claim-future','zero-delivered',
    'running-past-lease','future-epoch','fence-epoch','attempt-generation','missing-attempt-event','tail-state','reason','duplicate-event-id','active-dependency','dependency-generation'])
def test_old_runtime_protocol_rejects_claims_unknown_producers_and_unfinished_attempts_even_after_ttl(fault):
    args=old_runtime_protocol_context(direction='incoming');p=args[0]['predecessors'];row=p['public.extension_runtime_outbox'][0]
    attempt=p['public.extension_runtime_execution_attempt'][0];events=p['public.extension_runtime_execution_attempt_event']
    if fault in {'unknown-consumer','unknown-delivered'}:
        row['consumer_id']='other-consumer'
        if fault=='unknown-delivered':row['attempt']=1;row['delivered_at']=row['next_attempt']
    elif fault=='missing-outbox':p['public.extension_runtime_outbox'].pop()
    elif fault.startswith('claim-'):row['claim_until']='2000-01-01T00:00:00+00:00' if fault=='claim-past' else '2099-01-01T00:00:00+00:00'
    elif fault=='zero-delivered':row['delivered_at']=row['next_attempt']
    elif fault=='running-past-lease':attempt.update(state='running',completed_at=None,lease_until='2000-01-01T00:00:00+00:00')
    elif fault=='future-epoch':attempt['execution_epoch']=999
    elif fault=='fence-epoch':attempt['execution_epoch']=p['public.extension_runtime_binding'][0]['execution_epoch']
    elif fault=='attempt-generation':attempt['generation']=str(UUID(int=999111))
    elif fault=='missing-attempt-event':events.pop()
    elif fault=='tail-state':events[-1]['state']='failed'
    elif fault=='reason':attempt['terminal_reason_code']='UNKNOWN_REASON'
    elif fault=='duplicate-event-id':events[-1]['event_id']=events[0]['event_id']
    elif fault=='active-dependency':p['public.extension_runtime_dependency_ref'][0]['active']=True
    else:p['public.extension_runtime_dependency_ref'][0]['provider_generation']=str(UUID(int=999111))
    with pytest.raises(ValueError):verify_old_runtime_protocol(args)


def test_old_runtime_protocol_rejects_a_verification_parent_from_a_different_decoded_partition():
    args=old_runtime_protocol_context();packet,scope,expected,_,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    parent=reader._predecessor_runtime_verification(facts,scope=scope,installation_id=UUID(expected.installation_id),generation=facts.predecessors['public.extension_runtime_binding'][0]['generation'],source_lock=lock,ledger=ledger)
    with pytest.raises(ValueError):reader._predecessor_runtime_protocol(decode(packet,ledger),parent,scope=scope,ledger=ledger)


def test_old_runtime_protocol_uses_both_original_kernels_and_shared_budget():
    args=old_runtime_protocol_context();ledger=reader._WorkLedger()
    with mock.patch.object(reader,'_runtime_notification_rows',wraps=reader._runtime_notification_rows) as notify, \
         mock.patch.object(reader,'_attempt_dependency_rows',wraps=reader._attempt_dependency_rows) as attempts:
        result=verify_old_runtime_protocol(args,ledger)
    assert notify.call_count==attempts.call_count==1
    assert notify.call_args.kwargs['ledger'] is ledger and attempts.call_args.kwargs['ledger'] is ledger
    assert result.context.notifications.preparation_facts is result.verification.preparations


def test_current_runtime_protocol_wrappers_keep_terminal_guards_and_shared_kernels():
    args=attempt_dependency_context(direction='outgoing')
    with mock.patch.object(reader,'_runtime_notification_rows',wraps=reader._runtime_notification_rows) as notify, \
         mock.patch.object(reader,'_attempt_dependency_rows',wraps=reader._attempt_dependency_rows) as attempts:
        assert len(verify_attempt_dependencies(*args).attempts)==1
    assert notify.call_count==attempts.call_count==1
    args[0]['relations']['public.extension_runtime_binding'][0]['desired_state']='disabled'
    with pytest.raises(ValueError):verify_attempt_dependencies(*args)



def old_lease_terminal_context(count=0,lease_kind=None,mutator=None,registration_kind="FirstDispatchRegistrationReceipt",registration_defect=None,withdrawal=False,withdrawal_defect=None):
    original=withdrawal_origin_context(withdrawal_defect) if withdrawal else registration_origin_context(registration_kind,count=count,defect=registration_defect)
    def build():
        args=old_installation_record_context('active',original=original)
        prior=predecessor_lifecycle_context(context=original)
        for family in PREDECESSOR_FAMILIES:args[0]['predecessors'][family]=deepcopy(prior[0]['predecessors'][family])
        for family in _OLD_REGISTRATION_FAMILIES+('public.automation_schedule_binding','public.ecommerce_growth_runtime_command_receipt'):args[0]['predecessors'][family]=deepcopy(original[0]['relations'][family])
        if mutator is not None:mutator(args[0])
        ledger=reader._WorkLedger();facts=decode(args[0],ledger);scope=args[1]
        b=facts.predecessors['public.extension_runtime_binding'][0]
        verification=reader._predecessor_runtime_verification(facts,scope=scope,installation_id=b['installation_id'],generation=b['generation'],source_lock=args[4],ledger=ledger)
        protocol=reader._predecessor_runtime_protocol(facts,verification,scope=scope,ledger=ledger)
        cutovers=reader._predecessor_cutover_history(facts,scope=scope,ledger=ledger)
        lifecycle=reader._predecessor_lifecycle_history(facts,cutovers,scope=scope,ledger=ledger)
        refresh=reader._predecessor_refresh_history(facts,lifecycle,scope=scope,ledger=ledger)
        controls=reader._predecessor_control_history(facts,refresh,scope=scope,ledger=ledger)
        timeline=reader._predecessor_binding_timeline(facts,controls,scope=scope,ledger=ledger)
        return args,facts,protocol,timeline,ledger
    result=build()
    if lease_kind is None:return result
    args,facts,protocol,timeline,ledger=result;b=protocol.verification.binding
    versions=timeline.timelines[b['installation_id'],b['generation']].versions
    payload=dict(generation=str(b['generation']),expiresAt='2026-08-03T01:03:00+00:00')
    if lease_kind=='runtime_lease_rehydrated':
        payload['bindingRevision']=next(k for k,v in versions.items() if v.enabled and v.observed_state=='ready')
    else:payload['healthCheckedAt']='2026-08-03T01:00:00+00:00'
    if lease_kind=='runtime_inflight_lease_renewed':
        epoch=next(v.execution_epoch for v in versions.values() if v.enabled and v.observed_state=='ready')
        attempt=attempt_dependency_context(kind='recoverable_store')
        rows=deepcopy(attempt[0]['relations']['public.extension_runtime_execution_attempt'])
        rows[0].update(installation_id=str(b['installation_id']),generation=str(b['generation']),execution_epoch=epoch)
        original[0]['relations']['public.extension_runtime_execution_attempt']=rows
        original[0]['relations']['public.extension_runtime_execution_attempt_event']=deepcopy(attempt[0]['relations']['public.extension_runtime_execution_attempt_event'])
        payload.update(executionEpoch=epoch,attemptId=rows[0]['attempt_id'])
    add_preparation_renewal(original,lease_kind,payload)
    return build()


def verify_old_lease_terminals(context):
    args,facts,protocol,timeline,ledger=context
    return reader._predecessor_lease_terminals(facts,protocol,timeline,scope=args[1],ledger=ledger)


@pytest.mark.parametrize('count',[0,1,2])
@pytest.mark.parametrize('lease_kind',[None,'runtime_lease_renewed','runtime_lease_rehydrated','runtime_inflight_lease_renewed'])
def test_old_lease_terminals_join_real_old_protocol_and_control_parents_without_fake_current_graph(count,lease_kind):
    context=old_lease_terminal_context(count,lease_kind);before=deepcopy(context[0][0])
    result=verify_old_lease_terminals(context)
    assert result.protocol is context[2] and result.timeline is context[3]
    assert context[0][0]==before and not hasattr(result,'authorized')


def test_old_lease_terminals_refuse_different_native_partition_parents():
    context=old_lease_terminal_context();other=old_lease_terminal_context()
    with pytest.raises(ValueError):reader._predecessor_lease_terminals(context[1],other[2],context[3],scope=context[0][1],ledger=context[4])


def test_current_lease_history_still_uses_real_control_timeline_and_original_shared_kernel():
    args=nondispatch_context('enabled_undispatched');add_preparation_renewal(args,'runtime_lease_rehydrated')
    with mock.patch.object(reader,'_renewal_proof',wraps=reader._renewal_proof) as proof:
        assert verify_nondispatch_source(args).kind=='enabled_undispatched'
    assert proof.call_count==1



@pytest.mark.parametrize('fault',['generation','expiry-health','expiry-row','rehydrated-revision','rehydrated-bool','inflight-epoch','inflight-kind','terminal-key','terminal-hash'])
def test_old_lease_terminals_reject_wrong_historical_lease_or_preparation_terminal(fault):
    kind='runtime_lease_rehydrated' if fault.startswith('rehydrated') else 'runtime_inflight_lease_renewed' if fault.startswith('inflight') else 'runtime_lease_renewed'
    if fault.startswith('terminal'):kind=None
    def mutate(packet):
        p=packet['predecessors'];renewals=[e for e in p['public.extension_runtime_event'] if e['type'] in reader._PREPARATION_LEASE_EVENTS]
        if fault.startswith('terminal'):
            operation=next(o for o in p['public.extension_runtime_operation'] if o['kind']=='runtime-apply')
            operation['idempotency_key' if fault=='terminal-key' else 'request_hash']=''
            return
        if not renewals:return
        event=renewals[0];body=event['payload']
        if fault=='generation':body['generation']=str(UUID(int=999111))
        elif fault=='expiry-health':body['healthCheckedAt']=body['expiresAt']
        elif fault=='expiry-row':p['public.extension_runtime_resource_lease'][0]['expires_at']='2026-08-03T01:04:00+00:00'
        elif fault=='rehydrated-revision':body['bindingRevision']=999111
        elif fault=='rehydrated-bool':body['bindingRevision']=True
        elif fault=='inflight-epoch':body['executionEpoch']=999111
        else:p['public.extension_runtime_execution_attempt'][0]['operation_kind']='signed_read'
        event['payload_hash']=reader._digest(body)
    with pytest.raises(ValueError):verify_old_lease_terminals(old_lease_terminal_context(1,kind,mutate))


def test_old_lease_terminals_reject_a_control_parent_from_another_native_partition():
    context=old_lease_terminal_context();other=old_lease_terminal_context()
    with pytest.raises(ValueError):reader._predecessor_lease_terminals(context[1],context[2],other[3],scope=context[0][1],ledger=context[4])


def test_old_lease_terminals_keep_expired_historical_expiry_without_granting_a_new_lease():
    context=old_lease_terminal_context(2,'runtime_lease_renewed');before=deepcopy(context[0][0])
    result=verify_old_lease_terminals(context)
    assert len(result.renewal_operations)==1 and context[0][0]==before
    assert all(row['expires_at']<datetime(2026,10,26,tzinfo=row['expires_at'].tzinfo) for row in result.protocol.verification.preparations.resources.values())



def verify_ancestor_runtime_closure(context,locks=None):
    args,facts,protocol,timeline,ledger=context
    if locks is None:locks={protocol.verification.binding['installation_id']:args[4]}
    return reader._predecessor_runtime_closure(facts,timeline,scope=args[1],predecessor_locks=locks,ledger=ledger)


@pytest.mark.parametrize('count',[0,1,2])
@pytest.mark.parametrize('kind',[None,'runtime_lease_renewed','runtime_lease_rehydrated','runtime_inflight_lease_renewed'])
def test_ancestor_runtime_closure_consumes_only_fully_proven_old_runtime_operations(count,kind):
    context=old_lease_terminal_context(count,kind);args,facts,protocol,timeline,ledger=context;before=deepcopy(args[0]);pending=dict(timeline.pending_preparations)
    result=verify_ancestor_runtime_closure(context)
    assert result.timeline is timeline and len(result.terminals)==1 and not result.pending_locks
    assert not result.pending_preparations and dict(timeline.pending_preparations)==pending
    operations={r['operation_id']:r for r in facts.predecessors['public.extension_runtime_operation']}
    expected={identity for identity in timeline.pending_remaining_operations if operations[identity]['kind'] in {'runtime-apply','runtime-verify'}}
    assert len(expected)==2 and set(result.remaining_operations)==set(timeline.pending_remaining_operations)-expected
    assert args[0]==before and not hasattr(result,'authorized') and not hasattr(result,'complete')


def test_ancestor_runtime_closure_keeps_every_missing_lock_and_original_preparation_pending():
    context=old_lease_terminal_context(1);result=verify_ancestor_runtime_closure(context,{})
    assert not result.terminals and len(result.pending_locks)==1
    assert dict(result.pending_preparations)==dict(context[3].pending_preparations)
    assert result.remaining_operations==context[3].pending_remaining_operations


@pytest.mark.parametrize('fault',['extra-installation','wrong-lock','wrong-key-type','wrong-lock-type','foreign-lock-class'])
def test_ancestor_runtime_closure_refuses_unrelated_or_noncanonical_original_locks(fault):
    context=old_lease_terminal_context();key=context[2].verification.binding['installation_id'];lock=context[0][4];locks={key:lock}
    if fault=='extra-installation':locks[UUID(int=999111)]=lock
    elif fault=='wrong-lock':locks[key]=source_package_context()[2]
    elif fault=='wrong-key-type':locks={str(key):lock}
    elif fault=='wrong-lock-type':locks[key]=lock.model_dump(mode='python')
    else:
        class ForeignLock(type(lock)):pass
        locks[key]=ForeignLock.model_validate(lock.model_dump(mode='python',by_alias=True))
    with pytest.raises(ValueError):verify_ancestor_runtime_closure(context,locks)


def test_ancestor_runtime_closure_requires_the_same_decoded_timeline_parent_and_shared_ledger():
    context=old_lease_terminal_context();other=old_lease_terminal_context();args,facts,protocol,timeline,ledger=context
    with pytest.raises(ValueError):reader._predecessor_runtime_closure(facts,other[3],scope=args[1],predecessor_locks={},ledger=ledger)
    with mock.patch.object(reader,'_predecessor_runtime_verification',wraps=reader._predecessor_runtime_verification) as verification:
        verify_ancestor_runtime_closure(context)
    assert verification.call_count==1 and verification.call_args.kwargs['ledger'] is ledger


def test_detached_main_runtime_closure_preserves_missing_old_lock_and_all_original_pending():
    args=actual_successor_handover_context(1,1);graph=verify_detached_registration(args)
    assert graph.predecessor_runtime.timeline is graph.predecessor_timeline
    assert graph.predecessor_runtime.pending_locks and graph.predecessor_runtime.pending_preparations
    assert graph.successor_handover.pending_old_registration_refs
    assert not hasattr(graph,'authorized')


def test_detached_main_cannot_replace_missing_actual_old_source_rows_with_an_explicit_lock():
    args=actual_successor_handover_context(1,1);ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    old=facts.predecessors['public.extension_runtime_binding'][0]['installation_id']
    with pytest.raises(ValueError):reader._detached_registration_history(facts,scope=args[1],source=args[2],locked_source=args[3],source_lock=args[4],ledger=ledger,predecessor_locks={old:args[4]})



def test_ancestor_runtime_closure_does_not_consume_an_unproven_other_installation_operation():
    other_id=UUID(int=999211)
    def add_other(packet):
        p=packet['predecessors'];op=deepcopy(p['public.extension_runtime_operation'][0])
        op.update(operation_id=str(other_id),installation_id=str(UUID(int=999212)),kind='runtime-apply',
            status='failed',phase='accepted',revision=1,idempotency_key='other-installation-pending')
        p['public.extension_runtime_operation'].append(op)
        event=deepcopy(p['public.extension_runtime_event'][0]);event.update(operation_id=str(other_id),
            event_id=str(UUID(int=999213)),sequence=1,type='accepted',payload={'kind':'runtime-apply'})
        event['payload_hash']=reader._digest(event['payload']);p['public.extension_runtime_event'].append(event)
    context=old_lease_terminal_context(mutator=add_other);result=verify_ancestor_runtime_closure(context)
    assert result.terminals and other_id in result.remaining_operations
    assert other_id in context[3].pending_remaining_operations


def test_ancestor_runtime_closure_does_not_reset_the_existing_fact_work_budget():
    context=old_lease_terminal_context();ledger=context[4]
    with mock.patch.object(reader,'_MAX_ROW_VISITS',1):
        with pytest.raises(ValueError,match='budget'):verify_ancestor_runtime_closure(context)
    assert context[4] is ledger



_OLD_REGISTRATION_FAMILIES=('public.extension_dispatch_registration_receipt','public.extension_dispatch_successor_registration_receipt','public.extension_dispatch_withdrawal_receipt')


def test_ancestor_registration_input_v12_exact_literal_and_archived_v11_remains_unchanged():
    import hashlib
    root=Path(__file__).resolve().parents[4]/'.evidence/qyh-m2-terminal-source-implementation-20261025'
    old_path=root/'reader-v11-schema-literal-r305.json';old=json.loads(old_path.read_text());new=json.loads((root/'reader-v12-schema-literal-r358.json').read_text())
    assert new['priorLiteralSHA256']==hashlib.sha256(old_path.read_bytes()).hexdigest()
    assert new['relations']==old['relations'] and new['registry']==old['registry']
    expected=deepcopy(old['predecessors'])
    for row in expected:
        if row['name']=='public.bundle_composition_lock':row['columns'].append(['created_at','timestamp with time zone!'])
    assert new['predecessors'][:len(expected)]==expected
    items={r['name']:r for r in new['predecessors']};assert set(items) < set(reader._PREDECESSOR_RELATIONS)
    for name in items:
        schema=reader._PREDECESSOR_RELATIONS[name]
        assert schema.columns==tuple(map(tuple,items[name]['columns'])) and schema.key==tuple(items[name]['key']) and schema.cap==items[name]['cap']
    packet=empty_packet();packet['schema']='aos.reinstall-terminal-source-facts/v11'
    with pytest.raises(ValueError):decode(packet)


@pytest.mark.parametrize('family',_OLD_REGISTRATION_FAMILIES)
@pytest.mark.parametrize('fault',['missing-family','missing-field','duplicate-pk','scope','time'])
def test_ancestor_registration_input_requires_exact_native_fields_and_tenant(family,fault):
    packet=empty_packet();schema=reader._PREDECESSOR_RELATIONS[family];row=row_for(schema);packet['predecessors'][family]=[row]
    if fault=='missing-family':packet['predecessors'].pop(family)
    elif fault=='missing-field':row.pop('payload')
    elif fault=='duplicate-pk':packet['predecessors'][family].append(deepcopy(row))
    elif fault=='scope':row['org_id']='foreign'
    else:row['created_at']='2026-10-26T00:00:00'
    with pytest.raises(ValueError):reader._check_predecessor_scope(decode(packet),reader.TenantScope('fixture','fixture'),reader._WorkLedger())


def test_actual_old_stored_lock_is_rebuilt_from_its_original_timestamp_and_all_hashes():
    args=old_installation_record_context();ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    lock=reader._predecessor_stored_lock(facts,scope=args[1],installation_id=UUID(args[2].installation_id),ledger=ledger)
    assert type(lock) is reader.StoredCompositionLock and lock==args[4]
    assert lock.created_at==datetime.fromisoformat(args[0]['predecessors']['public.bundle_composition_lock'][0]['created_at'])
    assert reader._predecessor_stored_lock(facts,scope=args[1],installation_id=UUID(int=999111),ledger=ledger) is None


@pytest.mark.parametrize('fault',['missing-time','naive-time','missing-lock','missing-revision','wrong-hash','wrong-composition'])
def test_actual_old_stored_lock_does_not_fabricate_missing_context_when_old_head_exists(fault):
    args=old_installation_record_context();p=args[0]['predecessors'];lock=p['public.bundle_composition_lock'][0]
    if fault=='missing-time':lock.pop('created_at')
    elif fault=='naive-time':lock['created_at']='2026-10-26T00:00:00'
    elif fault=='missing-lock':p['public.bundle_composition_lock']=[]
    elif fault=='missing-revision':p['public.bundle_installation_revision']=[]
    elif fault=='wrong-hash':lock['lock_hash']='sha256:'+'e'*64
    else:p['public.bundle_installation_revision'][-1]['composition_pk']=str(UUID(int=999111))
    with pytest.raises(ValueError):reader._predecessor_stored_lock(decode(args[0]),scope=args[1],installation_id=UUID(args[2].installation_id),ledger=reader._WorkLedger())


@pytest.mark.parametrize('count',[0,1,2])
def test_actual_old_stored_lock_allows_runtime_closure_without_an_external_timestamp_or_lock(count):
    args,facts,protocol,timeline,ledger=old_lease_terminal_context(count,'runtime_lease_renewed')
    result=reader._predecessor_runtime_closure(facts,timeline,scope=args[1],predecessor_locks=None,ledger=ledger)
    assert result.terminals and not result.pending_locks and not result.pending_preparations
    explicit=reader._predecessor_runtime_closure(facts,timeline,scope=args[1],predecessor_locks={},ledger=ledger)
    assert not explicit.terminals and explicit.pending_locks



def verify_old_registration_origins(context,locks_mode=None):
    args,facts,protocol,timeline,ledger=context
    runtime=reader._predecessor_runtime_closure(facts,timeline,scope=args[1],predecessor_locks=locks_mode,ledger=ledger)
    return reader._predecessor_registration_history(facts,runtime,scope=args[1],ledger=ledger)


@pytest.mark.parametrize('kind',['FirstDispatchRegistrationReceipt','SuccessorDispatchRegistrationReceipt'])
@pytest.mark.parametrize('count',[0,1,2])
def test_old_registration_origins_use_original_receipt_snapshot_installed_and_control_pins(kind,count):
    context=old_lease_terminal_context(count,'runtime_lease_renewed',registration_kind=kind);before=deepcopy(context[0][0])
    result=verify_old_registration_origins(context)
    assert len(result.histories)==1 and not result.remaining_origin_refs and not result.pending_runtime_targets
    history=next(iter(result.histories.values()));assert len(history.origins)==1 and not history.unconsumed and not history.pending_control_roots
    assert len(result.pending_predecessors)==int(kind=='SuccessorDispatchRegistrationReceipt')
    assert context[0][0]==before and not hasattr(result,'authorized') and not hasattr(result,'complete')


@pytest.mark.parametrize('defect',['missing','binding','epoch','configuration','overlay','lock','installation-revision','ref-hash','actor','extra','body-after-row','row-after-prepare','target','request-hash'])
def test_old_registration_origins_reject_self_consistent_wrong_original_origin_or_parent(defect):
    with pytest.raises(ValueError):verify_old_registration_origins(old_lease_terminal_context(1,registration_defect=defect))


def test_old_registration_origins_do_not_consume_c_refs_before_actual_runtime_qualification():
    context=old_lease_terminal_context(1);result=verify_old_registration_origins(context,{})
    assert not result.histories and result.remaining_origin_refs and result.pending_runtime_targets


def test_old_registration_origins_refuse_runtime_parent_from_another_decoded_partition():
    context=old_lease_terminal_context();other=old_lease_terminal_context();args,facts,_,timeline,ledger=context
    runtime=reader._predecessor_runtime_closure(other[1],other[3],scope=other[0][1],predecessor_locks=None,ledger=other[4])
    with pytest.raises(ValueError):reader._predecessor_registration_history(facts,runtime,scope=args[1],ledger=ledger)


def test_current_registration_history_keeps_original_actual_control_wrapper_and_shared_kernel():
    args=registration_origin_context(count=1)
    with mock.patch.object(reader,'_registration_history_rows',wraps=reader._registration_history_rows) as shared:
        result=verify_registration_history(args)
    assert shared.call_count==1 and result.origins



def verify_old_withdrawal_origins(context,locks_mode=None):
    args,facts,protocol,timeline,ledger=context
    runtime=reader._predecessor_runtime_closure(facts,timeline,scope=args[1],predecessor_locks=locks_mode,ledger=ledger)
    registrations=reader._predecessor_registration_history(facts,runtime,scope=args[1],ledger=ledger)
    return reader._predecessor_withdrawal_history(facts,registrations,scope=args[1],ledger=ledger)


def test_ancestor_withdrawal_input_v13_exact_literal_and_old_packet_rejected():
    import hashlib
    root=Path(__file__).resolve().parents[4]/'.evidence/qyh-m2-terminal-source-implementation-20261025'
    prior=root/'reader-v12-schema-literal-r358.json';old=json.loads(prior.read_text());new=json.loads((root/'reader-v13-schema-literal-r374.json').read_text())
    assert new['priorLiteralSHA256']==hashlib.sha256(prior.read_bytes()).hexdigest()
    assert new['relations']==old['relations'] and new['registry']==old['registry']
    assert new['predecessors'][:len(old['predecessors'])]==old['predecessors']
    expected={r['name']:r for r in new['predecessors']};assert set(expected)==set(reader._PREDECESSOR_RELATIONS)
    for name,schema in reader._PREDECESSOR_RELATIONS.items():
        assert schema.columns==tuple(map(tuple,expected[name]['columns'])) and schema.key==tuple(expected[name]['key']) and schema.cap==expected[name]['cap']
    packet=empty_packet();packet['schema']='aos.reinstall-terminal-source-facts/v12'
    with pytest.raises(ValueError):decode(packet)


@pytest.mark.parametrize('family',['public.automation_schedule_binding','public.ecommerce_growth_runtime_command_receipt'])
@pytest.mark.parametrize('fault',['missing','duplicate','scope'])
def test_ancestor_withdrawal_input_requires_actual_dependency_families(family,fault):
    packet=empty_packet();row=row_for(reader._PREDECESSOR_RELATIONS[family]);packet['predecessors'][family]=[row]
    if fault=='missing':packet['predecessors'].pop(family)
    elif fault=='duplicate':packet['predecessors'][family].append(deepcopy(row))
    else:row['org_id']='foreign'
    with pytest.raises(ValueError):reader._check_predecessor_scope(decode(packet),reader.TenantScope('fixture','fixture'),reader._WorkLedger())


def test_old_withdrawal_origins_resolve_actual_first_parent_without_falsely_proving_pristine_cas():
    context=old_lease_terminal_context(withdrawal=True);before=deepcopy(context[0][0]);result=verify_old_withdrawal_origins(context)
    assert not result.remaining_receipt_ids and len(result.histories)==1
    history=next(iter(result.histories.values()))
    assert history.withdrawn_origins==(UUID(int=5401),) and history.pending_dependency_origins
    assert history.pending_installation_etags and context[0][0]==before and not hasattr(result,'authorized')


@pytest.mark.parametrize('defect',['missing-parent','wrong-parent-id','ref-hash','target','generation','group','extra','actor','executable','body-after-row','before-parent','consumed-parent'])
def test_old_withdrawal_origins_reject_wrong_parent_group_time_and_receipt(defect):
    with pytest.raises(ValueError):verify_old_withdrawal_origins(old_lease_terminal_context(withdrawal=True,withdrawal_defect=defect))


def test_old_withdrawal_origins_keep_missing_runtime_receipts_explicitly_unconsumed():
    result=verify_old_withdrawal_origins(old_lease_terminal_context(withdrawal=True),{})
    assert not result.histories and result.remaining_receipt_ids and result.pending_runtime_targets


def test_old_withdrawal_origins_require_the_same_decoded_registration_parent():
    c=old_lease_terminal_context(withdrawal=True);other=old_lease_terminal_context(withdrawal=True)
    args,facts,_,timeline,ledger=other
    runtime=reader._predecessor_runtime_closure(facts,timeline,scope=args[1],predecessor_locks=None,ledger=ledger)
    parent=reader._predecessor_registration_history(facts,runtime,scope=args[1],ledger=ledger)
    with pytest.raises(ValueError):reader._predecessor_withdrawal_history(c[1],parent,scope=c[0][1],ledger=c[4])


def test_current_withdrawal_origins_keep_original_source_wrapper_and_common_kernel():
    with mock.patch.object(reader,'_withdrawal_history_rows',wraps=reader._withdrawal_history_rows) as shared:
        assert verify_withdrawal_history(withdrawal_origin_context()).pending_dependency_origins
    assert shared.call_count==1



def test_old_withdrawal_origins_record_nonempty_schedule_and_command_dependencies_without_discharging_pending():
    command=deepcopy(command_history_context()[0]['relations']['public.ecommerce_growth_runtime_command_receipt'][0])
    def add_dependencies(packet):
        p=packet['predecessors'];binding=p['public.extension_runtime_binding'][0]
        first=p['public.extension_dispatch_withdrawal_receipt'][0]['payload']['oldDispatchSnapshot'][0]
        row=row_for(reader._PREDECESSOR_RELATIONS['public.automation_schedule_binding'])
        row.update(org_id=binding['org_id'],project_id=binding['project_id'],policy_id='ancestor-dependency',policy_revision=1,
            policy_hash='sha256:'+'a'*64,operation_id=first['operationId'],installation_id=binding['installation_id'],
            generation=binding['generation'],execution_epoch=1,timezone='Asia/Shanghai',cadence='event',weekly_day=None,
            local_time=None,effective_until=None,approved=True,enabled=False,watermark=None)
        assert (command['org_id'],command['project_id'])==(binding['org_id'],binding['project_id'])
        p['public.automation_schedule_binding']=[row]
        p['public.ecommerce_growth_runtime_command_receipt']=[deepcopy(command)]
    result=verify_old_withdrawal_origins(old_lease_terminal_context(withdrawal=True,mutator=add_dependencies))
    history=next(iter(result.histories.values()));observed=history.observed_current_dependencies[UUID(int=5401)]
    assert len(observed)==2 and {key[0] for key in observed}=={'schedule','command'}
    assert history.pending_dependency_origins and history.pending_installation_etags



@pytest.mark.parametrize('old_count',[0,1,2])
@pytest.mark.parametrize('new_count',[0,2])
def test_complete_mixed_source_joins_current_and_full_original_old_installation(old_count,new_count):
    args=actual_successor_handover_context(old_count,new_count,complete_old=True);before=deepcopy(args[0]);graph=verify_detached_registration(args)
    current=args[0]['relations']['public.bundle_installation'][0];old=args[0]['predecessors']['public.bundle_installation'][0]
    assert current['installation_id']!=old['installation_id'] and current['installation_pk']!=old['installation_pk']
    assert len(graph.successor_handover.matched)==1 and not graph.successor_handover.pending_refs
    assert graph.predecessor_runtime.terminals and not graph.predecessor_runtime.pending_locks and not graph.predecessor_runtime.pending_preparations
    assert not graph.predecessor_runtime.remaining_operations
    assert graph.predecessor_registrations.histories and not graph.predecessor_registrations.remaining_origin_refs
    assert not graph.predecessor_registrations.pending_predecessors
    assert graph.predecessor_withdrawals.histories and not graph.predecessor_withdrawals.remaining_receipt_ids
    assert args[0]==before and not hasattr(graph,'authorized') and not hasattr(graph,'complete')


def test_complete_mixed_source_missing_old_head_is_explicit_pending_not_qualified_absence():
    args=actual_successor_handover_context(1,1,complete_old=True);args[0]['predecessors']['public.bundle_installation']=[]
    graph=verify_detached_registration(args)
    assert graph.predecessor_runtime.pending_locks and graph.predecessor_registrations.remaining_origin_refs


@pytest.mark.parametrize('family',['public.bundle_composition_lock','public.extension_dispatch_registration_receipt'])
def test_complete_mixed_source_cannot_hide_missing_old_lock_or_actual_registration(family):
    args=actual_successor_handover_context(1,1,complete_old=True);args[0]['predecessors'][family]=[]
    with pytest.raises(ValueError):verify_detached_registration(args)


def test_complete_mixed_source_shared_registry_descriptor_tampering_is_rejected():
    args=actual_successor_handover_context(1,1,complete_old=True)
    args[0]['registry']['public.asset_bundle_version'][0]['content_hash']='sha256:'+'e'*64
    with pytest.raises(ValueError):verify_detached_registration(args)


@pytest.mark.parametrize('old_count,new_count',[(0,0),(2,0),(0,2)])
def test_successor_shared_detach_kernel_receives_original_row_and_same_lifecycle_parent(monkeypatch,old_count,new_count):
    args=actual_successor_handover_context(old_count,new_count,complete_old=True)
    before=deepcopy(args[0]);original=reader._successor_detach_match;calls=[]
    def observed(row,ref,predecessors,rows,*,scope,installation_id,ledger):
        calls.append((row,ref,predecessors,rows,scope,installation_id,ledger))
        return original(row,ref,predecessors,rows,scope=scope,installation_id=installation_id,ledger=ledger)
    monkeypatch.setattr(reader,'_successor_detach_match',observed)
    graph=verify_detached_registration(args)
    assert len(calls)==1 and len(graph.successor_handover.matched)==1
    row,ref,parent,rows,scope,installation_id,ledger=calls[0]
    assert parent is graph.predecessor_lifecycles
    assert rows is parent.cutovers.partition['public.extension_dispatch_lifecycle_receipt']
    assert graph.registrations.pending_predecessors[row['receipt_id']]==ref
    assert scope is args[1] and installation_id==args[2].installation_id
    assert type(ledger) is reader._WorkLedger and args[0]==before
    assert graph.successor_handover.pending_old_registration_refs


@pytest.mark.parametrize('defect',['ref-hash','snapshot-revision','group-revision','group','before-detach','same-installation'])
def test_successor_shared_detach_kernel_retains_every_original_rejection(monkeypatch,defect):
    original=reader._successor_detach_match;calls=[]
    def observed(*args,**kwargs):
        calls.append(True)
        return original(*args,**kwargs)
    monkeypatch.setattr(reader,'_successor_detach_match',observed)
    with pytest.raises(ValueError):verify_successor_handover(actual_successor_handover_context(defect=defect))
    assert calls==[True]


def test_successor_shared_detach_kernel_missing_actual_parent_stays_pending(monkeypatch):
    original=reader._successor_detach_match;results=[]
    def observed(*args,**kwargs):
        result=original(*args,**kwargs);results.append(result);return result
    monkeypatch.setattr(reader,'_successor_detach_match',observed)
    graph=verify_successor_handover(actual_successor_handover_context(defect='missing-id'))
    assert results==[None] and graph.pending_refs and not graph.matched
    assert graph.registrations.pending_predecessors and graph.unused_detach_receipts


def complete_successor_chain_context(depth=2,count=0,defect=None):
    """Build each installation from its original producers; never rewrite persisted identities."""
    from uuid import UUID as NativeUUID
    from functools import partial
    from datetime import timedelta
    from tests.asset_registry import test_composition_contracts as original
    constructor=source_history_context;package_constructor=source_package_context
    ancestors=[];registries=[];previous=None
    def shared_packages(**kwargs):
        with mock.patch(__name__+'.UUID',new=NativeUUID):return package_constructor(**kwargs)
    for index in range(depth+1):
        def scoped_uuid(*a,**k):
            if 'int' in k:k={**k,'int':k['int']+100000*(index+1)}
            return NativeUUID(*a,**k)
        kwargs=dict(count=count,idempotency_key='chain-activation-'+str(index))
        kind='FirstDispatchRegistrationReceipt'
        if previous is not None:
            parent=verify_predecessor_lifecycles(previous);identity=next(iter(parent.pairs));pair=parent.pairs[identity]
            snapshot=list(map(dict,pair.detach.dispatch_snapshot))
            actual=next(r for r in previous[0]['predecessors']['public.extension_dispatch_lifecycle_receipt'] if r['receipt_id']==str(pair.detach.receipt_id))
            registered=datetime.fromisoformat(actual['created_at'])+timedelta(microseconds=100)
            kwargs.update(old_revision=snapshot[0]['revision'],old_group_revision=snapshot[0]['cutoverGroupRevision'],group_id=snapshot[0]['cutoverGroupId'],
                predecessor_ref=dict(resourceType='DispatchDisableDetachReceipt',resourceId=str(pair.detach.receipt_id),revision=1,contentHash=pair.detach.content_hash),
                dispatch_snapshot=snapshot,registration_time=registered.isoformat(),cutover_time=(registered+timedelta(seconds=2)).isoformat())
            kind='SuccessorDispatchRegistrationReceipt'
            if index==1 and defect=='missing-detach':kwargs['predecessor_ref']['resourceId']=str(NativeUUID(int=999999))
            if index==1 and defect=='detach-hash':kwargs['predecessor_ref']['contentHash']='sha256:'+'e'*64
        with mock.patch(__name__+'.UUID',new=scoped_uuid),mock.patch.object(original,'INSTALLATION_ID',str(NativeUUID(int=8000+index))),mock.patch.object(original,'DECISION_ID',str(NativeUUID(int=28000+index))),mock.patch(__name__+'.source_package_context',new=shared_packages),                mock.patch(__name__+'.source_history_context',new=partial(constructor,installation_pk=str(NativeUUID(int=18000+index)))):
            current=registration_origin_context(kind,**kwargs)
        complete=old_installation_record_context('active',original=current);original_packet=deepcopy(current[0])
        previous=predecessor_lifecycle_context(count,context=deepcopy(current))
        for family in _OLD_INSTALLATION_FAMILIES:previous[0]['predecessors'][family]=deepcopy(complete[0]['predecessors'][family])
        for family in _OLD_REGISTRATION_FAMILIES+('public.automation_schedule_binding','public.ecommerce_growth_runtime_command_receipt'):
            previous[0]['predecessors'][family]=deepcopy(original_packet['relations'][family])
        if index<depth:ancestors.append(previous[0]);registries.append(original_packet['registry'])
    merged=current[0]['predecessors']
    for name,schema in reader._PREDECESSOR_RELATIONS.items():
        if name=='public.extension_operation_dispatch_binding':continue
        rows={}
        for packet in ancestors:
            for row in packet['predecessors'][name]:
                key=tuple(row[k] for k in schema.key)
                assert key not in rows or rows[key]==row, 'conflicting actual shared native key '+name
                rows[key]=deepcopy(row)
        merged[name]=list(rows.values())
    merged['public.extension_operation_dispatch_binding']=deepcopy(current[0]['relations']['public.extension_operation_dispatch_binding'])
    for registry in registries:assert registry==current[0]['registry']
    return current


@pytest.mark.parametrize('count',[0,1,2])
def test_ancestor_successor_graph_three_complete_installations_use_actual_original_parent_facts(count):
    args=complete_successor_chain_context(count=count);before=deepcopy(args[0]);graph=verify_detached_registration(args)
    assert len(graph.predecessor_runtime.terminals)==2
    assert len(graph.predecessor_registrations.histories)==2
    joined=graph.predecessor_successors
    assert joined.registrations is graph.predecessor_registrations
    assert joined.lifecycle is graph.predecessor_lifecycles
    assert len(joined.matched)==1 and not joined.pending_refs
    assert len(joined.ancestry_resolved_targets)==2
    assert graph.predecessor_registrations.pending_predecessors
    assert args[0]==before and not hasattr(joined,'authorized')


@pytest.mark.parametrize('defect',['missing-head','missing-detach','detach-hash'])
def test_ancestor_successor_graph_missing_actual_parent_remains_pending_or_bad_hash_rejected(defect):
    args=complete_successor_chain_context(defect=defect)
    if defect=='detach-hash':
        with pytest.raises(ValueError,match='invalid predecessor successor'):verify_detached_registration(args)
    elif defect=='missing-head':
        root=args[0]['predecessors']['public.bundle_installation'][0]['installation_id']
        args[0]['predecessors']['public.bundle_installation']=[r for r in args[0]['predecessors']['public.bundle_installation'] if r['installation_id']!=root]
        graph=verify_detached_registration(args)
        assert graph.predecessor_successors.pending_refs and not graph.predecessor_successors.ancestry_resolved_targets
    else:
        graph=verify_detached_registration(args);joined=graph.predecessor_successors
        assert len(joined.pending_refs)==1 and not joined.matched
        assert len(joined.ancestry_resolved_targets)==1
        assert joined.registrations.pending_predecessors and not joined.remaining_receipt_ids


@pytest.mark.parametrize('edges,expected',[
    ({0:set(),1:{0},2:{1}},[0,1,2]),
    ({0:set(),1:{0},2:{0},3:{1,2}},[0,1,2,3]),
    ({0:set(),1:set()},[0,1]),
])
def test_ancestor_successor_graph_topology_algorithm_orders_original_dependencies(edges,expected):
    ledger=reader._WorkLedger();before=deepcopy(edges)
    assert list(reader._ancestor_dependency_order(edges,ledger))==expected
    assert edges==before and ledger.row_visits>0


@pytest.mark.parametrize('edges',[{0:{0}},{0:{1},1:{0}},{0:{1},1:{2},2:{0}}, {0:set(),1:{2},2:{1}}])
def test_ancestor_successor_graph_topology_algorithm_rejects_cycles(edges):
    with pytest.raises(ValueError):reader._ancestor_dependency_order(edges,reader._WorkLedger())


def test_ancestor_successor_graph_topology_algorithm_is_nonrecursive_and_shares_budget():
    edges={i:({i-1} if i else set()) for i in range(1500)};ledger=reader._WorkLedger()
    assert len(reader._ancestor_dependency_order(edges,ledger))==1500
    ledger._charge(rows=reader._MAX_ROW_VISITS-ledger.row_visits)
    with pytest.raises(ValueError):reader._ancestor_dependency_order({0:set()},ledger)


@pytest.mark.parametrize('depth',[0,1,3])
def test_ancestor_successor_graph_handles_zero_one_and_deeper_actual_ancestry(depth):
    graph=verify_detached_registration(complete_successor_chain_context(depth=depth))
    assert len(graph.predecessor_successors.ancestry_resolved_targets)==depth
    assert len(graph.predecessor_successors.matched)==max(0,depth-1)
    assert not graph.predecessor_successors.pending_refs


def test_ancestor_successor_graph_rejects_separately_computed_lifecycle_even_on_same_partition():
    args=complete_successor_chain_context();packet,scope,source,locked,lock=args
    ledger=reader._WorkLedger();facts=decode(packet,ledger)
    graph=reader._detached_registration_history(facts,scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger)
    other=reader._predecessor_lifecycle_history(facts,graph.predecessor_cutovers,scope=scope,ledger=ledger)
    assert other.cutovers.partition is facts.predecessors and other is not graph.predecessor_lifecycles
    with pytest.raises(ValueError):reader._predecessor_successor_history(facts,graph.predecessor_registrations,other,scope=scope,ledger=ledger)


def test_ancestor_successor_graph_rejects_foreign_registration_parent_and_preserves_original_pending():
    args=complete_successor_chain_context();packet,scope,source,locked,lock=args
    ledger=reader._WorkLedger();facts=decode(packet,ledger)
    graph=reader._detached_registration_history(facts,scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger)
    pending=dict(graph.predecessor_registrations.pending_predecessors)
    repeated=reader._predecessor_successor_history(facts,graph.predecessor_registrations,graph.predecessor_lifecycles,scope=scope,ledger=ledger)
    assert not repeated.pending_refs and dict(graph.predecessor_registrations.pending_predecessors)==pending
    other=verify_detached_registration(args)
    with pytest.raises(ValueError):reader._predecessor_successor_history(facts,other.predecessor_registrations,graph.predecessor_lifecycles,scope=scope,ledger=ledger)
    assert dict(graph.predecessor_registrations.pending_predecessors)==pending


def test_ancestor_successor_graph_unqualified_old_runtime_retains_actual_receipt_ids():
    args=complete_successor_chain_context();packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    graph=reader._detached_registration_history(facts,scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger,predecessor_locks={})
    joined=graph.predecessor_successors
    assert not joined.matched and not joined.ancestry_resolved_targets
    assert joined.remaining_receipt_ids==tuple(r['receipt_id'] for r in facts.predecessors['public.extension_dispatch_successor_registration_receipt'])
    assert graph.predecessor_runtime.pending_preparations
    assert graph.predecessor_registrations.remaining_origin_refs


def test_ancestor_successor_graph_original_matcher_cannot_reset_exhausted_parent_budget():
    args=complete_successor_chain_context();packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    graph=reader._detached_registration_history(facts,scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger)
    ledger._charge(rows=reader._MAX_ROW_VISITS-ledger.row_visits)
    with pytest.raises(ValueError,match='budget exceeded'):
        reader._predecessor_successor_history(facts,graph.predecessor_registrations,graph.predecessor_lifecycles,scope=scope,ledger=ledger)


def verify_withdrawal_installation_pins(args,defect=None):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    cutovers=reader._cutover_history(facts,scope=scope,source=source,ledger=ledger)
    history=reader._withdrawal_history(facts,cutovers,scope=scope,source=source,ledger=ledger)
    revisions=facts.relations['public.bundle_installation_revision']
    if defect=='missing-row':revisions=tuple(r for r in revisions if r['revision']!=packet['relations']['public.extension_dispatch_registration_receipt'][1]['payload']['request']['installationRef']['revision'])
    return reader._withdrawal_installation_pins(facts.relations,history,scope=scope,installation_id=source.installation_id,
        installation_pk=locked.installation_pk,revisions=revisions,ledger=ledger)


def rehash_unused_withdrawn_installation_ref(args,field,value):
    rel=args[0]['relations'];parent=rel['public.extension_dispatch_registration_receipt'][1];withdrawal=rel['public.extension_dispatch_withdrawal_receipt'][0]
    body=parent['payload'];body['request']['installationRef'][field]=value
    parent['request_hash']=body['requestHash']=reader.canonical_sha256(body['request']);parent['content_hash']=reader.canonical_sha256(body)
    ref=dict(resourceType='FirstDispatchRegistrationReceipt',resourceId=parent['receipt_id'],revision=1,contentHash=parent['content_hash'])
    withdrawal['payload']['registrationReceiptRef']=deepcopy(ref);withdrawal['payload']['request']['registrationReceiptRef']=deepcopy(ref)
    withdrawal['request_hash']=withdrawal['payload']['requestHash']=reader.canonical_sha256(withdrawal['payload']['request'])
    withdrawal['content_hash']=reader.canonical_sha256(withdrawal['payload'])


def test_withdrawal_installation_pins_match_actual_saved_revision_without_claiming_historical_cas():
    args=withdrawal_origin_context();before=deepcopy(args[0]);pins=verify_withdrawal_installation_pins(args)
    assert len(pins.matched)==1 and pins.withdrawals.pending_installation_etags
    assert pins.pending_installation_etags is pins.withdrawals.pending_installation_etags
    assert pins.pending_dependency_origins is pins.withdrawals.pending_dependency_origins
    assert args[0]==before and not hasattr(pins,'authorized')


@pytest.mark.parametrize('field,value',[('lockHash','sha256:'+'e'*64),('overlayRevision','other-overlay')])
def test_withdrawal_installation_pins_reject_self_consistent_unused_first_ref_not_in_saved_revision(field,value):
    args=withdrawal_origin_context();rehash_unused_withdrawn_installation_ref(args,field,value)
    assert verify_withdrawal_history(args).receipts
    with pytest.raises(ValueError):verify_withdrawal_installation_pins(args)


def test_withdrawal_installation_pins_require_actual_saved_revision_row():
    args=withdrawal_origin_context()
    assert verify_withdrawal_history(args).receipts
    with pytest.raises(ValueError):verify_withdrawal_installation_pins(args,defect='missing-row')


def test_withdrawal_installation_pins_main_uses_same_history_and_keeps_original_pending():
    args=withdrawal_origin_context();graph=verify_detached_registration(args)
    pins=graph.withdrawal_installations
    assert pins.withdrawals is graph.withdrawals and len(pins.matched)==1
    assert graph.registrations.unconsumed and graph.withdrawals.pending_installation_etags
    assert not graph.predecessor_withdrawal_installations.histories


def test_withdrawal_installation_pins_main_empty_history_does_not_invent_an_origin():
    graph=verify_detached_registration(registration_origin_context())
    assert not graph.withdrawal_installations.matched
    assert not graph.withdrawal_installations.pending_installation_etags


def verify_old_withdrawal_installation_pins(context,locks_mode=None):
    args,facts,protocol,timeline,ledger=context
    history=verify_old_withdrawal_origins(context,locks_mode)
    return reader._predecessor_withdrawal_installations(facts,history,scope=args[1],ledger=ledger)


def test_old_withdrawal_installation_pins_use_original_same_runtime_and_actual_revision_rows():
    context=old_lease_terminal_context(withdrawal=True);before=deepcopy(context[0][0])
    result=verify_old_withdrawal_installation_pins(context);pins=next(iter(result.histories.values()))
    assert len(pins.matched)==1 and not result.remaining_receipt_ids
    assert pins.withdrawals is next(iter(result.withdrawals.histories.values()))
    assert pins.pending_installation_etags and pins.pending_dependency_origins
    assert context[0][0]==before and not hasattr(result,'authorized')


@pytest.mark.parametrize('field,value',[('lockHash','sha256:'+'e'*64),('overlayRevision','other-overlay')])
def test_old_withdrawal_installation_pins_reject_unused_origin_that_decoder_accepts(field,value):
    def mutate(packet):rehash_unused_withdrawn_installation_ref(({'relations':packet['predecessors']},),field,value)
    context=old_lease_terminal_context(withdrawal=True,mutator=mutate)
    assert verify_old_withdrawal_origins(context).histories
    with pytest.raises(ValueError):verify_old_withdrawal_installation_pins(context)


def test_old_withdrawal_installation_pins_missing_runtime_keeps_actual_receipts_remaining():
    result=verify_old_withdrawal_installation_pins(old_lease_terminal_context(withdrawal=True),{})
    assert not result.histories and result.remaining_receipt_ids
    assert result.withdrawals.pending_runtime_targets


def test_old_withdrawal_installation_pins_reject_foreign_decoded_parent():
    context=old_lease_terminal_context(withdrawal=True);other=old_lease_terminal_context(withdrawal=True)
    history=verify_old_withdrawal_origins(other)
    with pytest.raises(ValueError):reader._predecessor_withdrawal_installations(context[1],history,scope=context[0][1],ledger=context[4])


@pytest.mark.parametrize('fault',['foreign-scope','foreign-pk','foreign-history','budget'])
def test_withdrawal_installation_pins_scope_actual_rows_parent_and_budget_cannot_be_bypassed(fault):
    args=withdrawal_origin_context();packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    cutovers=reader._cutover_history(facts,scope=scope,source=source,ledger=ledger)
    history=reader._withdrawal_history(facts,cutovers,scope=scope,source=source,ledger=ledger)
    revisions=facts.relations['public.bundle_installation_revision'];pk=locked.installation_pk
    if fault=='foreign-scope':scope=reader.TenantScope('foreign',scope.project_id)
    elif fault=='foreign-pk':pk=UUID(int=999999)
    elif fault=='foreign-history':
        other=decode(packet,ledger);cutovers=reader._cutover_history(other,scope=scope,source=source,ledger=ledger)
        history=reader._withdrawal_history(other,cutovers,scope=scope,source=source,ledger=ledger)
    else:ledger._charge(rows=reader._MAX_ROW_VISITS-ledger.row_visits)
    with pytest.raises(ValueError):reader._withdrawal_installation_pins(facts.relations,history,scope=scope,installation_id=source.installation_id,
        installation_pk=pk,revisions=revisions,ledger=ledger)


@pytest.mark.parametrize('old_count',[0,1,2])
def test_withdrawal_installation_pins_main_mixed_source_includes_nonempty_actual_old_withdrawal(old_count):
    args=actual_successor_handover_context(old_count,1,complete_old=True,old_withdrawal=True);before=deepcopy(args[0])
    graph=verify_detached_registration(args);result=graph.predecessor_withdrawal_installations
    assert result.withdrawals is graph.predecessor_withdrawals and not result.remaining_receipt_ids
    pins=next(iter(result.histories.values()))
    assert pins.withdrawals is next(iter(graph.predecessor_withdrawals.histories.values()))
    assert len(pins.matched)==1 and pins.pending_dependency_origins and pins.pending_installation_etags
    assert graph.predecessor_registrations.histories and graph.successor_handover.matched
    assert args[0]==before and not hasattr(result,'authorized')


@pytest.mark.parametrize('depth',[0,1,2,3])
def test_registry_global_coverage_accounts_for_every_actual_shared_source_row(depth):
    args=complete_successor_chain_context(depth=depth);before=deepcopy(args[0]);graph=verify_detached_registration(args);coverage=graph.registry_coverage
    assert coverage.control is graph.control and coverage.predecessor_runtime is graph.predecessor_runtime
    assert len(coverage.targets)==depth+1
    assert not any(coverage.remaining.values())
    assert args[0]==before and not hasattr(coverage,'authorized')


def test_registry_global_coverage_unknown_extra_bundle_remains_explicit_not_filtered_to_success():
    args=actual_successor_handover_context(complete_old=True)
    row=deepcopy(args[0]['registry']['public.asset_bundle'][0]);row.update(bundle_pk=str(UUID(int=99001)),bundle_id='unexplained-package')
    args[0]['registry']['public.asset_bundle'].append(row)
    graph=verify_detached_registration(args);coverage=graph.registry_coverage
    assert coverage.remaining['public.asset_bundle']==((UUID(int=99001),),)
    assert not hasattr(coverage,'complete') and graph.successor_handover.pending_old_registration_refs


@pytest.mark.parametrize('fault',['bundle-coordinate','version-coordinate','orphan-version','orphan-artifact'])
def test_registry_global_coverage_rejects_global_alias_and_orphan_rows_before_selection(fault):
    args=actual_successor_handover_context(complete_old=True);r=args[0]['registry']
    if fault=='bundle-coordinate':
        row=deepcopy(r['public.asset_bundle'][0]);row['bundle_pk']=str(UUID(int=99001));r['public.asset_bundle'].append(row)
    elif fault=='version-coordinate':
        row=deepcopy(r['public.asset_bundle_version'][0]);row['version_pk']=str(UUID(int=99001));r['public.asset_bundle_version'].append(row)
    elif fault=='orphan-version':r['public.asset_bundle_version'][0]['bundle_pk']=str(UUID(int=99001))
    else:
        row=row_for(reader._REGISTRY['public.asset_bundle_artifact']);row.update(version_pk=str(UUID(int=99001)),relative_path='orphan.py',media_type='text/plain',size=1)
        r['public.asset_bundle_artifact'].append(row)
    with pytest.raises(ValueError):verify_detached_registration(args)


def test_registry_global_coverage_cannot_discharge_missing_old_runtime_by_shared_content():
    args=actual_successor_handover_context(complete_old=True);packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    graph=reader._detached_registration_history(facts,scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger,predecessor_locks={})
    assert len(graph.registry_coverage.targets)==1 and not any(graph.registry_coverage.remaining.values())
    assert graph.predecessor_runtime.pending_preparations


@pytest.mark.parametrize('old_members',[1,2,3])
def test_registry_global_coverage_distinct_actual_old_composition_and_package_union(old_members):
    args=actual_successor_handover_context(1,1,complete_old=True,old_member_count=old_members);before=deepcopy(args[0]);graph=verify_detached_registration(args)
    current=graph.control.timeline.history.graph.receipt.context.binding
    current_target=(current['installation_id'],current['generation']);old_target=next(iter(graph.predecessor_runtime.terminals))
    assert len(graph.registry_coverage.targets[current_target])==2
    assert len(graph.registry_coverage.targets[old_target])==old_members
    assert not any(graph.registry_coverage.remaining.values())
    assert len(args[0]['registry']['public.asset_bundle_version'])==max(2,old_members)
    assert args[0]['predecessors']['public.bundle_composition'][0]['composition_pk']!=args[0]['relations']['public.bundle_composition'][0]['composition_pk']
    assert args[0]==before and graph.successor_handover.matched


def test_registry_global_coverage_unproved_old_only_package_is_remaining_not_silently_filtered():
    args=actual_successor_handover_context(complete_old=True,old_member_count=3);packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    graph=reader._detached_registration_history(facts,scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger,predecessor_locks={})
    assert len(graph.registry_coverage.targets)==1
    assert graph.registry_coverage.remaining['public.asset_bundle_version']==((UUID(int=10002),),)
    assert graph.registry_coverage.remaining['public.asset_bundle']==((UUID(int=10002),),)
    assert graph.predecessor_runtime.pending_preparations


def test_registry_global_coverage_tampered_old_only_manifest_is_rejected_by_original_content_kernel():
    args=actual_successor_handover_context(complete_old=True,old_member_count=3)
    row=next(r for r in args[0]['registry']['public.asset_bundle_version'] if r['version_pk']==str(UUID(int=10002)))
    row['manifest_json']['spec']['tampered']=True
    with pytest.raises(ValueError):verify_detached_registration(args)


def test_registry_global_coverage_does_not_weaken_bare_current_package_strict_checker():
    args=actual_successor_handover_context(complete_old=True,old_member_count=3);ledger=reader._WorkLedger();facts=decode(args[0],ledger)
    with pytest.raises(ValueError):reader._verify_source_packages(facts,args[1],args[4],ledger)


def registry_global_coverage_parts(args):
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    graph=reader._detached_registration_history(facts,scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger)
    return facts,graph,ledger


@pytest.mark.parametrize('parent',['current','predecessor'])
def test_registry_global_coverage_rejects_same_content_parent_from_other_decoded_source(parent):
    args=actual_successor_handover_context(complete_old=True);facts,graph,ledger=registry_global_coverage_parts(args)
    other=verify_detached_registration(args)
    control=other.control if parent=='current' else graph.control
    runtime=other.predecessor_runtime if parent=='predecessor' else graph.predecessor_runtime
    with pytest.raises(ValueError):reader._registry_selection_coverage(facts,control,runtime,scope=args[1],ledger=ledger)


def test_registry_global_coverage_unselected_version_of_used_bundle_stays_remaining():
    args=actual_successor_handover_context(complete_old=True);r=args[0]['registry'];row=deepcopy(r['public.asset_bundle_version'][0])
    row['version_pk']=str(UUID(int=99001));row['version']='9.9.9';row['manifest_json']['metadata']['version']='9.9.9'
    row['content_hash']=reader.canonical_sha256(dict(manifest=row['manifest_json'],artifacts=[]));r['public.asset_bundle_version'].append(row)
    coverage=verify_detached_registration(args).registry_coverage
    assert coverage.remaining['public.asset_bundle_version']==((UUID(int=99001),),)
    assert not coverage.remaining['public.asset_bundle']


def test_registry_global_coverage_unqualified_old_only_artifact_is_retained_with_actual_key():
    args=actual_successor_handover_context(complete_old=True,old_member_count=3);r=args[0]['registry']
    row=row_for(reader._REGISTRY['public.asset_bundle_artifact']);row.update(version_pk=str(UUID(int=10002)),relative_path='unqualified.py',size=1,media_type='text/plain')
    r['public.asset_bundle_artifact'].append(row)
    packet,scope,source,locked,lock=args;ledger=reader._WorkLedger();facts=decode(packet,ledger)
    graph=reader._detached_registration_history(facts,scope=scope,source=source,locked_source=locked,source_lock=lock,ledger=ledger,predecessor_locks={})
    assert graph.registry_coverage.remaining['public.asset_bundle_artifact']==((UUID(int=10002),'unqualified.py'),)
    assert graph.predecessor_runtime.pending_preparations


def test_registry_global_coverage_uses_same_exhaustible_parent_budget():
    args=actual_successor_handover_context(complete_old=True);facts,graph,ledger=registry_global_coverage_parts(args)
    ledger._charge(rows=reader._MAX_ROW_VISITS-ledger.row_visits)
    with pytest.raises(ValueError,match='budget exceeded'):
        reader._registry_selection_coverage(facts,graph.control,graph.predecessor_runtime,scope=args[1],ledger=ledger)


def verify_predecessor_joint_proofs(context,locks_mode=None):
    args,facts,protocol,timeline,ledger=context
    runtime=reader._predecessor_runtime_closure(facts,timeline,scope=args[1],predecessor_locks=locks_mode,ledger=ledger)
    return reader._predecessor_proof_coverage(facts,runtime,scope=args[1],ledger=ledger)


@pytest.mark.parametrize('count',[0,1,2])
def test_predecessor_joint_proofs_link_actual_old_runtime_controls_and_installation_refs(count):
    context=old_lease_terminal_context(count);before=deepcopy(context[0][0]);proof=verify_predecessor_joint_proofs(context)
    assert len(proof.covered_pairs)==1
    assert not proof.remaining_disable_operations and not proof.remaining_timeline_operations
    assert not proof.remaining_refresh_control_operations and not proof.remaining_installation_refs
    original=proof.runtime.timeline.controls.refreshes
    assert bool(original.pending_installation_refs)==bool(count)
    assert original.lifecycle.pending_control_operations
    assert context[0][0]==before and not hasattr(proof,'authorized')


def test_predecessor_joint_proofs_missing_lock_does_not_discharge_parent_obligations():
    proof=verify_predecessor_joint_proofs(old_lease_terminal_context(2),{})
    assert not proof.covered_pairs
    assert proof.remaining_disable_operations and proof.remaining_timeline_operations
    assert proof.remaining_installation_refs and proof.remaining_refresh_control_operations
    assert proof.runtime.pending_preparations


@pytest.mark.parametrize('old_count',[0,1,2])
def test_predecessor_joint_proofs_main_joins_same_full_old_tree_without_mutating_original_pending(old_count):
    args=actual_successor_handover_context(old_count,1,complete_old=True,old_member_count=3)
    graph=verify_detached_registration(args);proof=graph.predecessor_proofs
    assert proof.runtime is graph.predecessor_runtime and len(proof.covered_pairs)==1
    assert not proof.remaining_installation_refs and not proof.remaining_refresh_control_operations
    assert graph.predecessor_lifecycles.pending_control_operations
    assert bool(graph.predecessor_refreshes.pending_installation_refs)==bool(old_count)


def test_predecessor_joint_proofs_empty_ancestry_does_not_invent_a_pair():
    graph=verify_detached_registration(registration_origin_context())
    assert not graph.predecessor_proofs.covered_pairs


def predecessor_joint_proofs_wrong_installation_context(field,value,count=1):
    original=detached_refresh_context
    def mutated(*args,**kwargs):
        context=original(*args,**kwargs);rows=context[0]['relations']['public.extension_dispatch_configuration_refresh_receipt']
        previous=None
        for row in sorted(rows,key=lambda r:r['revision']):
            row['request']['installationRef'][field]=value
            if previous is not None:
                row['request']['sourceAuthorityRef']=deepcopy(previous)
                row['previous_receipt_id']=previous['resourceId'];row['previous_hash']=previous['contentHash']
            rehash_original_refresh_row(row)
            previous=dict(resourceType='DispatchConfigurationRefreshReceipt',resourceId=row['receipt_id'],revision=row['revision'],contentHash=row['content_hash'])
        if rows:rebuild_lifecycle_pair_for_join_fixture(context,previous)
        return context
    with mock.patch(__name__+'.detached_refresh_context',new=mutated):return old_lease_terminal_context(count)


@pytest.mark.parametrize('field,value',[('lockHash','sha256:'+'e'*64),('overlayRevision','wrong-overlay'),('revision',1)])
@pytest.mark.parametrize('count',[1,2])
def test_predecessor_joint_proofs_reject_self_consistent_old_refresh_chain_with_wrong_saved_installation(field,value,count):
    context=predecessor_joint_proofs_wrong_installation_context(field,value,count)
    assert context[3].controls.linked_refresh_operations
    with pytest.raises(ValueError,match='invalid predecessor joint proof'):
        verify_predecessor_joint_proofs(context)


def test_predecessor_joint_proofs_require_actual_runtime_partition_and_same_budget():
    context=old_lease_terminal_context(1);other=old_lease_terminal_context(1)
    args,facts,_,timeline,ledger=context
    runtime=reader._predecessor_runtime_closure(other[1],other[3],scope=args[1],predecessor_locks=None,ledger=other[4])
    with pytest.raises(ValueError):reader._predecessor_proof_coverage(facts,runtime,scope=args[1],ledger=ledger)
    runtime=reader._predecessor_runtime_closure(facts,timeline,scope=args[1],predecessor_locks=None,ledger=ledger)
    ledger._charge(rows=reader._MAX_ROW_VISITS-ledger.row_visits)
    with pytest.raises(ValueError):reader._predecessor_proof_coverage(facts,runtime,scope=args[1],ledger=ledger)


class SourcePortFactsConnection(CurrentPermissionConnection):
    def __init__(self,packet,*,roles=('admin','admin'),failure=None):
        super().__init__(roles=roles);self.packet=deepcopy(packet);self.failure=failure;self.facts_calls=0;self.content_calls=0
    def execute(self,query,params=()):
        if 'public.reinstall_terminal_source_facts_v1' in query:
            self.calls.append((query,params));self.facts_calls+=1
            if self.failure is not None:raise self.failure
            return CurrentPermissionResult(row={'facts':deepcopy(self.packet)})
        if 'AS eligible' in query:
            self.calls.append((query,params));self.content_calls+=1
            return CurrentPermissionResult(rows=[{'eligible':True}])
        return super().execute(query,params)


def concrete_source_port_context(kind='detached'):
    from aos_api.asset_registry.composition_contracts import CreateInstallationRequest
    from aos_api.asset_registry.reinstall_origin_store import PostgresReinstallOriginAppender
    if kind=='content':args=source_history_context('active')
    elif kind=='approved':args=source_history_context('approved',backend=True)
    elif kind=='detached':args=registration_origin_context(count=1)
    else:args=nondispatch_context(kind)
    target_lock=args[4].model_copy(update={'composition_id':str(UUID(int=99010))})
    target=CreateInstallationRequest(compositionId=target_lock.composition_id,lockRevision=target_lock.revision,overlayRevision='port-fixture',displayName='Port fixture')
    appender=PostgresReinstallOriginAppender();port=reader.PostgresTerminalSourceReader(appender=appender)
    kwargs=dict(org_id=args[1].org_id,project_id=args[1].project_id,actor='fixture-user',markings=(),source=args[2],locked_source=args[3],source_lock=args[4],target=target,target_lock=target_lock)
    return args,port,appender,kwargs


@pytest.mark.parametrize('kind',['content','approved','never_enabled','configured_unactivated','enabled_undispatched','detached'])
def test_concrete_source_port_runs_original_six_branch_proof_on_same_caller_connection(kind):
    args,port,appender,kwargs=concrete_source_port_context(kind);before=deepcopy(args[0]);conn=SourcePortFactsConnection(args[0])
    from aos_api.extension_runtime import ui_current_principal as current
    with mock.patch.object(current,'openfga_api_url',lambda:None):result=port.check_current(conn,**kwargs)
    assert result is True and conn.membership_reads==2 and conn.facts_calls==1
    assert conn.content_calls==int(kind=='content') and args[0]==before
    facts=next(params for query,params in conn.calls if 'public.reinstall_terminal_source_facts_v1' in query)
    assert facts==(*args[1].key,UUID(args[2].installation_id),args[2].terminal_revision)


@pytest.mark.parametrize('roles',[(None,'admin'),('admin',None)])
def test_concrete_source_port_reads_current_source_and_target_permissions_before_facts(roles):
    args,port,_,kwargs=concrete_source_port_context('never_enabled');conn=SourcePortFactsConnection(args[0],roles=roles)
    from aos_api.extension_runtime import ui_current_principal as current
    with mock.patch.object(current,'openfga_api_url',lambda:None),pytest.raises((ValueError,PermissionError)):
        port.check_current(conn,**kwargs)
    assert conn.facts_calls==0


def test_concrete_source_port_preserves_driver_failure_without_retry_or_append():
    args,port,appender,kwargs=concrete_source_port_context();failure=RuntimeError('synthetic readlock fault');conn=SourcePortFactsConnection(args[0],failure=failure)
    from aos_api.extension_runtime import ui_current_principal as current
    # Only the fact read fails; keep principal reads available on the fake driver.
    conn.failure=None
    original=conn.execute
    def failing(query,params=()):
        if 'public.reinstall_terminal_source_facts_v1' in query:
            conn.facts_calls+=1;raise failure
        return original(query,params)
    conn.execute=failing
    with mock.patch.object(current,'openfga_api_url',lambda:None),pytest.raises(RuntimeError) as error:port.check_current(conn,**kwargs)
    assert error.value is failure and conn.facts_calls==1


@pytest.mark.parametrize('fault',['target-lock','source-ref','schema','transaction'])
def test_concrete_source_port_rejects_bad_trusted_inputs_or_fact_packet(fault):
    from psycopg.pq import TransactionStatus
    args,port,_,kwargs=concrete_source_port_context('never_enabled');conn=SourcePortFactsConnection(args[0])
    if fault=='target-lock':kwargs['target_lock']=args[4]
    elif fault=='source-ref':kwargs['source']=kwargs['source'].model_copy(update={'terminal_revision':1})
    elif fault=='schema':conn.packet['schema']='untrusted-version'
    else:conn.info.transaction_status=TransactionStatus.IDLE
    from aos_api.extension_runtime import ui_current_principal as current
    expected=RuntimeError if fault=='transaction' else (ValueError,TypeError)
    with mock.patch.object(current,'openfga_api_url',lambda:None),pytest.raises(expected):
        port.check_current(conn,**kwargs)


def test_concrete_source_port_constructor_has_no_callback_connector_or_branch_bypass():
    import inspect
    from aos_api.asset_registry.reinstall_origin_store import PostgresReinstallOriginAppender
    with pytest.raises(TypeError):reader.PostgresTerminalSourceReader(appender=object())
    assert set(inspect.signature(reader.PostgresTerminalSourceReader).parameters)=={'appender'}
    signature=inspect.signature(reader.PostgresTerminalSourceReader.check_current)
    assert set(signature.parameters)=={'self','conn','org_id','project_id','actor','markings','source','locked_source','source_lock','target','target_lock'}
    assert isinstance(reader.PostgresTerminalSourceReader(appender=PostgresReinstallOriginAppender()),reader.PostgresTerminalSourceReader)


def test_concrete_source_port_append_delegates_actual_original_sql_same_connection_and_none():
    from types import SimpleNamespace
    from psycopg.pq import TransactionStatus
    from tests.asset_registry import test_reinstall_origin_store as original
    case=original.OriginAppendTests();case.setUp()
    try:
        case.conn.info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        port=reader.PostgresTerminalSourceReader(appender=case.store)
        assert port.append_origin(case.conn,**case.args) is None
        assert len(case.conn.calls)==1
        assert 'INSERT INTO public.bundle_installation_reinstall_origin' in case.conn.calls[0][0]
        assert case.conn.calls[0][1]['source_pk']==case.locked.installation_pk
    finally:case.doCleanups()


def test_concrete_source_port_append_rejects_non_none_original_return():
    from types import SimpleNamespace
    from psycopg.pq import TransactionStatus
    from tests.asset_registry import test_reinstall_origin_store as original
    case=original.OriginAppendTests();case.setUp()
    try:
        case.conn.info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        port=reader.PostgresTerminalSourceReader(appender=case.store)
        with mock.patch.object(type(case.store),'append_origin',return_value=False),pytest.raises(ValueError):
            port.append_origin(case.conn,**case.args)
        assert not case.conn.calls
    finally:case.doCleanups()


def test_concrete_source_port_rechecks_both_permissions_on_each_same_connection_call():
    args,port,_,kwargs=concrete_source_port_context('never_enabled');conn=SourcePortFactsConnection(args[0])
    from aos_api.extension_runtime import ui_current_principal as current
    with mock.patch.object(current,'openfga_api_url',lambda:None):
        assert port.check_current(conn,**kwargs) is True
        conn.roles=['admin',None];conn.membership_reads=0
        with pytest.raises((ValueError,PermissionError)):port.check_current(conn,**kwargs)
    assert conn.membership_reads==2 and conn.facts_calls==1


def test_concrete_source_port_accepts_proved_mixed_old_packages_and_rejects_missing_old_runtime():
    _,port,_,kwargs=concrete_source_port_context();args=actual_successor_handover_context(1,1,complete_old=True,old_member_count=3)
    kwargs.update(source=args[2],locked_source=args[3],source_lock=args[4]);conn=SourcePortFactsConnection(args[0])
    from aos_api.extension_runtime import ui_current_principal as current
    with mock.patch.object(current,'openfga_api_url',lambda:None):assert port.check_current(conn,**kwargs) is True
    old_id=args[0]['predecessors']['public.bundle_installation'][0]['installation_id']
    args[0]['predecessors']['public.bundle_installation']=[r for r in args[0]['predecessors']['public.bundle_installation'] if r['installation_id']!=old_id]
    conn=SourcePortFactsConnection(args[0])
    with mock.patch.object(current,'openfga_api_url',lambda:None),pytest.raises(ValueError):port.check_current(conn,**kwargs)


def test_concrete_source_port_old_supplied_markings_cannot_replace_current_target_bearer():
    args,port,_,kwargs=concrete_source_port_context('never_enabled')
    _,_,target_lock=source_package_context(backend=True,markings=('target-mark',))
    kwargs['target_lock']=target_lock.model_copy(update={'composition_id':kwargs['target'].composition_id})
    kwargs['markings']=('target-mark',);conn=SourcePortFactsConnection(args[0]);conn.bearers=set()
    from aos_api.extension_runtime import ui_current_principal as current
    with mock.patch.object(current,'openfga_api_url',lambda:None),pytest.raises((ValueError,PermissionError)):
        port.check_current(conn,**kwargs)
    assert conn.membership_reads==2 and conn.facts_calls==0


def test_concrete_source_port_explicit_unexplained_registry_obligation_cannot_be_admitted():
    args,port,_,kwargs=concrete_source_port_context();packet=deepcopy(args[0]);extra=deepcopy(packet['registry']['public.asset_bundle'][0])
    extra.update(bundle_pk=str(UUID(int=99080)),bundle_id='unexplained-port-input');packet['registry']['public.asset_bundle'].append(extra)
    assert verify_detached_registration((packet,*args[1:])).registry_coverage.remaining['public.asset_bundle']
    conn=SourcePortFactsConnection(packet)
    from aos_api.extension_runtime import ui_current_principal as current
    with mock.patch.object(current,'openfga_api_url',lambda:None),pytest.raises(ValueError):port.check_current(conn,**kwargs)


def test_concrete_source_port_driver_fact_row_cannot_smuggle_authorized_flag():
    args,port,_,kwargs=concrete_source_port_context();conn=SourcePortFactsConnection(args[0]);original=conn.execute
    def extra_column(query,params=()):
        if 'public.reinstall_terminal_source_facts_v1' in query:return CurrentPermissionResult(row={'facts':deepcopy(conn.packet),'authorized':True})
        return original(query,params)
    conn.execute=extra_column
    from aos_api.extension_runtime import ui_current_principal as current
    with mock.patch.object(current,'openfga_api_url',lambda:None),pytest.raises(ValueError):port.check_current(conn,**kwargs)
