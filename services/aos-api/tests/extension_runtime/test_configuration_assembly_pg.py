"""Current-source assembly against isolated original AIP authorities."""
import pytest

from current_configuration_sources_case import source_case, _install_dependency_revision
from test_lifecycle_pg import database, pytestmark
from aos_api.aip_runtime_configuration_sources import assemble_current_configuration


def assemble(conn, refs, **changes):
    arguments = dict(org_id="org-org", project_id="dev-project",
                     policy_ref=refs["policy"], role_refs=(refs["role"],))
    arguments.update(changes)
    return assemble_current_configuration(conn, **arguments)


def test_assembly_derives_exact_data_and_budget_from_current_policy(source_case):
    conn, refs = source_case
    with conn.transaction():
        assert assemble(conn, refs) == refs["configuration"]


@pytest.mark.parametrize("case", ("empty", "duplicate", "list", "scope", "privileged", "hash", "authority"))
def test_assembly_rejects_invalid_selection_or_identity(source_case, case):
    conn, refs = source_case
    changes = {}
    if case == "empty": changes["role_refs"] = ()
    if case == "duplicate": changes["role_refs"] = (refs["role"], refs["role"])
    if case == "list": changes["role_refs"] = [refs["role"]]
    if case == "scope": changes["org_id"] = "dev-org"
    if case == "privileged": conn.execute("RESET ROLE")
    if case == "hash": changes["policy_ref"] = refs["policy"].model_copy(update={"hash": "sha256:" + "f" * 64})
    if case == "authority": changes["role_refs"] = (refs["data"],)
    with conn.transaction(), pytest.raises((ValueError, PermissionError)):
        assemble(conn, refs, **changes)


@pytest.mark.parametrize("table", (
    "aip_responsibility_plan_head", "aip_runtime_policy_head", "aip_network_policy_head",
    "aip_runtime_guard_policy_head", "aip_model_governance_policy_head", "aip_budget_head",
))
def test_assembly_rejects_changed_authority_heads(source_case, table):
    conn, refs = source_case
    from psycopg import sql
    with conn.transaction():
        conn.execute("RESET ROLE")
        conn.execute(sql.SQL("UPDATE {} SET current_revision=2").format(sql.Identifier(table)))
        conn.execute("SET ROLE aos_runtime")
        with pytest.raises((ValueError, LookupError, PermissionError)):
            assemble(conn, refs)


@pytest.mark.parametrize("key", ("network", "egress", "data", "quota", "budget_policy"))
@pytest.mark.parametrize("mode", ("inactive", "expired", "payload"))
def test_assembly_rejects_unusable_dependencies_even_with_matching_new_policy(source_case, key, mode):
    conn, refs = source_case
    with conn.transaction():
        conn.execute("RESET ROLE")
        policy_ref, _ = _install_dependency_revision(conn, refs, key, mode)
        conn.execute("SET ROLE aos_runtime")
        with pytest.raises((ValueError, LookupError, PermissionError)):
            assemble(conn, refs, policy_ref=policy_ref)
