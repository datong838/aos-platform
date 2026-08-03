"""M5-0 executable guards against ecommerce bundle boundary smuggling.

The four bundle skeletons and synthetic overlay are owned by other workers, so
this suite scans each frozen target as soon as it exists.  On an isolated W3
branch the targets may be absent; after integration the same tests become hard
gates over their complete, explicit locations.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ROOTS = (
    REPO_ROOT / "services/aos-api/aos_api",
    REPO_ROOT / "packages",
    REPO_ROOT / "apps/web/src",
)
BUNDLE_ROOT = REPO_ROOT / "bundles"
PLATFORM_BUNDLE_ROOT = BUNDLE_ROOT / "platforms/ecommerce-niushop"
OVERLAY_SCHEMA = (
    REPO_ROOT
    / "packages/contracts/schemas/asset-bundles/instance-overlay-v1alpha1.schema.json"
)
OVERLAY_FIXTURE = Path(__file__).parent / "fixtures/m5/instance-overlay.synthetic.json"
M5_SCAN_TARGETS = (BUNDLE_ROOT, OVERLAY_SCHEMA, OVERLAY_FIXTURE)

_TEXT_SUFFIXES = frozenset({".json", ".md", ".toml", ".txt", ".yaml", ".yml"})
_SOURCE_SUFFIXES = frozenset({".js", ".mjs", ".py", ".ts", ".tsx"})
_EXECUTABLE_SUFFIXES = frozenset(
    {".jar", ".js", ".mjs", ".ps1", ".py", ".sh", ".sql", ".ts", ".tsx", ".whl"}
)
_SYNTHETIC_MARKERS = ("dummy", "example", "fixture", "synthetic", "test")
_BUNDLE_COORDINATES = (
    "domain.ecommerce.core",
    "solution.ecommerce.operations-base",
    "solution.ecommerce.growth",
    "platform.ecommerce.niushop",
)
_IMPORT_BOUNDARY = re.compile(
    r"(?im)^\s*from\s+bundles(?:\.|\s)"
    r"|^\s*(?:from|import)\b[^\n]*(?:\becommerce\b|\bniushop\b)"
    r"|\b(?:from|import)\s*\(\s*['\"](?:[^'\"]*/)?bundles(?:/|['\"])"
    r"|\b(?:from|import)\s*\(\s*['\"][^'\"]*(?:ecommerce|niushop)",
)
_FORBIDDEN_M5_CONTENT = {
    "customer_name": re.compile(r"栖月汇|qiyuehui", re.IGNORECASE),
    "niushop_table": re.compile(r"\bns_[a-z0-9_]+\b", re.IGNORECASE),
    "openid": re.compile(r"\bopen[_-]?id\b", re.IGNORECASE),
    "order_record": re.compile(
        r"['\"]order[_-]?(?:id|no|number|detail|line)s?['\"]\s*:",
        re.IGNORECASE,
    ),
    "cn_mobile": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "private_key": re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
    ),
    "credential_url": re.compile(
        r"\b[a-z][a-z0-9+.-]{1,20}://[^/\s:@]{1,64}:[^/\s@]{1,64}@",
        re.IGNORECASE,
    ),
}
_INSTANCE_REFERENCE = re.compile(
    r"\b(?:org|project|source|secret|dataset)[_:-]"
    r"(?!(?:ref|refs|namespace)\b)[a-z0-9._-]+\b",
    re.IGNORECASE,
)
_PLATFORM_IMPLEMENTATION = {
    "schema_fingerprint": re.compile(
        r"schema[_ -]?fingerprint|schemaFingerprint", re.IGNORECASE
    ),
    "network_endpoint": re.compile(
        r"\b(?:https?|jdbc|mysql|postgres(?:ql)?|mongodb)://", re.IGNORECASE
    ),
    "sql_statement": re.compile(
        r"(?im)^\s*(?:select|insert\s+into|update\s+\S+\s+set|delete\s+from|"
        r"create\s+table|alter\s+table|drop\s+table)\b"
    ),
}


def _is_test_source(path: Path) -> bool:
    return (
        "tests" in path.parts
        or "__tests__" in path.parts
        or ".test." in path.name
        or ".spec." in path.name
    )


def _files_under(path: Path, *, suffixes: frozenset[str]) -> Iterator[Path]:
    if path.is_file():
        if path.suffix.lower() in suffixes:
            yield path
        return
    if not path.is_dir():
        return
    for candidate in sorted(path.rglob("*")):
        if (
            candidate.is_file()
            and candidate.suffix.lower() in suffixes
            and not {"dist", "node_modules", "__pycache__"}.intersection(
                candidate.parts
            )
        ):
            yield candidate


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _m5_text_files() -> list[Path]:
    files = {
        file
        for target in M5_SCAN_TARGETS
        for file in _files_under(target, suffixes=_TEXT_SUFFIXES)
    }
    return sorted(files)


def _matching_files(pattern: re.Pattern[str], files: list[Path]) -> list[str]:
    return [
        file.relative_to(REPO_ROOT).as_posix()
        for file in files
        if pattern.search(_read_text(file))
    ]


def _assert_synthetic_reference(value: object, *, location: str) -> None:
    if isinstance(value, str):
        normalized = value.lower()
        assert any(marker in normalized for marker in _SYNTHETIC_MARKERS), (
            f"non-synthetic reference at {location}"
        )
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_synthetic_reference(item, location=f"{location}.{key}")
        return
    pytest.fail(f"reference at {location} must be a string or object of strings")


def test_production_kernel_has_no_bundle_import_or_coordinate_special_case() -> None:
    violations: list[str] = []
    for root in PRODUCTION_ROOTS:
        for path in _files_under(root, suffixes=_SOURCE_SUFFIXES):
            if _is_test_source(path):
                continue
            content = _read_text(path)
            lowered = content.lower()
            if _IMPORT_BOUNDARY.search(content) or any(
                coordinate in lowered for coordinate in _BUNDLE_COORDINATES
            ):
                violations.append(path.relative_to(REPO_ROOT).as_posix())
    assert violations == [], (
        f"production kernel imports/special-cases M5 bundles: {violations}"
    )


def test_existing_m5_targets_contain_no_customer_secret_or_pii_smuggling() -> None:
    files = _m5_text_files()
    violations = {
        rule: matches
        for rule, pattern in _FORBIDDEN_M5_CONTENT.items()
        if (matches := _matching_files(pattern, files))
    }
    assert violations == {}


def test_existing_m5_instance_reference_tokens_are_explicitly_synthetic() -> None:
    violations: list[str] = []
    for path in _m5_text_files():
        for match in _INSTANCE_REFERENCE.finditer(_read_text(path)):
            if not any(
                marker in match.group(0).lower() for marker in _SYNTHETIC_MARKERS
            ):
                violations.append(path.relative_to(REPO_ROOT).as_posix())
                break
    assert violations == [], f"non-synthetic instance references found: {violations}"


def test_synthetic_overlay_references_cannot_hide_real_instance_ids() -> None:
    if not OVERLAY_FIXTURE.is_file():
        return
    payload = json.loads(_read_text(OVERLAY_FIXTURE))
    for field in (
        "orgRef",
        "projectRef",
        "compositionLockRef",
        "sourceRefs",
        "secretRefs",
        "datasetNamespace",
    ):
        _assert_synthetic_reference(payload[field], location=field)
    _assert_synthetic_reference(
        payload["approvals"]["overlayRevisionRef"],
        location="approvals.overlayRevisionRef",
    )


def test_bundle_content_directories_are_empty_declarations_only() -> None:
    if not BUNDLE_ROOT.is_dir():
        return
    violations: list[str] = []
    for content_root in sorted(BUNDLE_ROOT.glob("**/content")):
        for path in sorted(content_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(REPO_ROOT).as_posix()
            if path.name != ".gitkeep" or path.stat().st_size != 0:
                violations.append(relative)
    assert violations == [], (
        f"M5 content must contain empty .gitkeep files only: {violations}"
    )


def test_m5_targets_contain_no_executable_platform_assets() -> None:
    violations = [
        path.relative_to(REPO_ROOT).as_posix()
        for target in M5_SCAN_TARGETS
        for path in _files_under(target, suffixes=_EXECUTABLE_SUFFIXES)
    ]
    assert violations == [], (
        f"executable SQL/Connector/Pipeline/Action assets found: {violations}"
    )


def test_niushop_coordinate_is_allowed_but_platform_implementation_is_not() -> None:
    legal_manifest_fragment = "id: platform.ecommerce.niushop\n"
    assert all(
        pattern.search(legal_manifest_fragment) is None
        for pattern in _PLATFORM_IMPLEMENTATION.values()
    )

    files = list(_files_under(PLATFORM_BUNDLE_ROOT, suffixes=_TEXT_SUFFIXES))
    violations = {
        rule: matches
        for rule, pattern in _PLATFORM_IMPLEMENTATION.items()
        if (matches := _matching_files(pattern, files))
    }
    assert violations == {}


def test_existing_m5_scope_passes_repository_sensitive_scanner() -> None:
    existing_targets = [str(path) for path in M5_SCAN_TARGETS if path.exists()]
    if not existing_targets:
        return
    scanner = REPO_ROOT / "scripts/security/scan_sensitive.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(scanner),
            "--repo-root",
            str(REPO_ROOT),
            "--report",
            "summary",
            "--fail-on-warning",
            *existing_targets,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "critical=0 warning=0" in completed.stdout
