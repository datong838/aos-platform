"""SOURCE-only append tests; fake SQL is not native persistence evidence."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import UUID

from aos_api.asset_registry import reinstall_origin_store as subject
from aos_api.asset_registry.installation_store import LockedInstallation
from aos_api.asset_registry.reinstall_contracts import ReinstallSourceRef

spec = importlib.util.spec_from_file_location(
    "_origin_service_pure_fixtures", Path(__file__).with_name("test_reinstall_origin_service.py"))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []
        self.failure = None

    def execute(self, sql, params):
        self.calls.append((sql, params))
        if self.failure:
            raise self.failure
        return self

    def fetchall(self):
        return self.rows


class OriginAppendTests(unittest.TestCase):
    def setUp(self):
        self.source = fixtures.source_record()
        self.target = fixtures.draft_record()
        self.ref = ReinstallSourceRef.model_validate(fixtures.payload()["source"])
        self.locked = LockedInstallation(**fixtures.SCOPE, installation_pk=UUID(int=21), record=self.source)
        self.args = dict(**fixtures.SCOPE, actor="requester", source=self.ref,
                         locked_source=self.locked, target_record=self.target)
        self.row = dict(**fixtures.SCOPE, target_installation_pk=UUID(int=22), target_revision=1,
                        source_installation_pk=UUID(int=21), source_terminal_revision=4,
                        source_lock_hash=self.ref.lock_hash, target_lock_hash=self.target.current.lock_hash,
                        actor="requester", source_installation_id=self.source.installation_id,
                        target_installation_id=self.target.installation_id)
        self.conn = Connection([self.row])
        self.guard = self.enterContext(patch.object(subject, "require_runtime_role"))
        self.store = subject.PostgresReinstallOriginAppender()

    def test_fixed_insert_same_connection_and_no_transaction_end(self):
        self.assertIsNone(self.store.append_origin(self.conn, **self.args))
        self.assertEqual(len(self.conn.calls), 1)
        sql, params = self.conn.calls[0]
        self.assertIn("INSERT INTO public.bundle_installation_reinstall_origin", sql)
        self.assertNotIn("ON CONFLICT", sql)
        self.assertEqual(params["org_id"], "org-org")
        self.assertEqual(params["project_id"], "dev-project")
        self.assertEqual(params["source_pk"], self.locked.installation_pk)
        self.assertEqual(params["source_id"], UUID(self.source.installation_id))
        self.assertEqual(params["target_id"], UUID(self.target.installation_id))
        for predicate in ("s.etag_version = %(source_revision)s", "sr.state = 'uninstalled'",
                          "sr.lock_hash = %(source_hash)s", "t.current_revision = 1",
                          "t.etag_version = 1", "tr.state = 'draft'",
                          "t.created_by = %(actor)s", "tr.requested_by = %(actor)s"):
            self.assertIn(predicate, sql)
        self.guard.assert_called_once()
        self.assertIs(self.guard.call_args.args[0], self.conn)
        self.assertEqual(self.guard.call_args.kwargs["protected_tables"], (
            "public.bundle_installation", "public.bundle_installation_revision",
            "public.bundle_installation_reinstall_origin"))

    def test_wrong_inputs_never_insert(self):
        changes = [dict(org_id="dev-org"), dict(actor="other"), dict(actor=" requester"),
                   dict(source=self.ref.model_copy(update={"terminal_revision": True})),
                   dict(source=self.ref.model_copy(update={"lock_hash": "wrong"})),
                   dict(source=self.ref.model_copy(update={"terminal_revision": 3})),
                   dict(source=self.ref.model_dump()), dict(target_record=self.source),
                   dict(locked_source=SimpleNamespace(**self.locked.__dict__))
                   if hasattr(self.locked, "__dict__") else dict(locked_source=object()),
                   dict(locked_source=LockedInstallation(**fixtures.SCOPE, installation_pk="bad", record=self.source))]
        for change in changes:
            with self.subTest(change=list(change)):
                with self.assertRaises((ValueError, TypeError)):
                    self.store.append_origin(self.conn, **(self.args | change))
                self.assertEqual(self.conn.calls, [])

    def test_mutated_record_revalidated(self):
        target = deepcopy(self.target)
        object.__setattr__(target.current, "requested_by", "wrong")
        with self.assertRaises(ValueError):
            self.store.append_origin(self.conn, **(self.args | dict(target_record=target)))
        self.assertEqual(self.conn.calls, [])

    def test_model_construct_and_self_origin_rejected(self):
        bad = ReinstallSourceRef.model_construct(installation_id=self.ref.installation_id,
                    terminal_revision=0, lock_hash=self.ref.lock_hash)
        with self.assertRaises(ValueError):
            self.store.append_origin(self.conn, **(self.args | dict(source=bad)))
        target = self.target.model_dump(by_alias=True)
        target["installationId"] = self.source.installation_id
        target["current"]["installationId"] = self.source.installation_id
        target = fixtures.InstallationRecord.model_validate(target)
        with self.assertRaises(ValueError):
            self.store.append_origin(self.conn, **(self.args | dict(target_record=target)))
        self.assertEqual(self.conn.calls, [])

    def test_nonterminal_or_changed_source_rejected(self):
        for record in (self.target, self.source.model_copy(update={"etag_version": 3})):
            with self.subTest(state=record.state):
                locked = LockedInstallation(**fixtures.SCOPE, installation_pk=UUID(int=21), record=record)
                with self.assertRaises(ValueError):
                    self.store.append_origin(self.conn, **(self.args | dict(locked_source=locked)))
        self.assertEqual(self.conn.calls, [])

    def test_trusted_subclass_rejected(self):
        class Child(ReinstallSourceRef):
            pass
        child = Child.model_validate(self.ref.model_dump(by_alias=True))
        with self.assertRaises(TypeError):
            self.store.append_origin(self.conn, **(self.args | dict(source=child)))
        self.assertEqual(self.conn.calls, [])

    def test_role_or_transaction_failure_propagates_before_insert(self):
        self.guard.side_effect = RuntimeError("synthetic guard failure")
        with self.assertRaises(RuntimeError):
            self.store.append_origin(self.conn, **self.args)
        self.assertEqual(self.conn.calls, [])

    def test_complete_readback_exactly_one_row(self):
        wrong = [[], [self.row, self.row], [None], [self.row | dict(extra=True)]]
        for key, value in self.row.items():
            wrong.append([self.row | {key: None}])
            wrong.append([{k: v for k, v in self.row.items() if k != key}])
        wrong += [[self.row | dict(target_installation_pk=UUID(int=21))],
                  [self.row | dict(target_revision=True)],
                  [self.row | dict(source_terminal_revision=True)]]
        for rows in wrong:
            with self.subTest(rows=len(rows)):
                self.conn.rows = rows
                with self.assertRaises(ValueError):
                    self.store.append_origin(self.conn, **self.args)

    def test_database_failure_not_retried(self):
        error = RuntimeError("synthetic duplicate origin")
        self.conn.failure = error
        with self.assertRaises(RuntimeError) as caught:
            self.store.append_origin(self.conn, **self.args)
        self.assertIs(caught.exception, error)
        self.assertEqual(len(self.conn.calls), 1)

    def test_appender_cannot_satisfy_mandatory_current_checker(self):
        self.assertFalse(hasattr(self.store, "check_current"))
        store = fixtures.PostgresInstallationStore(connect_factory=lambda: None)
        delegate = fixtures.InstallationService(store=store, composition_store=object(), revalidator=object())
        with self.assertRaisesRegex(ValueError, "synchronous trusted origin"):
            fixtures.ReinstallOriginService(store=store, installation_service=delegate, origin_store=self.store)
