import asyncio
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.extension_runtime.preparation_worker import PreparedJob
from aos_api.ecommerce_analyst_stage_review_async_service import (
    build_current_installed_analyst_stage_review_service,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
INSTALLATION = uuid4()
GENERATION = uuid4()
PACKAGE_HASH = "sha256:" + "a" * 64
LOCK_HASH = "sha256:" + "b" * 64


class _Cursor:
    def __init__(self, row):
        self._row = deepcopy(row)

    def fetchone(self):
        return deepcopy(self._row)


class _Connection:
    def __init__(self, state):
        self.state = state
        self.active = False

    def execute(self, query, params=()):
        assert self.active
        if "FROM bundle_installation i" in query:
            return _Cursor(self.state["installation"])
        if "FROM extension_runtime_binding" in query:
            return _Cursor(self.state["binding"])
        raise AssertionError(query)


def _connect(state, observations):
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        connection = _Connection(state)
        connection.active = True
        observations.append(connection)
        try:
            yield connection
        finally:
            connection.active = False
    return connect


class _Store:
    def __init__(self, state):
        self.state = state

    def load_active_baseline_in_transaction(self, conn, *, org_id, project_id, requested_ref):
        assert type(conn) is HostTransaction and (org_id, project_id) == SCOPE.key
        assert requested_ref == CurrentInstallationRef(
            installationId=str(INSTALLATION), revision=4,
            lockHash=LOCK_HASH, overlayRevision="overlay-4"
        )
        return SimpleNamespace(server_ref=requested_ref, lock=SimpleNamespace(
            lock_hash=LOCK_HASH,
            payload=SimpleNamespace(
                resolved=[SimpleNamespace(id="solution.ecommerce.growth", content_hash=PACKAGE_HASH,
                                          model_dump=lambda **_: {"id": "solution.ecommerce.growth",
                                                                   "contentHash": PACKAGE_HASH})
                          for _ in range(self.state.get("package_count", 1))],
                permission_diff=SimpleNamespace(target=SimpleNamespace(markings=["internal"])),
            ),
        ))


def _state():
    return {
        "installation": {"active_revision": 4, "lock_hash": LOCK_HASH, "overlay_revision": "overlay-4"},
        "binding": {"installation_revision": 4, "package_lock_ref": {"lockHash": LOCK_HASH},
                    "profile_ref": "internal-python-v1", "config_ref": {}, "execution_epoch": 7,
                    "desired_state": "enabled", "observed_state": "ready", "enabled": True,
                    "operation_fence": False, "revision": 9},
    }


def _directory(calls, *, mutate=None):
    job = object.__new__(PreparedJob)
    job._tenant_scope = SCOPE
    job.plan = SimpleNamespace(installation_id=INSTALLATION, generation=GENERATION)

    async def invoke_selected_once(**kwargs):
        calls.append(kwargs)
        if mutate is not None:
            mutate()
        return {"ok": True}

    job.invoke_selected_once = invoke_selected_once
    directory = LivePreparedJobDirectory()
    directory.register(job)
    return directory


def _invoker(state, calls, observations, *, markings=("internal",), mutate=None):
    return CurrentInstalledPackageInvoker(
        scope=SCOPE, installation_id=INSTALLATION, generation=GENERATION,
        package_id="solution.ecommerce.growth", markings=markings,
        connect_factory=_connect(state, observations), installation_store=_Store(state),
        live_directory=_directory(calls, mutate=mutate),
    )


def test_invokes_once_between_two_closed_current_transactions():
    state, calls, observations = _state(), [], []
    invoker = _invoker(state, calls, observations)
    result = asyncio.run(invoker("ecommerce_growth_review_advance", {"kind": "validate_runtime"}))
    assert result == {"ok": True}
    assert len(observations) == 2 and not any(conn.active for conn in observations)
    assert calls == [{"package_id": "solution.ecommerce.growth", "package_hash": PACKAGE_HASH,
                      "operation": "ecommerce_growth_review_advance",
                      "payload": {"kind": "validate_runtime"}}]


def test_discards_response_when_binding_drifts_during_ipc_without_retry():
    state, calls, observations = _state(), [], []
    invoker = _invoker(state, calls, observations,
                       mutate=lambda: state["binding"].update(revision=10))
    with pytest.raises(PermissionError, match="authority changed"):
        asyncio.run(invoker("ecommerce_growth_review_advance", {}))
    assert len(calls) == 1


@pytest.mark.parametrize("change", [
    lambda state: state["binding"].update(enabled=False),
    lambda state: state["binding"].update(operation_fence=True),
    lambda state: state["binding"].update(observed_state="unknown"),
    lambda state: state["binding"].update(installation_revision=3),
    lambda state: state["binding"].update(package_lock_ref={"lockHash": "sha256:" + "0" * 64}),
])
def test_invalid_current_binding_never_invokes(change):
    state, calls, observations = _state(), [], []
    change(state)
    with pytest.raises(PermissionError):
        asyncio.run(_invoker(state, calls, observations)("ecommerce_growth_review_advance", {}))
    assert calls == []


def test_missing_marking_never_invokes():
    state, calls, observations = _state(), [], []
    with pytest.raises(PermissionError):
        asyncio.run(_invoker(state, calls, observations, markings=())("operation", {}))
    assert calls == []


def test_duplicate_package_or_missing_live_job_never_invokes():
    state, calls, observations = _state(), [], []
    state["package_count"] = 2
    with pytest.raises(PermissionError, match="not unique"):
        asyncio.run(_invoker(state, calls, observations)("operation", {}))
    assert calls == []

    state["package_count"] = 1
    empty = LivePreparedJobDirectory()
    invoker = CurrentInstalledPackageInvoker(
        scope=SCOPE, installation_id=INSTALLATION, generation=GENERATION,
        package_id="solution.ecommerce.growth", markings=("internal",),
        connect_factory=_connect(state, observations), installation_store=_Store(state),
        live_directory=empty,
    )
    with pytest.raises(LookupError, match="live prepared job unavailable"):
        asyncio.run(invoker("operation", {}))
    assert calls == []


@pytest.mark.parametrize("failure", [TimeoutError("unknown"), asyncio.CancelledError()])
def test_ipc_failure_or_cancel_is_never_retried(failure):
    state, calls, observations = _state(), [], []

    def fail():
        raise failure

    invoker = _invoker(state, calls, observations, mutate=fail)
    with pytest.raises(type(failure)):
        asyncio.run(invoker("operation", {}))
    assert len(calls) == 1
    assert len(observations) == 1


def test_stage_review_factory_binds_one_concrete_invoker_to_call_and_snapshot():
    state, calls, observations = _state(), [], []
    service = build_current_installed_analyst_stage_review_service(
        _connect(state, observations), scope=SCOPE, installation_id=INSTALLATION,
        generation=GENERATION, installation_store=_Store(state),
        live_directory=_directory(calls), markings=["internal"],
    )
    assert isinstance(service.invoke.__self__, CurrentInstalledPackageInvoker)
    assert service.installed_snapshot.__self__ is service.invoke.__self__


@pytest.mark.parametrize('replacement',['none','before','during'])
def test_expected_job_is_exact_before_and_after_ipc(replacement):
    state,calls,observations=_state(),[],[]
    directory=_directory(calls)
    job=directory.resolve(scope=SCOPE,installation_id=INSTALLATION,generation=GENERATION)
    other=_directory([]).resolve(scope=SCOPE,installation_id=INSTALLATION,generation=GENERATION)
    def replace_job():
        directory.unregister(job);directory.register(other)
    if replacement=='during':
        async def invoke_selected_once(**kwargs):
            calls.append(kwargs);replace_job();return {'ok':True}
        job.invoke_selected_once=invoke_selected_once
    invoker=CurrentInstalledPackageInvoker(scope=SCOPE,installation_id=INSTALLATION,generation=GENERATION,
        package_id='solution.ecommerce.growth',markings=('internal',),connect_factory=_connect(state,observations),
        installation_store=_Store(state),live_directory=directory,expected_job=job)
    if replacement=='before':replace_job()
    if replacement=='none':assert asyncio.run(invoker('analyst_workspace_view_v1',{}))=={'ok':True}
    else:
        with pytest.raises(PermissionError,match='PreparedJob changed'):asyncio.run(invoker('analyst_workspace_view_v1',{}))
    assert len(calls)==(0 if replacement=='before' else 1)
