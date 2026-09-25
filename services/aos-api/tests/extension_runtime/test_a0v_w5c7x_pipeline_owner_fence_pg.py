"""Disposable-PG composition of optional Pipeline Owner fencing; no live opt-in."""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
import pytest

from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.pipeline_runtime_control_owner import PipelineRuntimeControlOwner
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from tests.test_pipeline_runtime_control_contracts import payload


@pytest.fixture
def owner_case(fence_case, tmp_path, monkeypatch):
    admin_dsn, directory_dsn, runtime_dsn, org, project, _ = fence_case
    assert conninfo_to_dict(admin_dsn)["dbname"].startswith("aos_test_")
    table = sql.Identifier("a0v_w5c7x_probe_" + uuid4().hex[:8])
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE TABLE public.{}(kind text PRIMARY KEY)").format(table))
        admin.execute(sql.SQL("GRANT INSERT,SELECT ON public.{} TO aos_runtime").format(table))

    @contextmanager
    def directory():
        with psycopg.connect(directory_dsn, row_factory=dict_row) as conn:
            yield conn

    @contextmanager
    def runtime():
        with psycopg.connect(runtime_dsn, autocommit=True, row_factory=dict_row) as conn:
            conn.execute("SET ROLE aos_runtime")
            yield conn

    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    assert lease.acquire() == 1
    import aos_api.pipeline_control_service as module
    monkeypatch.setattr(module, "runtime_worker_connection", runtime)
    factory = PipelineControlServiceFactory(
        installation_store=PostgresInstallationStore(),
        policy=ReleasePolicy(trust_roots=None), allowlist_roots={"fixture": Path(tmp_path)},
    )
    service = factory.build(TenantScope(org, project), host_lease=lease)
    calls = []

    def write(kind, conn):
        row = conn.execute(
            "SELECT current_user AS role,current_setting('aos.org_id') AS org,"
            "current_setting('aos.project_id') AS project"
        ).fetchone()
        assert row == {"role": "aos_runtime", "org": org, "project": project}
        calls.append(kind)
        conn.execute(sql.SQL("INSERT INTO public.{}(kind) VALUES(%s)").format(table), (kind,))
        return SimpleNamespace(ref=kind)

    monkeypatch.setattr(PipelineSourceSelectionOwner, "append",
                        lambda self, conn, **kwargs: write("selection", conn))
    monkeypatch.setattr(PipelineRuntimeControlOwner, "append",
                        lambda self, conn, **kwargs: write("control", conn))
    monkeypatch.setattr(PipelineScheduleControlOwner, "bind",
                        lambda self, conn, **kwargs: write("bind", conn))
    body = payload()
    body["orgId"], body["projectId"] = org, project
    selection = dict(body)
    selection.pop("sourceSelectionRef")

    def invoke(kind):
        if kind == "selection":
            return service.approve_selection(draft=selection, actor="actor", idempotency_key="selection")
        if kind == "control":
            return service.approve_control(draft=body, actor="actor", idempotency_key="control")
        return service.bind_schedule(pipeline_id="pipeline", schedule_id="schedule",
                                     control_ref={}, actor="actor", idempotency_key="bind")

    def rows():
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            return {row[0] for row in admin.execute(sql.SQL("SELECT kind FROM public.{}").format(table))}

    return lease, invoke, rows, calls, table


def test_current_lease_guards_each_owner_write_in_its_transaction(owner_case):
    _, invoke, rows, calls, _ = owner_case
    for kind in ("selection", "control", "bind"):
        invoke(kind)
    assert calls == ["selection", "control", "bind"]
    assert rows() == {"selection", "control", "bind"}


def test_stale_epoch_rejects_all_owner_writes_before_callback(owner_case):
    lease, invoke, rows, calls, _ = owner_case
    lease._epoch += 1  # isolated stale-holder fault injection
    for kind in ("selection", "control", "bind"):
        with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_REJECTED"):
            invoke(kind)
    assert calls == []
    assert rows() == set()


def test_owner_error_rolls_back_same_guarded_transaction(owner_case, monkeypatch):
    _, invoke, rows, calls, table = owner_case

    def fail_after_insert(self, conn, **kwargs):
        conn.execute(sql.SQL("INSERT INTO public.{}(kind) VALUES('selection')").format(table))
        raise RuntimeError("isolated rollback")

    monkeypatch.setattr(PipelineSourceSelectionOwner, "append", fail_after_insert)
    with pytest.raises(RuntimeError, match="isolated rollback"):
        invoke("selection")
    assert calls == []
    assert rows() == set()
