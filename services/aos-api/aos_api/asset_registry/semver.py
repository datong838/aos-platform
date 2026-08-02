"""Controlled semantic-version parsing and range matching for asset bundles."""
from __future__ import annotations

from collections.abc import Iterable

from semantic_version import NpmSpec, Version
from semantic_version.base import BaseSpec

MAX_SEMVER_INPUT_LENGTH = 256


class SemVerError(ValueError):
    """Raised when a version or range is outside the accepted SemVer profile."""


def parse_version(value: str) -> Version:
    """Parse a strict SemVer version without coercion or a leading ``v``."""

    normalized = _validate_input(value, label="version")
    try:
        return Version(normalized)
    except ValueError as exc:
        raise SemVerError(f"invalid semantic version: {value!r}") from exc


def parse_range(value: str) -> BaseSpec:
    """Parse an npm-compatible SemVer range through ``semantic-version``."""

    normalized = _validate_input(value, label="range")
    try:
        return NpmSpec(normalized)
    except ValueError as exc:
        raise SemVerError(f"invalid semantic version range: {value!r}") from exc


def satisfies(version: str | Version, requirement: str | BaseSpec) -> bool:
    """Return whether a strict version satisfies a controlled range."""

    parsed_version = parse_version(version) if isinstance(version, str) else version
    if not isinstance(parsed_version, Version):
        raise SemVerError("version must be a string or semantic_version.Version")

    parsed_requirement = (
        parse_range(requirement) if isinstance(requirement, str) else requirement
    )
    if not isinstance(parsed_requirement, BaseSpec):
        raise SemVerError("requirement must be a string or semantic_version spec")
    return parsed_requirement.match(parsed_version)


def select_highest(
    versions: Iterable[str],
    requirement: str | BaseSpec,
) -> str | None:
    """Select the highest matching version deterministically, or ``None``."""

    parsed_requirement = (
        parse_range(requirement) if isinstance(requirement, str) else requirement
    )
    if not isinstance(parsed_requirement, BaseSpec):
        raise SemVerError("requirement must be a string or semantic_version spec")

    candidates = [parse_version(version) for version in versions]
    matching = [version for version in candidates if parsed_requirement.match(version)]
    if not matching:
        return None

    # SemVer precedence deliberately ignores build metadata. Sort the canonical
    # strings first so equivalent-precedence candidates cannot depend on input
    # or database row order, while Version still decides real precedence.
    ordered = sorted(matching, key=str)
    selected = ordered[0]
    for candidate in ordered[1:]:
        selected = max(selected, candidate)
    return str(selected)


def _validate_input(value: str, *, label: str) -> str:
    if not isinstance(value, str):
        raise SemVerError(f"{label} must be a string")
    if not value or value != value.strip():
        raise SemVerError(f"{label} must not be empty or padded with whitespace")
    if len(value) > MAX_SEMVER_INPUT_LENGTH:
        raise SemVerError(f"{label} is too long")
    if "\x00" in value:
        raise SemVerError(f"{label} contains a null byte")
    return value
