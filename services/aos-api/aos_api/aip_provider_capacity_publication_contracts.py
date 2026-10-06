"""Untrusted signed-body transport. Parsing never authenticates or grants rights."""
import base64
import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef, FormalEvaluationTenant
from aos_api.aip_provider_capacity_source_contracts import (
    CapacitySourceDeploymentTarget, FixedWindowTokenLimit, InflightTokenLimit,
    ProviderCapacitySourcePolicy, SupplierCapacityAttestation, _identifier, _window,
)
from aos_api.asset_registry.canonical_json import canonical_json


class _PublicationDocument(AipContractModel):
    model_config = ConfigDict(revalidate_instances="always", hide_input_in_errors=True)
    schema_version: StrictInt = Field(ge=1, le=1)
    tenant: FormalEvaluationTenant
    asset_id: StrictStr
    revision: StrictInt = Field(ge=1)
    publisher: StrictStr
    key_id: StrictStr
    valid_from: datetime
    valid_until: datetime
    deployment_target: CapacitySourceDeploymentTarget

    @field_validator("asset_id", "publisher", "key_id")
    @classmethod
    def identifiers(cls, value):
        return _identifier(value)

    @model_validator(mode="after")
    def validity(self):
        _window(self.valid_from, self.valid_until)
        return self


def _refs(refs, kinds):
    if (any(ref.asset_type not in kinds for ref in refs)
        or len({(r.asset_type, r.asset_id) for r in refs}) != len(refs)):
        raise ValueError("unique exact references of the required kind expected")
    for ref in refs:
        _identifier(ref.asset_id)


class ProviderCapacityOriginBootstrap(_PublicationDocument):
    purpose: Literal["provider_capacity_origin_bootstrap"]
    bootstrap_id: StrictStr
    publisher_subject: StrictStr
    policy_publisher_role: Literal["aos_provider_capacity_policy_publisher"]
    anchor_revision: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    root_snapshot_hash: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    allowed_document_refs: list[FormalExactRef] = Field(min_length=1, max_length=1000)

    @field_validator("bootstrap_id", "publisher_subject")
    @classmethod
    def bootstrap_identifiers(cls, value):
        return _identifier(value)

    @model_validator(mode="after")
    def allowed_documents(self):
        _refs(self.allowed_document_refs, {"ProviderCapacitySourcePolicyRevision",
            "SupplierCapacityAttestationRevision", "ProviderCapacitySigningPermitRevision"})
        return self


class ProviderCapacitySigningPermit(_PublicationDocument):
    purpose: Literal["provider_capacity_source_signing_permit"]
    source_policy_ref: FormalExactRef
    signer_publisher: StrictStr
    signer_key_id: StrictStr
    signer_root_revision: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    signer_public_key: StrictStr = Field(min_length=44, max_length=44)

    @field_validator("signer_publisher", "signer_key_id")
    @classmethod
    def signer_identifiers(cls, value):
        return _identifier(value)

    @field_validator("signer_public_key")
    @classmethod
    def canonical_public_key(cls, value):
        decoded = base64.b64decode(value, validate=True)
        if len(decoded) != 32 or base64.b64encode(decoded).decode("ascii") != value:
            raise ValueError("canonical Ed25519 public key required")
        return value

    @model_validator(mode="after")
    def parent_policy(self):
        _refs([self.source_policy_ref], {"ProviderCapacitySourcePolicyRevision"})
        return self


class PublishedProviderCapacitySource(_PublicationDocument):
    purpose: Literal["provider_capacity_published_source"]
    physical_account_id: StrictStr
    supplier_id: StrictStr
    supplier_account_fingerprint: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    provider_refs: list[FormalExactRef] = Field(min_length=1, max_length=1000)
    evidence_refs: list[FormalExactRef] = Field(min_length=1, max_length=1000)
    source_proposal_ref: FormalExactRef
    source_approval_ref: FormalExactRef
    allocation_request_ref: FormalExactRef
    allocation_approval_ref: FormalExactRef
    account_candidate_ref: FormalExactRef
    basis_candidate_ref: FormalExactRef
    source_policy_ref: FormalExactRef
    supplier_attestation_ref: FormalExactRef
    signing_permit_ref: FormalExactRef
    origin_ref: FormalExactRef
    origin_epoch: StrictInt = Field(ge=0)
    source_withdrawal_epoch: StrictInt = Field(ge=0)
    allocation_withdrawal_epoch: StrictInt = Field(ge=0)
    request_hash: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    max_concurrency: StrictInt = Field(ge=1, le=1000000)
    token_limit: Annotated[InflightTokenLimit | FixedWindowTokenLimit, Field(discriminator="mode")]
    observed_at: datetime
    issued_at: datetime
    execution_allowed: StrictBool

    @field_validator("physical_account_id")
    @classmethod
    def stable_database_id(cls, value):
        if str(UUID(value)) != value:
            raise ValueError("canonical server account UUID required")
        return value

    @field_validator("supplier_id")
    @classmethod
    def supplier_identifier(cls, value):
        return _identifier(value)

    @model_validator(mode="after")
    def provenance(self):
        _refs(self.provider_refs, {"ProviderInstanceRevision"})
        _refs(self.evidence_refs, {"EvidenceBundleRevision"})
        kinds = {
            "source_proposal_ref":"ActionProposal", "source_approval_ref":"ActionApprovalEvent",
            "allocation_request_ref":"ProviderCapacityRequest", "allocation_approval_ref":"ActionApprovalEvent",
            "account_candidate_ref":"ProviderPhysicalAccountCandidateRevision",
            "basis_candidate_ref":"ProviderCapacityBasisCandidateRevision",
            "source_policy_ref":"ProviderCapacitySourcePolicyRevision",
            "supplier_attestation_ref":"SupplierCapacityAttestationRevision",
            "signing_permit_ref":"ProviderCapacitySigningPermitRevision",
            "origin_ref":"ProviderCapacityOriginBootstrapRevision",
        }
        for name, kind in kinds.items():
            _refs([getattr(self, name)], {kind})
        for name, revision in (("source_proposal_ref", 2), ("source_approval_ref", 1),
                               ("allocation_request_ref", 1), ("allocation_approval_ref", 1)):
            if getattr(self, name).revision != revision:
                raise ValueError("original approval reference revision required")
        if self.source_approval_ref.asset_id == self.allocation_approval_ref.asset_id:
            raise ValueError("distinct original approvals required")
        if (self.execution_allowed is not False or self.issued_at.utcoffset() is None
            or self.observed_at.utcoffset() is None
            or not self.valid_from <= self.issued_at < self.valid_until
            or self.observed_at > self.issued_at):
            raise ValueError("nonexecuting source with aware issuance and observation required")
        return self


class CapacitySourceIssuanceContext(AipContractModel):
    """Signed claims only; authentic subject/native transaction must be rechecked."""
    model_config = ConfigDict(revalidate_instances="always", hide_input_in_errors=True)
    maker_subject: StrictStr
    oidc_issuer: StrictStr = Field(min_length=1, max_length=2000)
    oidc_audience: StrictStr
    authentication_expires_at: datetime
    issuer_role: Literal["aos_provider_capacity_issuer"]
    transaction_id: StrictStr = Field(min_length=1, max_length=20, pattern=r"^[1-9][0-9]*$")
    backend_pid: StrictInt = Field(ge=1, le=2147483647)
    attempt_id: StrictStr

    @field_validator("maker_subject", "oidc_audience")
    @classmethod
    def identity_claim(cls, value):
        _identifier(value)
        if value == "unknown":
            raise ValueError("explicit issuance identity claim required")
        return value

    @field_validator("oidc_issuer")
    @classmethod
    def issuer_url(cls, value):
        if (value != value.strip() or not value.isprintable()
            or any(char.isspace() for char in value) or "?" in value or "#" in value):
            raise ValueError("exact HTTPS issuer claim required")
        parsed = urlsplit(value)
        if (not value.startswith("https://") or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or (parsed.port is not None and not 1 <= parsed.port <= 65535)):
            raise ValueError("exact HTTPS issuer claim required")
        return value

    @field_validator("transaction_id")
    @classmethod
    def xid8_claim(cls, value):
        if int(value) > 18446744073709551615:
            raise ValueError("bounded native xid8 claim required")
        return value

    @field_validator("attempt_id")
    @classmethod
    def attempt_claim(cls, value):
        if str(UUID(value)) != value:
            raise ValueError("canonical server attempt UUID claim required")
        return value

    @field_validator("authentication_expires_at")
    @classmethod
    def aware_authentication_expiry(cls, value):
        if value.utcoffset() is None:
            raise ValueError("aware issuance authentication expiry required")
        return value


class PublishedProviderCapacitySourceV2(PublishedProviderCapacitySource):
    """Explicit v2 signed transcript, without JWT/signature/native authorization."""
    schema_version: StrictInt = Field(ge=2, le=2)
    issuance_context: CapacitySourceIssuanceContext

    @model_validator(mode="after")
    def issuance_authentication_window(self):
        if self.issuance_context.authentication_expires_at <= self.issued_at:
            raise ValueError("issuance must precede authentication expiry")
        return self


class CapacitySignedBodyProfileError(ValueError):
    """Safe rejection category; never contains caller bytes or field values."""
    def __init__(self, reason):
        self.reason = reason
        super().__init__("CAPACITY_SIGNED_BODY_PROFILE_REQUIRED:" + reason)


def parse_signed_capacity_body(raw: bytes, document_type):
    """Reject ambiguous encodings; returned model is still unauthenticated."""
    allowed = (ProviderCapacityOriginBootstrap, ProviderCapacitySigningPermit,
               PublishedProviderCapacitySource, PublishedProviderCapacitySourceV2,
               ProviderCapacitySourcePolicy, SupplierCapacityAttestation)
    if document_type not in allowed or type(raw) is not bytes:
        raise CapacitySignedBodyProfileError("TYPE")
    if not 0 < len(raw) <= 2 * 1024 * 1024:
        raise CapacitySignedBodyProfileError("SIZE")
    try:
        text = raw.decode("utf-8", errors="strict")
        depth = 0
        quoted = escaped = False
        for char in text:
            if quoted:
                if escaped: escaped = False
                elif char == "\\": escaped = True
                elif char == '"': quoted = False
            elif char == '"': quoted = True
            elif char in "[{":
                depth += 1
                if depth > 32: raise CapacitySignedBodyProfileError("DEPTH")
            elif char in "]}": depth -= 1

        def pairs(items):
            result = {}
            for key, value in items:
                if key in result: raise CapacitySignedBodyProfileError("DUPLICATE_KEY")
                result[key] = value
            return result

        def forbidden(value):
            raise CapacitySignedBodyProfileError("NON_INTEGER")

        payload = json.loads(text, object_pairs_hook=pairs, parse_float=forbidden, parse_constant=forbidden)

        def bounded(value):
            if isinstance(value, str):
                if "\x00" in value: raise CapacitySignedBodyProfileError("NUL")
                value.encode("utf-8", errors="strict")
            elif isinstance(value, list):
                if len(value) > 1000: raise CapacitySignedBodyProfileError("ARRAY")
                for item in value: bounded(item)
            elif isinstance(value, dict):
                if len(value) > 1000: raise CapacitySignedBodyProfileError("OBJECT")
                for key, item in value.items(): bounded(key); bounded(item)
        bounded(payload)
        model = document_type.model_validate(payload)
        if canonical_json(model.model_dump(mode="json", by_alias=True)) != raw:
            raise CapacitySignedBodyProfileError("NONCANONICAL")
        return model
    except CapacitySignedBodyProfileError:
        raise
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise CapacitySignedBodyProfileError("INVALID_DOCUMENT") from None
