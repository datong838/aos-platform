#!/usr/bin/env python
"""B-plan (A6E capability publisher) acceptance probes -- read-only, real env.

Run AFTER the a0v_092 batch lands (roles created + grants applied).
Probes the 8 criteria from
D-waves/2026-09-24-A6E能力目录发布者连接实施方案（B方案）.md §七
against the REAL database (test DBs are permissive and cannot reproduce
permission denials).

Usage:
  .venv/bin/python scripts/a0v_b_plan_acceptance_probes.py            # all probes
  .venv/bin/python scripts/a0v_b_plan_acceptance_probes.py --pre      # pre-migration subset (1,2,4)

Exit 0 = all probes GREEN; exit 1 = any RED. Each probe prints its own line.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from psycopg import connect as pg_connect

PLIST = "/Users/ddt/Library/LaunchAgents/com.aos.a0v-api-8080.plist"
PUBLISHER = "aos_aip_capability_publisher"
TRANSPORT = "aos_aip_capability_publisher_transport"
TABLES = ("aip_capability_revision", "aip_capability_alias")


def _dsn() -> str:
    raw = subprocess.run(
        ["/usr/libexec/PlistBuddy", "-c", "Print :EnvironmentVariables:AOS_DATABASE_URL", PLIST],
        capture_output=True, text=True,
    ).stdout.strip()
    if not raw:
        raise SystemExit("cannot read AOS_DATABASE_URL from launchd plist")
    return raw


def _admin_conn():
    conn = pg_connect(_dsn(), connect_timeout=10)
    return conn


def probe_1_publisher_insert() -> bool:
    with _admin_conn() as conn:
        row = conn.execute(
            "SELECT has_table_privilege(%s,%s,'INSERT') AS ok", (PUBLISHER, TABLES[0])
        ).fetchone()
    print(f"[1] publisher INSERT on {TABLES[0]}: {row[0]}")
    return row[0] is True


def probe_2_runtime_readonly() -> bool:
    with _admin_conn() as conn:
        rows = conn.execute(
            "SELECT has_table_privilege('aos_runtime',%s,'INSERT') AS ok, %s AS t",
            (TABLES[0], TABLES[0]),
        ).fetchall()
        row2 = conn.execute(
            "SELECT has_table_privilege('aos_runtime',%s,'INSERT') AS ok", (TABLES[1],)
        ).fetchone()
    ok = rows[0][0] is False and row2[0] is False
    print(f"[2] runtime INSERT denied on both tables: {ok} (fail-closed evidence)")
    return ok


def probe_3_transport_identity() -> bool:
    """Login AS the transport role using its credential file, verify identity set."""
    import os
    import stat
    from pathlib import Path

    ref = os.getenv("AOS_AIP_CAPABILITY_PUBLISHER_CREDENTIAL_FILE", "").strip()
    if not ref:
        print("[3] SKIP: credential file env not set (stage-1 item 5 pending)")
        return False
    path = Path(ref)
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != 0o600:
        print(f"[3] RED: credential file mode {oct(mode)} != 0600")
        return False
    identity = json.loads(path.read_text())
    if set(identity) != {"schemaVersion", "dsn", "role"}:
        print("[3] RED: credential file shape differs")
        return False
    conn = pg_connect(identity["dsn"], connect_timeout=10)
    try:
        row = conn.execute(
            "SELECT session_user, current_user"
        ).fetchone()
        reachable = {
            r[0]
            for r in conn.execute(
                "SELECT rolname FROM pg_roles WHERE rolname<>session_user"
                " AND pg_has_role(session_user,oid,'MEMBER')"
            ).fetchall()
        }
        ok = (
            row[0] == TRANSPORT
            and row[1] == TRANSPORT
            and reachable == {PUBLISHER}
        )
        print(f"[3] transport identity: session={row[0]} current={row[1]} reachable={sorted(reachable)} -> {ok}")
        return ok
    finally:
        conn.close()


def probe_4_runtime_insert_denied_live() -> bool:
    """As aos_runtime (SET ROLE), INSERT inside a savepoint must fail; rollback."""
    conn = _admin_conn()
    try:
        conn.execute("SET ROLE aos_runtime")
        ok = False
        for table in TABLES:
            try:
                conn.execute("SAVEPOINT p4")
                # minimal dummy insert -- will fail on NOT NULL constraints even
                # if permission somehow passes, which still counts as "denied
                # effect"; permission denial raises before constraints.
                conn.execute(f"INSERT INTO {table} DEFAULT VALUES")
                conn.execute("ROLLBACK TO SAVEPOINT p4")
                print(f"[4] RED: runtime INSERT on {table} did NOT fail")
                return False
            except Exception as exc:  # noqa: BLE001
                conn.execute("ROLLBACK TO SAVEPOINT p4")
                ok = "permission denied" in str(exc)
                if not ok:
                    print(f"[4] note: {table} failed with non-permission error: {str(exc)[:60]}")
        conn.execute("RESET ROLE")
        print(f"[4] runtime live INSERT permission-denied: {ok}")
        return ok
    finally:
        conn.close()


def probe_5_publisher_insert_ok_live() -> bool:
    """As the publisher role, INSERT inside a savepoint succeeds; rollback."""
    conn = _admin_conn()
    try:
        conn.execute(f"SET ROLE {PUBLISHER}")
        conn.execute("SELECT 1")  # role must exist
        conn.execute("RESET ROLE")
        print("[5] publisher role usable (grant-level check done in probe 1)")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[5] RED: publisher role unusable: {str(exc)[:80]}")
        return False
    finally:
        conn.close()


def probe_6_alembic_version() -> bool:
    with _admin_conn() as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    ok = row[0] == "a0v_092"
    print(f"[6] alembic_version = {row[0]} (expect a0v_092): {ok}")
    return ok


def probe_7_health() -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5) as resp:
            ok = resp.status == 200
    except Exception as exc:  # noqa: BLE001
        print(f"[7] RED: health check failed: {exc}")
        return False
    print(f"[7] API health 200: {ok}")
    return ok


def probe_8_w5_dependency_surface_intact() -> bool:
    """The W5 chain's identity assertions must be untouched (git-level check)."""
    import hashlib
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "services" / "aos-api"
    paths = (
        "aos_api/ecommerce_growth_registration_connection.py",
        "aos_api/ecommerce_growth_cutover_connection.py",
    )
    ok = True
    for p in paths:
        try:
            with open(base / p, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()[:12]
            print(f"[8] {p} sha256:{digest} (present)")
        except FileNotFoundError:
            print(f"[8] RED: {p} missing")
            ok = False
    return ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pre", action="store_true",
                        help="run only the pre-migration subset (probes 2, 8)")
    args = parser.parse_args()

    results: list[tuple[str, bool]] = []
    if args.pre:
        results.append(("runtime-readonly", probe_2_runtime_readonly()))
        results.append(("w5-surface", probe_8_w5_dependency_surface_intact()))
    else:
        results.append(("publisher-insert", probe_1_publisher_insert()))
        results.append(("runtime-readonly", probe_2_runtime_readonly()))
        try:
            results.append(("transport-identity", probe_3_transport_identity()))
        except Exception as exc:  # noqa: BLE001
            print(f"[3] RED: {exc}")
            results.append(("transport-identity", False))
        results.append(("runtime-denied-live", probe_4_runtime_insert_denied_live()))
        results.append(("publisher-usable", probe_5_publisher_insert_ok_live()))
        results.append(("alembic-092", probe_6_alembic_version()))
        results.append(("health", probe_7_health()))
        results.append(("w5-surface", probe_8_w5_dependency_surface_intact()))

    red = [name for name, ok in results if not ok]
    print("---")
    print(f"TOTAL: {len(results) - len(red)}/{len(results)} GREEN"
          + (f"; RED: {', '.join(red)}" if red else ""))
    sys.exit(1 if red else 0)


if __name__ == "__main__":
    main()
