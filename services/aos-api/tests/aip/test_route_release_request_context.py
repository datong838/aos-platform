import json

import pytest
from pydantic import SecretStr

from aos_api.aip_route_release_request_context import (
    RouteReleaseRequestContext,
    RouteReleaseRequestContextRejected,
    build_route_release_request_context,
    optional_route_release_request_context,
)
from aos_api.auth import Principal


TOKEN = "header.payload.signature"


def principal(*, kind="oidc", org="org-org", project="dev-project"):
    return Principal(subject="operator", org_id=org, project_id=project,
        roles=["operator"], token_kind=kind)


def test_current_oidc_context_keeps_bearer_server_only_and_masked():
    context = build_route_release_request_context(
        principal=principal(), authorization="Bearer " + TOKEN)
    assert type(context) is RouteReleaseRequestContext
    assert type(context.bearer_token) is SecretStr
    assert context.bearer_token.get_secret_value() == TOKEN
    assert TOKEN not in repr(context) and TOKEN not in str(context)
    with pytest.raises(TypeError):
        json.dumps(context)


@pytest.mark.parametrize("fault", ["dev", "org", "project", "header", "shape"])
def test_route_release_context_rejects_noncurrent_or_non_oidc_authority(fault):
    value = principal(
        kind="dev" if fault == "dev" else "oidc",
        org="dev-org" if fault == "org" else "org-org",
        project="other" if fault == "project" else "dev-project",
    )
    authorization = None if fault == "header" else (
        "Bearer opaque" if fault == "shape" else "Bearer " + TOKEN)
    with pytest.raises(RouteReleaseRequestContextRejected):
        build_route_release_request_context(
            principal=value, authorization=authorization)


def test_optional_route_context_preserves_nonroute_authenticated_paths():
    assert optional_route_release_request_context(
        authorization="Bearer dev", principal=principal(kind="dev", org="dev-org")) is None
    context = optional_route_release_request_context(
        authorization="Bearer " + TOKEN, principal=principal())
    assert type(context) is RouteReleaseRequestContext
    assert context.bearer_token.get_secret_value() == TOKEN
