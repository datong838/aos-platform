from __future__ import annotations

import pytest
from aos_api.asset_registry.semver import (
    SemVerError,
    parse_range,
    parse_version,
    satisfies,
    select_highest,
)
from semantic_version import Version


def test_parse_version_is_strict_and_uses_semantic_version_type() -> None:
    parsed = parse_version("1.7.0")

    assert isinstance(parsed, Version)
    assert str(parsed) == "1.7.0"


@pytest.mark.parametrize("value", ["", " 1.0.0", "1.0.0 ", "v1.0.0", "1.0"])
def test_parse_version_rejects_invalid_or_coerced_versions(value: str) -> None:
    with pytest.raises(SemVerError):
        parse_version(value)


def test_exact_and_bounded_ranges_respect_boundaries() -> None:
    assert satisfies("1.7.0", "1.7.0")
    assert satisfies("1.7.0", ">=1.7.0 <2.0.0")
    assert satisfies("1.99.0", ">=1.7.0 <2.0.0")
    assert not satisfies("1.6.9", ">=1.7.0 <2.0.0")
    assert not satisfies("2.0.0", ">=1.7.0 <2.0.0")


def test_prerelease_requires_an_explicit_prerelease_range() -> None:
    assert not satisfies("2.0.0-beta.1", ">=1.0.0 <2.0.0")
    assert satisfies("2.0.0-beta.2", ">=2.0.0-beta.1 <2.0.0")


def test_select_highest_is_deterministic_and_reports_no_intersection() -> None:
    versions = ["1.8.0", "1.7.9", "2.0.0", "1.8.0"]

    assert select_highest(versions, ">=1.7.0 <2.0.0") == "1.8.0"
    assert select_highest(reversed(versions), ">=1.7.0 <2.0.0") == "1.8.0"
    assert select_highest(versions, ">=3.0.0") is None


def test_select_highest_breaks_equal_precedence_build_ties_deterministically() -> None:
    versions = ["1.8.0+build-b", "1.8.0", "1.8.0+build-a"]

    first = select_highest(versions, ">=1.0.0 <2.0.0")
    second = select_highest(reversed(versions), ">=1.0.0 <2.0.0")

    assert first == second == "1.8.0"


@pytest.mark.parametrize("value", ["", " latest", "not-a-range", ">="])
def test_parse_range_rejects_invalid_ranges(value: str) -> None:
    with pytest.raises(SemVerError):
        parse_range(value)
