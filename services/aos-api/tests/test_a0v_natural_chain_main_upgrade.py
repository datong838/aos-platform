from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "scripts/a0v_natural_chain_main_upgrade.py"


def load_module():
    spec = importlib.util.spec_from_file_location("a0v_natural_chain_main_upgrade_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_upgrade_range_is_exact_and_bounded():
    module = load_module()
    assert module.SOURCE == "a0v_038" and module.TARGET == "a0v_050"
    assert module.CHAIN == [f"a0v_{value:03d}" for value in range(50, 38, -1)]
    assert len(module.FILES) == 12
    assert module.FILES[0] == "a0v_039_product_event_schedule_schema.py"
    assert module.FILES[-1] == "a0v_050_data_requirement_outbox_completion.py"
    assert module.CLONE != module.storage.MAIN


def test_all_migration_hashes_are_content_addressed_and_present():
    module = load_module()
    hashes = module.migration_hashes()
    assert tuple(hashes) == module.FILES
    assert all(value.startswith("sha256:") and len(value) == 71 for value in hashes.values())
    assert len(set(hashes.values())) == len(module.FILES)


def test_fingerprint_excludes_only_new_completion_columns():
    module = load_module()
    assert module._canonical_expression("data_requirement_outbox_delivery") == (
        "to_jsonb(t)-ARRAY['completion_fulfillment_ref','completion_analysis_ref']"
    )
    assert module._canonical_expression("data_requirement_outbox") == "to_jsonb(t)"
    assert "data_requirement_outbox_delivery" in module.BUSINESS_TABLES
    assert not set(module.NEW_TABLES) & set(module.BUSINESS_TABLES)


def test_protected_write_is_private_fsynced_and_non_overwriting(tmp_path):
    module = load_module()
    target = tmp_path / "proof.json"
    module.protected_write(target, {"outcome": "ok"})
    assert json.loads(target.read_text()) == {"outcome": "ok"}
    assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        module.protected_write(target, {"outcome": "changed"})


def test_lease_requires_exact_active_m1_and_branch(monkeypatch, tmp_path):
    module = load_module()
    root = tmp_path / "aos-platform"
    memory = root.parent / "docs/palantier/AOS项目开发上下文/memory"
    memory.mkdir(parents=True)
    module.ROOT = root
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    receipt = dict(task_id=module.TASK, owner="m1", status="ACTIVE", lease_expires_at=future)
    (memory / "leases.json").write_text(json.dumps({"leases": [receipt]}))
    monkeypatch.setattr(module.subprocess, "check_output", lambda *args, **kwargs: "m1\n")
    module.require_lease()
    receipt["owner"] = "another-writer"
    (memory / "leases.json").write_text(json.dumps({"leases": [receipt]}))
    with pytest.raises(ValueError, match="migration lease"):
        module.require_lease()


def test_retained_proof_rejects_backup_or_executor_drift(monkeypatch, tmp_path):
    module = load_module()
    module.STATE = tmp_path
    backup = tmp_path / "aos_meta_head-before-a0v_050.dump"
    descriptor = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(b"retained-backup")
    monkeypatch.setattr(module, "migration_hashes", lambda: {"migration": "sha256:m"})
    monkeypatch.setattr(module, "executor_hashes", lambda: {"executor": "sha256:e"})
    proof = dict(
        outcome="NATURAL_CHAIN_CLONE_UPGRADE_VERIFIED", source=module.SOURCE, target=module.TARGET,
        main=module.storage.MAIN, clone=module.CLONE,
        migrations=module.migration_hashes(), executors=module.executor_hashes(),
        backup=dict(path=str(backup), bytes=backup.stat().st_size, sha256=module.digest(backup)),
        before={"stable": True}, after={"stable": True},
    )
    module._proof_current(proof)
    proof["executors"] = {"executor": "sha256:changed"}
    with pytest.raises(ValueError, match="preparation differs"):
        module._proof_current(proof)
