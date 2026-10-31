"""Offline SQL-text contract only; PostgreSQL behavior requires separate tests."""
from pathlib import Path
import re
import unittest


SQL_PATH = (Path(__file__).resolve().parents[2] / "aos_api" /
            "extension_runtime_resource_origin_authority.sql")
IDENTITY = (
    "org_id", "project_id", "resource_id", "operation_id", "generation",
    "package_id", "package_hash", "engine_context", "resource_name", "owner_token_ref",
)
MUTABLE = ("create_claimed_at", "container_id", "cleanup_state", "observed_release", "expires_at")
FUNCTION = "public.extension_runtime_resource_origin_guard_v1"
TABLE = "public.extension_runtime_resource_lease"


class ResourceOriginSQLContractTest(unittest.TestCase):
    def setUp(self):
        # Deliberately no DB/driver/product-package imports or conftest execution.
        raw = SQL_PATH.read_text(encoding="utf-8")
        self.sql = re.sub(r"--[^\n]*", "", raw)
        self.flat = " ".join(self.sql.split())
        match = re.fullmatch(
            r"\s*CREATE FUNCTION " + re.escape(FUNCTION) +
            r"\(\)\s+RETURNS trigger\s+LANGUAGE plpgsql\s+SECURITY INVOKER\s+"
            r"SET search_path = pg_catalog, pg_temp\s+AS \$resource_origin\$(.*?)"
            r"\$resource_origin\$;(.*)\s*", self.sql, re.S,
        )
        self.assertIsNotNone(match, "fixed function envelope required")
        self.body, self.ddl = match.groups()
        self.body_flat = " ".join(self.body.split())

    def test_fixed_signature_invoker_and_search_path(self):
        self.assertEqual(self.sql.count("CREATE FUNCTION"), 1)
        self.assertNotIn("SECURITY DEFINER", self.sql)
        self.assertNotIn("OR REPLACE", self.sql)

    def test_exact_null_safe_identity_pair(self):
        rows = re.findall(r"ROW\s*\(([^()]*)\)", self.body, re.S)
        self.assertEqual(len(rows), 2)
        for prefix, row in zip(("OLD", "NEW"), rows):
            self.assertEqual([v.strip() for v in row.split(",")],
                             [prefix + "." + field for field in IDENTITY])
        self.assertRegex(self.body_flat, r"\) IS DISTINCT FROM ROW\(")
        self.assertEqual(self.body.count("IS DISTINCT FROM"), 1)

    def test_mutable_columns_not_frozen(self):
        for field in MUTABLE:
            with self.subTest(field=field):
                self.assertNotRegex(self.body, r"\b(?:OLD|NEW)\." + field + r"\b")

    def test_update_only_row_and_returns_new(self):
        self.assertIn("IF TG_OP = 'UPDATE' AND TG_LEVEL = 'ROW' THEN", self.body_flat)
        self.assertEqual(re.findall(r"RETURN\s+(\w+)\s*;", self.body), ["NEW"])
        self.assertIn("ERRCODE = '23514'", self.body)

    def test_wrong_table_timing_and_arguments_fail_closed(self):
        self.assertRegex(
            self.body_flat,
            r"^BEGIN IF TG_TABLE_SCHEMA <> 'public' OR TG_TABLE_NAME <> 'extension_runtime_resource_lease' "
            r"OR TG_WHEN <> 'BEFORE' OR TG_NARGS <> 0 THEN RAISE EXCEPTION",
        )
        for clause in ("TG_TABLE_SCHEMA <> 'public'", "TG_TABLE_NAME <> 'extension_runtime_resource_lease'",
                       "TG_WHEN <> 'BEFORE'", "TG_NARGS <> 0"):
            self.assertIn(clause, self.body_flat)
        guard = self.body_flat.split("IF TG_OP", 1)[0]
        self.assertIn("ERRCODE = '55000'", guard)
        self.assertNotIn("OLD.", guard)
        self.assertNotIn("NEW.", guard)

    def test_history_delete_and_truncate_are_rejected(self):
        self.assertIn("TG_OP = 'DELETE' AND TG_LEVEL = 'ROW'", self.body_flat)
        self.assertIn("TG_OP = 'TRUNCATE' AND TG_LEVEL = 'STATEMENT'", self.body_flat)
        # Both the recognized history mutation and unexpected context raise.
        self.assertEqual(self.body.count("ERRCODE = '55000'"), 3)
        self.assertNotIn("RETURN OLD", self.body)
        self.assertNotIn("RETURN NULL", self.body)

    def test_opaque_reference_only_in_comparison_and_no_value_errors(self):
        self.assertEqual(re.findall(r"(?:OLD|NEW)\.owner_token_ref", self.body),
                         ["OLD.owner_token_ref", "NEW.owner_token_ref"])
        raises = re.findall(r"RAISE EXCEPTION USING (.*?);", self.body, re.S)
        self.assertEqual(len(raises), 4)
        for item in raises:
            self.assertRegex(" ".join(item.split()),
                             r"^ERRCODE = '(?:23514|55000)', MESSAGE = '[a-z _]+'$")

    def test_function_has_no_queries_dml_dynamic_or_transaction_control(self):
        forbidden = r"\b(?:SELECT|INSERT|UPDATE|DELETE|TRUNCATE|EXECUTE|PERFORM|CALL|COMMIT|ROLLBACK)\b"
        # Event names are literals, not executable SQL statements.
        body_without_literals = re.sub(r"'[^']*'", "''", self.body)
        self.assertNotRegex(body_without_literals, forbidden)
        self.assertNotIn("||", self.body)
        self.assertNotRegex(self.body, r"\b(?:current_setting|set_config|dblink)\s*\(")

    def test_exact_installation_statements(self):
        statements = [" ".join(v.split()) for v in self.ddl.split(";") if v.strip()]
        self.assertEqual(statements, [
            f"REVOKE ALL ON FUNCTION {FUNCTION}() FROM PUBLIC",
            f"ALTER FUNCTION {FUNCTION}() OWNER TO aos_terminal_source_projection_owner",
            f"CREATE TRIGGER extension_runtime_resource_origin_row_v1 BEFORE UPDATE OR DELETE ON {TABLE} "
            f"FOR EACH ROW EXECUTE FUNCTION {FUNCTION}()",
            f"CREATE TRIGGER extension_runtime_resource_origin_truncate_v1 BEFORE TRUNCATE ON {TABLE} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION {FUNCTION}()",
        ])

    def test_no_installation_shortcuts_or_role_creation(self):
        for forbidden in (r"\bGRANT\b", r"\bCREATE ROLE\b", r"\bALTER ROLE\b", r"\bDROP\b",
                          r"\bIF NOT EXISTS\b", r"\bALTER TABLE\b", r"\bCOMMIT\b", r"\bROLLBACK\b"):
            self.assertNotRegex(self.sql, forbidden)


if __name__ == "__main__":
    unittest.main(verbosity=2)
