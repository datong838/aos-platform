"""Current source candidates, not configuration authorization or policy contents."""
from pydantic import BaseModel, ConfigDict, Field

from .configuration_catalog import check_catalog_target
from .configuration_contracts import ConfigurationSourceRef
from .configuration_stage_contracts import ConfigurationStageTarget
from .lifecycle_store import _values


class ConfigurationSourceChoice(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',frozen=True)
    label: str = Field(min_length=1,max_length=500)
    ref: ConfigurationSourceRef


class ConfigurationSourceCatalog(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',frozen=True)
    target: ConfigurationStageTarget | None
    installationRevision: int
    roles: tuple[ConfigurationSourceChoice,...]
    policies: tuple[ConfigurationSourceChoice,...]
    rolesHasMore: bool
    policiesHasMore: bool


def read_source_catalog(conn, *, org_id, project_id, view):
    target=check_catalog_target(conn,org_id=org_id,project_id=project_id,view=view)
    if target is None:
        return ConfigurationSourceCatalog(target=None,installationRevision=view.installationRevision,
            roles=(),policies=(),rolesHasMore=False,policiesHasMore=False)
    roles=conn.execute('''SELECT r.plan_id,r.revision,r.content_hash,r.profile
        FROM aip_responsibility_plan_head h JOIN aip_responsibility_plan_revision r
        ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.plan_id=h.plan_id AND r.revision=h.current_revision
        WHERE h.org_id=%s AND h.project_id=%s AND r.lifecycle='frozen' ORDER BY r.plan_id LIMIT 51''',target[:2]).fetchall()
    policies=conn.execute('''SELECT r.runtime_policy_id,r.revision,r.content_hash
        FROM aip_runtime_policy_head h JOIN aip_runtime_policy_revision r
        ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.runtime_policy_id=h.runtime_policy_id AND r.revision=h.current_revision
        WHERE h.org_id=%s AND h.project_id=%s AND r.lifecycle='active' AND r.payload->'killSwitchEnabled'='false'::jsonb
        ORDER BY r.runtime_policy_id LIMIT 51''',target[:2]).fetchall()
    role_items=[];policy_items=[]
    for row in roles[:50]:
        identity,revision,digest,profile=_values(row,('plan_id','revision','content_hash','profile'))
        role_items.append(ConfigurationSourceChoice(label='职责计划 · '+profile,
            ref=ConfigurationSourceRef(authority='aip.responsibility_plan_revision',id=identity,revision=revision,hash='sha256:'+digest)))
    for row in policies[:50]:
        identity,revision,digest=_values(row,('runtime_policy_id','revision','content_hash'))
        policy_items.append(ConfigurationSourceChoice(label='运行策略 · '+identity,
            ref=ConfigurationSourceRef(authority='aip.runtime_policy_revision',id=identity,revision=revision,hash='sha256:'+digest)))
    check_catalog_target(conn,org_id=org_id,project_id=project_id,view=view)
    return ConfigurationSourceCatalog(target=ConfigurationStageTarget(installationId=view.installationId,
        installationEtag=view.installationEtag,generation=view.binding.generation,bindingRevision=view.binding.revision),
        installationRevision=view.installationRevision,roles=tuple(role_items),policies=tuple(policy_items),
        rolesHasMore=len(roles)>50,policiesHasMore=len(policies)>50)
