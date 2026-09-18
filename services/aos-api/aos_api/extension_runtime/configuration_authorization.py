"""Trusted composition of current readers, not a business authority or permit."""
from contextlib import contextmanager
from contextvars import ContextVar
from types import MappingProxyType

from aos_api.asset_registry.control_policy import CONFIGURE_RUNTIME_OPERATION
from aos_api.asset_registry.installation_store import PostgresInstallationStore

from .configuration_contracts import ConfigurationDocument
from .configuration_store import _target
from .lifecycle_store import _require_transaction
from .runtime_gate import _reject_deferred


_LOCKED_PERMISSION_CACHE = ContextVar('locked_configuration_permission_cache', default=None)


class ConfigurationAuthorization:
    def __init__(self, *, permission, readers):
        if not callable(permission):
            raise ValueError('current actor permission reader required')
        registered=dict(readers)
        for key, reader in registered.items():
            if (type(key) is not tuple or len(key)!=2 or
                key[0] not in ('role','data','budget','policy') or
                type(key[1]) is not str or not key[1] or key[1]=='*' or
                not callable(reader)):
                raise ValueError('exact purpose and authority reader required')
        self._permission=permission
        self._readers=MappingProxyType(registered)

    @staticmethod
    def _check(reader, conn, **kwargs):
        result=reader(conn,**kwargs)
        _reject_deferred(result)
        if result is not True:
            raise PermissionError('current configuration authority denied')

    def __call__(self, conn, *, org_id, project_id, installation_id, generation, actor, configuration):
        target=_target(conn,org_id,project_id,installation_id,generation)
        if type(actor) is not str or not 1<=len(actor)<=240 or not actor.isprintable() or actor!=actor.strip():
            raise ValueError('exact configuration actor required')
        document=ConfigurationDocument.model_validate(configuration)
        context=dict(org_id=target[0],project_id=target[1],installation_id=str(target[2]),generation=str(target[3]),actor=actor)
        self._check(self._permission,conn,**context)
        checks=[]
        for purpose,refs in (('role',document.roleRefs),('data',document.dataRefs),
                             ('budget',(document.budgetRef,)),('policy',(document.policyRef,))):
            for ref in sorted(refs,key=lambda value:(value.authority,value.id)):
                reader=self._readers.get((purpose,ref.authority))
                if reader is None:
                    raise PermissionError('configuration source reader unavailable')
                checks.append((purpose,ref,reader))
        for purpose,ref,reader in checks:
            extra={'configuration':document} if purpose=='policy' else {}
            self._check(reader,conn,**context,purpose=purpose,ref=ref,**extra)
        return True


CURRENT_FOUR_SOURCE_AUTHORITIES = frozenset(
    {
        ("role", "aip.responsibility_plan_revision"),
        ("data", "aip.data_classification_policy_revision"),
        ("budget", "aip.budget_revision"),
        ("policy", "aip.runtime_policy_revision"),
    }
)
_CURRENT_FOUR_SOURCE_MINT = object()


class CurrentConfigurationPermission:
    """Concrete current-installation permission used by production admission."""

    def __init__(self, *, installation_store: PostgresInstallationStore):
        if type(installation_store) is not PostgresInstallationStore:
            raise TypeError("current configuration permission requires PostgreSQL store")
        from . import current_permission as permission_module

        self._store = installation_store
        self._permission = permission_module.CurrentControlPermission(
            operation=CONFIGURE_RUNTIME_OPERATION
        )

    @contextmanager
    def reuse_locked_transaction(self, conn):
        """Reuse one proven permission only inside the caller-owned transaction."""
        _require_transaction(conn)
        current = _LOCKED_PERMISSION_CACHE.get()
        token = None
        if current is None:
            token = _LOCKED_PERMISSION_CACHE.set({})
        try:
            yield
        finally:
            if token is not None:
                _LOCKED_PERMISSION_CACHE.reset(token)

    def __call__(
        self,
        conn,
        *,
        org_id,
        project_id,
        installation_id,
        generation,
        actor,
        **_context,
    ):
        _require_transaction(conn)
        cache = _LOCKED_PERMISSION_CACHE.get()
        key = (
            id(self), id(conn), conn.info.backend_pid,
            org_id, project_id, str(installation_id), str(generation), actor,
        )
        if cache is not None and key in cache:
            return True
        row = conn.execute(
            """SELECT etag_version FROM bundle_installation
               WHERE org_id=%s AND project_id=%s AND installation_id=%s
               FOR UPDATE""",
            (org_id, project_id, installation_id),
        ).fetchone()
        if row is None:
            raise LookupError("configuration installation not found")
        etag = row["etag_version"] if isinstance(row, dict) else row[0]
        locked = self._store.lock_for_transition_in_transaction(
            conn,
            org_id=org_id,
            project_id=project_id,
            installation_id=installation_id,
            expected_etag_version=etag,
        )
        allowed = self._permission(conn=conn, locked=locked, actor=actor)
        if allowed is True and cache is not None:
            cache[key] = True
        return allowed


class CurrentFourSourceConfigurationAuthorization(ConfigurationAuthorization):
    """Closed production admission type for the current AIP four-source set."""

    def __init__(self, *, permission, readers, _mint=None):
        if _mint is not _CURRENT_FOUR_SOURCE_MINT:
            raise TypeError("current four-source authority requires AIP factory")
        if type(permission) is not CurrentConfigurationPermission:
            raise TypeError("current configuration permission required")
        super().__init__(permission=permission, readers=readers)
        if frozenset(self._readers) != CURRENT_FOUR_SOURCE_AUTHORITIES:
            raise ValueError("current four-source configuration readers required")


def _mint_current_four_source_authorization(*, permission):
    """Mint only the fixed AIP readers; arbitrary reader injection is impossible."""
    from aos_api import aip_runtime_configuration_sources as sources

    readers = {
        ("role", "aip.responsibility_plan_revision"):
            sources.read_current_responsibility_plan_ref,
        ("data", "aip.data_classification_policy_revision"):
            sources.read_current_data_classification_ref,
        ("budget", "aip.budget_revision"):
            sources.read_current_configuration_budget_ref,
        ("policy", "aip.runtime_policy_revision"):
            sources.read_current_runtime_policy_ref,
    }
    return CurrentFourSourceConfigurationAuthorization(
        permission=permission, readers=readers, _mint=_CURRENT_FOUR_SOURCE_MINT
    )
