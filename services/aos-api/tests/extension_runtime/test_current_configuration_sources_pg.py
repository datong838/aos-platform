"""Collect the reusable current AIP source authority checks."""

from current_configuration_sources_case import *  # noqa: F403


@pytest.mark.xfail(strict=True, raises=psycopg.errors.InsufficientPrivilege,
                   reason='read-only runtime cannot take original Plan FOR SHARE lock')
def test_current_responsibility_plan_readonly_runtime_retains_stable_version(source_case):
    from aos_api.aip_runtime_configuration_sources import read_current_responsibility_plan_ref
    conn, refs = source_case
    conn.execute('RESET ROLE')
    conn.execute('REVOKE UPDATE ON aip_responsibility_plan_head FROM aos_runtime')
    conn.execute('SET ROLE aos_runtime')
    with conn.transaction():
        assert read_current_responsibility_plan_ref(conn, org_id='org-org',
            project_id='dev-project', purpose='role', ref=refs['role']) is True
