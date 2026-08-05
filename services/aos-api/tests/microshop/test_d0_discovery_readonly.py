"""D0 discovery readonly regression tests.

Covers AC-D0-1..7 of docs/.../微商城电商接入方案/D0-只读发现与配置冻结执行规格.md.
These tests assert the discovery contract without requiring a live tunnel:
they validate frozen artefact integrity, PII hygiene, and the script module
surface.  Live-tunnel behaviour is validated by running the script directly.
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

FROZEN_DIR = Path(
    "/Users/ddt/work/projects/ai_agent/docs/palantier/20_tech/电商平台接入/微商城电商接入方案/frozen"
)
SCRIPT_PATH = Path("/Users/ddt/work/projects/ai_agent/aos-platform/scripts/qyh_discover_readonly.py")

PII_PATTERNS = [
    re.compile(r"1[3-9]\d{9}"),
    re.compile(r"\b\d{15}(?:\d{2}[\dXx])?\b"),
    re.compile(r"62\d{14,17}"),
]


def _scan_pii(text: str) -> list[str]:
    hits: list[str] = []
    for pat in PII_PATTERNS:
        for m in pat.finditer(text):
            hits.append(m.group(0))
    return hits


def test_d0_frozen_artefacts_exist() -> None:
    for name in (
        "01-schema-fingerprint.md",
        "02-pipeline-manifest.yaml",
        "03-openapi-write-contract.md",
        "04-discovery-report.md",
    ):
        assert (FROZEN_DIR / name).is_file(), f"missing frozen artefact: {name}"


def test_d0_schema_fingerprint_has_seven_tables() -> None:
    text = (FROZEN_DIR / "01-schema-fingerprint.md").read_text(encoding="utf-8")
    for table in (
        "ns_site",
        "ns_goods",
        "ns_goods_sku",
        "ns_goods_category",
        "ns_order",
        "ns_order_goods",
        "ns_express_delivery_package",
    ):
        assert table in text, f"schema fingerprint missing table {table}"


def test_d0_pipeline_manifest_has_seven_pipelines() -> None:
    text = (FROZEN_DIR / "02-pipeline-manifest.yaml").read_text(encoding="utf-8")
    for pid in ("P01", "P02", "P03", "P04", "P05", "P06", "P07"):
        assert pid in text, f"pipeline manifest missing {pid}"


def test_d0_pipeline_manifest_records_shipping_status_correction() -> None:
    text = (FROZEN_DIR / "02-pipeline-manifest.yaml").read_text(encoding="utf-8")
    assert "delivery_status" in text
    assert "D-001" in text or "shipping_status" in text


def test_d0_pipeline_manifest_records_orderline_cursor_correction() -> None:
    text = (FROZEN_DIR / "02-pipeline-manifest.yaml").read_text(encoding="utf-8")
    assert "D-002" in text
    assert "快照" in text or "snapshot" in text.lower()


def test_d0_openapi_contract_is_draft_only() -> None:
    text = (FROZEN_DIR / "03-openapi-write-contract.md").read_text(encoding="utf-8")
    assert "D4" in text
    assert "Draft-only" in text or "不调用" in text
    assert "[TBC]" in text


def test_d0_discovery_report_differences_have_disposition() -> None:
    text = (FROZEN_DIR / "04-discovery-report.md").read_text(encoding="utf-8")
    for did in ("D-001", "D-002", "D-003", "D-004", "D-005", "D-006"):
        assert did in text, f"discovery report missing difference {did}"
    assert "空处置" in text
    assert "闭环" in text


def test_d0_no_pii_in_frozen_artefacts() -> None:
    for name in (
        "01-schema-fingerprint.md",
        "02-pipeline-manifest.yaml",
        "03-openapi-write-contract.md",
        "04-discovery-report.md",
    ):
        text = (FROZEN_DIR / name).read_text(encoding="utf-8")
        hits = _scan_pii(text)
        assert hits == [], f"PII pattern hits in {name}: {hits}"


def test_d0_discovery_script_exists_and_importable() -> None:
    assert SCRIPT_PATH.is_file(), "qyh_discover_readonly.py not found"
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    try:
        mod = importlib.import_module("qyh_discover_readonly")
    finally:
        sys.path.pop(0)
    for attr in ("discover_schema", "build_frozen_artefacts", "READ_ONLY_FLAG"):
        assert hasattr(mod, attr), f"qyh_discover_readonly missing {attr}"


def test_d0_discovery_script_enforces_read_only() -> None:
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    try:
        mod = importlib.import_module("qyh_discover_readonly")
    finally:
        sys.path.pop(0)
    assert mod.READ_ONLY_FLAG is True
    assert "SET SESSION TRANSACTION READ ONLY" in mod.READ_ONLY_SQL
