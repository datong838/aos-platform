#!/usr/bin/env python3
"""Run the isolated A0-V ecommerce Runtime Host as one fail-closed process."""
from __future__ import annotations

from contextlib import ExitStack
import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import sys
import traceback
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services/aos-api"
RECOVERY = ROOT.parent / ".aos-recovery-20260912"
DEFAULT_CREDENTIALS = RECOVERY / "state/ecommerce-runtime-host/runtime-host-identities.json"
DEFAULT_STATUS = RECOVERY / "logs/ecommerce-runtime-host-status.json"
HOST_LOCK_PATHS = (
    RECOVERY / "state/ecommerce-runtime-host/singleton.lock",
    DEFAULT_STATUS.with_suffix(".lock"),
    ROOT.parent / ".aos-recovery-20260913/logs/runtime-host-aa3010c4.lock",
)
EXPECTED_ROLES = {
    "web": "aos_a0v_web_20260912",
    "runtime": "aos_a0v_runtime_20260912",
    "directory": "aos_a0v_directory_20260912",
}


class HostBlocked(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _safe_error_chain(error: BaseException) -> list[dict[str, Any]]:
    """Keep bounded causal locations, never exception values or frame locals."""
    result: list[dict[str, Any]] = []
    seen: set[int] = set()
    current: BaseException | None = error
    relation = "raised"
    while current is not None and id(current) not in seen and len(result) < 16:
        seen.add(id(current))
        result.append({
            "errorType": type(current).__name__,
            "relation": relation,
            "frames": [{"file": frame.filename, "function": frame.name, "line": frame.lineno}
                       for frame in traceback.extract_tb(current.__traceback__)[-32:]],
        })
        if current.__cause__ is not None:
            current, relation = current.__cause__, "cause"
        else:
            current, relation = current.__context__, "context"
    return result


def _load_credentials(path: Path) -> dict[str, dict[str, str]]:
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise HostBlocked("CREDENTIAL_FILE_INVALID")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostBlocked("CREDENTIAL_FILE_INVALID") from exc
    if type(value) is not dict or set(value) != set(EXPECTED_ROLES):
        raise HostBlocked("CREDENTIAL_FILE_INVALID")
    for plane, role in EXPECTED_ROLES.items():
        item = value.get(plane)
        if (
            type(item) is not dict
            or set(item) != {"dsn", "password", "role"}
            or item.get("role") != role
            or any(type(item.get(key)) is not str or not item[key] for key in item)
        ):
            raise HostBlocked("CREDENTIAL_FILE_INVALID")
    return value


def _configure_environment(
    credential_file: Path, *, bundle_root: Path,
    trust_roots_file: Path,
) -> None:
    if not credential_file.is_absolute():
        raise HostBlocked("CREDENTIAL_FILE_INVALID")
    _load_credentials(credential_file)
    if not bundle_root.is_dir():
        raise HostBlocked("BUNDLE_ROOT_INVALID")
    if not trust_roots_file.is_file():
        raise HostBlocked("TRUST_ROOTS_INVALID")
    values = {
        "AOS_DOTENV_DISABLED": "1",
        "AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE": str(credential_file),
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "1",
        "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
        "AOS_EXTENSION_RUNTIME_PLATFORM": "linux/arm64",
        "AOS_BUNDLE_ROOT": str(bundle_root.resolve()),
        "AOS_BUNDLE_TRUST_ROOTS_FILE": str(trust_roots_file.resolve()),
    }
    for name in ("AOS_DATABASE_URL", "AOS_EXTENSION_RUNTIME_DATABASE_URL",
                 "AOS_EXTENSION_DIRECTORY_DATABASE_URL"):
        os.environ.pop(name, None)
    os.environ.update(values)


def _build_runtime():
    if str(API) not in sys.path:
        sys.path.insert(0, str(API))
    from aos_api.asset_registry.control_wiring import (
        build_production_runtime_host_selection,
        build_runtime_control_plane,
    )
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent

    plane = build_runtime_control_plane(
        disable_dependent=EcommerceGrowthDisableDependent()
    )
    selected = build_production_runtime_host_selection(control_plane=plane)
    if selected.status != "ACTIVE" or selected.host is None:
        raise HostBlocked(selected.error_code or "HOST_SELECTION_INACTIVE")
    return selected.host, plane


def _build_business_workers(control_plane):
    from aos_api.ecommerce_analysis_data_requirement_worker import (
        build_analysis_data_requirement_worker,
    )
    from aos_api.ecommerce_product_event_worker import build_product_event_worker

    product_event = build_product_event_worker(control_plane)
    analysis_data = build_analysis_data_requirement_worker(control_plane)
    if product_event is None or analysis_data is None:
        raise HostBlocked("BUSINESS_WORKER_DEPENDENCY_MISSING")
    return product_event, analysis_data


def _business_status(public, control_plane, product_event_worker):
    targets = control_plane.live_job_directory.current_targets()
    return {**public,
        "liveTargets": [{"tenant": list(scope.key), "installationId": str(installation),
                         "generation": str(generation)}
                        for scope, installation, generation in targets],
        "productEventWorker": dict(product_event_worker.last_status)}


async def _serve(args: argparse.Namespace) -> None:
    _configure_environment(
        args.credential_file,
        bundle_root=args.bundle_root.resolve(),
        trust_roots_file=args.trust_roots_file.resolve(),
    )
    host, control_plane = _build_runtime()
    product_event_worker, analysis_data_worker = _build_business_workers(control_plane)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop_event.set)
    public = {
        "outcome": "RUNTIME_HOST_ACTIVE",
        "pid": os.getpid(),
        "hostId": "a0v-local-ecommerce-host-20260912",
        "tenantCount": 1,
        "positiveTenant": "org-org/dev-project",
        "canaryTenantCount": 0,
        "intervalSeconds": args.interval_seconds,
        "businessWorkers": ["product-event", "analysis-data-requirement"],
    }
    _write(args.status_file.resolve(), _business_status(
        public, control_plane, product_event_worker))
    print(json.dumps(public, ensure_ascii=False, sort_keys=True), flush=True)
    host_task = asyncio.create_task(
        host.serve(stop_event, interval_seconds=args.interval_seconds),
        name="extension-runtime-host",
    )
    host_ready = lambda: not host_task.done()
    worker_tasks = (
        asyncio.create_task(
            product_event_worker.serve(stop_event, host_ready=host_ready),
            name="product-event-consumption",
        ),
        asyncio.create_task(
            analysis_data_worker.serve(stop_event, host_ready=host_ready),
            name="analysis-data-requirement",
        ),
    )
    async def report_status():
        while not stop_event.is_set():
            _write(args.status_file.resolve(), _business_status(
                public, control_plane, product_event_worker))
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=2)
            except TimeoutError:
                continue
    reporter_task = asyncio.create_task(report_status(), name="runtime-business-status")
    stop_task = asyncio.create_task(stop_event.wait(), name="runtime-host-stop")
    try:
        done, _ = await asyncio.wait(
            (host_task, *worker_tasks, reporter_task, stop_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not stop_event.is_set():
            if host_task in done:
                error = host_task.exception()
                if error is not None:
                    raise error
            elif reporter_task in done:
                error = reporter_task.exception()
                if error is not None:
                    raise error
                raise HostBlocked("BUSINESS_STATUS_REPORTER_STOPPED")
            else:
                finished = next(task for task in worker_tasks if task in done)
                error = finished.exception()
                if error is not None:
                    raise error
                raise HostBlocked("BUSINESS_WORKER_STOPPED")
    finally:
        stop_event.set()
        await asyncio.gather(host_task, *worker_tasks, reporter_task, return_exceptions=True)
        if not stop_task.done():
            stop_task.cancel()
        await asyncio.gather(stop_task, return_exceptions=True)
        stopped = {**_business_status(public, control_plane, product_event_worker),
                   "outcome": "RUNTIME_HOST_STOPPED"}
        _write(args.status_file.resolve(), stopped)
        print(json.dumps(stopped, ensure_ascii=False, sort_keys=True), flush=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credential-file", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--trust-roots-file", type=Path, required=True)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--interval-seconds", type=int, default=2)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = sorted({path.resolve() for path in (*HOST_LOCK_PATHS, args.status_file.resolve().with_suffix(".lock"))})
    with ExitStack() as locks:
        try:
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                lock = locks.enter_context(path.open("a+"))
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # A competing launcher must not replace the owner's active status.
            print(json.dumps({"outcome": "SAFE_BLOCKED", "reasonCode": "HOST_ALREADY_RUNNING"}), flush=True)
            return 2
        if not 1 <= args.interval_seconds <= 300:
            _write(args.status_file.resolve(), {"outcome": "SAFE_BLOCKED", "reasonCode": "INTERVAL_INVALID"})
            return 2
        try:
            asyncio.run(_serve(args))
            return 0
        except HostBlocked as exc:
            result = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.code}
        except Exception as exc:
            result = {
                "outcome": "SAFE_BLOCKED",
                "reasonCode": "HOST_RUNTIME_FAILED",
                "errorType": type(exc).__name__,
                "errorChain": _safe_error_chain(exc),
                "frames": [{"file": frame.filename, "function": frame.name, "line": frame.lineno}
                           for frame in traceback.extract_tb(exc.__traceback__)],
            }
        _write(args.status_file.resolve(), result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
