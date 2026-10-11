def _require_identity(conn, config: BIIssuerDatabaseConfig, scope: TenantScope,
                      *, read_only: bool, issuer_login: str = ISSUER_LOGIN) -> None:
    identity = conn.execute("""SELECT current_database() AS db,
      session_user AS login,current_user AS role,
      current_setting('aos.org_id',true) AS org_id,
      current_setting('aos.project_id',true) AS project_id,
      (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_timeout_ms,
      (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_timeout_ms,
      (SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle_timeout_ms,
      r.rolcanlogin,r.rolsuper,r.rolbypassrls,r.rolinherit,
      r.rolcreaterole,r.rolcreatedb,r.rolreplication,
      EXISTS(SELECT 1 FROM pg_roles other WHERE other.rolname<>session_user
        AND pg_has_role(session_user,other.oid,'MEMBER')) AS other_role_member,
      pg_has_role(session_user,'aos_app','MEMBER') AS owner_member,
      pg_has_role(session_user,'aos_runtime','MEMBER') AS runtime_member
      FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
    if (identity is None or identity["db"] != config.database
            or issuer_login not in _SOURCE_ISSUER_LOGINS
            or identity["login"] != issuer_login or identity["role"] != issuer_login
            or (identity["org_id"], identity["project_id"]) != scope.key
            or not identity["rolcanlogin"] or identity["rolsuper"]
            or identity["rolbypassrls"] or identity["rolinherit"]
            or identity["rolcreaterole"] or identity["rolcreatedb"] or identity["rolreplication"]
            or identity["other_role_member"]
            or identity["owner_member"] or identity["runtime_member"]
            or conn.read_only is not read_only
            or (identity['statement_timeout_ms'], identity['lock_timeout_ms'], identity['idle_timeout_ms'])
                != (10000, 5000, 10000)):
        raise BIIssuerDatabaseBlocked("BI_ISSUER_DATABASE_IDENTITY_REQUIRED")

class _ScopedBIIssuerConnection:
    """Rebind the transaction-local scope after an original Store commit."""

    __slots__ = ("_raw", "_config", "_scope", "_issuer_login")

    def __init__(self, raw, config: BIIssuerDatabaseConfig, scope: TenantScope,
                 issuer_login: str = ISSUER_LOGIN) -> None:
        self._raw, self._config, self._scope = raw, config, scope
        self._issuer_login = issuer_login

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def _rebind(self) -> None:
        _bind_scope(self._raw, self._scope)
        _require_identity(self._raw, self._config, self._scope, read_only=False,
                          issuer_login=self._issuer_login)

    def commit(self) -> None:
        self._raw.commit()
        self._rebind()

    def rollback(self) -> None:
        self._raw.rollback()
        self._rebind()

def _connect_bi_issuer(config: BIIssuerDatabaseConfig, scope: TenantScope,
                       *, read_only: bool, issuer_login: str = ISSUER_LOGIN) -> Iterator:
    if (type(config) is not BIIssuerDatabaseConfig or type(scope) is not TenantScope
            or issuer_login not in _SOURCE_ISSUER_LOGINS
            or any(os.environ.get(name) for name in _FORBIDDEN_PG_ENV)):
        raise BIIssuerDatabaseBlocked("BI_ISSUER_EXACT_CONNECTION_REQUIRED")
    config.__post_init__()
    try:
        conn = connect(host=config.host, port=config.port, dbname=config.database,
                       user=issuer_login, passfile=str(config.passfile),
                       connect_timeout=5, options=_TIMEOUT_OPTIONS, row_factory=dict_row)
    except Exception:
        raise BIIssuerDatabaseBlocked("BI_ISSUER_DATABASE_CONNECTION_FAILED") from None
    with conn:
        try:
            conn.isolation_level = (IsolationLevel.REPEATABLE_READ if read_only
                                    else IsolationLevel.SERIALIZABLE)
            conn.read_only = read_only
            _bind_scope(conn, scope)
            _require_identity(conn, config, scope, read_only=read_only, issuer_login=issuer_login)
        except BIIssuerDatabaseBlocked:
            raise
        except Exception:
            raise BIIssuerDatabaseBlocked("BI_ISSUER_DATABASE_IDENTITY_REQUIRED") from None
        yield conn if read_only else _ScopedBIIssuerConnection(conn, config, scope, issuer_login)
