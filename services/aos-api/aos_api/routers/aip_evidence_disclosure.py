"""W-L10 Evidence disclosure resolve/get API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractError,
)
from aos_api.aip_production_contracts import (
    EvidenceDisclosureDecision,
    ResolveEvidenceDisclosureRequest,
)
from aos_api.auth import Principal, require_principal
from aos_api.routers.aip_production_contracts import _key, _map, _scope, get_store

router = APIRouter(prefix="/v1/aip/evidence", tags=["aip-evidence-disclosure"])


@router.post("/disclosures/resolve", response_model=EvidenceDisclosureDecision, status_code=201)
def resolve_disclosure(
    body: ResolveEvidenceDisclosureRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipProductionContractStore = Depends(get_store),
):
    try:
        return store.resolve_evidence_disclosure(
            _scope(principal),
            principal.subject,
            _key(idempotency_key),
            body,
            markings=principal.markings,
        )
    except ProductionContractError as exc:
        raise _map(exc) from exc


@router.get("/disclosures/{decision_id}", response_model=EvidenceDisclosureDecision)
def get_disclosure(
    decision_id: str,
    principal: Principal = Depends(require_principal),
    store: AipProductionContractStore = Depends(get_store),
):
    try:
        return store.get_evidence_disclosure(
            _scope(principal),
            decision_id,
            markings=principal.markings,
            enforce_current_policy=True,
        )
    except ProductionContractError as exc:
        raise _map(exc) from exc
