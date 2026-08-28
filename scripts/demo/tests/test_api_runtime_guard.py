from __future__ import annotations

from pathlib import Path

import pytest

from scripts.demo.api_runtime_guard import evaluate_runtime_owner


def _pid_file(tmp_path: Path, value: str = "4312") -> Path:
    path = tmp_path / "aos-api.pid"
    path.write_text(value, encoding="utf-8")
    return path


def test_exact_live_uvicorn_listener_is_green(tmp_path: Path) -> None:
    result = evaluate_runtime_owner(
        pid_file=_pid_file(tmp_path),
        port=8080,
        expected_tokens=("uvicorn", "aos_api.main:app"),
        process_exists=lambda pid: pid == 4312,
        command_reader=lambda pid: "python -m uvicorn aos_api.main:app --port 8080",
        listener_reader=lambda port: {4312},
    )

    assert result == {
        "ok": True,
        "code": "RUNTIME_OWNER_EXACT",
        "pid": 4312,
        "port": 8080,
        "listenerPids": [4312],
    }


def test_missing_pid_file_fails_closed(tmp_path: Path) -> None:
    result = evaluate_runtime_owner(
        pid_file=tmp_path / "missing.pid",
        port=8080,
        expected_tokens=("uvicorn",),
        process_exists=lambda _pid: True,
        command_reader=lambda _pid: "uvicorn",
        listener_reader=lambda _port: {4312},
    )

    assert result["ok"] is False
    assert result["code"] == "PID_FILE_MISSING"


@pytest.mark.parametrize("raw", ["", "not-a-pid", "-1", "0"])
def test_invalid_pid_file_fails_closed(tmp_path: Path, raw: str) -> None:
    result = evaluate_runtime_owner(
        pid_file=_pid_file(tmp_path, raw),
        port=8080,
        expected_tokens=("uvicorn",),
        process_exists=lambda _pid: True,
        command_reader=lambda _pid: "uvicorn",
        listener_reader=lambda _port: {4312},
    )

    assert result["ok"] is False
    assert result["code"] == "PID_FILE_INVALID"


def test_dead_process_fails_closed(tmp_path: Path) -> None:
    result = evaluate_runtime_owner(
        pid_file=_pid_file(tmp_path),
        port=8080,
        expected_tokens=("uvicorn",),
        process_exists=lambda _pid: False,
        command_reader=lambda _pid: "uvicorn",
        listener_reader=lambda _port: {4312},
    )

    assert result["ok"] is False
    assert result["code"] == "PROCESS_NOT_ALIVE"


def test_command_identity_drift_fails_closed(tmp_path: Path) -> None:
    result = evaluate_runtime_owner(
        pid_file=_pid_file(tmp_path),
        port=8080,
        expected_tokens=("uvicorn", "aos_api.main:app"),
        process_exists=lambda _pid: True,
        command_reader=lambda _pid: "python -m http.server 8080",
        listener_reader=lambda _port: {4312},
    )

    assert result["ok"] is False
    assert result["code"] == "PROCESS_IDENTITY_MISMATCH"


def test_old_process_holding_port_fails_closed(tmp_path: Path) -> None:
    result = evaluate_runtime_owner(
        pid_file=_pid_file(tmp_path),
        port=8080,
        expected_tokens=("uvicorn", "aos_api.main:app"),
        process_exists=lambda _pid: True,
        command_reader=lambda _pid: "python -m uvicorn aos_api.main:app --port 8080",
        listener_reader=lambda _port: {9981},
    )

    assert result["ok"] is False
    assert result["code"] == "LISTENER_OWNER_MISMATCH"
    assert result["listenerPids"] == [9981]


def test_multiple_listener_owners_fail_closed(tmp_path: Path) -> None:
    result = evaluate_runtime_owner(
        pid_file=_pid_file(tmp_path),
        port=8080,
        expected_tokens=("uvicorn", "aos_api.main:app"),
        process_exists=lambda _pid: True,
        command_reader=lambda _pid: "python -m uvicorn aos_api.main:app --port 8080",
        listener_reader=lambda _port: {4312, 9981},
    )

    assert result["ok"] is False
    assert result["code"] == "LISTENER_OWNER_MISMATCH"
    assert result["listenerPids"] == [4312, 9981]


def test_ensure_api_disables_provider_health_maintenance_by_default() -> None:
    script = Path(__file__).parents[1] / "ensure-api.sh"

    assert "export AOS_AIP_TEXT_HEALTH_MAINTENANCE_ENABLED=false" in script.read_text(
        encoding="utf-8"
    )
