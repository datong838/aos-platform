from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeRevisionConflict
from aos_api.extension_runtime.runtime_view import (
    RuntimeBindingView,
    RuntimeInstallationView,
    RuntimeOperationView,
    RuntimeUiSessionView,
    RuntimeViewReader,
    _derive_control_state,
)
from aos_api.routers import bundle_runtime_installations


INSTALLATION_ID = str(uuid4())
OPERATION_ID = str(uuid4())
GENERATION = str(uuid4())
CONFIGURATION_ID = str(uuid4())
NOW = datetime.now(timezone.utc).isoformat()


def _principal() -> Principal:
    return Principal(
        subject="operator-1",
        org_id="org-org",
        project_id="dev-project",
        roles=["admin"],
        markings=["public"],
    )


def _operation(**changes) -> RuntimeOperationView:
    payload = dict(
        operationId=OPERATION_ID,
        installationId=INSTALLATION_ID,
        kind="runtime-apply",
        phase="accepted",
        status="accepted",
        revision=1,
        requestedBy="operator-1",
        approvedBy=None,
        expectedInstallationEtag=3,
        expectedBindingRevision=None,
        deadline=NOW,
        failureCode=None,
        createdAt=NOW,
        events=(),
    )
    payload.update(changes)
    return RuntimeOperationView.model_validate(payload)


def _view(**changes) -> RuntimeInstallationView:
    payload = dict(
        installationId=INSTALLATION_ID,
        installationRevision=3,
        installationEtag=3,
        installationState="approved",
        effectiveState="not_prepared",
        binding=None,
        currentOperation=None,
        allowedActions=("runtime-apply",),
        reasons=("运行资源尚未准备。",),
    )
    payload.update(changes)
    return RuntimeInstallationView.model_validate(payload)


class ViewReader:
    def __init__(self) -> None:
        self.installation_calls = []
        self.operation_calls = []

    def get_installation(self, **kwargs):
        self.installation_calls.append(kwargs)
        return _view()

    def get_operation(self, **kwargs):
        self.operation_calls.append(kwargs)
        return _operation()


class CommandService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls = []
        self.error = error

    def request_preparation(self, **kwargs):
        return self._call(kwargs)

    def request(self, **kwargs):
        return self._call(kwargs)

    def _call(self, kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            response_json={
                "installationId": INSTALLATION_ID,
                "operationId": OPERATION_ID,
                "phase": "accepted",
                "status": "accepted",
                "revision": 1,
            },
            response_etag='"1"',
        )


class _Result:
    def __init__(self, row=None) -> None:
        self._row = row

    def fetchone(self):
        return self._row


class _ReadyRuntimeConnection:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params):
        if "FROM extension_runtime_resource_lease" in query:
            return _Result({"resource_count": 3, "live": True})
        if "FROM extension_runtime_binding" in query:
            return _Result({
                "generation": GENERATION,
                "installation_revision": 3,
                "profile_ref": "internal-python-v1",
                "config_ref": {"configurationId": CONFIGURATION_ID},
                "execution_epoch": 2,
                "desired_state": "enabled",
                "observed_state": "ready",
                "enabled": True,
                "operation_fence": False,
                "revision": 4,
            })
        if "FROM extension_runtime_operation" in query:
            return _Result(None)
        raise AssertionError("unexpected runtime projection query")

    def commit(self):
        self.committed = True


class _InstallationReader:
    def get(self, **_kwargs):
        return SimpleNamespace(state="active", current_revision=3, etag_version=3)


def _app(control_plane=None) -> FastAPI:
    app = FastAPI()
    app.include_router(bundle_runtime_installations.router)
    app.dependency_overrides[require_principal] = _principal
    register_exception_handlers(app)
    if control_plane is not None:
        app.state.extension_runtime_control_plane = control_plane
        app.state.extension_runtime_view_reader = control_plane.view_reader
    return app


def _control_plane(*, command_error: Exception | None = None):
    lifecycle = CommandService(error=command_error)
    configuration = CommandService(error=command_error)
    disable = CommandService(error=command_error)
    return SimpleNamespace(
        view_reader=ViewReader(),
        lifecycle_service=lifecycle,
        configuration_service=configuration,
        disable_service=disable,
    )


def test_runtime_view_absence_fails_closed_without_exception_detail() -> None:
    response = TestClient(_app()).get(
        f"/v1/bundle-runtime-installations/{INSTALLATION_ID}",
        headers={"Authorization": "Bearer ignored"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "RUNTIME_VIEW_UNAVAILABLE"
    assert "运行状态读取服务" in response.json()["message"]


def test_command_control_plane_absence_still_fails_closed() -> None:
    app = _app()
    app.state.extension_runtime_view_reader = ViewReader()
    response = TestClient(app).post(
        f"/v1/bundle-runtime-installations/{INSTALLATION_ID}/operations",
        headers={"Authorization": "Bearer ignored", "Idempotency-Key": "prepare-1", "If-Match": '"3"'},
        json={"kind": "runtime-apply"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "RUNTIME_CONTROL_UNAVAILABLE"


def test_get_runtime_view_uses_only_current_principal_scope() -> None:
    control = _control_plane()
    response = TestClient(_app(control)).get(
        f"/v1/bundle-runtime-installations/{INSTALLATION_ID}",
        headers={"Authorization": "Bearer ignored"},
    )
    assert response.status_code == 200
    assert response.json()["allowedActions"] == ["runtime-apply"]
    assert control.view_reader.installation_calls == [{
        "installation_id": INSTALLATION_ID,
        "org_id": "org-org",
        "project_id": "dev-project",
        "roles": ["admin"],
        "markings": ["public"],
    }]


def test_runtime_view_can_carry_only_the_strict_server_ui_session() -> None:
    ui = RuntimeUiSessionView(
        title="隔离测试扩展",
        signedResourceUrl="http://127.0.0.1:18182/extensions/test/index.html?contentHash=sha256%3A" + "a" * 64,
        resourceHash="sha256:" + "a" * 64,
        initialRoute="/test",
        routeClaims=("/test",),
        readOperationClaims=("test.read",),
        commandOperationClaims=(),
    )
    payload = _view(ui=ui).model_dump(mode="json")
    assert payload["ui"]["resourceHash"] == "sha256:" + "a" * 64
    assert payload["ui"]["readOperationClaims"] == ["test.read"]


def test_ready_runtime_resolves_ui_from_the_exact_tenant_generation_and_epoch() -> None:
    calls = []

    def resolve_ui(**kwargs):
        calls.append(kwargs)
        return RuntimeUiSessionView(
            title="隔离测试扩展",
            signedResourceUrl="http://127.0.0.1:18182/extensions/test/index.html?contentHash=sha256%3A" + "a" * 64,
            resourceHash="sha256:" + "a" * 64,
            initialRoute="/test",
            routeClaims=("/test",),
            readOperationClaims=("test.read",),
            commandOperationClaims=(),
        )

    connection = _ReadyRuntimeConnection()
    reader = RuntimeViewReader(
        installation_reader=_InstallationReader(),
        connect_factory=lambda: connection,
        ui_session_resolver=resolve_ui,
    )
    result = reader.get_installation(
        installation_id=INSTALLATION_ID,
        org_id="org-org",
        project_id="dev-project",
        roles=["admin"],
        markings=["public"],
    )
    assert result.effectiveState == "ready"
    assert result.ui is not None
    assert calls == [{
        "installation": _InstallationReader().get(),
        "org_id": "org-org",
        "project_id": "dev-project",
        "installation_id": INSTALLATION_ID,
        "installation_revision": 3,
        "generation": GENERATION,
        "execution_epoch": 2,
        "roles": ["admin"],
        "markings": ["public"],
    }]
    assert connection.committed is True


def test_ui_resolver_failure_keeps_the_ready_runtime_page_closed_without_raw_detail() -> None:
    secret = "https://signed.example.test/private?token=must-not-leak"

    def fail_ui(**_kwargs):
        raise RuntimeError(secret)

    reader = RuntimeViewReader(
        installation_reader=_InstallationReader(),
        connect_factory=_ReadyRuntimeConnection,
        ui_session_resolver=fail_ui,
    )
    result = reader.get_installation(
        installation_id=INSTALLATION_ID,
        org_id="org-org",
        project_id="dev-project",
        roles=["admin"],
        markings=["public"],
    )
    assert result.ui is None
    assert "前端扩展资源会话校验失败" in result.reasons[-1]
    assert secret not in "".join(result.reasons)


def test_get_operation_returns_strong_revision_and_hides_other_tenant_by_reader() -> None:
    control = _control_plane()
    response = TestClient(_app(control)).get(
        f"/v1/bundle-runtime-installations/operations/{OPERATION_ID}",
        headers={"Authorization": "Bearer ignored"},
    )
    assert response.status_code == 200
    assert response.headers["etag"] == '"1"'
    assert control.view_reader.operation_calls[0]["org_id"] == "org-org"


def test_runtime_apply_is_receipt_first_and_sets_location() -> None:
    control = _control_plane()
    response = TestClient(_app(control)).post(
        f"/v1/bundle-runtime-installations/{INSTALLATION_ID}/operations",
        headers={
            "Authorization": "Bearer ignored",
            "Idempotency-Key": "prepare-1",
            "If-Match": '"3"',
        },
        json={"kind": "runtime-apply", "target": None},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.headers["etag"] == '"1"'
    assert response.headers["location"].endswith(OPERATION_ID)
    call = control.lifecycle_service.calls[0]
    assert call["kind"] == "runtime-apply"
    assert call["org_id"] == "org-org"
    assert "target" not in call


def test_configure_and_disable_dispatch_exact_targets() -> None:
    control = _control_plane()
    client = TestClient(_app(control))
    configure_target = {
        "generation": GENERATION,
        "bindingRevision": 4,
        "configRef": {
            "configurationId": CONFIGURATION_ID,
            "revision": 1,
            "hash": "sha256:" + "a" * 64,
        },
    }
    response = client.post(
        f"/v1/bundle-runtime-installations/{INSTALLATION_ID}/operations",
        headers={"Authorization": "Bearer ignored", "Idempotency-Key": "configure-1", "If-Match": '"3"'},
        json={"kind": "configure", "target": configure_target},
    )
    assert response.status_code == 202
    assert control.configuration_service.calls[0]["target"] == configure_target

    response = client.post(
        f"/v1/bundle-runtime-installations/{INSTALLATION_ID}/operations",
        headers={"Authorization": "Bearer ignored", "Idempotency-Key": "disable-1", "If-Match": '"3"'},
        json={"kind": "disable", "target": {"generation": GENERATION, "bindingRevision": 4}},
    )
    assert response.status_code == 202
    assert control.disable_service.calls[0]["target"]["generation"] == GENERATION


def test_target_and_header_contracts_reject_ambiguous_requests() -> None:
    client = TestClient(_app(_control_plane()))
    missing_target = client.post(
        f"/v1/bundle-runtime-installations/{INSTALLATION_ID}/operations",
        headers={"Authorization": "Bearer ignored", "Idempotency-Key": "configure-1", "If-Match": '"3"'},
        json={"kind": "configure"},
    )
    assert missing_target.status_code == 400
    extra_target = client.post(
        f"/v1/bundle-runtime-installations/{INSTALLATION_ID}/operations",
        headers={"Authorization": "Bearer ignored", "Idempotency-Key": "prepare-1", "If-Match": '"3"'},
        json={"kind": "runtime-apply", "target": {}},
    )
    assert extra_target.status_code == 400
    missing_headers = client.post(
        f"/v1/bundle-runtime-installations/{INSTALLATION_ID}/operations",
        headers={"Authorization": "Bearer ignored"},
        json={"kind": "runtime-apply"},
    )
    assert missing_headers.status_code in {400, 428}


def test_runtime_conflicts_use_fixed_chinese_messages_without_raw_details() -> None:
    secret = "postgresql://user:password@host/private"
    for error, status_code, code in (
        (RuntimeConflict(secret), 409, "RUNTIME_STATE_CONFLICT"),
        (RuntimeRevisionConflict(secret), 412, "RUNTIME_REVISION_CONFLICT"),
        (PermissionError(secret), 403, "RUNTIME_ACCESS_DENIED"),
        (LookupError(secret), 404, "RUNTIME_NOT_FOUND"),
    ):
        control = _control_plane(command_error=error)
        response = TestClient(_app(control)).post(
            f"/v1/bundle-runtime-installations/{INSTALLATION_ID}/operations",
            headers={"Authorization": "Bearer ignored", "Idempotency-Key": "prepare-1", "If-Match": '"3"'},
            json={"kind": "runtime-apply"},
        )
        assert response.status_code == status_code
        assert response.json()["code"] == code
        assert secret not in response.text


def test_server_derived_actions_never_report_in_progress_as_ready() -> None:
    state = _derive_control_state(
        installation_state="active",
        installation_revision=3,
        binding=RuntimeBindingView(
            generation=GENERATION,
            installationRevision=3,
            profileRef="internal-python-v1",
            configRef={"configurationId": CONFIGURATION_ID},
            executionEpoch=2,
            desiredState="enabled",
            observedState="ready",
            enabled=True,
            operationFence=False,
            revision=4,
        ),
        operation=_operation(kind="disable", status="running", phase="draining"),
    )
    assert state[0] == "operation_in_progress"
    assert state[1] == ()


def test_server_derived_actions_require_current_binding_revision() -> None:
    state = _derive_control_state(
        installation_state="active",
        installation_revision=4,
        binding=RuntimeBindingView(
            generation=GENERATION,
            installationRevision=3,
            profileRef="internal-python-v1",
            configRef=None,
            executionEpoch=1,
            desiredState="disabled",
            observedState="ready",
            enabled=False,
            operationFence=False,
            revision=2,
        ),
        operation=None,
    )
    assert state[0] == "stale_binding"
    assert state[1] == ()


def test_successful_configuration_or_disable_can_be_enabled_again() -> None:
    binding = RuntimeBindingView(
        generation=GENERATION,
        installationRevision=3,
        profileRef="internal-python-v1",
        configRef={"configurationId": CONFIGURATION_ID},
        executionEpoch=2,
        desiredState="disabled",
        observedState="unknown",
        enabled=False,
        operationFence=True,
        revision=5,
    )
    for kind in ("configure", "disable"):
        state = _derive_control_state(
            installation_state="active",
            installation_revision=3,
            binding=binding,
            operation=_operation(kind=kind, status="succeeded", phase="succeeded"),
        )
        assert state[0] == "disabled"
        assert state[1] == ("configure", "enable")


def test_successful_verification_unlocks_only_configuration() -> None:
    state = _derive_control_state(
        installation_state="active",
        installation_revision=3,
        binding=RuntimeBindingView(
            generation=GENERATION,
            installationRevision=3,
            profileRef="internal-python-v1",
            configRef=None,
            executionEpoch=1,
            desiredState="disabled",
            observedState="ready",
            enabled=False,
            operationFence=True,
            revision=1,
        ),
        operation=_operation(kind="runtime-verify", status="succeeded", phase="succeeded"),
    )
    assert state[0] == "configuration_required"
    assert state[1] == ("configure",)


def test_failed_verification_keeps_the_binding_fenced() -> None:
    state = _derive_control_state(
        installation_state="active",
        installation_revision=3,
        binding=RuntimeBindingView(
            generation=GENERATION,
            installationRevision=3,
            profileRef="internal-python-v1",
            configRef=None,
            executionEpoch=1,
            desiredState="disabled",
            observedState="ready",
            enabled=False,
            operationFence=True,
            revision=1,
        ),
        operation=_operation(kind="runtime-verify", status="failed", phase="failed"),
    )
    assert state[0] == "fenced"
    assert state[1] == ()


def test_failed_fenced_operation_never_unlocks_enable() -> None:
    state = _derive_control_state(
        installation_state="active",
        installation_revision=3,
        binding=RuntimeBindingView(
            generation=GENERATION,
            installationRevision=3,
            profileRef="internal-python-v1",
            configRef={"configurationId": CONFIGURATION_ID},
            executionEpoch=2,
            desiredState="disabled",
            observedState="unknown",
            enabled=False,
            operationFence=True,
            revision=5,
        ),
        operation=_operation(kind="disable", status="failed", phase="failed"),
    )
    assert state[0] == "fenced"
    assert state[1] == ()


def test_missing_runtime_storage_is_explicit_and_never_unlocks_commands() -> None:
    state = _derive_control_state(
        installation_state="active",
        installation_revision=5,
        binding=None,
        operation=None,
        runtime_storage_available=False,
    )
    assert state[0] == "runtime_storage_unavailable"
    assert state[1] == ()
    assert "运行操作保持关闭" in state[2][0]
