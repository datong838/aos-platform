"""Closed product command envelope over the existing exact phase contracts."""
from typing import Literal
from pydantic import model_validator
from aos_api.aip_contracts import AipContractModel
from aos_api.ecommerce_growth_cutover import (
    CutoverPrepareRequest, CutoverCommitRequest, CutoverFinalizeRequest,
    CutoverRollbackRequest, CutoverExactRef,
)
from aos_api.ecommerce_growth_cutover_control import _PHASES


class CutoverProductCommand(AipContractModel):
    phase: Literal['prepare','pause','commit','validate','resume','rollback-prepare','rollback-commit']
    request: CutoverPrepareRequest | CutoverCommitRequest | CutoverFinalizeRequest | CutoverRollbackRequest
    validate_receipt_ref: CutoverExactRef | None = None

    @model_validator(mode='after')
    def _exact_phase(self):
        if type(self.request) is not _PHASES[self.phase][0]:
            raise ValueError('request does not match cutover phase')
        if self.phase=='prepare' and self.request.registration_receipt_ref is None:
            raise ValueError('first cutover requires registration origin')
        if self.phase=='resume':
            if self.validate_receipt_ref is None or self.validate_receipt_ref.resource_type!='CutoverValidateReceipt':
                raise ValueError('resume requires exact validation receipt')
        elif self.validate_receipt_ref is not None:
            raise ValueError('unexpected validation receipt')
        return self
