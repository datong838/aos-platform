"""Executable M5 contract checks for the synthetic InstanceOverlay file."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    REPO_ROOT
    / "packages/contracts/schemas/asset-bundles/"
    / "instance-overlay-v1alpha1.schema.json"
)
FIXTURE_PATH = Path(__file__).parent / "fixtures/m5/instance-overlay.synthetic.json"
SCHEMA: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
FIXTURE: dict[str, Any] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _resolve_ref(ref: str) -> dict[str, Any]:
    assert ref.startswith("#/$defs/")
    return SCHEMA["$defs"][ref.removeprefix("#/$defs/")]


def _validation_errors(
    instance: Any,
    schema: dict[str, Any] | None = None,
    *,
    path: str = "$",
) -> list[str]:
    """Validate the closed JSON Schema keyword subset used by this fixture."""

    current = SCHEMA if schema is None else schema
    if "$ref" in current:
        return _validation_errors(instance, _resolve_ref(current["$ref"]), path=path)

    errors: list[str] = []
    if "const" in current and (
        type(instance) is not type(current["const"]) or instance != current["const"]
    ):
        errors.append(f"{path}: const mismatch")
    if "enum" in current and instance not in current["enum"]:
        errors.append(f"{path}: outside enum")

    expected_type = current.get("type")
    type_matches = {
        "object": isinstance(instance, dict),
        "array": isinstance(instance, list),
        "string": isinstance(instance, str),
        "integer": isinstance(instance, int) and not isinstance(instance, bool),
        "boolean": isinstance(instance, bool),
    }.get(expected_type, True)
    if not type_matches:
        return [f"{path}: expected {expected_type}"]

    if isinstance(instance, dict):
        properties = current.get("properties", {})
        for required in current.get("required", []):
            if required not in instance:
                errors.append(f"{path}: missing {required}")
        if current.get("additionalProperties") is False:
            for key in instance.keys() - properties.keys():
                errors.append(f"{path}: unknown {key}")
        for key, value in instance.items():
            if key in properties:
                errors.extend(
                    _validation_errors(value, properties[key], path=f"{path}.{key}")
                )

    if isinstance(instance, list):
        if len(instance) < current.get("minItems", 0):
            errors.append(f"{path}: too few items")
        if "maxItems" in current and len(instance) > current["maxItems"]:
            errors.append(f"{path}: too many items")
        if current.get("uniqueItems") and any(
            value in instance[:index] for index, value in enumerate(instance)
        ):
            errors.append(f"{path}: duplicate items")
        if "items" in current:
            for index, value in enumerate(instance):
                errors.extend(
                    _validation_errors(value, current["items"], path=f"{path}[{index}]")
                )

    if isinstance(instance, str):
        if len(instance) < current.get("minLength", 0):
            errors.append(f"{path}: too short")
        if "maxLength" in current and len(instance) > current["maxLength"]:
            errors.append(f"{path}: too long")
        if "pattern" in current and re.search(current["pattern"], instance) is None:
            errors.append(f"{path}: pattern mismatch")

    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in current and instance < current["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in current and instance > current["maximum"]:
            errors.append(f"{path}: above maximum")
    return errors


def _assert_valid(instance: Any) -> None:
    assert _validation_errors(instance) == []


def _assert_invalid(instance: Any) -> None:
    assert _validation_errors(instance)


def test_schema_and_fixture_freeze_one_closed_synthetic_contract() -> None:
    assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert SCHEMA["additionalProperties"] is False
    assert set(SCHEMA["required"]) == set(SCHEMA["properties"])
    assert SCHEMA["properties"]["apiVersion"]["const"] == "aos.dev/v1alpha1"
    assert SCHEMA["properties"]["kind"]["const"] == "InstanceOverlay"
    assert all(
        definition["additionalProperties"] is False
        for definition in (
            SCHEMA["$defs"]["metadata"],
            SCHEMA["$defs"]["compositionLockRef"],
            SCHEMA["$defs"]["namedOpaqueRef"],
            SCHEMA["$defs"]["disabledSchedule"],
            SCHEMA["$defs"]["disabledFeatureFlag"],
            SCHEMA["$defs"]["approvalReference"],
        )
    )
    _assert_valid(FIXTURE)


def test_fixture_is_neutral_disabled_and_contains_no_self_asserted_status() -> None:
    assert FIXTURE["metadata"]["id"].startswith("synthetic.")
    assert FIXTURE["orgRef"].startswith("synthetic-ref:")
    assert FIXTURE["projectRef"].startswith("synthetic-ref:")
    assert FIXTURE["datasetNamespace"].startswith("synthetic.")
    assert all(item.startswith("synthetic.") for item in FIXTURE["selectedDomains"])
    assert all(
        item["ref"].startswith("synthetic-ref:") for item in FIXTURE["sourceRefs"]
    )
    assert all(
        item["ref"].startswith("synthetic-ref:") for item in FIXTURE["secretRefs"]
    )
    assert all(item["enabled"] is False for item in FIXTURE["schedules"])
    assert all(item["enabled"] is False for item in FIXTURE["featureFlags"])
    assert FIXTURE["approvals"]["overlayRevisionRef"] == FIXTURE["metadata"]["revision"]
    serialized = json.dumps(FIXTURE, sort_keys=True).lower()
    for forbidden in (
        "overlayhash",
        "approved",
        "production",
        "validated",
        "contenthash",
    ):
        assert forbidden not in serialized


def test_canonical_hash_is_external_stable_and_order_independent() -> None:
    reversed_fixture = dict(reversed(list(FIXTURE.items())))
    expected = "sha256:5c1d43e9d41081e43ed25b5e3790abefbe23f2ae7b60dff35397d788be7056e7"

    assert "overlayHash" not in FIXTURE
    assert canonical_json(FIXTURE) == canonical_json(reversed_fixture)
    assert canonical_sha256(FIXTURE) == canonical_sha256(reversed_fixture) == expected


@pytest.mark.parametrize("missing", list(SCHEMA["required"]))
def test_every_top_level_field_is_required(missing: str) -> None:
    payload = deepcopy(FIXTURE)
    del payload[missing]
    _assert_invalid(payload)


@pytest.mark.parametrize(
    ("path", "field"),
    [
        ((), "unknown"),
        (("metadata",), "displayName"),
        (("compositionLockRef",), "state"),
        (("sourceRefs", 0), "value"),
        (("secretRefs", 0), "plaintext"),
        (("schedules", 0), "timezone"),
        (("featureFlags", 0), "reason"),
        (("approvals",), "actor"),
    ],
)
def test_unknown_fields_are_rejected_at_every_object_level(
    path: tuple[str | int, ...], field: str
) -> None:
    payload = deepcopy(FIXTURE)
    target: Any = payload
    for part in path:
        target = target[part]
    target[field] = "not-allowed"
    _assert_invalid(payload)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("metadata", "id"), "tenant.overlay"),
        (("orgRef",), "organization-live"),
        (("projectRef",), "project-live"),
        (("sourceRefs", 0, "ref"), "https://service.invalid/source"),
        (("secretRefs", 0, "ref"), "plain-value"),
        (("datasetNamespace",), "tenant.orders"),
        (("selectedDomains", 0), "orders"),
        (("compositionLockRef", "revision"), 0),
        (("compositionLockRef", "revision"), True),
        (("compositionLockRef", "lockHash"), "sha256:" + "A" * 64),
        (("schedules", 0, "enabled"), 0),
        (("schedules", 0, "enabled"), True),
        (("featureFlags", 0, "enabled"), 0),
        (("featureFlags", 0, "enabled"), True),
        (("approvals", "overlayRevisionRef"), " padded"),
    ],
)
def test_real_refs_plain_values_coercion_and_enabling_are_rejected(
    path: tuple[str | int, ...], value: Any
) -> None:
    payload = deepcopy(FIXTURE)
    target: Any = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    _assert_invalid(payload)


@pytest.mark.parametrize(
    "field",
    [
        "roles",
        "markings",
        "dataScopes",
        "actionTypes",
        "permissions",
        "capabilities",
    ],
)
def test_permission_or_capability_expansion_fields_are_not_in_contract(
    field: str,
) -> None:
    assert field not in SCHEMA["properties"]
    payload = deepcopy(FIXTURE)
    payload[field] = []
    _assert_invalid(payload)


@pytest.mark.parametrize("field", ["sourceRefs", "secretRefs", "selectedDomains"])
def test_exact_duplicate_refs_or_domains_are_rejected(field: str) -> None:
    payload = deepcopy(FIXTURE)
    payload[field].append(deepcopy(payload[field][0]))
    _assert_invalid(payload)
