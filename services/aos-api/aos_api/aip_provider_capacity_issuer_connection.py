"""Exact private SCRAM caller, keeping its issuer identity throughout the transaction."""
from contextlib import contextmanager
from dataclasses import dataclass,field
from pathlib import Path
import os,re,stat

import psycopg
from psycopg.rows import dict_row

from aos_api.aip_provider_capacity_formal_boundary import ISSUER,require_capacity_issuer_identity,ProviderCapacityFormalBoundaryBlocked
from aos_api.tenant_scope import TenantScope


class ProviderCapacityIssuerConnectionBlocked(ValueError):
    pass


@dataclass(frozen=True,slots=True)
class ProviderCapacityIssuerDatabaseConfig:
    host: str
    port: int
    database: str
    passfile: Path=field(repr=False)

    def __post_init__(self):
        try:
            if (self.host not in {'127.0.0.1','::1'} or type(self.port) is not int or not 1<=self.port<=65535
                or type(self.database) is not str or not re.fullmatch(r'[a-z][a-z0-9_]{0,62}',self.database)):
                raise ValueError('exact database required')
            path=Path(self.passfile)
            if not path.is_absolute() or any(part=='..' for part in path.parts):raise ValueError('absolute private path required')
            for part in [path,*path.parents]:
                if stat.S_ISLNK(part.lstat().st_mode):raise ValueError('symlink rejected')
            parent,secret=path.parent.lstat(),path.lstat()
            if (not stat.S_ISDIR(parent.st_mode) or not stat.S_ISREG(secret.st_mode)
                or parent.st_uid!=os.geteuid() or secret.st_uid!=os.geteuid() or secret.st_nlink!=1
                or stat.S_IMODE(parent.st_mode)!=0o700 or stat.S_IMODE(secret.st_mode)!=0o600):
                raise ValueError('private credential required')
            object.__setattr__(self,'passfile',path)
        except (OSError,TypeError,ValueError):
            raise ProviderCapacityIssuerConnectionBlocked('CAPACITY_ISSUER_PRIVATE_CONFIG_REQUIRED') from None


@contextmanager
def connect_capacity_issuer(config,scope):
    if (type(config) is not ProviderCapacityIssuerDatabaseConfig or type(scope) is not TenantScope
        or scope.key!=('org-org','dev-project') or any(os.environ.get(key) for key in
            ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'))):
        raise ProviderCapacityIssuerConnectionBlocked('CAPACITY_ISSUER_EXACT_CONNECTION_REQUIRED')
    config.__post_init__()
    try:
        conn=psycopg.connect(host=config.host,port=config.port,dbname=config.database,user=ISSUER,passfile=str(config.passfile),
            require_auth='scram-sha-256',connect_timeout=5,row_factory=dict_row,
            options='-c statement_timeout=10000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=10000')
    except Exception:
        raise ProviderCapacityIssuerConnectionBlocked('CAPACITY_ISSUER_CONNECTION_FAILED') from None
    with conn:
        try:
            conn.isolation_level=psycopg.IsolationLevel.SERIALIZABLE;conn.read_only=False
            conn.execute('SET LOCAL search_path=pg_catalog,public,pg_temp')
            conn.execute("SET LOCAL TimeZone='UTC'")
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
            require_capacity_issuer_identity(conn,scope)
            row=conn.execute("SELECT current_database() AS db,(SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_ms,"
                "(SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_ms,"
                "(SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle_ms").fetchone()
            if row!=dict(db=config.database,statement_ms=10000,lock_ms=5000,idle_ms=10000) or not conn.pgconn.used_password:
                raise ValueError('connection identity drift')
        except ProviderCapacityFormalBoundaryBlocked as exc:
            raise ProviderCapacityIssuerConnectionBlocked(str(exc)) from None
        except Exception:
            raise ProviderCapacityIssuerConnectionBlocked('CAPACITY_ISSUER_CONNECTION_BOUNDARY_REQUIRED') from None
        yield conn
