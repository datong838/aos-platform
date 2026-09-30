"""Read-only HBA gate against the isolated BG00ck PostgreSQL clone."""

import json
import os
import subprocess

import pytest

from scripts.a0v_network_issuer_hba_gate import IssuerHbaBlocked, assess_hba_rows


def test_exact_scram_first_match_covers_socket_and_both_loopbacks() -> None:
    database = "aos_current_preview_20260927"
    rows = [
        {"line_number": n, "type": kind, "database": [database],
         "user_name": ["aos_network_approval_issuer"], "address": address,
         "netmask": mask, "auth_method": "scram-sha-256", "error": None}
        for n, kind, address, mask in (
            (1, "local", None, None),
            (2, "host", "127.0.0.1", "255.255.255.255"),
            (3, "host", "::1", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"),
        )
    ]
    rows.append({"line_number": 4, "type": "host", "database": ["all"],
                 "user_name": ["all"], "address": "all", "netmask": None,
                 "auth_method": "trust", "error": None})
    assess_hba_rows(rows, database=database)
    with pytest.raises(IssuerHbaBlocked, match="ISSUER_HBA_UNSAFE"):
        assess_hba_rows([{**rows[-1], "line_number": 0}, *rows[:3]], database=database)


def test_isolated_clone_rejects_local_trust_before_issuer_login() -> None:
    if os.environ.get("AOS_BG00CL_TEST_CONTAINER") != "aos-bg00ck-isolated-pg":
        pytest.skip("explicit BG00ck isolated container required")
    result = subprocess.run(
        ["docker", "--context", "colima-aos-a0v-test-only", "exec",
         "aos-bg00ck-isolated-pg", "psql", "-X", "-v", "ON_ERROR_STOP=1",
         "-U", "postgres", "-d", "aos_current_preview_20260927", "-Atc",
         "SELECT coalesce(json_agg(row_to_json(h) ORDER BY line_number),'[]'::json) "
         "FROM (SELECT line_number,type,database,user_name,address,netmask,"
         "auth_method,error FROM pg_hba_file_rules) h"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    with pytest.raises(IssuerHbaBlocked, match="ISSUER_HBA_UNSAFE"):
        assess_hba_rows(json.loads(result.stdout), database="aos_current_preview_20260927")
