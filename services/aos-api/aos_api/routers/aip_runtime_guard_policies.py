"""Canonical tenant-scoped runtime egress and data-classification policies."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from aos_api.aip_network_consumer_contracts import NetworkConsumerReferences
from aos_api.aip_network_consumer_application import execute_consumer, ConsumerApplicationBlocked
from aos_api.aip_network_issuer_application import execute_issuer, IssuerApplicationBlocked

from aos_api.aip_runtime_guard_policy_contracts import (
    DataClassificationPolicyRevision,
    DataClassificationPolicyRevisionCreate,
    EgressPolicyRevision,
    EgressPolicyRevisionCreate,
)
from aos_api.aip_runtime_guard_policy_store import (
    AipRuntimeGuardPolicyStore,
    GuardPolicyConflict,
    GuardPolicyDependencyBlocked,
    EgressPolicyApprovalRequired,
    DataPolicyApprovalRequired,
    GuardPolicyIdempotencyConflict,
    GuardPolicyNotFound,
    GuardPolicyStoreError,
)
from aos_api.aip_network_policy_contracts import (
    NetworkPolicyRevision,
    NetworkPolicyRevisionCreate,
)
from aos_api.aip_network_policy_activation_preview import preview_network_activation
from aos_api.aip_network_policy_action_producer import (
    NetworkActivationProposalRequest,
    NetworkPolicyProducerBlocked,
    decide_network_activation,
    propose_network_activation,
)
from aos_api.aip_network_policy_activation_target import NetworkPolicyActivationTargetBlocked
from aos_api.aip_action_models import ActionDraftBundle, DecideActionProposalRequest
from aos_api.aip_action_store import (
    AipActionConflict,
    AipActionIdempotencyConflict,
    AipActionNotFound,
    AipActionStoreError,
    AipActionTransitionBlocked,
)
from aos_api.aip_network_policy_store import (
    AipNetworkPolicyStore,
    NetworkPolicyConflict,
    NetworkPolicyDependencyBlocked,
    NetworkPolicyIdempotencyConflict,
    NetworkPolicyNotFound,
    NetworkPolicyStoreError,
    NetworkPolicyApprovalRequired,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


router = APIRouter(prefix="/v1/aip/runtime-guard-policies", tags=["aip-runtime-guard-policies"])
_STORE = AipRuntimeGuardPolicyStore()
_NETWORK_STORE = AipNetworkPolicyStore()


def get_store() -> AipRuntimeGuardPolicyStore:
    return _STORE


def get_network_store() -> AipNetworkPolicyStore:
    return _NETWORK_STORE


def get_consumer_application_config(request: Request):
    return getattr(request.app.state, 'network_consumer_config', None)


def get_issuer_application_config(request: Request):
    return getattr(request.app.state, 'network_issuer_config', None)


def _issuer_response(proposal_id, body, key, principal, authorization, config, response, *, inquiry):
    try:
        result = execute_issuer(config, proposal_id, key, body, principal, authorization, inquiry=inquiry)
    except IssuerApplicationBlocked as exc:
        raise ApiError(code=exc.code, message='网络策略审批尚未获准或需要对账',
                       status_code=exc.status_code) from None
    response.status_code = {'unresolved': 202, 'observed': 200, 'conflict': 409, 'blocked': 403}[result['status']]
    return result


@router.post('/networks/activation-proposals/{proposal_id}/decision-attempts')
def attempt_network_decision(proposal_id: str, body: DecideActionProposalRequest, response: Response,
                             idempotency_key: str = Header(alias='Idempotency-Key'),
                             authorization: str | None = Header(default=None),
                             principal: Principal = Depends(require_principal),
                             config=Depends(get_issuer_application_config)):
    return _issuer_response(proposal_id, body, idempotency_key, principal, authorization,
                            config, response, inquiry=False)


@router.post('/networks/activation-proposals/{proposal_id}/decision-attempts/inquiry')
def inquire_network_decision(proposal_id: str, body: DecideActionProposalRequest, response: Response,
                             idempotency_key: str = Header(alias='Idempotency-Key'),
                             authorization: str | None = Header(default=None),
                             principal: Principal = Depends(require_principal),
                             config=Depends(get_issuer_application_config)):
    return _issuer_response(proposal_id, body, idempotency_key, principal, authorization,
                            config, response, inquiry=True)


def _consume_response(body, principal, authorization, config, response, *, inquiry):
    try:
        result = execute_consumer(config, body, principal, authorization, inquiry=inquiry)
    except ConsumerApplicationBlocked as exc:
        raise ApiError(code=exc.code, message='网络策略消费尚未获准或需要对账',
                       status_code=exc.status_code) from None
    response.status_code = {'unresolved': 202, 'observed': 200, 'conflict': 409, 'blocked': 403}[result['status']]
    return result


@router.post('/networks/activation-consumptions')
def consume_network(body: NetworkConsumerReferences, response: Response,
                    authorization: str | None = Header(default=None),
                    principal: Principal = Depends(require_principal),
                    config=Depends(get_consumer_application_config)):
    return _consume_response(body, principal, authorization, config, response, inquiry=False)


@router.post('/networks/activation-consumptions/inquiry')
def inquire_network_consumption(body: NetworkConsumerReferences, response: Response,
                               authorization: str | None = Header(default=None),
                               principal: Principal = Depends(require_principal),
                               config=Depends(get_consumer_application_config)):
    return _consume_response(body, principal, authorization, config, response, inquiry=True)


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _key(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 120:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="Idempotency-Key must be 1..120 characters", status_code=400)
    return cleaned


def _version(value: str) -> int:
    cleaned = value.strip().strip('"')
    if not cleaned.isdigit():
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="If-Match must be an integer authority version", status_code=400)
    return int(cleaned)


def _map(exc: GuardPolicyStoreError) -> ApiError:
    if isinstance(exc, GuardPolicyNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, (GuardPolicyConflict, GuardPolicyIdempotencyConflict)):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, GuardPolicyDependencyBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, EgressPolicyApprovalRequired):
        return ApiError(code=exc.code, message="当前出站策略缺少可核验的正式审批，不能发布为生效状态。", status_code=422)
    if isinstance(exc, DataPolicyApprovalRequired):
        return ApiError(code=exc.code, message="当前数据分类策略缺少可核验的正式审批，不能发布为生效状态。", status_code=422)
    return ApiError(code=exc.code, message="runtime guard policy persistence failed", status_code=503)


def _publish(method: str, body, key: str, if_match: str, principal: Principal, store: AipRuntimeGuardPolicyStore):
    try:
        return getattr(store, method)(
            _scope(principal),
            principal.subject,
            _key(key),
            body,
            expected_version=_version(if_match),
        )
    except GuardPolicyStoreError as exc:
        raise _map(exc) from exc


def _get(method: str, policy_id: str, revision: int | None, principal: Principal, store: AipRuntimeGuardPolicyStore):
    try:
        return getattr(store, method)(_scope(principal), policy_id, revision)
    except GuardPolicyStoreError as exc:
        raise _map(exc) from exc


def _map_network(exc: NetworkPolicyStoreError) -> ApiError:
    if isinstance(exc, NetworkPolicyNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, (NetworkPolicyConflict, NetworkPolicyIdempotencyConflict)):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, NetworkPolicyDependencyBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, NetworkPolicyApprovalRequired):
        return ApiError(code=exc.code, message="当前网络策略缺少可核验的正式审批，不能发布为生效状态。", status_code=422)
    return ApiError(code=exc.code, message="network policy persistence failed", status_code=503)


@router.post("/egress", response_model=EgressPolicyRevision, status_code=status.HTTP_201_CREATED)
def publish_egress(
    body: EgressPolicyRevisionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    principal: Principal = Depends(require_principal),
    store: AipRuntimeGuardPolicyStore = Depends(get_store),
):
    return _publish("publish_egress", body, idempotency_key, if_match, principal, store)


@router.get("/egress/{policy_id}", response_model=EgressPolicyRevision)
def get_egress(
    policy_id: str,
    revision: int | None = Query(default=None, ge=1),
    principal: Principal = Depends(require_principal),
    store: AipRuntimeGuardPolicyStore = Depends(get_store),
):
    return _get("get_egress", policy_id, revision, principal, store)


@router.post("/data-classifications", response_model=DataClassificationPolicyRevision, status_code=status.HTTP_201_CREATED)
def publish_data_classification(
    body: DataClassificationPolicyRevisionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    principal: Principal = Depends(require_principal),
    store: AipRuntimeGuardPolicyStore = Depends(get_store),
):
    return _publish("publish_data_classification", body, idempotency_key, if_match, principal, store)


@router.get("/data-classifications/{policy_id}", response_model=DataClassificationPolicyRevision)
def get_data_classification(
    policy_id: str,
    revision: int | None = Query(default=None, ge=1),
    principal: Principal = Depends(require_principal),
    store: AipRuntimeGuardPolicyStore = Depends(get_store),
):
    return _get("get_data_classification", policy_id, revision, principal, store)


@router.post("/networks", response_model=NetworkPolicyRevision, status_code=status.HTTP_201_CREATED)
def publish_network(
    body: NetworkPolicyRevisionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    principal: Principal = Depends(require_principal),
    store: AipNetworkPolicyStore = Depends(get_network_store),
):
    try:
        return store.publish(
            _scope(principal), principal.subject, _key(idempotency_key), body,
            expected_version=_version(if_match),
        )
    except NetworkPolicyStoreError as exc:
        raise _map_network(exc) from exc


@router.post("/networks/activation-preview")
def preview_network(
    body: NetworkPolicyRevisionCreate,
    if_match: str = Header(alias="If-Match"),
    principal: Principal = Depends(require_principal),
    store: AipNetworkPolicyStore = Depends(get_network_store),
):
    return preview_network_activation(
        _scope(principal), body, expected_version=_version(if_match), store=store,
    )


@router.post("/networks/activation-proposals", response_model=ActionDraftBundle, status_code=status.HTTP_201_CREATED)
def propose_network(
    body: NetworkActivationProposalRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    principal: Principal = Depends(require_principal),
):
    try:
        return propose_network_activation(
            principal, body.candidate, expected_version=_version(if_match),
            idempotency_key=_key(idempotency_key), expires_at=body.expires_at,
        )
    except NetworkPolicyProducerBlocked as exc:
        code = str(exc)
        raise ApiError(code=code, message="当前正式网络策略动作来源或身份不满足要求", status_code=403 if code.startswith("OIDC_") else 422) from exc
    except (NetworkPolicyActivationTargetBlocked, AipActionTransitionBlocked) as exc:
        raise ApiError(code="AIP_NETWORK_PROPOSAL_BLOCKED", message=str(exc), status_code=422) from exc
    except (AipActionIdempotencyConflict, AipActionConflict) as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=409) from exc
    except AipActionNotFound as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=404) from exc
    except AipActionStoreError as exc:
        raise ApiError(code=exc.code, message="network action proposal persistence failed", status_code=503) from exc


@router.post("/networks/activation-proposals/{proposal_id}/decision", response_model=ActionDraftBundle)
def decide_network(
    proposal_id: str,
    body: DecideActionProposalRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
):
    try:
        return decide_network_activation(principal, proposal_id, _key(idempotency_key), body)
    except NetworkPolicyProducerBlocked as exc:
        code = str(exc)
        raise ApiError(code=code, message="当前正式网络策略审批身份或绑定不满足要求", status_code=403 if code.startswith("OIDC_") else 422) from exc
    except (AipActionIdempotencyConflict, AipActionConflict) as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=409) from exc
    except AipActionNotFound as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=404) from exc
    except AipActionTransitionBlocked as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=422) from exc
    except AipActionStoreError as exc:
        raise ApiError(code=exc.code, message="network action decision persistence failed", status_code=503) from exc


@router.get("/networks/{policy_id}", response_model=NetworkPolicyRevision)
def get_network(
    policy_id: str,
    revision: int | None = Query(default=None, ge=1),
    principal: Principal = Depends(require_principal),
    store: AipNetworkPolicyStore = Depends(get_network_store),
):
    try:
        return store.get(_scope(principal), policy_id, revision)
    except NetworkPolicyStoreError as exc:
        raise _map_network(exc) from exc
