"""Fail-closed tests for the standalone A0-V ecommerce Runtime Host."""
from __future__ import annotations

import importlib.util
import argparse
import asyncio
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ecommerce_runtime_host.py"
SPEC = importlib.util.spec_from_file_location("a0v_ecommerce_runtime_host", SCRIPT)
assert SPEC and SPEC.loader
HOST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOST)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch,tmp_path):
    monkeypatch.setattr(HOST, "HOST_LOCK_PATHS", (tmp_path/"canonical.lock",tmp_path/"legacy.lock"))
    monkeypatch.setattr(os, 'environ', dict(os.environ))


def _credential_file(path: Path) -> tuple[Path, dict[str, dict[str, str]]]:
    value = {
        plane: {"role": f"aos_current_{plane}", "password": f"secret-{plane}",
                "dsn": f"dbname=current user=aos_current_{plane} password=secret-{plane}"}
        for plane in ("web", "runtime", "directory")
    }
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return path, value


def test_credentials_require_private_current_distinct_roles(tmp_path: Path) -> None:
    path, expected = _credential_file(tmp_path / "identities.json")
    assert HOST._load_credentials(path) == expected
    path.chmod(0o644)
    with pytest.raises(HOST.HostBlocked) as captured:
        HOST._load_credentials(path)
    assert captured.value.code == "CREDENTIAL_FILE_INVALID"


@pytest.mark.parametrize("defect", ["role", "password", "duplicate_role", "duplicate_dsn"])
def test_local_credentials_reject_declared_identity_drift(tmp_path: Path, defect: str) -> None:
    path, value = _credential_file(tmp_path / "identities.json")
    if defect == "role":
        value["runtime"]["role"] = "another_role"
    elif defect == "password":
        value["runtime"]["password"] = "another_password"
    elif defect == "duplicate_role":
        value["runtime"]["role"] = value["web"]["role"]
    else:
        value["runtime"]["dsn"] = value["web"]["dsn"]
    path.write_text(json.dumps(value))
    with pytest.raises(HOST.HostBlocked) as captured:
        HOST._load_credentials(path)
    assert captured.value.code == "CREDENTIAL_FILE_INVALID"
    assert "secret-" not in str(captured.value)


def test_environment_uses_reference_without_secret_dsns(tmp_path: Path, monkeypatch) -> None:
    path, credentials = _credential_file(tmp_path / "identities.json")
    bundle = tmp_path / "bundles"
    bundle.mkdir()
    trust = tmp_path / "trust.json"
    trust.write_text("{}")
    for key in (
        "AOS_DATABASE_URL", "AOS_EXTENSION_RUNTIME_DATABASE_URL",
        "AOS_EXTENSION_DIRECTORY_DATABASE_URL",
    ):
        monkeypatch.setenv(key, 'inherited-secret-must-be-removed')

    HOST._configure_environment(
        path, bundle_root=bundle, trust_roots_file=trust
    )

    assert os.environ['AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE'] == str(path)
    for key in ('AOS_DATABASE_URL', 'AOS_EXTENSION_RUNTIME_DATABASE_URL', 'AOS_EXTENSION_DIRECTORY_DATABASE_URL'):
        assert key not in os.environ
    assert os.environ["AOS_EXTENSION_RUNTIME_HOST_ENABLED"] == "1"
    assert os.environ["AOS_DOTENV_DISABLED"] == "1"


def test_invalid_interval_fails_before_loading_credentials(tmp_path: Path, monkeypatch) -> None:
    status = tmp_path / "status.json"
    monkeypatch.setattr(
        HOST, "_load_credentials",
        lambda _path: (_ for _ in ()).throw(AssertionError("credentials loaded")),
    )
    assert HOST.main([
        "--bundle-root", str(tmp_path), "--trust-roots-file", str(tmp_path / "missing"),
        "--status-file", str(status), "--interval-seconds", "0",
    ]) == 2
    assert json.loads(status.read_text()) == {
        "outcome": "SAFE_BLOCKED", "reasonCode": "INTERVAL_INVALID"
    }


def test_host_requires_explicit_credential_file_before_serve(tmp_path: Path, monkeypatch) -> None:
    status = tmp_path / "status.json"
    monkeypatch.setattr(HOST, "_serve", lambda _: pytest.fail("Host reached without explicit credentials"))
    assert HOST.main([
        "--bundle-root", str(tmp_path), "--trust-roots-file", str(tmp_path / "trust.json"),
        "--status-file", str(status),
    ]) == 2
    assert json.loads(status.read_text()) == {
        "outcome": "SAFE_BLOCKED", "reasonCode": "CREDENTIAL_FILE_REQUIRED"
    }


def test_host_requires_current_signed_receipt_before_serve(tmp_path: Path, monkeypatch) -> None:
    credential, _ = _credential_file(tmp_path / "identities.json")
    status = tmp_path / "status.json"
    monkeypatch.setattr(HOST, "_serve", lambda _: pytest.fail("Host reached without signed receipt"))
    assert HOST.main([
        "--credential-file", str(credential), "--bundle-root", str(tmp_path),
        "--trust-roots-file", str(tmp_path / "trust.json"), "--status-file", str(status),
    ]) == 2
    assert json.loads(status.read_text()) == {
        "outcome": "SAFE_BLOCKED", "reasonCode": "SIGNED_RECEIPT_REQUIRED"
    }


def test_current_preflight_failure_stops_before_serve(tmp_path: Path, monkeypatch) -> None:
    credential, _ = _credential_file(tmp_path / "identities.json")
    status = tmp_path / "status.json"
    monkeypatch.setattr(HOST, "_current_preflight", lambda *_: (_ for _ in ()).throw(
        HOST.HostBlocked("CREDENTIAL_DATABASE_DRIFT")))
    monkeypatch.setattr(HOST, "_serve", lambda _: pytest.fail("Host reached after failed preflight"))
    assert HOST.main([
        "--credential-file", str(credential), "--signed-receipt", str(tmp_path / "signed.json"),
        "--bundle-root", str(tmp_path), "--trust-roots-file", str(tmp_path / "trust.json"),
        "--status-file", str(status),
    ]) == 2
    assert json.loads(status.read_text()) == {
        "outcome": "SAFE_BLOCKED", "reasonCode": "CREDENTIAL_DATABASE_DRIFT"
    }


@pytest.mark.parametrize("report", [
    {},
    {"outcome": "CURRENT_SIGNED_HOST_READONLY_PREFLIGHT_GREEN",
     "scope": ["org-org", "dev-project"], "hostId": ""},
    {"outcome": "CURRENT_SIGNED_HOST_READONLY_PREFLIGHT_GREEN",
     "scope": ["dev-org", "dev-project"], "hostId": "current-host"},
])
def test_current_host_id_requires_exact_validated_report(report) -> None:
    with pytest.raises(HOST.HostBlocked, match="CURRENT_HOST_ID_INVALID"):
        HOST._require_current_host_id(report)


def test_current_host_id_comes_from_exact_report() -> None:
    assert HOST._require_current_host_id({
        "outcome": "CURRENT_SIGNED_HOST_READONLY_PREFLIGHT_GREEN",
        "authorization": "PREFLIGHT_ONLY_NO_RUNTIME_START",
        "scope": ["org-org", "dev-project"], "hostId": "current-host",
    }) == "current-host"


def test_serve_rejects_missing_current_host_id_before_environment(monkeypatch) -> None:
    monkeypatch.setattr(HOST, "_configure_environment",
                        lambda *_a, **_k: pytest.fail("environment configured without Host ID"))
    with pytest.raises(HOST.HostBlocked, match="CURRENT_HOST_ID_INVALID"):
        asyncio.run(HOST._serve(argparse.Namespace(), current_host_id=""))


def test_current_preflight_green_is_not_formal_owner_authority(tmp_path: Path, monkeypatch) -> None:
    credential, _ = _credential_file(tmp_path / "identities.json")
    status = tmp_path / "status.json"
    seen = []
    monkeypatch.setattr(HOST, "_current_preflight", lambda *_: seen.append("checked") or "current-host")
    monkeypatch.setattr(HOST, "_serve", lambda _: pytest.fail("Host reached without formal Owner"))
    assert HOST.main([
        "--credential-file", str(credential), "--signed-receipt", str(tmp_path / "signed.json"),
        "--bundle-root", str(tmp_path), "--trust-roots-file", str(tmp_path / "trust.json"),
        "--status-file", str(status),
    ]) == 2
    assert seen == ["checked"]
    assert json.loads(status.read_text()) == {
        "outcome": "SAFE_BLOCKED", "reasonCode": "FORMAL_OWNER_AUTHORITY_UNPROVEN"
    }


def test_serve_records_active_then_clean_stop(tmp_path: Path, monkeypatch) -> None:
    credential_path, _credentials = _credential_file(tmp_path / "identities.json")
    bundle = tmp_path / "bundles"
    bundle.mkdir()
    trust = tmp_path / "trust.json"
    trust.write_text("{}")
    status = tmp_path / "status.json"

    class Host:
        async def serve(self, stop_event, *, interval_seconds):
            assert isinstance(stop_event, asyncio.Event)
            assert interval_seconds == 3

    class Worker:
        last_status = {'targetsChecked': 0, 'candidates': 0, 'occurrences': 0,
                       'analysesAccepted': 0, 'failed': 0}
        async def serve(self, stop_event, *, host_ready):
            assert isinstance(stop_event, asyncio.Event)
            assert host_ready() is False

    plane = type('Plane', (), {'live_job_directory': type('Directory', (), {
        'current_targets': lambda self: ()})()})()
    monkeypatch.setattr(HOST, "_build_runtime", lambda: (Host(), plane))
    monkeypatch.setattr(HOST, "_build_business_workers", lambda _plane: (Worker(), Worker(), Worker(), Worker()))
    asyncio.run(HOST._serve(argparse.Namespace(
        credential_file=credential_path,
        bundle_root=bundle,
        trust_roots_file=trust,
        status_file=status,
        interval_seconds=3,
    ), current_host_id="current-host"))

    result = json.loads(status.read_text())
    assert result["outcome"] == "RUNTIME_HOST_STOPPED"
    assert result["hostId"] == "current-host"
    assert result["tenantCount"] == 1
    assert result["canaryTenantCount"] == 0
    assert result["recoverableStoreExecutionLimitSeconds"] == 1800
    assert result["businessWorkers"] == ["product-event", "baseline-assessment", "analysis-data-requirement", "analyst-stage-readiness"]
    assert "baselineAssessmentWorker" in result
    assert "analystStageReadinessWorker" in result


def test_serve_runs_business_workers_with_same_stop_and_live_host(tmp_path, monkeypatch):
    credential_path, _ = _credential_file(tmp_path / 'identities.json')
    bundle = tmp_path / 'bundles'; bundle.mkdir()
    trust = tmp_path / 'trust.json'; trust.write_text('{}')
    status = tmp_path / 'status.json'
    seen = []

    class Host:
        async def serve(self, stop_event, *, interval_seconds):
            seen.append(('host', stop_event, interval_seconds))
            await stop_event.wait()

    class Worker:
        last_status = {'targetsChecked': 0, 'candidates': 0, 'occurrences': 0,
                       'analysesAccepted': 0, 'failed': 0}
        def __init__(self, name, stop=False): self.name, self.stop = name, stop
        async def serve(self, stop_event, *, host_ready):
            await asyncio.sleep(0)
            seen.append((self.name, stop_event, host_ready()))
            if self.stop: stop_event.set()
            else: await stop_event.wait()

    plane = type('Plane', (), {'live_job_directory': type('Directory', (), {
        'current_targets': lambda self: ()})()})()
    monkeypatch.setattr(HOST, '_build_runtime', lambda: (Host(), plane))
    monkeypatch.setattr(HOST, '_build_business_workers',
        lambda _plane: (Worker('product-event'), Worker('analysis-data', stop=True), Worker('baseline'), Worker('readiness')))
    asyncio.run(HOST._serve(argparse.Namespace(credential_file=credential_path,
        bundle_root=bundle, trust_roots_file=trust, status_file=status, interval_seconds=2),
        current_host_id="current-host"))

    assert [item[0] for item in seen] == ['host', 'product-event', 'analysis-data', 'baseline', 'readiness']
    stop_events = [item[1] for item in seen]
    assert len({id(item) for item in stop_events}) == 1 and stop_events[0].is_set()
    assert seen[1][2] is True and seen[2][2] is True and seen[3][2] is True


def test_business_worker_construction_fails_before_active_status(tmp_path, monkeypatch):
    credential_path, _ = _credential_file(tmp_path / 'identities.json')
    bundle = tmp_path / 'bundles'; bundle.mkdir()
    trust = tmp_path / 'trust.json'; trust.write_text('{}')
    status = tmp_path / 'status.json'
    monkeypatch.setattr(HOST, '_build_runtime', lambda: (object(), object()))
    monkeypatch.setattr(HOST, '_build_business_workers',
        lambda _plane: (_ for _ in ()).throw(RuntimeError('worker unavailable')))

    with pytest.raises(RuntimeError, match='worker unavailable'):
        asyncio.run(HOST._serve(argparse.Namespace(credential_file=credential_path,
            bundle_root=bundle, trust_roots_file=trust, status_file=status, interval_seconds=2),
            current_host_id="current-host"))
    assert not status.exists()


def test_serve_rejects_symlink_before_build(tmp_path, monkeypatch):
    path, _ = _credential_file(tmp_path / 'identities.json')
    link = tmp_path / 'link'
    link.symlink_to(path)
    monkeypatch.setattr(HOST, '_build_runtime', lambda: pytest.fail('symlink reached host construction'))
    with pytest.raises(HOST.HostBlocked):
        asyncio.run(HOST._serve(argparse.Namespace(
            credential_file=link, bundle_root=tmp_path, trust_roots_file=path,
            status_file=tmp_path / 'status.json', interval_seconds=2,
        ), current_host_id="current-host"))


def test_runtime_failure_chain_omits_private_exception_values():
    try:
        try:
            raise TimeoutError("password=do-not-record-original")
        except TimeoutError as original:
            raise RuntimeError("token=do-not-record-cleanup") from original
    except RuntimeError as error:
        result = HOST._safe_error_chain(error)
    assert [item["errorType"] for item in result] == ["RuntimeError", "TimeoutError"]
    assert result[1]["relation"] == "cause"
    assert "do-not-record" not in json.dumps(result)


def test_error_chain_context_cycle_and_bound():
    first = RuntimeError("private")
    second = ValueError("private")
    first.__context__ = second
    second.__context__ = first
    result = HOST._safe_error_chain(first)
    assert len(result) == 2
    assert result[1]["relation"] == "context"
    current = first = RuntimeError()
    for _ in range(30):
        current.__cause__ = RuntimeError()
        current = current.__cause__
    assert len(HOST._safe_error_chain(first)) == 16


@pytest.mark.parametrize('lock_kind',['canonical','legacy','status'])
@pytest.mark.parametrize('interval',['2','0'])
def test_competing_host_cannot_overwrite_status_or_reach_serve(tmp_path,monkeypatch,capsys,lock_kind,interval):
    import fcntl
    status=tmp_path/'status.json'; status.write_text('original-active-status')
    path={'canonical':HOST.HOST_LOCK_PATHS[0],'legacy':HOST.HOST_LOCK_PATHS[1],'status':status.with_suffix('.lock')}[lock_kind]
    monkeypatch.setattr(HOST,'_serve',lambda _:pytest.fail('second host reached serve'))
    with path.open('a+') as held:
        fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert HOST.main(['--bundle-root',str(tmp_path),'--trust-roots-file',str(tmp_path/'missing'),
                          '--status-file',str(status),'--interval-seconds',interval])==2
    assert status.read_text()=='original-active-status'
    assert json.loads(capsys.readouterr().out)['reasonCode']=='HOST_ALREADY_RUNNING'


def test_all_locks_held_during_preflight_and_released_after(tmp_path,monkeypatch):
    import fcntl
    status=tmp_path/'custom-status.json'
    paths=(*HOST.HOST_LOCK_PATHS,status.with_suffix('.lock'))
    def preflight(_signed, _credential):
        for path in paths:
            with path.open('a+') as competing:
                with pytest.raises(BlockingIOError):fcntl.flock(competing,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return 'current-host'
    monkeypatch.setattr(HOST,'_current_preflight',preflight)
    assert HOST.main(['--bundle-root',str(tmp_path),'--trust-roots-file',str(tmp_path/'missing'),
                      '--status-file',str(status),
                      '--credential-file',str(tmp_path/'identities.json'),
                      '--signed-receipt',str(tmp_path/'signed.json')])==2
    assert json.loads(status.read_text())['reasonCode']=='FORMAL_OWNER_AUTHORITY_UNPROVEN'
    for path in paths:
        with path.open('a+') as free:fcntl.flock(free,fcntl.LOCK_EX|fcntl.LOCK_NB)
