import os

import pytest

from aos_api.db import init_schema, seed_if_empty
from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.metrics import reset_metrics
from aos_api.module_store import seed_modules_if_empty
from aos_api import mock_data
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    # Unit tests must not hit real Agnes / network LLM
    for k in (
        "AGNES_API_KEY",
        "AGNES_BASE_URL",
        "AGNES_TEXT_MODEL",
        "AGNES_IMAGE_MODEL",
        "AOS_LITELLM_URL",
    ):
        os.environ.pop(k, None)
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    # ensure schema for ontology tests
    try:
        init_schema()
        seed_if_empty()
        seed_modules_if_empty()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"PG unavailable: {exc}")
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers():
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
        "X-Trace-Id": "test-trace-1",
    }
