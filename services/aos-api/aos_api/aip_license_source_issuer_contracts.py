"""Exact issuance requests; original approved Proposal remains the authority."""
from dataclasses import dataclass, field
from typing import Literal

from pydantic import Field, StrictInt, ValidationError, field_validator

from aos_api.aip_action_store import canonical_hash
from aos_api.aip_license_source_proposal_contracts import _SourceCommand, _canonical_text
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.tenant_scope import TenantScope


class ApprovedSourceLicenseProposalRef(ExactRevisionRef):
    resource_type: Literal['ActionProposal'] = 'ActionProposal'
    revision: StrictInt = Field(ge=2)

    @field_validator('resource_id', mode='before')
    @classmethod
    def _identifier(cls, value):
        value = _canonical_text(value)
        if any(char.isspace() for char in value):
            raise ValueError('exact approved proposal identifier required')
        return value


class SourceLicenseIssuanceCommand(_SourceCommand):
    approved_proposal: ApprovedSourceLicenseProposalRef


@dataclass(frozen=True, slots=True)
class SourceLicenseIssuanceBinding:
    content_hash: str
    authorization: Literal['ISSUANCE_REQUEST_ONLY_NO_START'] = field(
        default='ISSUANCE_REQUEST_ONLY_NO_START', init=False)


def _source_issuance_request_hash(scope, maker, approved_proposal):
    """Original nonsecret request hash; supplies no authenticated command."""
    return canonical_hash({
        'schema': 'aos-source-license-issuance/v1',
        'tenant': {'orgId': scope.org_id, 'projectId': scope.project_id},
        'maker': maker,
        'approvedProposal': approved_proposal.model_dump(mode='json', by_alias=True),
    })

def source_license_issuance_binding(scope: TenantScope, maker: str,
                                   command: SourceLicenseIssuanceCommand) -> SourceLicenseIssuanceBinding:
    try:
        if type(scope) is not TenantScope or type(command) is not SourceLicenseIssuanceCommand:
            raise ValueError('exact command and scope required')
        _canonical_text(maker)
        if maker == 'unknown' or any(char.isspace() for char in maker):
            raise ValueError('exact authenticated maker required')
        checked = SourceLicenseIssuanceCommand.model_validate(
            command.model_dump(mode='python', by_alias=True))
        if scope.key != (checked.org_id, checked.project_id):
            raise ValueError('command tenant mismatch')
        return SourceLicenseIssuanceBinding(_source_issuance_request_hash(
            scope, maker, checked.approved_proposal))
    except (ValidationError, ValueError, TypeError, AttributeError):
        raise ValueError('SOURCE_LICENSE_ISSUANCE_REQUEST_INVALID') from None
