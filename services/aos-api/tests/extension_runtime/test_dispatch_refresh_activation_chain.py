"""Offline migration contract; no PostgreSQL, authority or lifecycle acceptance."""
import ast
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

VERSIONS = Path(__file__).resolve().parents[2] / "alembic/versions"
MIGRATION = VERSIONS / "a0v_166_dispatch_refresh_activation_chain.py"
OLD_KEY = ["org_id", "project_id", "cutover_group_id", "revision"]
NEW_KEY = ["org_id", "project_id", "cutover_group_id", "activation_operation_id", "revision"]


def original_sql():
    tree = ast.parse((VERSIONS / "a0v_069_dispatch_configuration_refresh_scope.py").read_text())
    upgrade = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    return ast.literal_eval(upgrade.body[0].value.args[0])


@pytest.fixture
def migration():
    assert MIGRATION.is_file(), "activation-scoped refresh forward migration is missing"
    spec = importlib.util.spec_from_file_location("refresh_activation_candidate", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Result:
    def __init__(self, row): self.row = row
    def mappings(self): return self
    def one(self): return deepcopy(self.row)


class Connection:
    dialect = SimpleNamespace(name="postgresql")
    def __init__(self, module):
        self.module = module; self.calls = []; self.transaction = True
        self.connection = SimpleNamespace(driver_connection=SimpleNamespace(autocommit=False))
        self.options = {}
        self.key = {"pk_name": "refresh_pkey", "pk_columns": OLD_KEY, "incoming_pk_fks": False}
        self.seal = {"value": {"rls": True, "force_rls": True, "constraints": ["original"], "acl": "original"},
                     "guard_body": ""}
        tree = ast.parse((VERSIONS / "a0v_067_dispatch_configuration_refresh.py").read_text())
        upgrade = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="upgrade")
        sql = ast.literal_eval(upgrade.body[0].value.args[0])
        self.seal["guard_body"] = sql.split("AS $$",1)[1].split("$$",1)[0]
        self.writer = {"body": original_sql().split("AS $$",1)[1].split("$$",1)[0],
                       "shape": {"owner": 10, "acl": "original", "security_definer": True,
                                 "config": ["search_path=pg_catalog, public, pg_temp"]}, "acl_valid": True}
        self.drift_after = False
    def in_transaction(self): return self.transaction
    def get_execution_options(self): return self.options
    def exec_driver_sql(self, sql):
        self.calls.append(sql)
        if sql == self.module.KEY_SQL: return Result(self.key)
        if sql == self.module.SEAL_SQL:
            row=deepcopy(self.seal)
            if self.drift_after and any("ADD PRIMARY KEY" in c for c in self.calls): row["value"]["acl"]="drifted"
            return Result(row)
        if sql == self.module.WRITER_SQL: return Result(self.writer)
        if "ADD PRIMARY KEY" in sql: self.key={**self.key,"pk_columns": NEW_KEY}
        if sql.startswith("CREATE OR REPLACE FUNCTION"):
            self.writer["body"]=sql.split("AS $$",1)[1].split("$$",1)[0]
        return Result({})


def attach(module, connection):
    module.op = SimpleNamespace(get_bind=lambda: connection)


def test_forward_branch_and_old_function_exact_delta(migration):
    assert migration.revision=="a0v_166" and migration.down_revision=="a0v_165"
    sql=original_sql();expected=sql[sql.index("CREATE OR REPLACE FUNCTION"):sql.index("END $$;")+len("END $$;")]
    expected=expected.replace("AND newer.revision>v_existing.revision", "AND newer.activation_operation_id=v_existing.activation_operation_id\n              AND newer.revision>v_existing.revision")
    anchor="WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group\n        ORDER BY revision DESC LIMIT 1 FOR UPDATE;"
    expected=expected.replace(anchor,"WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group\n          AND activation_operation_id=v_root.cutover_operation_id\n          AND installation_id=v_installation_id AND generation=v_generation\n        ORDER BY revision DESC LIMIT 1 FOR UPDATE;")
    assert migration.REFRESH_SQL==expected
    assert "AND idempotency_key=p_request->>'idempotencyKey'" in migration.REFRESH_SQL
    assert "operation_id=ANY(v_operations)" in migration.REFRESH_SQL
    assert "GRANT " not in migration.REFRESH_SQL and "REVOKE " not in migration.REFRESH_SQL


def test_upgrade_preserves_original_history_and_changes_only_key_and_writer(migration):
    c=Connection(migration);attach(migration,c);migration.upgrade()
    assert c.key["pk_columns"]==NEW_KEY
    mutations=[s for s in c.calls if s not in (migration.KEY_SQL,migration.SEAL_SQL,migration.WRITER_SQL)]
    assert mutations[0]=="LOCK TABLE public.extension_dispatch_configuration_refresh_receipt IN ACCESS EXCLUSIVE MODE"
    assert len(mutations)==4
    assert "DROP CONSTRAINT" in mutations[1] and "CASCADE" not in mutations[1]
    assert "ADD PRIMARY KEY (org_id,project_id,cutover_group_id,activation_operation_id,revision)" in mutations[2]
    assert mutations[3]==migration.REFRESH_SQL
    assert not any(s.lstrip().startswith(("DELETE ","UPDATE ","TRUNCATE ","INSERT ","GRANT ","REVOKE ")) for s in mutations)


@pytest.mark.parametrize("defect",["key","fk","body","acl","guard","rls","force_rls","security","search_path","transaction","dialect","driver-autocommit","option-autocommit"])
def test_drift_refuses_before_any_mutation(migration,defect):
    c=Connection(migration)
    if defect=="key":c.key["pk_columns"]=["receipt_id"]
    elif defect=="fk":c.key["incoming_pk_fks"]=True
    elif defect=="body":c.writer["body"]+="--changed"
    elif defect=="acl":c.writer["acl_valid"]=False
    elif defect=="guard":c.seal["guard_body"]+="--changed"
    elif defect in ("rls","force_rls"):c.seal["value"][defect]=False
    elif defect=="security":c.writer["shape"]["security_definer"]=False
    elif defect=="search_path":c.writer["shape"]["config"]=["search_path=unsafe"]
    elif defect=="transaction":c.transaction=False
    elif defect=="driver-autocommit":c.connection.driver_connection.autocommit=True
    elif defect=="option-autocommit":c.options={"isolation_level":"AUTOCOMMIT"}
    elif defect=="dialect":c.dialect=SimpleNamespace(name="sqlite")
    attach(migration,c)
    with pytest.raises(RuntimeError):migration.upgrade()
    assert not any("DROP CONSTRAINT" in s or "ADD PRIMARY KEY" in s or s==migration.REFRESH_SQL for s in c.calls)


def test_postcondition_drift_raises_for_outer_transaction_rollback(migration):
    c=Connection(migration);c.drift_after=True;attach(migration,c)
    with pytest.raises(RuntimeError):migration.upgrade()
    assert any("ADD PRIMARY KEY" in s for s in c.calls)


def test_constraint_name_is_quoted_without_cascade(migration):
    c=Connection(migration);c.key["pk_name"]='quoted"name';attach(migration,c);migration.upgrade()
    assert any('DROP CONSTRAINT "quoted""name"' in s for s in c.calls)


def test_no_downgrade_can_remove_historical_refresh_chains(migration):
    with pytest.raises(RuntimeError):migration.downgrade()


def test_postgresql_parser_accepts_catalog_queries_key_change_and_original_body(migration):
    from pglast import parse_sql, parse_plpgsql
    for query in (migration.KEY_SQL,migration.SEAL_SQL,migration.WRITER_SQL,
                  'ALTER TABLE public.extension_dispatch_configuration_refresh_receipt ADD PRIMARY KEY (org_id,project_id,cutover_group_id,activation_operation_id,revision)',
                  migration.REFRESH_SQL):
        assert parse_sql(query)
    assert parse_plpgsql(migration.REFRESH_SQL)
