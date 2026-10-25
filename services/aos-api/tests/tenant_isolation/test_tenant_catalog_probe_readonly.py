"""Stdlib-only tests of original probe and legacy schema AST functions."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest


PRODUCT = Path(__file__).resolve().parents[2] / "aos_api" / "tenant_catalog.py"


def original_functions():
    tree = ast.parse(PRODUCT.read_bytes(), filename=str(PRODUCT))
    names = {"_catalog_tables_present", "ensure_tenant_catalog_schema"}
    functions = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in functions} == names
    tables = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "_CATALOG_TABLES"
                          for target in node.targets))
    return functions, ast.literal_eval(tables)


class ProbeReadonlyTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.count = 3
        self.failure = None
        events = self.events
        owner = self

        class Connection:
            def execute(self, sql, params=None):
                events.append(("execute", sql, params))
                if owner.failure == "execute":
                    raise RuntimeError("synthetic execute failure")
                return self

            def fetchone(self):
                events.append(("fetchone",))
                if owner.failure == "fetchone":
                    raise RuntimeError("synthetic fetch failure")
                return {"n": owner.count}

            def commit(self):
                events.append(("commit",))

        @contextmanager
        def readonly(**kwargs):
            events.append(("readonly", kwargs))
            self.assertEqual(kwargs, {"inherit_scope": False, "platform_role": True})
            if owner.failure == "connect":
                raise RuntimeError("synthetic connection failure")
            yield Connection()

        @contextmanager
        def legacy_write(**kwargs):
            events.append(("legacy_write", kwargs))
            self.assertEqual(kwargs, {"inherit_scope": False})
            yield Connection()

        def forbidden_platform():
            events.append(("forbidden_platform",))
            raise AssertionError("probe must never open a read-write platform connection")

        self.ns = {
            "connect_read_only": readonly,
            "connect_platform": forbidden_platform,
            "connect": legacy_write,
            "persistence_enabled": lambda: True,
            "_schema_ready": False,
            "log": SimpleNamespace(debug=lambda *a, **k: None, info=lambda *a, **k: None),
        }
        functions, tables = original_functions()
        self.ns["_CATALOG_TABLES"] = tables
        # Compile original AST nodes unchanged: no substitution of call sites.
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(PRODUCT), "exec"), self.ns)

    def probe(self):
        return self.ns["_catalog_tables_present"]()

    def assert_readonly_connection(self):
        self.assertEqual([e for e in self.events if e[0] == "readonly"],
                         [("readonly", {"inherit_scope": False, "platform_role": True})])
        self.assertFalse(any(e[0] == "forbidden_platform" for e in self.events))

    def test_existing_three_tables_selects_in_readonly_transaction(self):
        self.assertIs(self.probe(), True)
        self.assert_readonly_connection()
        calls = [e for e in self.events if e[0] == "execute"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(" ".join(calls[0][1].split()),
                         "SELECT count(*) AS n FROM pg_class WHERE relkind = 'r' AND relname = ANY(%s)")
        self.assertEqual(calls[0][2], (["meta_org", "meta_workspace", "meta_membership"],))
        self.assertFalse(any(e[0] in {"commit", "legacy_write"} for e in self.events))

    def test_original_count_comparison_is_preserved(self):
        for count in (0, 1, 2, 4):
            with self.subTest(count=count):
                self.events.clear()
                self.count = count
                self.assertIs(self.probe(), False)
                self.assert_readonly_connection()

    def test_connection_failure_is_closed(self):
        self.failure = "connect"
        self.assertIs(self.probe(), False)
        self.assert_readonly_connection()
        self.assertFalse(any(e[0] == "execute" for e in self.events))

    def test_execute_failure_is_closed(self):
        self.failure = "execute"
        self.assertIs(self.probe(), False)
        self.assert_readonly_connection()
        self.assertTrue(any(e[0] == "execute" for e in self.events))

    def test_fetch_failure_is_closed(self):
        self.failure = "fetchone"
        self.assertIs(self.probe(), False)
        self.assert_readonly_connection()
        self.assertTrue(any(e[0] == "fetchone" for e in self.events))

    def test_legacy_existing_schema_avoids_ddl(self):
        self.ns["ensure_tenant_catalog_schema"]()
        self.assertIs(self.ns["_schema_ready"], True)
        self.assert_readonly_connection()
        self.assertFalse(any(e[0] in {"legacy_write", "commit"} for e in self.events))

    def test_legacy_missing_schema_keeps_separate_original_write_transaction(self):
        self.count = 0
        self.ns["ensure_tenant_catalog_schema"]()
        self.assertIs(self.ns["_schema_ready"], True)
        self.assert_readonly_connection()
        writes = [e for e in self.events if e[0] == "legacy_write"]
        self.assertEqual(writes, [("legacy_write", {"inherit_scope": False})])
        ddl = [e[1] for e in self.events if e[0] == "execute" and e[1].strip().startswith("CREATE")]
        self.assertEqual(len(ddl), 3)
        for table, statement in zip(("meta_org", "meta_workspace", "meta_membership"), ddl):
            self.assertIn("CREATE TABLE IF NOT EXISTS " + table, statement)
        self.assertEqual(self.events[-1], ("commit",))

    def test_memory_schema_mode_never_connects(self):
        self.ns["persistence_enabled"] = lambda: False
        self.ns["ensure_tenant_catalog_schema"]()
        self.assertEqual(self.events, [])
        self.assertIs(self.ns["_schema_ready"], False)

    def test_cached_schema_never_connects(self):
        self.ns["_schema_ready"] = True
        self.ns["ensure_tenant_catalog_schema"]()
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
