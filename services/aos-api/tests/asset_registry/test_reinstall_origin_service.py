"""SOURCE-only transaction tests. No concrete native/RLS/PG qualification."""
from __future__ import annotations

import os
from pathlib import Path
import sys

EFFECTS = []
os.environ["AOS_DOTENV_DISABLED"] = "1"
if __name__ == "__main__":
    if not sys.flags.isolated or not sys.dont_write_bytecode or len(sys.argv) != 1:
        raise SystemExit(2)
    for key in tuple(os.environ):
        if key.startswith(("PG", "AOS_DATABASE", "AOS_TEST_")):
            os.environ.pop(key, None)

    def audit(event, args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "subprocess.Popen",
                     "os.system", "os.posix_spawn", "os.fork"}:
            EFFECTS.append(event)
            raise RuntimeError("REINSTALL_SERVICE_EFFECT_DENIED")
        if event == "open":
            name, mode, flags = args
            if isinstance(name, (str, bytes)):
                leaf = Path(os.fsdecode(name)).name
                if leaf in {".env", ".secrets.env"} or leaf.endswith("-identity.json"):
                    EFFECTS.append("private")
                    raise RuntimeError("REINSTALL_SERVICE_PRIVATE_DENIED")
            if (isinstance(mode, str) and any(c in mode for c in "wax+")
                    or isinstance(flags, int) and flags & (
                        os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                EFFECTS.append("write")
                raise RuntimeError("REINSTALL_SERVICE_WRITE_DENIED")

    sys.addaudithook(audit)
    import psycopg

    def deny(*args, **kwargs):
        EFFECTS.append("database")
        raise RuntimeError("REINSTALL_SERVICE_DB_DENIED")

    psycopg.connect = deny
    psycopg.Connection.connect = staticmethod(deny)

sys.path.insert(0, str(Path(__file__).absolute().parents[2]))
import asyncio
from contextlib import ExitStack
from copy import deepcopy
import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import UUID

from aos_api.asset_registry.composition_contracts import InstallationRecord
import aos_api.asset_registry.reinstall_origin_service as reinstall_module
from aos_api.asset_registry.control_policy import REINSTALL_INSTALLATION_OPERATION
from aos_api.asset_registry.errors import (
    AssetNotFoundError, DutySeparationRequiredError, IdempotencyConflictError,
    InstallationStateConflictError, LockIntegrityCorruptError, MarkingAccessDeniedError,
    RevisionConflictError, PreconditionRequiredError, PreconditionInvalidError,
    IdempotencyKeyRequiredError,
)
from aos_api.asset_registry.installation_evidence import build_event_evidence
from aos_api.asset_registry.installation_service import InstallationService
import aos_api.asset_registry.installation_service as service_module
import aos_api.asset_registry.installation_store as store_module
from aos_api.asset_registry.installation_store import PostgresInstallationStore, command_request_hash
from aos_api.asset_registry.reinstall_contracts import ReinstallInstallationRequest
from aos_api.asset_registry.reinstall_origin_service import ReinstallOriginService

spec = importlib.util.spec_from_file_location(
    "_original_pure_installation_fixtures", Path(__file__).with_name("test_composition_contracts.py"))
assert spec and spec.loader
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)

SCOPE = dict(org_id="org-org", project_id="dev-project")
TARGET_ID = str(UUID(int=42))
NEW_ID = str(UUID(int=43))


def source_record():
    value = original._append_installation_state(original._approved_record_payload(), "uninstalled")
    current = value["current"]
    value["events"][-1]["evidence"] = build_event_evidence(
        evidence_type="uninstall", installation_id=value["installationId"],
        from_revision=3, to_revision=4, from_state="approved",
        lock_hash=current["lockHash"], permission_diff_hash=current["permissionDiffHash"],
        migration_plan_hash=current["migrationPlanHash"],
        contribution_diff_hash=current["contributionDiffHash"],
        decision_id=current["decisionId"], observed_at=value["createdAt"],
    )
    return InstallationRecord.model_validate(value)


def draft_record():
    created = original._approved_record_payload()["createdAt"]
    current = original._revision(state="draft", revision=1, decision_id=None)
    current.update(installationId=NEW_ID, compositionId=TARGET_ID, createdAt=created)
    return InstallationRecord.model_validate(dict(
        installationId=NEW_ID, displayName="Synthetic reinstall", state="draft",
        currentRevision=1, activeRevision=None, previousActiveRevision=None,
        etagVersion=1, createdAt=created, updatedAt=created, current=current, decision=None,
        events=[dict(sequence=1, fromRevision=None, toRevision=1, fromState=None,
                     toState="draft", actor="requester", reason=None, evidence=None, createdAt=created)],
    ))


def payload():
    return dict(source=dict(installationId=original.INSTALLATION_ID, terminalRevision=4,
                            lockHash=original.SHA_A),
                target=dict(compositionId=TARGET_ID, lockRevision=1,
                            overlayRevision="synthetic", displayName="Synthetic reinstall"))


def fake_lock():
    return SimpleNamespace(
        lock_hash=original.SHA_A, permission_diff_hash=original.SHA_B,
        migration_plan_hash=original.SHA_C, contribution_diff_hash=original.SHA_D,
        payload=SimpleNamespace(permission_diff=SimpleNamespace(
            target=SimpleNamespace(markings=frozenset()))),
    )


class FakeConnection:
    """Only the SQL boundary is fake; the original command executor runs."""
    def __init__(self, owner):
        self.owner = owner
        self.trace = owner.trace
        self.pending = deepcopy(owner.committed)
        self.row = None

    def __enter__(self):
        self.trace.append("enter")
        return self

    def __exit__(self, kind, value, tb):
        if kind is not None:
            self.trace.append("rollback")
            self.pending = deepcopy(self.owner.committed)

    def execute(self, query, params=()):
        text = " ".join(query.split())
        self.owner.sql_calls.append((text, params))
        if "pg_advisory_xact_lock" in text:
            self.trace.append("advisory")
            self.row = None
        elif "FROM bundle_installation_command" in text:
            self.trace.append("cached_select")
            self.row = deepcopy(self.pending["commands"].get(tuple(params)))
        elif "INSERT INTO bundle_installation_command" in text:
            self.trace.append("command_insert")
            if self.owner.fail_insert:
                raise RuntimeError("synthetic command insert failure")
            self.pending["commands"][tuple(params[:4])] = dict(
                subject=params[4], request_hash=params[5], status_code=params[6],
                response_json=deepcopy(params[7].obj), response_etag=params[8],
            )
            self.row = None
        elif "FROM bundle_installation" in text and "FOR UPDATE" in text:
            self.trace.append("source_head")
            valid = tuple(params[:2]) == tuple(SCOPE.values()) and str(params[2]) == original.INSTALLATION_ID
            self.row = (dict(installation_pk=UUID(int=21),
                             etag_version=self.owner.source.etag_version) if valid else None)
        else:
            raise AssertionError("unexpected fake SQL boundary")
        return self

    def fetchone(self):
        return self.row

    def commit(self):
        self.trace.append("commit")
        self.owner.committed = deepcopy(self.pending)


class FakeOrigin:
    def __init__(self, owner):
        self.owner = owner
        self.verdict = True
        self.append_result = None
        self.raise_append = False
        self.checks = []
        self.appends = []

    def check_current(self, conn, **values):
        self.owner.trace.append("current_authority")
        self.checks.append((conn, values))
        return self.verdict

    def append_origin(self, conn, **values):
        self.owner.trace.append("origin")
        self.appends.append((conn, values))
        conn.pending["origins"].append((values["source"].model_dump(by_alias=True),
                                        values["target_record"].installation_id))
        if self.raise_append:
            raise RuntimeError("synthetic origin append failure")
        return self.append_result


class ReinstallOriginServiceTests(unittest.TestCase):
    def setUp(self):
        self.trace, self.sql_calls, self.connections = [], [], []
        self.committed = dict(commands={}, drafts=[], origins=[])
        self.source, self.draft = source_record(), draft_record()
        self.source_lock, self.target_lock = fake_lock(), fake_lock()
        self.fail_insert = False

        def connect():
            conn = FakeConnection(self)
            self.connections.append(conn)
            return conn

        self.store = PostgresInstallationStore(connect_factory=connect)
        self.original_executor = self.store.execute_idempotent.__func__
        self.origin = FakeOrigin(self)
        composition = SimpleNamespace(get_lock=lambda **kwargs: self.target_lock)
        self.delegate = InstallationService(store=self.store, composition_store=composition,
                                            revalidator=object())
        self.service = ReinstallOriginService(store=self.store, installation_service=self.delegate,
                                               origin_store=self.origin)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(store_module, "apply_asset_transaction_scope",
            side_effect=lambda conn, **scope: self.trace.append("scope")))
        self.stack.enter_context(patch.object(store_module, "_load_record_by_pk",
            side_effect=lambda conn, **scope: self.source))

        def load(conn, *, composition_id, **scope):
            self.trace.append("source_lock" if composition_id == original.COMPOSITION_ID else "target_lock")
            return UUID(int=22), (self.source_lock if composition_id == original.COMPOSITION_ID
                                  else self.target_lock)

        self.stack.enter_context(patch.object(service_module, "load_stored_lock", side_effect=load))
        self.stack.enter_context(patch.object(reinstall_module, "load_stored_lock", side_effect=load))

        def create(conn, **values):
            self.trace.append("draft")
            self.assertEqual(values["org_id"], SCOPE["org_id"])
            self.assertEqual(values["project_id"], SCOPE["project_id"])
            conn.pending["drafts"].append(self.draft.installation_id)
            return self.draft

        self.stack.enter_context(patch.object(self.store, "create_draft_in_transaction", side_effect=create))

    def call(self, **changes):
        values = dict(installation_id=original.INSTALLATION_ID, request=payload(),
                      actor="requester", roles=["developer"], markings=[],
                      idempotency_key="synthetic-reinstall-1", if_match='"4"', **SCOPE)
        values.update(changes)
        return self.service.reinstall(**values)

    def assert_no_effect(self):
        self.assertEqual(self.committed, dict(commands={}, drafts=[], origins=[]))
        self.assertNotIn("commit", self.trace)

    def test_original_executor_cas_order_same_connection_and_exact_receipt(self):
        before = self.source.model_dump(mode="json", by_alias=True)
        receipt = self.call()
        self.assertIs(self.store.execute_idempotent.__func__, self.original_executor)
        self.assertEqual((receipt.status_code, receipt.response_etag, receipt.replayed), (201, '"1"', False))
        self.assertEqual(receipt.response_json["installationId"], NEW_ID)
        names = ["scope", "advisory", "source_head", "source_lock", "target_lock",
                 "current_authority", "cached_select", "draft", "origin", "command_insert", "commit"]
        self.assertEqual(sorted(names, key=self.trace.index), names)
        self.assertEqual(self.trace.count("commit"), 1)
        conn, checked = self.origin.checks[0]
        append_conn, appended = self.origin.appends[0]
        self.assertIs(conn, append_conn)
        self.assertIs(conn, self.connections[0])
        self.assertIs(checked["locked_source"], appended["locked_source"])
        self.assertIs(appended["target_record"], self.draft)
        self.assertIs(checked["source_lock"], self.source_lock)
        self.assertIs(checked["target_lock"], self.target_lock)
        self.assertEqual(self.source.model_dump(mode="json", by_alias=True), before)
        self.assertEqual(self.committed["drafts"], [NEW_ID])
        self.assertEqual(len(self.committed["origins"]), 1)
        self.assertNotEqual(NEW_ID, self.source.installation_id)

    def test_cached_receipt_checks_current_authority_before_select_without_second_append(self):
        first = self.call()
        self.trace.clear()
        second = self.call()
        self.assertTrue(second.replayed)
        self.assertEqual(first.response_json, second.response_json)
        self.assertLess(self.trace.index("current_authority"), self.trace.index("cached_select"))
        self.assertNotIn("draft", self.trace)
        self.assertNotIn("origin", self.trace)
        self.assertEqual(len(self.origin.checks), 2)
        self.assertEqual(len(self.origin.appends), 1)
        self.origin.verdict = False
        self.trace.clear()
        with self.assertRaises(PermissionError):
            self.call()
        self.assertNotIn("cached_select", self.trace)
        self.assertNotIn("commit", self.trace)

    def test_false_truthy_and_async_current_verdicts_are_not_authority(self):
        async def deferred():
            raise AssertionError("must never execute coroutine")
        for value in (False, 1, "yes", None, deferred()):
            with self.subTest(shape=type(value).__name__):
                self.trace.clear()
                self.origin.verdict = value
                with self.assertRaises((PermissionError, ValueError)):
                    self.call()
                self.assertNotIn("cached_select", self.trace)
                self.assert_no_effect()

    def test_input_shape_path_etag_role_key_and_tenant_reject_before_connect(self):
        invalid = [(dict(installation_id=NEW_ID), RevisionConflictError),
                   (dict(if_match='"3"'), RevisionConflictError),
                   (dict(if_match=None), PreconditionRequiredError),
                   (dict(if_match='W/"4"'), PreconditionInvalidError),
                   (dict(if_match='"9223372036854775808"'), PreconditionInvalidError),
                   (dict(roles=["viewer"]), DutySeparationRequiredError),
                   (dict(idempotency_key=None), IdempotencyKeyRequiredError),
                   (dict(org_id=""), ValueError), (dict(project_id=" padded "), ValueError),
                   (dict(request={**payload(), "actor": "untrusted"}), ValueError)]
        for changes, expected in invalid:
            with self.subTest(fields=tuple(changes)), self.assertRaises(expected):
                self.call(**changes)
        self.assertEqual(self.connections, [])
        self.assert_no_effect()

    def test_root_subclass_and_tampered_request_cannot_bypass_validation(self):
        calls = []

        class Hostile(ReinstallInstallationRequest):
            def model_dump(self, *args, **kwargs):
                calls.append("override")
                raise AssertionError("must not invoke hostile override")

        with self.assertRaises(ValueError):
            self.call(request=Hostile.model_validate(payload()))
        value = ReinstallInstallationRequest.model_validate(payload())
        object.__setattr__(value.source, "terminal_revision", -1)
        with self.assertRaises(ValueError):
            self.call(request=value)
        self.assertEqual(calls, [])
        self.assertEqual(self.connections, [])

    def test_terminal_and_exact_source_hash_requirements_precede_port(self):
        changed = payload()
        changed["source"]["lockHash"] = original.SHA_B
        with self.assertRaises(LockIntegrityCorruptError):
            self.call(request=changed)
        self.assertEqual(self.origin.checks, [])
        for field, invalid in (("installation_id", NEW_ID), ("current_revision", 9)):
            self.source = source_record()
            object.__setattr__(self.source, field, invalid)
            with self.subTest(field=field), self.assertRaises(LockIntegrityCorruptError):
                self.call()
        self.source = InstallationRecord.model_validate(original._approved_record_payload())
        changed = payload()
        changed["source"]["terminalRevision"] = 3
        with self.assertRaises(InstallationStateConflictError):
            self.call(request=changed, if_match='"3"')
        self.assertEqual(self.origin.checks, [])
        self.assert_no_effect()

    def test_missing_corrupt_or_wrong_terminal_evidence_is_not_reinstall_proof(self):
        for change in ("missing", "hash", "type"):
            with self.subTest(change=change):
                self.source = source_record()
                tail = self.source.events[-1]
                if change == "missing":
                    tail.evidence = None
                elif change == "hash":
                    tail.evidence.evidence_hash = original.SHA_D
                else:
                    object.__setattr__(tail.evidence, "type", "rollback")
                with self.assertRaises(LockIntegrityCorruptError):
                    self.call()
        self.assertEqual(self.origin.checks, [])
        self.assert_no_effect()

    def test_all_four_lock_hashes_and_both_marking_sides_precede_cached_receipt(self):
        for attr in ("lock_hash", "permission_diff_hash", "migration_plan_hash", "contribution_diff_hash"):
            with self.subTest(hash_field=attr):
                self.source_lock = fake_lock()
                setattr(self.source_lock, attr, "sha256:" + "e" * 64)
                with self.assertRaises(LockIntegrityCorruptError):
                    self.call()
        self.source_lock = fake_lock()
        for side in (self.source_lock, self.target_lock):
            side.payload.permission_diff.target.markings = frozenset({"private-marking"})
            with self.assertRaises(MarkingAccessDeniedError):
                self.call()
            side.payload.permission_diff.target.markings = frozenset()
        self.assertEqual(self.origin.checks, [])
        self.assertNotIn("cached_select", self.trace)
        self.assert_no_effect()

    def test_hash_identity_and_tenant_namespace_are_original(self):
        legacy_key = (SCOPE["org_id"], SCOPE["project_id"], "bundle_installations.create", "synthetic-reinstall-1")
        self.committed["commands"][legacy_key] = dict(legacy_sentinel="unchanged")
        self.call()
        key = (SCOPE["org_id"], SCOPE["project_id"], REINSTALL_INSTALLATION_OPERATION, "synthetic-reinstall-1")
        row = self.committed["commands"][key]
        self.assertEqual(row["request_hash"], command_request_hash(
            subject="requester", path_params={"installationId": original.INSTALLATION_ID},
            body=payload(), if_match='"4"'))
        changed = payload()
        changed["target"]["displayName"] = "Other request"
        for kwargs in (dict(request=changed), dict(actor="other-actor")):
            with self.subTest(fields=tuple(kwargs)), self.assertRaises(IdempotencyConflictError):
                self.call(**kwargs)
        with self.assertRaises(AssetNotFoundError):
            self.call(org_id="dev-org")
        self.assertEqual(len(self.committed["origins"]), 1)
        self.assertEqual(self.committed["commands"][legacy_key], dict(legacy_sentinel="unchanged"))

    def test_append_failure_and_non_none_return_roll_back_entire_original_command(self):
        async def deferred():
            raise AssertionError("must not execute append coroutine")
        def generated():
            yield "not an append"
        future = asyncio.Future(loop=SimpleNamespace(get_debug=lambda: False))
        for value in (True, {}, deferred(), generated(), future):
            with self.subTest(shape=type(value).__name__):
                self.trace.clear()
                self.origin.append_result = value
                with self.assertRaises(ValueError):
                    self.call()
                self.assertIn("rollback", self.trace)
                self.assert_no_effect()
        self.assertTrue(future.cancelled())
        self.origin.append_result = None
        self.origin.raise_append = True
        self.trace.clear()
        with self.assertRaises(RuntimeError):
            self.call()
        self.assert_no_effect()

    def test_command_insert_failure_and_invalid_draft_roll_back_origin(self):
        with patch.object(self.store, "create_draft_in_transaction", side_effect=RuntimeError("synthetic draft failure")):
            with self.assertRaises(RuntimeError):
                self.call()
        self.assert_no_effect()
        self.fail_insert = True
        with self.assertRaises(RuntimeError):
            self.call()
        self.assert_no_effect()
        self.fail_insert = False
        object.__setattr__(self.draft, "etag_version", 999)
        with self.assertRaises(LockIntegrityCorruptError):
            self.call()
        self.assert_no_effect()

    def test_postcommit_readback_failure_does_not_imply_zero_effect_or_resend(self):
        self.delegate._composition_store.get_lock = lambda **kwargs: (_ for _ in ()).throw(
            AssetNotFoundError("synthetic postcommit revocation"))
        with self.assertRaises(AssetNotFoundError):
            self.call()
        self.assertEqual(self.trace.count("commit"), 1)
        self.assertEqual(len(self.committed["commands"]), 1)
        self.assertEqual(len(self.committed["origins"]), 1)
        self.assertEqual(len(self.connections), 1)

    def test_constructor_requires_exact_original_graph_and_synchronous_port(self):
        def build(store=None, delegate=None, origin=None):
            return ReinstallOriginService(store=store if store is not None else self.store,
                installation_service=delegate if delegate is not None else self.delegate,
                origin_store=origin if origin is not None else self.origin)
        for name in ("check_current", "append_origin"):
            async def asynchronous(*args, **kwargs):
                return None
            def generator(*args, **kwargs):
                yield None
            async def async_generator(*args, **kwargs):
                yield None
            for value in (None, asynchronous, generator, async_generator):
                origin = SimpleNamespace(check_current=self.origin.check_current,
                                         append_origin=self.origin.append_origin)
                setattr(origin, name, value)
                with self.subTest(name=name), self.assertRaises(ValueError):
                    build(origin=origin)
        with self.assertRaises(TypeError):
            ReinstallOriginService()
        with self.assertRaises(ValueError):
            build(store=object())
        with self.assertRaises(ValueError):
            build(delegate=object())
        class StoreSubclass(PostgresInstallationStore):
            pass
        with self.assertRaises(ValueError):
            build(store=StoreSubclass(connect_factory=lambda: None))
        other_store = PostgresInstallationStore(connect_factory=lambda: None)
        with self.assertRaises(ValueError):
            build(store=other_store)
        self.assertEqual(self.connections, [])
        self.assertEqual(EFFECTS, [])


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ReinstallOriginServiceTests))
    print("EXTERNAL_OR_PRIVATE_ATTEMPTS", len(EFFECTS))
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun == 13
                     and not result.skipped and not EFFECTS else 1)
