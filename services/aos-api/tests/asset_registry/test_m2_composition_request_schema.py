"""Executable checks for the frozen CompositionRequest JSON Schema."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from aos_api.asset_registry.semver import SemVerError, parse_range

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    REPO_ROOT
    / "packages/contracts/schemas/asset-bundles/"
    / "composition-request-v1alpha1.schema.json"
)
SCHEMA: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _base_request() -> dict[str, Any]:
    return {
        "requested": [
            {
                "publisher": "aos",
                "id": "solution.example",
                "version": "^1.2.3 || >=2.0.0 <3.0.0",
            }
        ],
        "platformApiVersion": "1.7.0",
        "platformRelease": "aos-platform/1.7.0",
        "environment": "dev",
    }


def _current_installation_ref() -> dict[str, Any]:
    return {
        "installationId": "8b09391f-9c91-4fb6-b086-0799a50f012b",
        "revision": 3,
        "lockHash": "sha256:" + "a" * 64,
        "overlayRevision": "overlay-v1",
    }


def _resolve_ref(ref: str) -> dict[str, Any]:
    assert ref.startswith("#/$defs/")
    return SCHEMA["$defs"][ref.removeprefix("#/$defs/")]


def _validation_errors(
    instance: Any,
    schema: dict[str, Any] | None = None,
    *,
    path: str = "$",
) -> list[str]:
    """Validate the deliberately small keyword subset used by this schema."""

    current = SCHEMA if schema is None else schema
    if "$ref" in current:
        return _validation_errors(instance, _resolve_ref(current["$ref"]), path=path)
    if "oneOf" in current:
        matches = sum(
            not _validation_errors(instance, option, path=path)
            for option in current["oneOf"]
        )
        return [] if matches == 1 else [f"{path}: expected exactly one schema match"]

    errors: list[str] = []
    expected_type = current.get("type")
    type_matches = {
        "object": isinstance(instance, dict),
        "array": isinstance(instance, list),
        "string": isinstance(instance, str),
        "integer": isinstance(instance, int) and not isinstance(instance, bool),
        "null": instance is None,
    }.get(expected_type, True)
    if not type_matches:
        return [f"{path}: expected {expected_type}"]

    if "enum" in current and instance not in current["enum"]:
        errors.append(f"{path}: outside enum")

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
                    _validation_errors(
                        value,
                        current["items"],
                        path=f"{path}[{index}]",
                    )
                )

    if isinstance(instance, str):
        if len(instance) < current.get("minLength", 0):
            errors.append(f"{path}: too short")
        if "maxLength" in current and len(instance) > current["maxLength"]:
            errors.append(f"{path}: too long")
        if "pattern" in current and re.search(current["pattern"], instance) is None:
            errors.append(f"{path}: pattern mismatch")
        if current.get("format") == "npm-semver-range":
            try:
                parse_range(instance)
            except SemVerError:
                errors.append(f"{path}: invalid npm SemVer range")

    if (
        isinstance(instance, int)
        and not isinstance(instance, bool)
        and "minimum" in current
        and instance < current["minimum"]
    ):
        errors.append(f"{path}: below minimum")
    return errors


def _assert_valid(instance: Any) -> None:
    assert _validation_errors(instance) == []


def _assert_invalid(instance: Any) -> None:
    assert _validation_errors(instance)


def _set_path(payload: dict[str, Any], path: tuple[str | int, ...], value: Any) -> None:
    current: Any = payload
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = value


def _semver_with_length(length: int) -> str:
    prefix = "1.2.3-"
    assert length > len(prefix)
    return prefix + "a" * (length - len(prefix))


def test_schema_declares_the_frozen_closed_contract() -> None:
    assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert SCHEMA["additionalProperties"] is False
    assert SCHEMA["required"] == [
        "requested",
        "platformApiVersion",
        "platformRelease",
        "environment",
    ]
    assert set(SCHEMA["properties"]) == {
        "requested",
        "platformApiVersion",
        "platformRelease",
        "environment",
        "registrySnapshotHash",
        "currentInstallationRef",
    }
    requested_schema = SCHEMA["properties"]["requested"]
    assert requested_schema["uniqueItems"] is True
    assert "unique (publisher,id) coordinates" in requested_schema["$comment"]
    assert "canonical (publisher,id,version) order" in requested_schema["$comment"]
    assert SCHEMA["$defs"]["requestedBundle"]["required"] == [
        "publisher",
        "id",
        "version",
    ]
    assert SCHEMA["$defs"]["currentInstallationRef"]["required"] == [
        "installationId",
        "revision",
        "lockHash",
        "overlayRevision",
    ]
    assert all(
        definition.get("additionalProperties") is False
        for definition in (
            SCHEMA["$defs"]["requestedBundle"],
            SCHEMA["$defs"]["currentInstallationRef"],
        )
    )
    assert SCHEMA["$defs"]["npmSemverRange"]["format"] == "npm-semver-range"
    assert SCHEMA["$defs"]["currentInstallationRef"]["properties"][
        "overlayRevision"
    ] == {"$ref": "#/$defs/normalizedRevision"}
    assert SCHEMA["$defs"]["normalizedRevision"]["maxLength"] == 160


def test_valid_exact_range_and_optional_null_semantics() -> None:
    exact = _base_request()
    exact["requested"][0]["version"] = "1.2.3-alpha.1+build.7"
    _assert_valid(exact)

    ranged = _base_request()
    ranged["registrySnapshotHash"] = None
    ranged["currentInstallationRef"] = None
    _assert_valid(ranged)

    current = _base_request()
    current["registrySnapshotHash"] = "sha256:" + "c" * 64
    current["currentInstallationRef"] = _current_installation_ref()
    _assert_valid(current)


@pytest.mark.parametrize(
    ("count", "valid"),
    [(0, False), (1, True), (63, True), (64, True), (65, False)],
)
def test_requested_count_boundaries(count: int, valid: bool) -> None:
    payload = _base_request()
    payload["requested"] = []
    for index in range(count):
        requested = deepcopy(_base_request()["requested"][0])
        requested["id"] = f"solution.example-{index}"
        payload["requested"].append(requested)
    assert (not _validation_errors(payload)) is valid


def test_exact_duplicate_requested_items_are_rejected() -> None:
    payload = _base_request()
    payload["requested"].append(deepcopy(payload["requested"][0]))
    _assert_invalid(payload)


@pytest.mark.parametrize(
    ("path", "limit", "factory"),
    [
        (("requested", 0, "publisher"), 120, lambda size: "a" * size),
        (("requested", 0, "id"), 160, lambda size: "a" * size),
        (("requested", 0, "version"), 256, _semver_with_length),
        (("platformRelease",), 160, lambda size: "r" * size),
    ],
)
def test_string_max_minus_one_max_and_max_plus_one(
    path: tuple[str | int, ...],
    limit: int,
    factory: Any,
) -> None:
    for size, valid in ((limit - 1, True), (limit, True), (limit + 1, False)):
        payload = _base_request()
        _set_path(payload, path, factory(size))
        assert (not _validation_errors(payload)) is valid


def test_overlay_revision_max_minus_one_max_and_max_plus_one() -> None:
    for size, valid in ((159, True), (160, True), (161, False)):
        payload = _base_request()
        payload["currentInstallationRef"] = _current_installation_ref()
        payload["currentInstallationRef"]["overlayRevision"] = "o" * size
        assert (not _validation_errors(payload)) is valid


@pytest.mark.parametrize("location", ["top", "requested", "current"])
def test_unknown_fields_are_rejected_at_every_object_level(location: str) -> None:
    payload = _base_request()
    if location == "top":
        payload["orgId"] = "must-not-come-from-body"
    elif location == "requested":
        payload["requested"][0]["displayName"] = "unknown"
    else:
        payload["currentInstallationRef"] = _current_installation_ref()
        payload["currentInstallationRef"]["state"] = "active"
    _assert_invalid(payload)


def test_requested_bundle_requires_publisher() -> None:
    payload = _base_request()
    del payload["requested"][0]["publisher"]
    _assert_invalid(payload)


@pytest.mark.parametrize(
    "missing",
    ["installationId", "revision", "lockHash", "overlayRevision"],
)
def test_current_installation_ref_requires_the_complete_quadruple(missing: str) -> None:
    payload = _base_request()
    payload["currentInstallationRef"] = _current_installation_ref()
    del payload["currentInstallationRef"][missing]
    _assert_invalid(payload)


@pytest.mark.parametrize(
    ("path", "invalid"),
    [
        (("requested", 0, "publisher"), "AOS"),
        (("requested", 0, "id"), "solution_example"),
        (("requested", 0, "version"), "1.2.3.4"),
        (("requested", 0, "version"), ">=banana"),
        (("platformApiVersion",), "^1.7.0"),
        (("platformApiVersion",), "01.7.0"),
        (("platformRelease",), " padded"),
        (("platformRelease",), "padded "),
        (("platformRelease",), "release\x00name"),
        (("environment",), "qa"),
        (("registrySnapshotHash",), "sha256:" + "A" * 64),
    ],
)
def test_cross_field_formats_reject_noncanonical_values(
    path: tuple[str | int, ...],
    invalid: Any,
) -> None:
    payload = _base_request()
    _set_path(payload, path, invalid)
    _assert_invalid(payload)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("installationId", "8B09391F-9C91-4FB6-B086-0799A50F012B"),
        ("revision", 0),
        ("lockHash", "sha256:" + "g" * 64),
        ("overlayRevision", ""),
        ("overlayRevision", " overlay-v1"),
        ("overlayRevision", "overlay-v1 "),
        ("overlayRevision", "overlay\x00v1"),
    ],
)
def test_current_installation_ref_formats_are_cross_checked(
    field: str,
    invalid: Any,
) -> None:
    payload = _base_request()
    payload["currentInstallationRef"] = _current_installation_ref()
    payload["currentInstallationRef"][field] = invalid
    _assert_invalid(payload)
