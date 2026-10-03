"""Default-off non-owner connection for canonical AIP Registry commands.

Provisioning, external authorization, and current-database ACL cutover are
separate gates; this factory only admits an exact isolated database identity.
"""

from __future__ import annotations

import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

from psycopg import IsolationLevel, connect
from psycopg.rows import dict_row

from aos_api.tenant_scope import TenantScope


ISSUER_LOGIN = "aos_aip_registry_issuer"
SKILL_ISSUER_LOGIN = "aos_aip_skill_issuer"
CAPABILITY_ISSUER_LOGIN = "aos_aip_capability_issuer"
_ISSUER_LOGINS = {"agent": ISSUER_LOGIN, "skill": SKILL_ISSUER_LOGIN,
                  "capability": CAPABILITY_ISSUER_LOGIN,
                  "capability_lifecycle": CAPABILITY_ISSUER_LOGIN}
_DATABASE = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")
_FORBIDDEN_PG_ENV = ("PGPASSWORD", "PGPASSFILE", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")
_OPTIONS = ("-c statement_timeout=10000 -c lock_timeout=5000 "
            "-c idle_in_transaction_session_timeout=10000 -c search_path=public,pg_catalog")


class RegistryIssuerConnectionBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistryIssuerDatabaseConfig:
    host: str
    port: int
    database: str
    passfile: Path

    def __post_init__(self) -> None:
        if (self.host not in {"127.0.0.1", "::1"}
                or type(self.port) is not int or not 1 <= self.port <= 65535
                or type(self.database) is not str or _DATABASE.fullmatch(self.database) is None):
            raise RegistryIssuerConnectionBlocked("REGISTRY_ISSUER_EXACT_DATABASE_REQUIRED")
        path = Path(self.passfile)
        try:
            parent, secret = path.parent.lstat(), path.lstat()
            if (not path.is_absolute() or not stat.S_ISDIR(parent.st_mode)
                    or not stat.S_ISREG(secret.st_mode)
                    or parent.st_uid != os.geteuid() or secret.st_uid != os.geteuid()
                    or stat.S_IMODE(parent.st_mode) != 0o700
                    or stat.S_IMODE(secret.st_mode) != 0o600):
                raise ValueError("private passfile required")
        except (OSError, TypeError, ValueError):
            raise RegistryIssuerConnectionBlocked("REGISTRY_ISSUER_PRIVATE_CREDENTIAL_REQUIRED") from None
        object.__setattr__(self, "passfile", path)


def _require_identity(conn, config: RegistryIssuerDatabaseConfig, scope: TenantScope,
                      command_family: Literal["agent", "skill", "capability", "capability_lifecycle"]) -> None:
    row = conn.execute("""SELECT current_database() AS database,
      session_user AS login,current_user AS role,
      current_setting('aos.org_id',true) AS org_id,
      current_setting('aos.project_id',true) AS project_id,
      current_setting('search_path') AS search_path,
      (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_ms,
      (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_ms,
      (SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle_ms,
      r.rolcanlogin,r.rolsuper,r.rolbypassrls,r.rolcreatedb,r.rolcreaterole,r.rolreplication,
      pg_has_role(session_user,'aos_app','MEMBER') AS owner_member,
      pg_has_role(session_user,'aos_runtime','MEMBER') AS runtime_member,
      (SELECT pg_has_role(session_user,relowner,'MEMBER') FROM pg_class
        WHERE oid='public.aip_agent_registry_receipt'::regclass) AS receipt_owner_member,
      (SELECT pg_has_role(session_user,relowner,'MEMBER') FROM pg_class
        WHERE oid='public.aip_agent_instance'::regclass) AS instance_owner_member,
      (SELECT pg_has_role(session_user,relowner,'MEMBER') FROM pg_class
        WHERE oid='public.aip_capability_binding'::regclass) AS capability_owner_member,
      (SELECT relrowsecurity AND relforcerowsecurity FROM pg_class
        WHERE oid='public.aip_agent_registry_receipt'::regclass) AS receipt_rls,
      (SELECT relrowsecurity AND relforcerowsecurity FROM pg_class
        WHERE oid='public.aip_agent_instance'::regclass) AS instance_rls,
      has_table_privilege(session_user,'public.aip_agent_registry_receipt','SELECT') AS receipt_select,
      has_table_privilege(session_user,'public.aip_agent_registry_receipt','INSERT') AS receipt_insert,
      has_table_privilege(session_user,'public.aip_agent_registry_receipt','UPDATE') AS receipt_update,
      has_table_privilege(session_user,'public.aip_agent_registry_receipt','DELETE') AS receipt_delete,
      has_table_privilege('aos_runtime','public.aip_agent_registry_receipt','INSERT') AS runtime_insert,
      has_table_privilege(session_user,'public.aip_agent_instance','SELECT') AS instance_select,
      has_table_privilege(session_user,'public.aip_agent_instance','INSERT') AS instance_insert,
      has_table_privilege(session_user,'public.aip_agent_instance','UPDATE') AS instance_update,
      has_table_privilege(session_user,'public.aip_agent_instance','DELETE') AS instance_delete,
      has_table_privilege(session_user,'public.aip_agent_template_revision','SELECT') AS template_select,
      (SELECT relrowsecurity AND relforcerowsecurity FROM pg_class
        WHERE oid='public.aip_skill_binding'::regclass) AS skill_rls,
      has_table_privilege(session_user,'public.aip_skill_template_revision','SELECT') AS skill_template_select,
      (SELECT relrowsecurity AND relforcerowsecurity FROM pg_class
        WHERE oid='public.aip_publication_event'::regclass) AS publication_rls,
      has_table_privilege(session_user,'public.aip_publication_event','SELECT') AS publication_select,
      (has_table_privilege(session_user,'public.aip_publication_event','INSERT') OR
       has_table_privilege(session_user,'public.aip_publication_event','UPDATE') OR
       has_table_privilege(session_user,'public.aip_publication_event','DELETE')) AS publication_write,
      has_table_privilege(session_user,'public.aip_capability_binding','SELECT') AS capability_select,
      has_table_privilege(session_user,'public.aip_capability_binding','INSERT') AS capability_insert,
      has_table_privilege(session_user,'public.aip_capability_binding','UPDATE') AS capability_update,
      has_table_privilege(session_user,'public.aip_capability_binding','DELETE') AS capability_delete,
      has_table_privilege(session_user,'public.aip_capability_revision','SELECT') AS capability_revision_select,
      (SELECT relrowsecurity AND relforcerowsecurity FROM pg_class
        WHERE oid='public.aip_capability_binding'::regclass) AS capability_rls,
      has_table_privilege(session_user,'public.aip_skill_binding','SELECT') AS skill_select,
      has_table_privilege(session_user,'public.aip_skill_binding','INSERT') AS skill_insert,
      has_table_privilege(session_user,'public.aip_skill_binding','UPDATE') AS skill_update,
      has_table_privilege(session_user,'public.aip_skill_binding','DELETE') AS skill_delete,
      (has_table_privilege(session_user,'public.aip_capability_revision','INSERT') OR
       has_table_privilege(session_user,'public.aip_capability_revision','UPDATE') OR
       has_table_privilege(session_user,'public.aip_capability_revision','DELETE') OR
       has_table_privilege(session_user,'public.aip_skill_template_revision','INSERT') OR
       has_table_privilege(session_user,'public.aip_skill_template_revision','UPDATE') OR
       has_table_privilege(session_user,'public.aip_skill_template_revision','DELETE') OR
       has_table_privilege(session_user,'public.aip_agent_template_revision','INSERT') OR
       has_table_privilege(session_user,'public.aip_agent_template_revision','UPDATE') OR
       has_table_privilege(session_user,'public.aip_agent_template_revision','DELETE') OR
       has_table_privilege(session_user,'public.aip_tool_binding','INSERT') OR
       has_table_privilege(session_user,'public.aip_tool_binding','UPDATE') OR
       has_table_privilege(session_user,'public.aip_tool_binding','DELETE') OR
       has_table_privilege(session_user,'public.aip_assignee_resolution_receipt','INSERT') OR
       has_table_privilege(session_user,'public.aip_assignee_resolution_receipt','UPDATE') OR
       has_table_privilege(session_user,'public.aip_assignee_resolution_receipt','DELETE')) AS cross_domain_write
      FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
    if (row is None or row["database"] != config.database
            or row["login"] != _ISSUER_LOGINS[command_family]
            or row["role"] != row["login"]
            or (row["org_id"], row["project_id"]) != scope.key
            or row["search_path"] != "public,pg_catalog"
            or (row["statement_ms"], row["lock_ms"], row["idle_ms"]) != (10000, 5000, 10000)
            or not row["rolcanlogin"] or row["rolsuper"] or row["rolbypassrls"]
            or row["rolcreatedb"] or row["rolcreaterole"] or row["rolreplication"]
            or row["owner_member"] or row["runtime_member"]
            or row["receipt_owner_member"] or row["instance_owner_member"]
            or row["capability_owner_member"] or not row["receipt_rls"]
            or not row["receipt_select"] or not row["receipt_insert"]
            or row["receipt_update"] or row["receipt_delete"] or row["runtime_insert"]
            or row["instance_delete"]
            or (command_family == "agent" and (
                not row["instance_rls"] or not row["instance_select"]
                or not row["instance_insert"] or not row["instance_update"]))
            or (command_family == "skill" and (
                not row["instance_rls"] or not row["instance_select"]
                or row["instance_insert"] or row["instance_update"]))
            or (command_family in {"capability", "capability_lifecycle"} and (
                row["instance_select"] or row["instance_insert"]
                or row["instance_update"]))
            or (command_family not in {"capability", "capability_lifecycle"} and not row["template_select"])
            or row["cross_domain_write"] or row["publication_write"] or conn.read_only
            or (command_family == "skill" and (
                not row["skill_rls"] or not row["skill_template_select"]
                or not row["publication_rls"] or not row["publication_select"]
                or not row["capability_select"] or not row["capability_rls"]
                or not row["skill_select"]
                or not row["skill_insert"] or not row["skill_update"]
                or row["skill_delete"]))
            or (command_family != "skill" and (
                row["skill_insert"] or row["skill_update"] or row["skill_delete"]))
            or (command_family in {"capability", "capability_lifecycle"} and (
                not row["capability_rls"] or not row["capability_revision_select"]
                or not row["capability_select"] or not row["capability_insert"]
                or row["capability_delete"]
                or row["capability_update"] != (command_family == "capability_lifecycle")))
            or (command_family not in {"capability", "capability_lifecycle"} and (
                row["capability_insert"] or row["capability_update"]
                or row["capability_delete"]))):
        raise RegistryIssuerConnectionBlocked("REGISTRY_ISSUER_DATABASE_IDENTITY_REQUIRED")


@dataclass(frozen=True)
class RegistryIssuerConnectionFactory:
    config: RegistryIssuerDatabaseConfig
    command_family: Literal["agent", "skill", "capability", "capability_lifecycle"] = "agent"

    @contextmanager
    def __call__(self, scope: TenantScope) -> Iterator:
        if (type(scope) is not TenantScope or type(self.config) is not RegistryIssuerDatabaseConfig
                or type(self.command_family) is not str
                or self.command_family not in _ISSUER_LOGINS
                or any(os.environ.get(key) for key in _FORBIDDEN_PG_ENV)):
            raise RegistryIssuerConnectionBlocked("REGISTRY_ISSUER_EXACT_CONNECTION_REQUIRED")
        self.config.__post_init__()
        try:
            login = _ISSUER_LOGINS[self.command_family]
            conn = connect(host=self.config.host, port=self.config.port,
                           dbname=self.config.database, user=login,
                           passfile=str(self.config.passfile), connect_timeout=5,
                           options=_OPTIONS, row_factory=dict_row)
        except Exception:
            raise RegistryIssuerConnectionBlocked("REGISTRY_ISSUER_CONNECTION_FAILED") from None
        with conn:
            try:
                conn.isolation_level = IsolationLevel.SERIALIZABLE
                conn.read_only = False
                conn.execute("SELECT set_config('aos.org_id',%s,true), set_config('aos.project_id',%s,true)", scope.key)
                _require_identity(conn, self.config, scope, self.command_family)
            except RegistryIssuerConnectionBlocked:
                raise
            except Exception:
                raise RegistryIssuerConnectionBlocked("REGISTRY_ISSUER_DATABASE_IDENTITY_REQUIRED") from None
            yield conn
