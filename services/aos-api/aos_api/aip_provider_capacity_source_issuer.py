"""External issuance ingress; identity and request binding supply no capacity grant."""
from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand,capacity_issuance_binding
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.auth import Principal,resolve_principal
from aos_api.tenant_scope import TenantScope


class ProviderCapacityIssuanceBlocked(ValueError):
    pass


def authenticate_capacity_issuance_command(command):
    """Verify the original JWT every time; never accept a caller's Principal."""
    try:
        if type(command) is not ProviderCapacityIssuanceCommand:
            raise ValueError('native issuance command required')
        command=ProviderCapacityIssuanceCommand.model_validate(command.model_dump(mode='python',by_alias=True))
        _require_external_oidc_config()
        principal=resolve_principal(token=command.bearer_token.get_secret_value(),
            header_org=command.tenant.org_id,header_project=command.tenant.project_id)
        if (type(principal) is not Principal or principal.token_kind!='oidc'
            or (principal.org_id,principal.project_id)!=('org-org','dev-project')):
            raise ValueError('native external positive tenant required')
        capacity_issuance_binding(TenantScope(principal.org_id,principal.project_id),principal.subject,command)
        return principal
    except Exception:
        raise ProviderCapacityIssuanceBlocked('CAPACITY_ISSUANCE_EXTERNAL_IDENTITY_REQUIRED') from None
