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


def check_native_capacity_supplier_inputs(conn,command,policy_document,attestation_document,*,trust_roots):
    """Match authentic signed material to original approved rows in one caller.

    This is a nonexecuting pre-publication check, not a formal Source. Database
    deployment identity, root/policy COMMIT coordination and global mapping
    remain mandatory for the publication transaction; never consume this
    return value as authority instead of rechecking the original inputs.
    """
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
    from aos_api.aip_provider_capacity_source_contracts import (
        ProviderPhysicalAccountCandidate,ProviderCapacityBasisCandidate,
        SignedCapacitySourcePolicy,SignedSupplierCapacityAttestation)
    try:
        if (type(command) is not ProviderCapacityIssuanceCommand
            or type(policy_document) is not SignedCapacitySourcePolicy
            or type(attestation_document) is not SignedSupplierCapacityAttestation):
            raise ValueError('exact original command and signed documents required')
        command=ProviderCapacityIssuanceCommand.model_validate(command.model_dump(mode='python',by_alias=True))
        policy_document=SignedCapacitySourcePolicy.model_validate(policy_document.model_dump(mode='python',by_alias=True))
        attestation_document=SignedSupplierCapacityAttestation.model_validate(attestation_document.model_dump(mode='python',by_alias=True))
        approved=read_capacity_approved_claims(conn,command)
        scope=TenantScope(command.tenant.org_id,command.tenant.project_id)
        source=approved.source
        account=ProviderCapacitySourceActionGuard._candidate(conn,scope,source.physical_account_ref,'account',
            ProviderPhysicalAccountCandidate,approved.maker)
        basis=ProviderCapacitySourceActionGuard._candidate(conn,scope,source.basis_ref,'basis',
            ProviderCapacityBasisCandidate,approved.maker)
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        check_signed_capacity_documents(command,approved.maker,policy_document,attestation_document,
            trust_roots=trust_roots,checked_at=now)
        policy,attestation=policy_document.payload,attestation_document.payload
        def exact_providers(refs):
            return sorted((ref.asset_type,ref.asset_id,ref.revision,ref.content_hash) for ref in refs)
        if ((attestation.supplier_id,attestation.supplier_account_fingerprint)
            !=(account.supplier_id,account.supplier_account_fingerprint)
            or exact_providers(attestation.provider_refs)!=exact_providers(account.provider_refs)
            or attestation.evidence_ref!=basis.evidence_ref
            or attestation.max_concurrency<basis.max_concurrency
            or attestation.token_limit.mode!=basis.token_limit.mode
            or attestation.token_limit.unit!=basis.token_limit.unit
            or attestation.token_limit.max_tokens<basis.token_limit.max_tokens
            or not attestation.valid_from<=source.valid_from<source.valid_until<=attestation.valid_until
            or not policy.valid_from<=source.valid_from<source.valid_until<=policy.valid_until
            or not basis.valid_from<=source.valid_from<source.valid_until<=basis.valid_until
            or (basis.basis_kind=='supplier_limit_claim' and attestation.observed_at!=basis.observed_at)):
            raise ValueError('signed supplier source must cover exact approved terms')
        if basis.token_limit.mode=='fixed_window_rate' and (
            attestation.token_limit.window_seconds!=basis.token_limit.window_seconds
            or attestation.token_limit.window_anchor!=basis.token_limit.window_anchor):
            raise ValueError('same rate window required; no implicit conversion')
        principal=authenticate_capacity_issuance_command(command)
        if principal.subject!=approved.maker:raise ValueError('authenticated maker changed')
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        events=conn.execute('SELECT e.approval_event_id,e.expires_at AS event_expiry,p.expires_at AS proposal_expiry '
            'FROM public.aip_action_approval_event e JOIN public.aip_action_proposal p '
            'ON (p.org_id,p.project_id,p.proposal_id)=(e.org_id,e.project_id,e.proposal_id) '
            'WHERE e.org_id=%s AND e.project_id=%s AND e.approval_event_id=ANY(%s)',
            (*scope.key,[command.approval_event.asset_id,source.allocation_approval_ref.asset_id])).fetchall()
        if (len(events)!=2 or {row['approval_event_id'] for row in events}
            !={command.approval_event.asset_id,source.allocation_approval_ref.asset_id}
            or any(row['event_expiry'] is None or row['proposal_expiry'] is None
                or row['event_expiry']<=now or row['proposal_expiry']<=now for row in events)
            or not source.valid_from<=now<source.valid_until):
            raise ValueError('original approvals and terms expired')
        return check_signed_capacity_documents(command,approved.maker,policy_document,attestation_document,
            trust_roots=trust_roots,checked_at=now)
    except Exception:
        raise ProviderCapacityIssuanceBlocked('CAPACITY_NATIVE_SIGNED_SUPPLIER_INPUTS_REQUIRED') from None


def capacity_source_preparation_bytes(command):
    """Build secret-free untrusted SQL input from verified original identity.

    The DB independently validates original facts. The controlled signer must
    authenticate the original JWT again and compare these hints to the exact
    pending transcript; these bytes themselves are never signing authority.
    """
    from datetime import UTC,datetime
    import os
    from aos_api.oidc import verify_access_token
    from aos_api.aip_provider_capacity_publication_contracts import CapacitySourceAuthenticationClaims
    from aos_api.asset_registry.canonical_json import canonical_json
    try:
        principal=authenticate_capacity_issuance_command(command)
        claims=verify_access_token(command.bearer_token.get_secret_value())
        audience=os.environ.get('AOS_OIDC_AUDIENCE','').strip()
        actual_audience=claims.get('aud')
        if (type(claims.get('sub')) is not str or claims['sub']!=principal.subject
            or type(claims.get('exp')) is not int or type(claims.get('iss')) is not str
            or not (actual_audience==audience or (type(actual_audience) is list and audience in actual_audience))):
            raise ValueError('original exact verified identity claims required')
        hint=CapacitySourceAuthenticationClaims(makerSubject=principal.subject,
            oidcIssuer=claims['iss'],oidcAudience=audience,
            authenticationExpiresAt=datetime.fromtimestamp(claims['exp'],UTC))
        if hint.authentication_expires_at<=datetime.now(UTC):
            raise ValueError('current authentication required')
        return canonical_json(dict(protocol='aos-provider-capacity-source-command/v1',
            makerSubject=principal.subject,
            requestHash=capacity_issuance_binding(TenantScope(principal.org_id,principal.project_id),
                principal.subject,command).content_hash,
            command=command.model_dump(mode='json',by_alias=True,exclude={'bearer_token','idempotency_key'}),
            authentication=hint.model_dump(mode='json',by_alias=True)))
    except Exception:
        raise ProviderCapacityIssuanceBlocked('CAPACITY_SOURCE_PREPARATION_AUTHENTICATION_REQUIRED') from None
