"""Provider Health Action template plugin package acceptance."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aos_api.action_template_registry import (
    DEFAULTS,
    REQUIRED,
    _template_from_manifest,
    install_plugin,
    list_action_plugins,
    uninstall_plugin,
)
from aos_api.aip_action_store import AipActionStore
from aos_api.aip_provider_health_action import PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
from aos_api.aip_provider_health_action_authority import (
    provider_health_action_type_snapshot,
)
from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.routers.wave_ext import _require_action_plugin_mutation_authority
from aos_api.tenant_scope import TenantScope, bind_tenant_scope

SCOPE = TenantScope("org-org", "dev-project")
MANIFEST = (
    Path(__file__).resolve().parents[4]
    / "plugins"
    / "actions"
    / "provider-health-probe"
    / "manifest.json"
)


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_maps_exactly_to_code_backed_action_snapshot() -> None:
    manifest = _manifest()
    assert manifest["id"] == "provider-health-probe"
    assert manifest["actionTypeId"] == PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
    assert manifest["runtime"] == "stub"
    assert manifest["configSchema"] == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    template = _template_from_manifest(manifest)
    template.pop("pluginId")
    expected = provider_health_action_type_snapshot()
    assert template == {key: expected[key] for key in template}
    from aos_api.aip_action_store import canonical_hash

    assert canonical_hash(template) == expected["revisionHash"]


def test_manifest_contains_no_endpoint_model_prompt_or_secret_configuration() -> None:
    encoded = MANIFEST.read_text(encoding="utf-8").lower()
    for forbidden in (
        "apikey",
        "api_key",
        "secretref",
        "password",
        "endpoint",
        "prompt",
        "baseurl",
        "base_url",
    ):
        assert forbidden not in encoded


def test_catalog_discovers_plugin_without_default_or_required_install() -> None:
    assert "provider-health-probe" not in DEFAULTS
    assert "provider-health-probe" not in REQUIRED
    with bind_tenant_scope(SCOPE):
        items = {
            item["id"]: item for item in list_action_plugins()["items"]
        }
    item = items["provider-health-probe"]
    assert item["actionTypeId"] == PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
    assert item["required"] is False
    assert item["installed"] is False


@pytest.mark.parametrize(
    "principal",
    [
        Principal(
            subject="user:developer",
            org_id=SCOPE.org_id,
            project_id=SCOPE.project_id,
            roles=["developer"],
        ),
        Principal(
            subject="user:admin",
            org_id="dev-org",
            project_id="dev-project",
            roles=["admin"],
        ),
    ],
)
def test_provider_health_plugin_mutation_rejects_wrong_authority_before_write(
    principal: Principal,
) -> None:
    with pytest.raises(ApiError) as error:
        _require_action_plugin_mutation_authority(
            "provider-health-probe",
            principal,
        )
    assert error.value.code == "FORBIDDEN"
    assert error.value.status_code == 403


def test_provider_health_plugin_mutation_accepts_canonical_admin() -> None:
    _require_action_plugin_mutation_authority(
        "provider-health-probe",
        Principal(
            subject="user:admin",
            org_id=SCOPE.org_id,
            project_id=SCOPE.project_id,
            roles=["admin"],
        ),
    )


def test_explicit_test_install_persists_exact_snapshot_only() -> None:
    with bind_tenant_scope(SCOPE):
        result = install_plugin("provider-health-probe")
        try:
            assert result == {
                "id": "provider-health-probe",
                "installed": True,
                "actionTypeId": PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
            }
            installed = AipActionStore().action_type_snapshot(
                SCOPE, PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
            )
            assert installed == provider_health_action_type_snapshot()
        finally:
            uninstall_plugin("provider-health-probe")
    with bind_tenant_scope(SCOPE):
        item = next(
            item
            for item in list_action_plugins()["items"]
            if item["id"] == "provider-health-probe"
        )
    assert item["installed"] is False
