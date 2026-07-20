"""181m — TWA tenant catalog persistence (org/workspace/member/invite/person).

Write-through: in-memory APIs remain; when mode=pg, mutations also hit PG and
startup hydrates memory from PG (or dumps seeds if empty).
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.twa-pg")

_MODE_CACHE: str | None = None

TWA_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS twa_org (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'standard',
  join_policy TEXT NOT NULL DEFAULT 'invite_or_apply',
  discoverable BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS twa_workspace (
  org_id TEXT NOT NULL REFERENCES twa_org(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  deletable BOOLEAN NOT NULL DEFAULT TRUE,
  kind TEXT NOT NULL DEFAULT 'custom',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (org_id, project_id)
);

CREATE TABLE IF NOT EXISTS twa_ws_member (
  org_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  role TEXT NOT NULL,
  PRIMARY KEY (org_id, project_id, subject)
);

CREATE TABLE IF NOT EXISTS twa_person_profile (
  subject TEXT PRIMARY KEY,
  email TEXT,
  phone TEXT,
  display_name TEXT,
  title TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS twa_invite (
  token TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  role TEXT NOT NULL,
  max_uses INT NOT NULL DEFAULT 10,
  uses INT NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  expires_ts DOUBLE PRECISION NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS twa_join_request (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  message TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL,
  decided_by TEXT,
  decided_at TEXT
);

CREATE TABLE IF NOT EXISTS twa_audit (
  id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  org_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  action TEXT NOT NULL,
  detail JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS twa_otp (
  id TEXT PRIMARY KEY,
  channel TEXT NOT NULL,
  destination TEXT NOT NULL,
  purpose TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  expires_ts DOUBLE PRECISION NOT NULL,
  consumed BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def clear_mode_cache() -> None:
    global _MODE_CACHE
    _MODE_CACHE = None


def mode() -> str:
    """Return 'pg' or 'memory'. Default auto → pg if DB reachable."""
    global _MODE_CACHE
    if _MODE_CACHE is not None:
        return _MODE_CACHE
    raw = (os.getenv("AOS_TWA_STORE") or "auto").strip().lower()
    if raw in {"memory", "mem"}:
        _MODE_CACHE = "memory"
        return _MODE_CACHE
    if raw == "pg":
        _MODE_CACHE = "pg"
        return _MODE_CACHE
    # auto
    try:
        from aos_api.db import connect

        with connect() as conn:
            conn.execute("SELECT 1")
        _MODE_CACHE = "pg"
    except Exception as exc:
        log.warning("twa_store_auto_fallback_memory err=%s", exc)
        _MODE_CACHE = "memory"
    return _MODE_CACHE


def enabled() -> bool:
    return mode() == "pg"


def ensure_schema(conn=None) -> None:
    from aos_api.db import connect

    def _run(c) -> None:
        c.execute(TWA_SCHEMA_SQL)

    if conn is None:
        with connect() as c:
            _run(c)
            c.commit()
    else:
        _run(conn)


def _with_conn(fn):
    from aos_api.db import connect

    with connect() as conn:
        out = fn(conn)
        conn.commit()
        return out


def truncate_all() -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute(
            """
            TRUNCATE twa_audit, twa_otp, twa_join_request, twa_invite,
                     twa_ws_member, twa_person_profile, twa_workspace, twa_org
            CASCADE
            """
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_truncate_skip err=%s", exc)


# --- org ---


def upsert_org(row: dict[str, Any]) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute(
            """
            INSERT INTO twa_org (id, name, kind, join_policy, discoverable)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
              name=EXCLUDED.name,
              kind=EXCLUDED.kind,
              join_policy=EXCLUDED.join_policy,
              discoverable=EXCLUDED.discoverable
            """,
            (
                row["id"],
                row.get("name") or row["id"],
                row.get("kind") or "standard",
                row.get("joinPolicy") or "invite_or_apply",
                bool(row.get("discoverable", True)),
            ),
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_upsert_org_skip err=%s", exc)


def delete_org(org_id: str) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute("DELETE FROM twa_org WHERE id=%s", (org_id,))

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_delete_org_skip err=%s", exc)


def truncate_orgs() -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute("TRUNCATE twa_org CASCADE")

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_truncate_orgs_skip err=%s", exc)


# --- workspace ---


def upsert_workspace(row: dict[str, Any]) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        # ensure parent org exists (FK)
        conn.execute(
            """
            INSERT INTO twa_org (id, name)
            VALUES (%s,%s)
            ON CONFLICT (id) DO NOTHING
            """,
            (row["orgId"], row["orgId"]),
        )
        conn.execute(
            """
            INSERT INTO twa_workspace (org_id, project_id, name, deletable, kind)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (org_id, project_id) DO UPDATE SET
              name=EXCLUDED.name,
              deletable=EXCLUDED.deletable,
              kind=EXCLUDED.kind
            """,
            (
                row["orgId"],
                row["id"],
                row.get("name") or row["id"],
                bool(row.get("deletable", True)),
                row.get("kind") or "custom",
            ),
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_upsert_workspace_skip err=%s", exc)


def delete_workspace(org_id: str, project_id: str) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute(
            "DELETE FROM twa_workspace WHERE org_id=%s AND project_id=%s",
            (org_id, project_id),
        )
        conn.execute(
            "DELETE FROM twa_ws_member WHERE org_id=%s AND project_id=%s",
            (org_id, project_id),
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_delete_workspace_skip err=%s", exc)


def truncate_workspaces() -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute("TRUNCATE twa_workspace CASCADE")

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_truncate_ws_skip err=%s", exc)


# --- members ---


def upsert_member(org_id: str, project_id: str, subject: str, role: str) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute(
            """
            INSERT INTO twa_ws_member (org_id, project_id, subject, role)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (org_id, project_id, subject) DO UPDATE SET role=EXCLUDED.role
            """,
            (org_id, project_id, subject, role),
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_upsert_member_skip err=%s", exc)


def delete_member(org_id: str, project_id: str, subject: str) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute(
            "DELETE FROM twa_ws_member WHERE org_id=%s AND project_id=%s AND subject=%s",
            (org_id, project_id, subject),
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_delete_member_skip err=%s", exc)


def delete_members_for_project(org_id: str, project_id: str) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute(
            "DELETE FROM twa_ws_member WHERE org_id=%s AND project_id=%s",
            (org_id, project_id),
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_delete_members_project_skip err=%s", exc)


def delete_members_for_org(org_id: str) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute("DELETE FROM twa_ws_member WHERE org_id=%s", (org_id,))

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_delete_members_org_skip err=%s", exc)


def truncate_members() -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute("TRUNCATE twa_ws_member, twa_audit")

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_truncate_members_skip err=%s", exc)


def append_audit(row: dict[str, Any]) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute(
            """
            INSERT INTO twa_audit (id, ts, org_id, project_id, actor_id, action, detail)
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                row["id"],
                row["ts"],
                row["orgId"],
                row["projectId"],
                row["actorId"],
                row["action"],
                json.dumps(row.get("detail") or {}),
            ),
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_append_audit_skip err=%s", exc)


# --- person ---


def upsert_person(row: dict[str, Any]) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute(
            """
            INSERT INTO twa_person_profile (subject, email, phone, display_name, title)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (subject) DO UPDATE SET
              email=EXCLUDED.email,
              phone=EXCLUDED.phone,
              display_name=EXCLUDED.display_name,
              title=EXCLUDED.title,
              updated_at=NOW()
            """,
            (
                row["subject"],
                row.get("email"),
                row.get("phone"),
                row.get("displayName"),
                row.get("title"),
            ),
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_upsert_person_skip err=%s", exc)


def truncate_persons() -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute("TRUNCATE twa_person_profile")

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_truncate_persons_skip err=%s", exc)


# --- invites ---


def upsert_invite(row: dict[str, Any]) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute(
            """
            INSERT INTO twa_invite (
              token, org_id, project_id, role, max_uses, uses, created_by,
              created_at, expires_at, expires_ts, status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (token) DO UPDATE SET
              uses=EXCLUDED.uses,
              status=EXCLUDED.status
            """,
            (
                row["token"],
                row["orgId"],
                row["projectId"],
                row["role"],
                int(row["maxUses"]),
                int(row["uses"]),
                row["createdBy"],
                row["createdAt"],
                row["expiresAt"],
                float(row.get("_expiresTs") or 0),
                row["status"],
            ),
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_upsert_invite_skip err=%s", exc)


def upsert_join_request(row: dict[str, Any]) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute(
            """
            INSERT INTO twa_join_request (
              id, org_id, project_id, subject, message, status,
              created_at, decided_by, decided_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
              status=EXCLUDED.status,
              project_id=EXCLUDED.project_id,
              decided_by=EXCLUDED.decided_by,
              decided_at=EXCLUDED.decided_at
            """,
            (
                row["id"],
                row["orgId"],
                row["projectId"],
                row["subject"],
                row.get("message") or "",
                row["status"],
                row["createdAt"],
                row.get("decidedBy"),
                row.get("decidedAt"),
            ),
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_upsert_join_skip err=%s", exc)


def delete_invites_for_org(org_id: str) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute("DELETE FROM twa_invite WHERE org_id=%s", (org_id,))
        conn.execute("DELETE FROM twa_join_request WHERE org_id=%s", (org_id,))

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_delete_invites_org_skip err=%s", exc)


def truncate_invites() -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute("TRUNCATE twa_invite, twa_join_request")

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_truncate_invites_skip err=%s", exc)


# --- bootstrap / hydrate ---


def count_orgs() -> int:
    if not enabled():
        return 0
    from aos_api.db import connect

    try:
        with connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM twa_org").fetchone()
            return int(row["c"] if row else 0)
    except Exception:
        return 0


def dump_memory_to_pg() -> None:
    """Persist current in-memory TWA state (used when PG empty at boot)."""
    if not enabled():
        return
    from aos_api import membership as mem
    from aos_api import org_invites as invites
    from aos_api import orgs as org_mod
    from aos_api import person_identity as person
    from aos_api import workspaces_catalog as ws_cat

    for row in org_mod._ORGS.values():  # noqa: SLF001
        upsert_org(row)
    for row in ws_cat._WS.values():  # noqa: SLF001
        upsert_workspace(row)
    for (o, p, s), role in mem._MEMBERS.items():  # noqa: SLF001
        upsert_member(o, p, s, role)
    for row in mem._AUDIT:  # noqa: SLF001
        append_audit(row)
    for row in person._PERSONS.values():  # noqa: SLF001
        upsert_person(row)
    for row in invites._INVITES.values():  # noqa: SLF001
        upsert_invite(row)
    for row in invites._JOIN_REQS.values():  # noqa: SLF001
        upsert_join_request(row)
    log.info("twa_pg_dump_memory_done")


def load_pg_to_memory() -> None:
    """Replace in-memory TWA state from PG."""
    if not enabled():
        return
    from aos_api import membership as mem
    from aos_api import org_invites as invites
    from aos_api import orgs as org_mod
    from aos_api import person_identity as person
    from aos_api import workspaces_catalog as ws_cat
    from aos_api.db import connect

    org_mod._ORGS.clear()  # noqa: SLF001
    ws_cat._WS.clear()  # noqa: SLF001
    mem._MEMBERS.clear()  # noqa: SLF001
    mem._AUDIT.clear()  # noqa: SLF001
    person._PERSONS.clear()  # noqa: SLF001
    invites._INVITES.clear()  # noqa: SLF001
    invites._JOIN_REQS.clear()  # noqa: SLF001

    with connect() as conn:
        for r in conn.execute("SELECT * FROM twa_org ORDER BY id").fetchall():
            org_mod._ORGS[r["id"]] = {  # noqa: SLF001
                "id": r["id"],
                "name": r["name"],
                "kind": r["kind"],
                "joinPolicy": r["join_policy"],
                "discoverable": bool(r["discoverable"]),
            }
        for r in conn.execute(
            "SELECT * FROM twa_workspace ORDER BY org_id, project_id"
        ).fetchall():
            ws_cat._WS[(r["org_id"], r["project_id"])] = {  # noqa: SLF001
                "id": r["project_id"],
                "orgId": r["org_id"],
                "name": r["name"],
                "deletable": bool(r["deletable"]),
                "kind": r["kind"],
            }
        for r in conn.execute("SELECT * FROM twa_ws_member").fetchall():
            mem._MEMBERS[(r["org_id"], r["project_id"], r["subject"])] = r["role"]  # noqa: SLF001
        for r in conn.execute("SELECT * FROM twa_person_profile").fetchall():
            person._PERSONS[r["subject"]] = {  # noqa: SLF001
                "subject": r["subject"],
                "email": r["email"],
                "phone": r["phone"],
                "displayName": r["display_name"],
                "title": r["title"],
            }
            # drop Nones
            person._PERSONS[r["subject"]] = {  # noqa: SLF001
                k: v
                for k, v in person._PERSONS[r["subject"]].items()  # noqa: SLF001
                if v is not None
            }
        for r in conn.execute("SELECT * FROM twa_invite").fetchall():
            invites._INVITES[r["token"]] = {  # noqa: SLF001
                "token": r["token"],
                "orgId": r["org_id"],
                "projectId": r["project_id"],
                "role": r["role"],
                "maxUses": int(r["max_uses"]),
                "uses": int(r["uses"]),
                "createdBy": r["created_by"],
                "createdAt": r["created_at"],
                "expiresAt": r["expires_at"],
                "_expiresTs": float(r["expires_ts"]),
                "status": r["status"],
            }
        for r in conn.execute("SELECT * FROM twa_join_request").fetchall():
            invites._JOIN_REQS[r["id"]] = {  # noqa: SLF001
                "id": r["id"],
                "orgId": r["org_id"],
                "projectId": r["project_id"],
                "subject": r["subject"],
                "message": r["message"] or "",
                "status": r["status"],
                "createdAt": r["created_at"],
                "decidedBy": r["decided_by"],
                "decidedAt": r["decided_at"],
            }
        seq = 0
        for rid in invites._JOIN_REQS:  # noqa: SLF001
            if rid.startswith("jr-"):
                try:
                    seq = max(seq, int(rid.split("-", 1)[1]))
                except ValueError:
                    pass
        invites._JR_SEQ = seq  # noqa: SLF001
        for r in conn.execute("SELECT * FROM twa_audit ORDER BY id").fetchall():
            detail = r["detail"]
            if isinstance(detail, str):
                try:
                    detail = json.loads(detail)
                except Exception:
                    detail = {}
            mem._AUDIT.append(  # noqa: SLF001
                {
                    "id": r["id"],
                    "ts": r["ts"],
                    "orgId": r["org_id"],
                    "projectId": r["project_id"],
                    "actorId": r["actor_id"],
                    "action": r["action"],
                    "detail": detail or {},
                }
            )
    log.info(
        "twa_pg_hydrate orgs=%s workspaces=%s members=%s",
        len(org_mod._ORGS),  # noqa: SLF001
        len(ws_cat._WS),  # noqa: SLF001
        len(mem._MEMBERS),  # noqa: SLF001
    )


def bootstrap() -> None:
    """Called from init_schema / lifespan when PG mode."""
    clear_mode_cache()
    if not enabled():
        log.info("twa_store mode=memory")
        return
    ensure_schema()
    n = count_orgs()
    if n == 0:
        dump_memory_to_pg()
        log.info("twa_store bootstrapped seeds into empty pg")
    else:
        load_pg_to_memory()
        log.info("twa_store hydrated from pg org_count=%s", n)


# OTP helpers (182m) -------------------------------------------------


def otp_insert(
    *,
    otp_id: str,
    channel: str,
    destination: str,
    purpose: str,
    code_hash: str,
    expires_ts: float,
) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute(
            """
            INSERT INTO twa_otp (id, channel, destination, purpose, code_hash, expires_ts)
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (otp_id, channel, destination, purpose, code_hash, expires_ts),
        )

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_otp_insert_skip err=%s", exc)


def otp_get(otp_id: str) -> dict[str, Any] | None:
    if not enabled():
        return None
    from aos_api.db import connect

    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM twa_otp WHERE id=%s", (otp_id,)
            ).fetchone()
            return dict(row) if row else None
    except Exception as exc:
        log.warning("twa_pg_otp_get_skip err=%s", exc)
        return None


def otp_consume(otp_id: str) -> None:
    if not enabled():
        return

    def _run(conn) -> None:
        conn.execute("UPDATE twa_otp SET consumed=TRUE WHERE id=%s", (otp_id,))

    try:
        _with_conn(_run)
    except Exception as exc:
        log.warning("twa_pg_otp_consume_skip err=%s", exc)


def now_ts() -> float:
    return time.time()
