"""Readiness is a blocked metadata view, never an approval."""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import Response

from aos_api import data_os_store
from aos_api.routers import pipeline_controls
from aos_api.tenant_scope import TenantScope


REVISION = UUID("11111111-1111-4111-8111-111111111111")


def _store(monkeypatch, *, pipeline=None, receipt=None, source=None, graph=None,
           installations=(), bindings=()):
    calls = []

    class Cursor:
        def __init__(self, row): self.row = row
        def fetchone(self): return self.row
        def fetchall(self): return self.row

    class Connection:
        def execute(self, sql, params):
            calls.append((sql, params))
            if "FROM meta_pipeline" in sql: return Cursor(pipeline)
            if "FROM pipeline_registration_receipt" in sql: return Cursor(receipt)
            if "FROM meta_source" in sql: return Cursor(source)
            if "FROM phase5_pipeline_graph" in sql: return Cursor(graph)
            if "FROM bundle_installation i" in sql: return Cursor(installations)
            if "FROM extension_runtime_binding" in sql: return Cursor(bindings)
            raise AssertionError("unexpected read")

    @contextmanager
    def read(scope):
        assert scope == TenantScope("org-org", "dev-project")
        yield Connection()

    monkeypatch.setattr(data_os_store, "connect_read_only", read)
    return calls


def test_empty_pipeline_is_scoped_and_never_ready(monkeypatch):
    calls = _store(monkeypatch)
    result = data_os_store.read_pipeline_source_selection_readiness(
        TenantScope("org-org", "dev-project"), "P01")
    assert result["ready"] is False
    assert result["nextAction"] == "REGISTER_PIPELINE"
    assert result["sourceId"] is None
    assert "INSTALLATION_MISSING" in result["blockers"]
    assert len(calls) == 3
    assert all(params[:2] == ("org-org", "dev-project") for _, params in calls)


def test_saved_graph_still_requires_exact_runtime_revalidation(monkeypatch):
    _store(monkeypatch, pipeline={"id": "P01", "source_id": "source-one"},
        receipt={"source_id": "source-one", "source_configuration_revision": REVISION},
        source={"configuration_revision": REVISION}, graph={"revision": 3})
    result = data_os_store.read_pipeline_source_selection_readiness(
        TenantScope("org-org", "dev-project"), "P01")
    assert result["formallyRegistered"] is True
    assert result["sourceConfigurationRevision"] == str(REVISION)
    assert result["graphRevision"] == 3
    assert result["ready"] is False
    assert result["blockers"] == ["EXACT_RUNTIME_REVALIDATION_REQUIRED", "INSTALLATION_MISSING"]


def test_source_drift_or_missing_graph_blocks(monkeypatch):
    receipt = {"source_id": "source-one", "source_configuration_revision": REVISION}
    pipeline = {"id": "P01", "source_id": "source-one"}
    _store(monkeypatch, pipeline=pipeline, receipt=receipt,
        source={"configuration_revision": UUID("22222222-2222-4222-8222-222222222222")})
    assert data_os_store.read_pipeline_source_selection_readiness(
        TenantScope("org-org", "dev-project"), "P01")["nextAction"] == "REGISTER_SOURCE"
    _store(monkeypatch, pipeline=pipeline, receipt=receipt,
        source={"configuration_revision": REVISION})
    assert data_os_store.read_pipeline_source_selection_readiness(
        TenantScope("org-org", "dev-project"), "P01")["nextAction"] == "SAVE_GRAPH"


@pytest.mark.parametrize("installations,bindings,expected,action", [
    (({"installation_id": REVISION, "active_revision": None, "state": None},), (),
     "INSTALLATION_NOT_ACTIVE", "REVIEW_INSTALLATION"),
    (({"installation_id": REVISION, "active_revision": 3, "state": "active"},), (),
     "RUNTIME_BINDING_MISSING", "CONFIGURE_RUNTIME"),
    (({"installation_id": REVISION, "active_revision": 3, "state": "active"},),
     ({"config_ref": None, "execution_epoch": 1},), "RUNTIME_CONFIGURATION_MISSING", "CONFIGURE_RUNTIME"),
    (({"installation_id": REVISION, "active_revision": 3, "state": "active"},),
     ({"config_ref": {"configurationId": str(REVISION)}, "execution_epoch": 1},),
     "EXACT_RUNTIME_REVALIDATION_REQUIRED", "REVALIDATE_RUNTIME"),
    (({"installation_id": REVISION, "active_revision": 3, "state": "active"},
      {"installation_id": REVISION, "active_revision": 3, "state": "active"}), (),
     "INSTALLATION_AMBIGUOUS", "REVIEW_INSTALLATION"),
])
def test_installation_and_binding_diagnostics_never_grant_approval(
        monkeypatch, installations, bindings, expected, action):
    _store(monkeypatch, pipeline={"id": "P01", "source_id": "source-one"},
        receipt={"source_id": "source-one", "source_configuration_revision": REVISION},
        source={"configuration_revision": REVISION}, graph={"revision": 3},
        installations=installations, bindings=bindings)
    result = data_os_store.read_pipeline_source_selection_readiness(
        TenantScope("org-org", "dev-project"), "P01")
    assert result["ready"] is False
    assert expected in result["blockers"]
    assert result["nextAction"] == action
    assert "draft" not in result


def test_http_entry_uses_principal_and_sanitizes_unknown(monkeypatch):
    observed = []
    def read(scope, pipeline_id):
        observed.append((scope.key, pipeline_id))
        return {"pipelineId": pipeline_id, "ready": False}
    monkeypatch.setattr(data_os_store, "read_pipeline_source_selection_readiness", read)
    principal = SimpleNamespace(org_id="org-org", project_id="dev-project")
    response = Response()
    assert pipeline_controls.read_selection_readiness("P01", response, principal)["ready"] is False
    assert response.headers["cache-control"] == "no-store"
    assert observed == [(("org-org", "dev-project"), "P01")]
    monkeypatch.setattr(data_os_store, "read_pipeline_source_selection_readiness",
        lambda *args: (_ for _ in ()).throw(RuntimeError("private-sentinel")))
    with pytest.raises(pipeline_controls.ApiError) as error:
        pipeline_controls.read_selection_readiness("P01", Response(), principal)
    assert error.value.code == "PIPELINE_READINESS_UNCONFIRMED"
    assert "private-sentinel" not in str(error.value)
