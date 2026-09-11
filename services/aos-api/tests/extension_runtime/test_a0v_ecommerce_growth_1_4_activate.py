"""Tests for the bounded growth 1.4 activation executor."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ecommerce_growth_1_4_activate.py"
SPEC = importlib.util.spec_from_file_location("growth_1_4_activate", SCRIPT)
assert SPEC and SPEC.loader
ACTIVATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACTIVATE)


def test_apply_requires_exact_isolated_database(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        ACTIVATE, "_load_first",
        lambda: (_ for _ in ()).throw(AssertionError("database connector loaded")),
    )
    args = ACTIVATE.parse_args([
        "--apply", "--database-name", "wrong",
        "--trust-roots-file", str(tmp_path / "trust.json"),
    ])
    try:
        ACTIVATE.run(args)
    except ACTIVATE.ActivationBlocked as exc:
        assert exc.code == "EXPLICIT_ISOLATED_DATABASE_REQUIRED"
    else:
        raise AssertionError("activation unexpectedly allowed")


def test_main_records_domain_failure_without_secret_fields(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "result.json"
    monkeypatch.setattr(
        ACTIVATE, "run",
        lambda _args: (_ for _ in ()).throw(ACTIVATE.ActivationBlocked("TEST_BLOCK")),
    )
    assert ACTIVATE.main([
        "--trust-roots-file", str(tmp_path / "trust.json"),
        "--output", str(output),
    ]) == 2
    assert json.loads(output.read_text()) == {
        "message": "TEST_BLOCK", "outcome": "SAFE_BLOCKED", "reasonCode": "TEST_BLOCK"
    }
