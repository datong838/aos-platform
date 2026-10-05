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


def check_signed_capacity_documents(command,maker,policy_document,attestation_document,*,trust_roots,checked_at):
    """Pure signature/ref checks; no JWT, DB, approval, mapping or grant authority.

    The formal private transaction must authenticate the command, supply its
    own current DB clock, validate the deployment and original approved rows,
    then re-run this check before publication. Its result cannot be an input
    authority for that transaction.
    """
    from datetime import datetime,timedelta
    from aos_api.aip_action_store import canonical_hash
    from aos_api.asset_registry.canonical_json import canonical_json
    from aos_api.asset_registry.signature import FileTrustRootProvider,verify_ed25519
    from aos_api.aip_provider_capacity_source_contracts import (
        SignedCapacitySourcePolicy,SignedSupplierCapacityAttestation,CapacitySupplierDocumentCheck)
    try:
        if (type(command) is not ProviderCapacityIssuanceCommand
            or type(policy_document) is not SignedCapacitySourcePolicy
            or type(attestation_document) is not SignedSupplierCapacityAttestation
            or type(trust_roots) is not FileTrustRootProvider
            or not isinstance(checked_at,datetime) or checked_at.utcoffset() is None):
            raise ValueError('exact signed documents and current clock required')
        command=ProviderCapacityIssuanceCommand.model_validate(command.model_dump(mode='python',by_alias=True))
        policy_document=SignedCapacitySourcePolicy.model_validate(policy_document.model_dump(mode='python',by_alias=True))
        attestation_document=SignedSupplierCapacityAttestation.model_validate(attestation_document.model_dump(mode='python',by_alias=True))
        scope=TenantScope(command.tenant.org_id,command.tenant.project_id)
        binding=capacity_issuance_binding(scope,maker,command)
        roots=trust_roots.snapshot()
        policy,attestation=policy_document.payload,attestation_document.payload
        for document,ref,kind in (
            (policy_document,command.source_policy_ref,'ProviderCapacitySourcePolicyRevision'),
            (attestation_document,command.supplier_attestation_ref,'SupplierCapacityAttestationRevision')):
            body=document.payload;payload=body.model_dump(mode='json',by_alias=True)
            if ((ref.asset_type,ref.asset_id,ref.revision,ref.content_hash)
                !=(kind,body.asset_id,body.revision,canonical_hash(payload))
                or (body.tenant.org_id,body.tenant.project_id)!=scope.key
                or not body.valid_from<=checked_at<body.valid_until
                or not verify_ed25519(payload=canonical_json(payload),signature_b64=document.signature,
                    publisher=body.publisher,key_id=body.key_id,trust_roots=roots,
                    algorithm=document.algorithm,verified_at=checked_at)):
                raise ValueError('exact current signed source document required')
        root=roots.get_trust_root(publisher=attestation.publisher,key_id=attestation.key_id)
        if ((attestation.publisher,attestation.key_id,attestation.supplier_id)
            !=(policy.attestation_publisher,policy.attestation_key_id,policy.supplier_id)
            or root is None or root.revision!=policy.attestation_root_revision
            or attestation.token_limit.mode not in policy.allowed_token_modes
            or attestation.observed_at>checked_at+timedelta(seconds=policy.max_future_skew_seconds)
            or checked_at-attestation.observed_at>timedelta(seconds=policy.max_observation_age_seconds)
            or attestation.valid_from<policy.valid_from or attestation.valid_until>policy.valid_until):
            raise ValueError('source policy applicability required')
        return CapacitySupplierDocumentCheck(binding.content_hash,command.source_policy_ref.content_hash,
            command.supplier_attestation_ref.content_hash)
    except Exception:
        raise ProviderCapacityIssuanceBlocked('CAPACITY_SIGNED_SUPPLIER_DOCUMENTS_REQUIRED') from None
