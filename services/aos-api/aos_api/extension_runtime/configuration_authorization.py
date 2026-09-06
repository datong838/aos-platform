"""Trusted composition of current readers, not a business authority or permit."""
from types import MappingProxyType

from .configuration_contracts import ConfigurationDocument
from .configuration_store import _target
from .runtime_gate import _reject_deferred


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
