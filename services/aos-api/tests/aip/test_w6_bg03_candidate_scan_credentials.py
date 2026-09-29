"""The historical candidate scanner must load a bounded private runtime identity."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from psycopg.conninfo import make_conninfo


ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("w6_bg03_candidate_scan", SCRIPTS / "a0v_w6_bg03_candidate_scan.py")
assert spec is not None and spec.loader is not None
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def _credentials(path: Path, *, runtime_role: str = "aos_a0v_runtime_20260912",
                 database: str = "aos_meta_head", host: str = "127.0.0.1", port: int = 18435) -> Path:
    planes = {
        "web": "aos_a0v_web_20260912",
        "runtime": runtime_role,
        "directory": "aos_a0v_directory_20260912",
    }
    value = {}
    for plane, role in planes.items():
        password = f"fixture-{plane}-only"
        value[plane] = {"role": role, "password": password,
                        "dsn": make_conninfo(host=host, port=port, dbname=database,
                                             user=role, password=password)}
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)
    return path


def test_private_runtime_identity_is_loaded_lazily_without_source_literal(tmp_path: Path) -> None:
    path = _credentials(tmp_path / "identities.json")
    dsn = scanner._runtime_dsn(path)
    assert "user=aos_a0v_runtime_20260912" in dsn
    assert "password=" not in (SCRIPTS / "a0v_w6_bg03_candidate_scan.py").read_text()


@pytest.mark.parametrize("change", [
    {"runtime_role": "aos_app"}, {"database": "aos_current_preview_20260927"},
    {"host": "localhost"}, {"port": 5432},
])
def test_drifted_target_or_role_is_rejected(tmp_path: Path, change: dict[str, object]) -> None:
    path = _credentials(tmp_path / "identities.json", **change)
    with pytest.raises(RuntimeError, match="W6_BG03_RUNTIME_IDENTITY_DRIFT"):
        scanner._runtime_dsn(path)


def test_missing_or_public_credential_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "identities.json"
    with pytest.raises(RuntimeError):
        scanner._runtime_dsn(path)
    _credentials(path)
    path.chmod(0o644)
    with pytest.raises(RuntimeError):
        scanner._runtime_dsn(path)
