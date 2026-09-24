"""Default-off Host lease lifecycle; no real Host launch or business DB mutation."""

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import psycopg
from psycopg.rows import dict_row

from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case


ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location("a0v_host_w5c5j", ROOT / "scripts/a0v_ecommerce_runtime_host.py")
HOST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOST)


class _Conn:
    def __init__(self, records, fail=False):
        self.records = records
        self.fail = fail

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, values=None):
        self.records.append((statement, values))
        if self.fail and "host_lease_" in statement:
            raise RuntimeError("private credential must not escape")
        self.statement = statement
        return self

    def fetchone(self):
        if "_acquire_" in self.statement:
            return {"epoch": 1, "expires_at": object()}
        if "_renew_" in self.statement:
            return {"expires_at": object()}
        return {"extension_runtime_host_lease_release_a0v_093": None}


def test_client_uses_scoped_directory_role_and_never_reacquires_unknown():
    records = []
    lease = OptInHostLease(connect=lambda: _Conn(records),
                           scope=TenantScope("org-org", "dev-project"))
    assert lease.acquire() == 1
    lease.renew()
    lease.release()
    assert any(text == "SET ROLE aos_extension_directory" for text, _ in records)
    assert any("set_config('aos.org_id'" in text for text, _ in records)
    assert any("host_lease_acquire" in text for text, _ in records)
    assert any("host_lease_renew" in text for text, _ in records)
    assert any("host_lease_release" in text for text, _ in records)
    with pytest.raises(HostLeaseBlocked, match="ALREADY_ATTEMPTED"):
        lease.acquire()
    failed = OptInHostLease(connect=lambda: _Conn([], fail=True),
                            scope=TenantScope("org-org", "dev-project"))
    with pytest.raises(HostLeaseBlocked, match="DATABASE_GATE_FAILED") as captured:
        failed.acquire()
    assert "private credential" not in str(captured.value)
    with pytest.raises(HostLeaseBlocked, match="ALREADY_ATTEMPTED"):
        failed.acquire()


def test_client_calls_real_lease_functions_in_disposable_pg(host_lease_case):
    admin_dsn, role_dsn, org, project, _ = host_lease_case
    lease = OptInHostLease(connect=lambda: psycopg.connect(role_dsn, row_factory=dict_row),
                           scope=TenantScope(org, project))
    assert lease.acquire() == 1
    lease.renew()
    lease.release()
    with psycopg.connect(admin_dsn) as admin:
        assert admin.execute(
            "SELECT event_kind FROM extension_runtime_host_lease_event_a0v_093 "
            "WHERE org_id=%s AND project_id=%s ORDER BY event_id", (org, project)
        ).fetchall() == [("acquire",), ("renew",), ("release",)]


def test_default_off_does_not_construct_or_connect(monkeypatch):
    monkeypatch.setattr(HOST, "_build_runtime", lambda: (_ for _ in ()).throw(AssertionError()))
    assert HOST._opt_in_host_lease(argparse.Namespace()) is None
    assert HOST.parse_args(["--bundle-root", "/tmp", "--trust-roots-file", "/tmp"]).host_lease_opt_in is False


def _inputs(tmp_path):
    credential = tmp_path / "identities.json"
    credential.write_text(json.dumps({plane: {"role": role, "password": "x", "dsn": plane}
                                      for plane, role in HOST.EXPECTED_ROLES.items()}))
    credential.chmod(0o600)
    bundle = tmp_path / "bundles"
    bundle.mkdir()
    trust = tmp_path / "trust.json"
    trust.write_text("{}")
    return argparse.Namespace(credential_file=credential, bundle_root=bundle,
                              trust_roots_file=trust, status_file=tmp_path / "status.json",
                              interval_seconds=2, host_lease_opt_in=True)


def _workers(events):
    class Worker:
        last_status = {"checked": 0}

        async def serve(self, stop_event, *, host_ready):
            events.append(("worker", host_ready()))
            await stop_event.wait()

    return (Worker(), Worker(), Worker())


def test_acquire_failure_never_starts_host_or_publishes_active(tmp_path, monkeypatch):
    args = _inputs(tmp_path)
    events = []

    class Lease:
        def acquire(self):
            raise HostLeaseBlocked("ACQUIRE_REJECTED")

    monkeypatch.setattr(HOST, "_build_runtime", lambda: (SimpleNamespace(),
                         SimpleNamespace(live_job_directory=SimpleNamespace(current_targets=lambda: ()))))
    monkeypatch.setattr(HOST, "_build_business_workers", lambda _plane: _workers(events))
    monkeypatch.setattr(HOST, "_opt_in_host_lease", lambda _args: Lease())
    with pytest.raises(HostLeaseBlocked, match="ACQUIRE_REJECTED"):
        asyncio.run(HOST._serve(args))
    assert events == []
    assert not args.status_file.exists()


def test_renew_failure_stops_workers_and_attempts_release(tmp_path, monkeypatch):
    args = _inputs(tmp_path)
    events = []

    class Lease:
        def acquire(self):
            events.append("acquire")

        async def renew_until_stopped(self, _stop_event):
            await asyncio.sleep(0)
            raise HostLeaseBlocked("RENEW_REJECTED")

        def release(self):
            events.append("release")

    class Runtime:
        async def serve(self, stop_event, *, interval_seconds):
            await stop_event.wait()

    plane = SimpleNamespace(live_job_directory=SimpleNamespace(current_targets=lambda: ()))
    monkeypatch.setattr(HOST, "_build_runtime", lambda: (Runtime(), plane))
    monkeypatch.setattr(HOST, "_build_business_workers", lambda _plane: _workers(events))
    monkeypatch.setattr(HOST, "_opt_in_host_lease", lambda _args: Lease())
    with pytest.raises(HostLeaseBlocked, match="RENEW_REJECTED"):
        asyncio.run(HOST._serve(args))
    assert events[0] == "acquire"
    assert events[-1] == "release"
    assert json.loads(args.status_file.read_text())["outcome"] == "RUNTIME_HOST_STOPPED"
