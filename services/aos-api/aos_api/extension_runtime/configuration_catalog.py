"""Bounded staged configuration references; no policy bodies or execution authority."""
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from .configuration_contracts import ConfigurationRef
from .configuration_store import _decode
from .lifecycle_store import RuntimeConflict, _values


class ConfigurationChoice(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',frozen=True)
    ref: ConfigurationRef
    isCurrent: bool


class ConfigurationCatalog(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',frozen=True)
    installationId: str
    installationRevision: int
    installationEtag: int
    generation: str | None
    bindingRevision: int | None
    items: tuple[ConfigurationChoice,...]
    hasMore: bool


def read_catalog(conn, *, org_id, project_id, view):
    binding=view.binding
    common=dict(installationId=view.installationId,installationRevision=view.installationRevision,
        installationEtag=view.installationEtag,generation=binding.generation if binding else None,
        bindingRevision=binding.revision if binding else None)
    if binding is None:return ConfigurationCatalog(**common,items=(),hasMore=False)
    target=(org_id,project_id,UUID(view.installationId),UUID(binding.generation))
    def check():
        row=conn.execute('''SELECT b.revision,b.installation_revision,i.etag_version
            FROM extension_runtime_binding b JOIN bundle_installation i USING(org_id,project_id,installation_id)
            WHERE b.org_id=%s AND b.project_id=%s AND b.installation_id=%s AND b.generation=%s''',target).fetchone()
        if row is None or _values(row,('revision','installation_revision','etag_version'))!=(binding.revision,view.installationRevision,view.installationEtag):
            raise RuntimeConflict('configuration catalog target changed')
    check()
    rows=conn.execute('''SELECT configuration_id,revision,payload,content_hash,previous_hash,actor
        FROM extension_runtime_configuration WHERE org_id=%s AND project_id=%s
        AND installation_id=%s AND generation=%s ORDER BY configuration_id,revision DESC LIMIT 51''',target).fetchall()
    items=[]
    for row in rows[:50]:
        ref,_document=_decode(target,row)
        items.append(ConfigurationChoice(ref=ref,isCurrent=ref.model_dump(mode='json')==binding.configRef))
    check()
    return ConfigurationCatalog(**common,items=tuple(items),hasMore=len(rows)>50)
