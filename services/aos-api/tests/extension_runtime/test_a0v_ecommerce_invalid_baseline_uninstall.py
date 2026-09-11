"""Tests for the invalid ecommerce baseline uninstall executor."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ecommerce_invalid_baseline_uninstall.py"
SPEC = importlib.util.spec_from_file_location("invalid_baseline_uninstall", SCRIPT)
assert SPEC and SPEC.loader
UNINSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UNINSTALL)


def test_apply_requires_exact_isolated_database(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        UNINSTALL, "_load_first",
        lambda: (_ for _ in ()).throw(AssertionError("connector loaded")),
    )
    args = UNINSTALL.parse_args([
        "--apply", "--database-name", "wrong",
        "--trust-roots-file", str(tmp_path / "trust.json"),
    ])
    with pytest.raises(UNINSTALL.UninstallBlocked) as captured:
        UNINSTALL.run(args)
    assert captured.value.code == "EXPLICIT_ISOLATED_DATABASE_REQUIRED"


def test_uninstall_identity_and_reason_are_immutable() -> None:
    source = SCRIPT.read_text()
    assert UNINSTALL.INSTALLATION_ID == "c1eb714f-56de-4f28-ba06-c3440b3d18cb"
    assert UNINSTALL.KEY == "a0v-ecommerce-invalid-1.4-uninstall-v1"
    assert "Signed runtime API declarations are absent" in source
    assert "secondReplayed" in source
