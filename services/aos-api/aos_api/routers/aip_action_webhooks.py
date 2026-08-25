"""Provider-facing canonical Action webhook ingress."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from aos_api.aip_action_webhook_models import ActionWebhookInboxSnapshot
from aos_api.aip_action_webhook_service import (
    ActionWebhookError,
    AipActionWebhookService,
    get_action_webhook_service,
)
from aos_api.errors import ApiError

router = APIRouter(tags=["aip-action-webhooks"])


@router.post(
    "/v1/aip/action-webhooks/{endpoint_key}/events",
    response_model=ActionWebhookInboxSnapshot,
    status_code=202,
)
async def receive_action_webhook(
    endpoint_key: str,
    request: Request,
    service: AipActionWebhookService = Depends(get_action_webhook_service),
) -> ActionWebhookInboxSnapshot:
    # This ingress intentionally does not consume browser/internal Principal or
    # X-Org-Id/X-Project-Id. Tenant authority comes only from endpoint identity.
    body = await request.body()
    try:
        return service.receive(endpoint_key, request.headers, body)
    except ActionWebhookError as exc:
        raise ApiError(code=exc.code, message="webhook request was rejected", status_code=exc.status_code) from exc
