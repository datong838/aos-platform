from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "memoryctl.py"
SPEC = importlib.util.spec_from_file_location("memoryctl", MODULE_PATH)
assert SPEC and SPEC.loader
memoryctl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(memoryctl)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def authority(revision: str = "AOS-000001") -> dict[str, object]:
    return {
        "schema": "aos-memory-authority/v1",
        "project": "AOS",
        "project_revision": revision,
        "authority_owner": "test",
        "current_phase": "SHARED_MEMORY_PHASE2",
        "delivery_status": "IMPLEMENTED_GREEN",
        "last_green_gate": "SHARED_MEMORY_PHASE1",
        "next_gate": "SHARED_MEMORY_PHASE3",
        "source_commits": {"aos-platform": "abc1234", "docs": "def5678"},
        "source_files": ["docs/status.md", "docs/checkpoint.md"],
        "hard_boundaries": ["org-org/dev-project only"],
        "completed": ["phase 1"],
        "incomplete": ["phase 3"],
        "next_steps": ["run phase 3"],
        "evidence": [{"kind": "test", "ref": "unit"}],
        "evidence_cutoff": "2026-08-12T12:00:00+08:00",
        "updated_at": "2026-08-12T12:00:00+08:00",
    }


def paths(tmp_path: Path, projections: list[dict[str, object]]) -> object:
    context = tmp_path / "context"
    ai_root = tmp_path / "ai"
    codex = tmp_path / "codex"
    prime = tmp_path / "prime" / "harness_state.json"
    write_json(context / "memory" / "authority.json", authority())
    write_json(
        context / "memory" / "projection-manifest.json",
        {
            "schema": "aos-memory-projection-manifest/v1",
            "authority": "${CONTEXT_ROOT}/memory/authority.json",
            "projections": projections,
        },
    )
    schema_directory = context / "memory" / "schemas"
    for name in (
        "authority.schema.json",
        "event.schema.json",
        "health.schema.json",
        "leases.schema.json",
        "projection.schema.json",
        "projection-manifest.schema.json",
        "task-receipt.schema.json",
        "delivery-receipt.schema.json",
        "prime-version-state.schema.json",
    ):
        write_json(schema_directory / name, {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"})
    write_json(
        context / "memory" / "prime-version-state.json",
        {
            "schema": "aos-memory-prime-version-state/v1",
            "updated_at": "2026-08-12T12:00:00+08:00",
            "entries": {},
        },
    )
    write_json(
        context / "memory" / "templates" / "task-receipt-template.json",
        {
            "schema": "aos-memory-task-receipt/v1",
            "task_id": "replace-me",
            "owner": "replace-me",
            "base_revision": "AOS-000001",
            "scope": ["replace-me"],
            "excluded_scope": [],
            "expected_outputs": [],
            "lease_expires_at": "2099-01-01T00:00:00+08:00",
            "status": "ACTIVE",
            "created_at": "2026-08-12T12:00:00+08:00",
        },
    )
    write_json(
        context / "memory" / "templates" / "delivery-receipt-template.json",
        {
            "schema": "aos-memory-delivery-receipt/v1",
            "task_id": "replace-me",
            "base_revision": "AOS-000001",
            "completed_revision": "AOS-000002",
            "result": "IMPLEMENTED_GREEN",
            "changed_files": [],
            "commits": [],
            "verification": [],
            "risks": [],
            "blockers": [],
            "completed_at": "2026-08-12T12:00:00+08:00",
        },
    )
    return memoryctl.MemoryPaths(
        ai_root=ai_root,
        context_root=context,
        codex_memory_root=codex,
        prime_harness_state=prime,
    )


def test_content_hash_ignores_runtime_noise() -> None:
    first = authority()
    second = authority()
    second["updated_at"] = "2030-01-01T00:00:00+08:00"
    second["evidence_cutoff"] = "2030-01-01T00:00:00+08:00"
    assert memoryctl.authority_content_hash(first) == memoryctl.authority_content_hash(second)


def test_sync_is_dry_run_then_idempotent_apply(tmp_path: Path) -> None:
    status_path = "${CONTEXT_ROOT}/01-status.md"
    projection_path = "${CONTEXT_ROOT}/memory/projections/project.json"
    codex_path = "${CODEX_MEMORY_ROOT}/extensions/ad_hoc/notes"
    p = paths(
        tmp_path,
        [
            {"id": "status", "adapter": "authority_frontmatter", "consistency": "strong", "path": status_path},
            {"id": "project", "adapter": "json_file", "consistency": "strong", "path": projection_path},
            {"id": "codex", "adapter": "codex_ad_hoc", "consistency": "eventual", "path": codex_path},
        ],
    )
    status_file = p.context_root / "01-status.md"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text("# status\n", encoding="utf-8")

    dry = memoryctl.sync_projections(p, apply=False)
    assert dry["changed"] == 3
    assert not (p.context_root / "memory/projections/project.json").exists()

    first = memoryctl.sync_projections(p, apply=True)
    original = (p.context_root / "memory/projections/project.json").read_text()
    projection = json.loads(original)
    assert projection["generated_at"] == "2026-08-12T12:00:00+08:00"
    second = memoryctl.sync_projections(p, apply=True)
    assert first["changed"] == 3
    assert second["changed"] == 0
    assert (p.context_root / "memory/projections/project.json").read_text() == original
    assert "project_revision: AOS-000001" in status_file.read_text()
    assert "Authority 管理状态（自动生成，请勿手改）" in status_file.read_text()

    report = memoryctl.memory_status(p)
    statuses = {item["id"]: item["status"] for item in report["projections"]}
    assert statuses == {"status": "CURRENT", "project": "CURRENT", "codex": "PENDING_ASYNC"}
    assert report["overall"] == "GREEN_WITH_WARNINGS"


def test_status_detects_stale_ahead_drifted_and_unavailable(tmp_path: Path) -> None:
    projections = []
    for name in ("stale", "ahead", "drifted", "missing"):
        projections.append(
            {
                "id": name,
                "adapter": "json_file",
                "consistency": "strong",
                "path": f"${{CONTEXT_ROOT}}/memory/projections/{name}.json",
            }
        )
    p = paths(tmp_path, projections)
    expected = memoryctl.canonical_projection(authority())
    stale = dict(expected, project_revision="AOS-000000")
    ahead = dict(expected, project_revision="AOS-000002")
    drifted = dict(expected, content_hash="sha256:bad")
    write_json(p.context_root / "memory/projections/stale.json", stale)
    write_json(p.context_root / "memory/projections/ahead.json", ahead)
    write_json(p.context_root / "memory/projections/drifted.json", drifted)

    report = memoryctl.memory_status(p)
    statuses = {item["id"]: item["status"] for item in report["projections"]}
    assert statuses == {
        "stale": "STALE",
        "ahead": "AHEAD",
        "drifted": "DRIFTED",
        "missing": "UNAVAILABLE",
    }
    assert report["overall"] == "RED"


def test_full_json_and_managed_frontmatter_drift_are_detected(tmp_path: Path) -> None:
    p = paths(
        tmp_path,
        [
            {
                "id": "project",
                "adapter": "json_file",
                "consistency": "strong",
                "path": "${CONTEXT_ROOT}/memory/projections/project.json",
            },
            {
                "id": "status",
                "adapter": "authority_frontmatter",
                "consistency": "strong",
                "path": "${CONTEXT_ROOT}/status.md",
            },
        ],
    )
    (p.context_root / "status.md").write_text("# status\n", encoding="utf-8")
    memoryctl.sync_projections(p, apply=True)
    projection_path = p.context_root / "memory/projections/project.json"
    projection = json.loads(projection_path.read_text())
    projection["current_phase"] = "tampered"
    write_json(projection_path, projection)
    status_path = p.context_root / "status.md"
    status_path.write_text(status_path.read_text().replace("SHARED_MEMORY_PHASE2", "tampered", 1), encoding="utf-8")
    statuses = {item["id"]: item["status"] for item in memoryctl.memory_status(p)["projections"]}
    assert statuses == {"project": "DRIFTED", "status": "DRIFTED"}


def test_prime_projection_marker_is_checked(tmp_path: Path) -> None:
    p = paths(
        tmp_path,
        [
            {
                "id": "prime",
                "adapter": "prime_harness",
                "consistency": "strong",
                "entry_id": "aos-milestones",
            }
        ],
    )
    expected = memoryctl.canonical_projection(authority())
    marker = memoryctl.projection_marker(expected)
    content = f"facts\n{marker}\n"
    write_json(p.prime_harness_state, {"entries": {"memory": {"aos-milestones": {"content": content, "version": 2}}}})
    write_json(
        p.prime_version_state_path,
        {
            "schema": "aos-memory-prime-version-state/v1",
            "updated_at": "2026-08-12T12:00:00+08:00",
            "entries": {
                "aos-milestones": {
                    "version": 2,
                    "project_revision": "AOS-000001",
                    "authority_content_hash": expected["content_hash"],
                    "entry_content_hash": "sha256:" + hashlib.sha256(content.encode()).hexdigest(),
                }
            },
        },
    )
    assert memoryctl.memory_status(p)["projections"][0]["status"] == "DRIFTED"

    data = json.loads(p.prime_harness_state.read_text())
    current_content = memoryctl.prime_projection_block(expected)
    data["entries"]["memory"]["aos-milestones"]["content"] = current_content
    write_json(p.prime_harness_state, data)
    state = json.loads(p.prime_version_state_path.read_text())
    state["entries"]["aos-milestones"]["entry_content_hash"] = "sha256:" + hashlib.sha256(
        current_content.encode()
    ).hexdigest()
    write_json(p.prime_version_state_path, state)
    assert memoryctl.memory_status(p)["projections"][0]["status"] == "CURRENT"

    data["entries"]["memory"]["aos-milestones"]["version"] = 1
    write_json(p.prime_harness_state, data)
    assert memoryctl.memory_status(p)["projections"][0]["status"] == "DRIFTED"

    data["entries"]["memory"]["aos-milestones"]["version"] = 2
    data["entries"]["memory"]["aos-milestones"]["content"] = "facts without marker"
    write_json(p.prime_harness_state, data)
    assert memoryctl.memory_status(p)["projections"][0]["status"] == "UNVERSIONED"


def test_prime_sync_recovers_monotonic_version_and_is_idempotent(tmp_path: Path) -> None:
    p = paths(
        tmp_path,
        [
            {
                "id": "prime",
                "adapter": "prime_harness",
                "consistency": "strong",
                "entry_id": "aos-milestones",
                "title": "AOS Milestones",
                "path": "aos/milestones",
            }
        ],
    )
    write_json(
        p.prime_harness_state,
        {
            "schema": 1,
            "entries": {
                "memory": {
                    "aos-milestones": {
                        "id": "aos-milestones",
                        "kind": "memory",
                        "title": "AOS Milestones",
                        "content": "historical facts",
                        "path": "aos/milestones",
                        "scope": "global",
                        "reference": {},
                        "arguments": {},
                        "metadata": {},
                        "source": "agent",
                        "created_at": "2026-08-08T00:00:00+00:00",
                        "updated_at": "2026-08-08T00:00:00+00:00",
                        "version": 1,
                    }
                }
            },
            "refinements": [{"id": "keep-me"}],
        },
    )
    write_json(
        p.prime_version_state_path,
        {
            "schema": "aos-memory-prime-version-state/v1",
            "updated_at": "2026-08-12T11:00:00+08:00",
            "entries": {
                "aos-milestones": {
                    "version": 21,
                    "project_revision": "AOS-000000",
                    "authority_content_hash": "sha256:" + "0" * 64,
                    "entry_content_hash": "sha256:" + "0" * 64,
                }
            },
        },
    )

    first = memoryctl.sync_projections(p, apply=True, include_prime=True)
    harness = json.loads(p.prime_harness_state.read_text())
    entry = harness["entries"]["memory"]["aos-milestones"]
    assert first["changed"] == 1
    assert entry["version"] == 22
    assert entry["content"].startswith("<!-- AOS_PRIME_PROJECTION_BEGIN -->")
    assert "## 历史材料（仅供追溯，可能过时）\n\nhistorical facts" in entry["content"]
    assert "AOS-000001" in entry["content"]
    assert harness["refinements"] == [{"id": "keep-me"}]
    state = json.loads(p.prime_version_state_path.read_text())
    assert state["entries"]["aos-milestones"]["version"] == 22
    assert memoryctl.memory_status(p)["projections"][0]["status"] == "CURRENT"

    first_harness = p.prime_harness_state.read_text()
    first_state = p.prime_version_state_path.read_text()
    second = memoryctl.sync_projections(p, apply=True, include_prime=True)
    assert second["changed"] == 0
    assert p.prime_harness_state.read_text() == first_harness
    assert p.prime_version_state_path.read_text() == first_state
    assert list((p.prime_harness_state.parent / "backups").glob("*.json"))


def test_gate_separates_delivery_and_memory(tmp_path: Path) -> None:
    p = paths(
        tmp_path,
        [
            {
                "id": "project",
                "adapter": "json_file",
                "consistency": "strong",
                "path": "${CONTEXT_ROOT}/memory/projections/project.json",
            }
        ],
    )
    report = memoryctl.memory_status(p)
    gate = memoryctl.evaluate_gate(memoryctl.load_authority(p), report)
    assert gate == {"delivery_status": "IMPLEMENTED_GREEN", "memory_health": "RED", "can_change_state": False}


def test_authority_update_uses_cas_and_increments_revision(tmp_path: Path) -> None:
    p = paths(tmp_path, [])
    updated = memoryctl.update_authority(
        p,
        expected_revision="AOS-000001",
        current_phase="SHARED_MEMORY_PHASE3",
        delivery_status="IN_PROGRESS",
        last_green_gate="SHARED_MEMORY_PHASE2",
        next_gate="SHARED_MEMORY_PHASE3",
    )
    assert updated["project_revision"] == "AOS-000002"
    with pytest.raises(memoryctl.RevisionConflict):
        memoryctl.update_authority(
            p,
            expected_revision="AOS-000001",
            current_phase="bad",
            delivery_status="IN_PROGRESS",
            last_green_gate="bad",
            next_gate="bad",
        )


def test_task_receipt_lease_conflict_and_delivery_release(tmp_path: Path) -> None:
    p = paths(tmp_path, [])
    task = memoryctl.start_task(
        p,
        task_id="task-1",
        owner="codex",
        expected_revision="AOS-000001",
        scope=["scripts/memory"],
        excluded_scope=[],
        expected_outputs=["memoryctl.py"],
        lease_expires_at="2099-01-01T00:00:00+08:00",
    )
    assert task["status"] == "ACTIVE"
    with pytest.raises(memoryctl.LeaseConflict):
        memoryctl.start_task(
            p,
            task_id="task-2",
            owner="other",
            expected_revision="AOS-000001",
            scope=["scripts/memory/tests"],
            excluded_scope=[],
            expected_outputs=[],
            lease_expires_at="2099-01-01T00:00:00+08:00",
        )

    memoryctl.update_authority(
        p,
        expected_revision="AOS-000001",
        current_phase="SHARED_MEMORY_PHASE3",
        delivery_status="IN_PROGRESS",
        last_green_gate="SHARED_MEMORY_PHASE2",
        next_gate="SHARED_MEMORY_PHASE3",
    )
    delivery = memoryctl.complete_task(
        p,
        task_id="task-1",
        expected_revision="AOS-000002",
        result="IMPLEMENTED_GREEN",
        changed_files=["scripts/memory/memoryctl.py"],
        commits=["abc1234"],
        verification=["8 passed"],
        risks=[],
        blockers=[],
    )
    assert delivery["result"] == "IMPLEMENTED_GREEN"
    assert delivery["base_revision"] == "AOS-000001"
    assert delivery["completed_revision"] == "AOS-000002"
    leases = json.loads((p.context_root / "memory/leases.json").read_text())
    assert leases["leases"] == []
    events = list((p.context_root / "memory/events").glob("*.jsonl"))
    assert events and len(events[0].read_text().splitlines()) == 3


def test_task_receipt_rejects_path_traversal_and_expired_lease(tmp_path: Path) -> None:
    p = paths(tmp_path, [])
    with pytest.raises(memoryctl.MemoryErrorBase):
        memoryctl.start_task(
            p,
            task_id="../../escape",
            owner="codex",
            expected_revision="AOS-000001",
            scope=["scripts/memory"],
            excluded_scope=[],
            expected_outputs=[],
            lease_expires_at="2099-01-01T00:00:00+08:00",
        )
    with pytest.raises(memoryctl.MemoryErrorBase):
        memoryctl.start_task(
            p,
            task_id="absolute",
            owner="codex",
            expected_revision="AOS-000001",
            scope=["/Users/ddt/project"],
            excluded_scope=[],
            expected_outputs=[],
            lease_expires_at="2099-01-01T00:00:00+08:00",
        )
    with pytest.raises(memoryctl.MemoryErrorBase):
        memoryctl.start_task(
            p,
            task_id="expired",
            owner="codex",
            expected_revision="AOS-000001",
            scope=["scripts/memory"],
            excluded_scope=[],
            expected_outputs=[],
            lease_expires_at="2000-01-01T00:00:00+08:00",
        )


def test_validate_and_monitor_write_read_only_health_snapshot(tmp_path: Path) -> None:
    p = paths(
        tmp_path,
        [
            {
                "id": "project",
                "adapter": "json_file",
                "consistency": "strong",
                "path": "${CONTEXT_ROOT}/memory/projections/project.json",
            }
        ],
    )
    memoryctl.sync_projections(p, apply=True)
    assert memoryctl.validate_installation(p)["status"] == "GREEN"
    before = p.authority_path.read_text(encoding="utf-8")
    target = tmp_path / "runtime" / "health.json"
    health = memoryctl.monitor_once(p, output_path=target)
    assert health["memory_health"] == "GREEN"
    assert health["can_change_state"] is True
    assert target.exists()
    assert p.authority_path.read_text(encoding="utf-8") == before

    invalid = json.loads(p.authority_path.read_text())
    invalid["project_revision"] = "invalid-revision"
    write_json(p.authority_path, invalid)
    with pytest.raises(memoryctl.MemoryErrorBase):
        memoryctl.validate_installation(p)


def test_secret_scanner_fails_closed(tmp_path: Path) -> None:
    p = paths(tmp_path, [])
    payload = authority()
    payload["completed"] = ["token=sk-live-example-secret-value"]
    write_json(p.authority_path, payload)
    with pytest.raises(memoryctl.SecretDetected):
        memoryctl.load_authority(p)


def test_cli_parser_accepts_wrapper_argument_order() -> None:
    parser = memoryctl.build_parser()
    sync = parser.parse_args(["sync", "--json", "--apply", "--prime"])
    status = parser.parse_args(["status", "--json"])
    validate = parser.parse_args(["validate", "--json"])
    monitor = parser.parse_args(["monitor", "--json"])
    quiet_monitor = parser.parse_args(["monitor", "--quiet"])
    assert sync.command == "sync" and sync.as_json and sync.apply and sync.prime
    assert status.command == "status" and status.as_json
    assert validate.command == "validate" and validate.as_json
    assert monitor.command == "monitor" and monitor.as_json
    assert quiet_monitor.command == "monitor" and quiet_monitor.quiet


def test_builtin_schema_validator_rejects_wrong_type() -> None:
    with pytest.raises(memoryctl.MemoryErrorBase):
        memoryctl.validate_json_schema("not-an-array", {"type": "array"}, source="unit")
