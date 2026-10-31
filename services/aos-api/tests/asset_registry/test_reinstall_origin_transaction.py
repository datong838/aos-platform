"""Offline driver edges only: no PostgreSQL, native cancel or role qualification."""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import importlib.util
from pathlib import Path
from unittest.mock import patch

import psycopg
import pytest

from aos_api.asset_registry import reinstall_origin_transaction as bounded
from aos_api.asset_registry import composition_store as composition_module
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.installation_store import CommandReceipt

_NATIVE_CONNECT_ENTRY = bounded._BoundedReinstallConnection.connect.__func__


def test_settings_require_explicit_endpoint_and_hide_values():
    with pytest.raises(TypeError):
        bounded.ReinstallConnectionSettings()
    settings = bounded.ReinstallConnectionSettings(
        host="/offline/socket", port=5432, dbname="offline", user="offline",
        password="synthetic-offline-not-a-credential",
    )
    assert "synthetic-offline" not in repr(settings)
    assert "offline/socket" not in repr(settings)


def test_native_subclasses_preserve_canonical_driver_identity():
    assert issubclass(bounded._BoundedReinstallConnection, psycopg.Connection)
    assert issubclass(bounded._BoundedReinstallCursor, psycopg.Cursor)


class FakeTimer:
    def __init__(self, interval, function):
        self.interval, self.function = interval, function
        self.daemon = False
        self.started = self.cancelled = self.joined = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def join(self, timeout):
        self.joined = True

    def is_alive(self):
        return False


@pytest.fixture
def harness():
    spec = importlib.util.spec_from_file_location(
        "_reinstall_original_transaction_fixtures",
        Path(__file__).with_name("test_reinstall_origin_service.py"),
    )
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    h = original.ReinstallOriginServiceTests()
    h.setUp()
    h.now = 0.0
    h.driver_connections, h.connect_kwargs, h.roots, h.timers = [], [], [], []
    h.cursor_rows = {}
    h.fail_commit = h.fail_rollback = h.fail_close = h.fail_cancel = False
    h.late_commit = h.late_statement = False
    h.post_failure = h.post_deadline = False
    h.hook = None

    def timer(interval, function):
        value = FakeTimer(interval, function)
        h.timers.append(value)
        return value

    def connection_init(conn, pgconn, row_factory):
        conn._offline = original.FakeConnection(h)
        conn.pending = conn._offline.pending
        conn._offline_closed = False
        conn.row_factory = row_factory
        conn.cursor_factory = psycopg.Cursor

    def connect(cls, **kwargs):
        h.connect_kwargs.append(kwargs)
        h.roots.append(bounded._CURRENT.get())
        conn = cls(object(), row_factory=kwargs["row_factory"])
        h.driver_connections.append(conn)
        return conn

    def cursor_init(cursor, connection, *, row_factory=None):
        cursor._conn = connection
        cursor._closed = False

    def execute(cursor, query, params=None, **kwargs):
        conn = cursor.connection
        if query == bounded._TIMEOUT_SQL:
            h.trace.append("timeouts")
            h.last_timeouts = params
            h.cursor_rows[id(cursor)] = None
        else:
            if h.hook:
                h.hook(conn, query)
            if query == "SELECT current_user AS current_user":
                h.trace.append("native_scope_identity")
                h.cursor_rows[id(cursor)] = {"current_user": "aos_app"}
            elif "set_config('aos.org_id'" in query:
                h.trace.append("native_scope_gucs")
                h.cursor_rows[id(cursor)] = None
            else:
                result = conn._offline.execute(query, params)
                h.cursor_rows[id(cursor)] = result.row
            if h.late_statement:
                h.now = 61.0
        return cursor

    def commit(conn):
        if h.fail_commit:
            raise psycopg.OperationalError("synthetic commit outcome unknown")
        conn._offline.commit()
        if h.late_commit:
            h.now = 61.0

    def rollback(conn):
        h.trace.append("driver_rollback")
        if h.fail_rollback:
            raise RuntimeError("synthetic rollback failure")
        conn._offline.pending = deepcopy(h.committed)

    def close(conn):
        h.trace.append("driver_close")
        if h.fail_close:
            raise RuntimeError("synthetic close failure")
        conn._offline_closed = True

    def cancel(conn, *, timeout):
        h.trace.append("driver_cancel")
        assert timeout == 1.0
        if h.fail_cancel:
            raise RuntimeError("synthetic cancel failure")

    stack = ExitStack()
    stack.enter_context(patch.object(bounded, "monotonic", side_effect=lambda: h.now))
    stack.enter_context(patch.object(bounded, "Timer", side_effect=timer))
    stack.enter_context(patch.object(psycopg.capabilities, "has_cancel_safe", return_value=True))
    for name, value in (("__init__", connection_init), ("commit", commit),
                        ("rollback", rollback), ("close", close), ("cancel_safe", cancel),
                        ("_check_connection_ok", lambda conn: None),
                        ("closed", property(lambda conn: conn._offline_closed)),
                        ("broken", property(lambda conn: False))):
        stack.enter_context(patch.object(psycopg.Connection, name, value))
    stack.enter_context(patch.object(bounded._BoundedReinstallConnection, "connect",
                                    classmethod(connect)))
    for name, value in (("__init__", cursor_init), ("execute", execute),
                        ("fetchone", lambda c: h.cursor_rows.get(id(c))),
                        ("fetchmany", lambda c, n=0: []), ("fetchall", lambda c: []),
                        ("close", lambda c: setattr(c, "_closed", True))):
        stack.enter_context(patch.object(psycopg.Cursor, name, value))

    h.owner = bounded.ReinstallOriginTransactions(bounded.ReinstallConnectionSettings(
        host="/offline/socket", port=5432, dbname="offline", user="offline",
        password="synthetic-offline-not-a-credential"))
    h.store._connect_factory = h.owner.connection_factory
    composition = PostgresCompositionStore(connect_factory=h.owner.connection_factory)
    h.delegate._composition_store = composition
    stack.enter_context(patch.object(composition_module, "apply_asset_transaction_scope",
                                    side_effect=lambda conn, **scope: h.trace.append("post_scope")))

    def select(conn, **kwargs):
        h.trace.append("post_read")
        assert bounded._CURRENT.get() is conn._budget
        if h.post_deadline:
            h.now = 61.0
        if h.post_failure:
            raise PermissionError("synthetic postcommit authorization failure")
        return {"synthetic": True}

    stack.enter_context(patch.object(composition_module, "_select_by_id", side_effect=select))
    stack.enter_context(patch.object(composition_module, "_stored_lock_from_row",
                                    side_effect=lambda row: h.target_lock))
    h.executor = h.owner.bind(h.service)

    def call(**changes):
        values = dict(installation_id=original.original.INSTALLATION_ID,
            request=original.payload(), actor="requester", roles=["developer"],
            markings=[], idempotency_key="synthetic-reinstall-1", if_match='"4"',
            **original.SCOPE)
        values.update(changes)
        return h.executor.reinstall(**values)

    h.bounded_call = call
    try:
        yield h
    finally:
        stack.close()
        h.stack.close()


def test_original_graph_commit_and_post_read_share_one_root(harness):
    h = harness
    receipt = h.bounded_call()
    assert type(receipt) is CommandReceipt
    assert len(h.driver_connections) == 2
    first, second = h.driver_connections
    assert first._budget is second._budget is h.roots[0] is h.roots[1]
    assert isinstance(first, psycopg.Connection)
    assert first is h.origin.checks[0][0] is h.origin.appends[0][0]
    assert h.trace.count("commit") == 1
    assert h.trace.index("current_authority") < h.trace.index("cached_select")
    assert h.trace.index("command_insert") < h.trace.index("commit") < h.trace.index("post_read")
    assert all(conn.closed for conn in h.driver_connections)
    assert all(t.started and t.cancelled and t.joined for t in h.timers)
    assert bounded._CURRENT.get() is None
    assert h.roots[0].commit_outcome == "acknowledged"
    assert "default_transaction_read_only=on" not in h.connect_kwargs[0]["options"]
    assert "default_transaction_read_only=on" in h.connect_kwargs[1]["options"]


def test_replay_retains_current_before_cache_and_no_second_append(harness):
    h = harness
    h.bounded_call()
    h.trace.clear()
    receipt = h.bounded_call()
    assert receipt.replayed
    assert h.trace.index("current_authority") < h.trace.index("cached_select")
    assert "origin" not in h.trace and "draft" not in h.trace
    assert h.trace.count("commit") == 1
    assert h.roots[0] is not h.roots[2]
    h.origin.verdict = False
    h.trace.clear()
    with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
        h.bounded_call()
    assert caught.value.commit_outcome == "not_started"
    assert "cached_select" not in h.trace


@pytest.mark.parametrize("field,value", [
    ("host", "localhost"), ("host", "/one,/two"), ("port", True), ("port", 0),
    ("dbname", ""), ("user", " padded "), ("password", ""), ("password", "bad\0value"),
])
def test_settings_reject_bad_types_and_multihost_without_values(field, value):
    settings = dict(host="/offline/socket", port=5432, dbname="offline", user="offline",
                    password="synthetic-offline")
    settings[field] = value
    with pytest.raises(ValueError) as caught:
        bounded.ReinstallConnectionSettings(**settings)
    assert "synthetic-offline" not in str(caught.value)


def test_factory_without_root_and_mutated_graph_are_rejected(harness):
    h = harness
    with pytest.raises(bounded._AttemptFailure):
        with h.owner.connection_factory():
            pytest.fail("must not connect")
    h.store._connect_factory = lambda: None
    with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
        h.bounded_call()
    assert caught.value.commit_outcome == "not_started"
    assert not h.driver_connections


def test_configuration_is_not_a_permission_or_driver_capability(harness):
    h = harness
    with patch.object(psycopg.capabilities, "has_cancel_safe", return_value=False):
        with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
            h.bounded_call()
    assert caught.value.commit_outcome == "not_started"
    assert not h.driver_connections


@pytest.mark.parametrize("stage", ["insert", "origin", "commit", "post", "late_commit", "late_post"])
def test_failure_classification_does_not_claim_rollback_after_ack(harness, stage):
    h = harness
    if stage == "insert":
        h.fail_insert = True
    elif stage == "origin":
        h.origin.raise_append = True
    elif stage == "commit":
        h.fail_commit = True
    elif stage == "post":
        h.post_failure = True
    elif stage == "late_commit":
        h.late_commit = True
    else:
        h.post_deadline = True
    with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
        h.bounded_call()
    expected = "unknown" if stage == "commit" else (
        "not_started" if stage in {"insert", "origin"} else "acknowledged")
    assert caught.value.commit_outcome == expected
    assert caught.value.cleanup_outcome == "closed"
    assert all(conn.closed for conn in h.driver_connections)
    assert bounded._CURRENT.get() is None
    if expected == "not_started":
        assert h.committed == dict(commands={}, drafts=[], origins=[])
    if expected == "acknowledged":
        assert len(h.committed["commands"]) == 1
        assert h.trace.count("commit") == 1


def test_deadline_before_commit_never_calls_native_commit(harness):
    h = harness
    def expire_before_command(conn, query):
        if "INSERT INTO bundle_installation_command" in query:
            h.now = 61.0
    h.hook = expire_before_command
    with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
        h.bounded_call()
    assert caught.value.commit_outcome == "not_started"
    assert "commit" not in h.trace


def test_watchdog_cancel_failure_and_late_timer_do_not_target_next_root(harness):
    h = harness
    h.fail_cancel = True
    def expire(conn, query):
        if "pg_advisory_xact_lock" in query:
            h.now = 61.0
            h.timers[-1].function()
    h.hook = expire
    with pytest.raises(bounded.ReinstallOriginAttemptError):
        h.bounded_call()
    assert h.trace.count("driver_cancel") == 1
    old_timer = h.timers[-1]
    h.hook = None
    h.fail_cancel = False
    h.now = 100.0
    h.bounded_call()
    before = h.trace.count("driver_cancel")
    old_timer.function()
    assert h.trace.count("driver_cancel") == before


@pytest.mark.parametrize("failure", ["rollback", "close", "timer"])
def test_cleanup_failure_cannot_return_success(harness, failure):
    h = harness
    h.fail_rollback = failure == "rollback"
    h.fail_close = failure == "close"
    if failure == "timer":
        timer_context = patch.object(FakeTimer, "is_alive", return_value=True)
    else:
        timer_context = ExitStack()
    with timer_context:
        with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
            h.bounded_call()
    assert caught.value.cleanup_outcome == "unconfirmed"
    assert bounded._CURRENT.get() is None


def test_root_starts_before_original_validation_and_resets(harness):
    h = harness
    seen = []
    original = h.service.reinstall
    def inspect_root(**kwargs):
        root = bounded._CURRENT.get()
        seen.append(root)
        h.now = root.deadline + 1
        return original(**kwargs)
    with patch.object(h.service, "reinstall", side_effect=inspect_root):
        with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
            h.bounded_call()
    assert seen and caught.value.commit_outcome == "not_started"
    assert not h.driver_connections
    assert bounded._CURRENT.get() is None


def test_nested_root_wrong_owner_and_unqualified_channels_rejected(harness):
    h = harness
    checked = []
    def check(conn, query):
        if checked:
            return
        checked.append(True)
        with pytest.raises(bounded.ReinstallOriginAttemptError):
            h.bounded_call()
        other = bounded.ReinstallOriginTransactions(h.owner._settings)
        with pytest.raises(bounded._AttemptFailure):
            with other.connection_factory():
                pytest.fail("wrong owner")
        for method in (conn.transaction, conn.pipeline, conn.tpc_begin,
                       conn.set_autocommit, conn.__enter__):
            with pytest.raises(bounded._AttemptFailure):
                method()
        with pytest.raises(bounded._AttemptFailure):
            conn.cursor("server_cursor")
    h.hook = check
    h.bounded_call()
    assert checked


def test_native_type_still_runs_original_tenant_binding(harness):
    h = harness
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.asset_registry import installation_store as store_module
    with patch.object(store_module, "apply_asset_transaction_scope", apply_asset_transaction_scope):
        h.bounded_call()
    assert h.trace.index("native_scope_identity") < h.trace.index("native_scope_gucs")
    assert h.trace.index("native_scope_gucs") < h.trace.index("advisory")


def test_startup_caps_and_each_control_round_trip_are_positive(harness):
    h = harness
    h.now = 10.0
    h.bounded_call()
    assert all(2 <= value["connect_timeout"] <= 5 for value in h.connect_kwargs)
    assert all(value["passfile"] == "/dev/null" for value in h.connect_kwargs)
    assert all("statement_timeout=10000" in value["options"] for value in h.connect_kwargs)
    assert all("lock_timeout=1000" in value["options"] for value in h.connect_kwargs)
    assert tuple(map(int, h.last_timeouts)) == (10000, 1000)


def test_deadline_crossed_during_timer_join_cannot_return_success(harness):
    h = harness
    def join(timer, timeout):
        timer.joined = True
        h.now = h.roots[0].deadline + 1
    with patch.object(FakeTimer, "join", join):
        with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
            h.bounded_call()
    assert caught.value.commit_outcome == "acknowledged"
    assert caught.value.reason == "deadline"


def test_expired_native_construction_explicitly_closes_owned_pgconn(harness):
    h = harness
    root = bounded._AttemptBudget(h.owner)
    token = bounded._CURRENT.set(root)
    try:
        h.now = root.deadline + 1
        with pytest.raises(bounded._AttemptFailure):
            bounded._BoundedReinstallConnection(object())
        assert "driver_close" in h.trace
    finally:
        bounded._CURRENT.reset(token)


def test_native_connect_rejects_missing_root_before_touching_driver():
    with pytest.raises(bounded._AttemptFailure, match="missing_attempt"):
        _NATIVE_CONNECT_ENTRY(bounded._BoundedReinstallConnection)


def test_postcommit_connect_insufficient_budget_is_not_zero_timeout(harness):
    h = harness
    def nearly_expired(conn, query):
        if "INSERT INTO bundle_installation_command" in query:
            h.now = 58.5
    h.hook = nearly_expired
    with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
        h.bounded_call()
    assert caught.value.commit_outcome == "acknowledged"
    assert len(h.connect_kwargs) == 1
    assert all(v["connect_timeout"] >= 2 for v in h.connect_kwargs)


def test_wrong_thread_cannot_use_even_a_copied_root(harness):
    h = harness
    checked = []
    def check(conn, query):
        if not checked:
            checked.append(True)
            with patch.object(bounded, "get_ident", return_value=conn._budget.thread + 1):
                with pytest.raises(bounded._AttemptFailure, match="inactive_attempt"):
                    conn.cursor()
    h.hook = check
    h.bounded_call()
    assert checked


def test_unknown_commit_preserves_original_store_and_psycopg_causes(harness):
    h = harness
    h.fail_commit = True
    from aos_api.asset_registry.installation_store import InstallationPersistenceError
    with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
        h.bounded_call()
    assert caught.value.commit_outcome == "unknown"
    assert isinstance(caught.value.__cause__, InstallationPersistenceError)
    assert isinstance(caught.value.__cause__.__cause__, psycopg.OperationalError)
    assert "driver_rollback" not in h.trace
    assert len(h.driver_connections) == 1


def test_postcommit_read_cannot_commit_a_second_transaction(harness):
    h = harness
    original = composition_module._select_by_id
    def post_commit(conn, **kwargs):
        with pytest.raises(bounded._AttemptFailure, match="unexpected_commit"):
            conn.commit()
        return original(conn, **kwargs)
    with patch.object(composition_module, "_select_by_id", side_effect=post_commit):
        h.bounded_call()
    assert h.trace.count("commit") == 1


@pytest.mark.parametrize("fail_number,expected", [(1, "not_started"), (2, "acknowledged")])
def test_connect_exception_after_constructor_closes_registered_connection(harness, fail_number, expected):
    h = harness
    original_connect = bounded._BoundedReinstallConnection.connect
    def fail_after_constructor(cls, **kwargs):
        conn = original_connect(**kwargs)
        if len(h.driver_connections) == fail_number:
            raise psycopg.OperationalError("synthetic failure after native construction")
        return conn
    with patch.object(bounded._BoundedReinstallConnection, "connect",
                      classmethod(fail_after_constructor)):
        with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
            h.bounded_call()
    assert caught.value.commit_outcome == expected
    assert caught.value.cleanup_outcome == "closed"
    assert len(h.driver_connections) == fail_number
    assert all(conn.closed for conn in h.driver_connections)
    assert not h.roots[-1].connections
    assert h.trace.count("driver_close") == fail_number
    assert "driver_cancel" not in h.trace
    assert bounded._CURRENT.get() is None


def test_connect_exception_before_construction_does_not_invent_connection_cleanup(harness):
    h = harness
    def fail_before_constructor(cls, **kwargs):
        raise psycopg.OperationalError("synthetic preconstruction failure")
    with patch.object(bounded._BoundedReinstallConnection, "connect",
                      classmethod(fail_before_constructor)):
        with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
            h.bounded_call()
    assert caught.value.commit_outcome == "not_started"
    assert caught.value.cleanup_outcome == "not_opened"
    assert not h.driver_connections
    assert "driver_close" not in h.trace


def test_connect_cleanup_error_preserves_primary_connect_cause(harness):
    h = harness
    original_connect = bounded._BoundedReinstallConnection.connect
    def fail_after_constructor(cls, **kwargs):
        original_connect(**kwargs)
        raise psycopg.OperationalError("synthetic primary connect failure")
    h.fail_close = True
    with patch.object(bounded._BoundedReinstallConnection, "connect",
                      classmethod(fail_after_constructor)):
        with pytest.raises(bounded.ReinstallOriginAttemptError) as caught:
            h.bounded_call()
    assert caught.value.commit_outcome == "not_started"
    assert caught.value.cleanup_outcome == "unconfirmed"
    assert h.trace.count("driver_close") == 1
    error = caught.value.__cause__
    while error.__cause__ is not None:
        error = error.__cause__
    assert isinstance(error, psycopg.OperationalError)
