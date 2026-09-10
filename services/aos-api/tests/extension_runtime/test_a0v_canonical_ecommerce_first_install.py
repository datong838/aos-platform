"""Fail-closed tests for the A0-V canonical ecommerce first-install executor."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_canonical_ecommerce_first_install.py"
SPEC = importlib.util.spec_from_file_location("a0v_first_install", SCRIPT)
assert SPEC and SPEC.loader
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    builder = INSTALLER._load_builder()
    output = tmp_path / "built"
    shutil.copytree(builder.CANDIDATE_ROOT, output)
    build = {
        "outcome": "BUILD_GREEN",
        "gitHead": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "output": str(output),
        "outputTreeHash": builder._tree_hash(output),
        "contentHashes": builder._content_hashes(output),
        "engine": {"platform": INSTALLER.PLATFORM},
        "effects": INSTALLER.EXPECTED_EFFECTS,
    }
    build_path = tmp_path / "build.json"
    build_path.write_text(json.dumps(build, sort_keys=True), encoding="utf-8")
    runtime_ids = {
        "domain.ecommerce.core",
        "platform.ecommerce.niushop",
        "solution.ecommerce.growth",
    }
    qualification = {
        "outcome": "QUALIFICATION_GREEN",
        "gitHead": build["gitHead"],
        "buildReceipt": str(build_path),
        "buildReceiptHash": INSTALLER._sha256(build_path.read_bytes()),
        "outputTreeHash": build["outputTreeHash"],
        "moduleCount": 8,
        "runtimeMemberCount": 3,
        "ephemeralSignaturePersisted": False,
        "effects": INSTALLER.EXPECTED_EFFECTS,
        "tamperRejections": list(INSTALLER.EXPECTED_TAMPER_REJECTIONS),
        "resolved": [
            {"id": bundle_id, "version": version}
            for bundle_id, version in (
                ("domain.ecommerce.core", "1.1.0"),
                ("platform.ecommerce.niushop", "1.1.0"),
                ("solution.ecommerce.growth", "1.4.0"),
                ("solution.ecommerce.operations-base", "1.2.0"),
            )
        ],
        "schemaRequirements": {item: {} for item in runtime_ids},
        "runtimeAdmissions": {item: {} for item in runtime_ids},
    }
    qualification_path = tmp_path / "qualification.json"
    qualification_path.write_text(
        json.dumps(qualification, sort_keys=True), encoding="utf-8"
    )
    return output, build_path, qualification_path


def test_preflight_verifies_bound_inputs_without_database_docker_or_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, build, qualification = _fixture(tmp_path)
    monkeypatch.setattr(
        INSTALLER,
        "_verify_source_revision",
        lambda head: head,
    )
    result = INSTALLER.run(
        INSTALLER.parse_args(
            [
                "--build-dir",
                str(output),
                "--build-receipt",
                str(build),
                "--qualification-receipt",
                str(qualification),
            ]
        )
    )
    assert result["outcome"] == "PREFLIGHT_GREEN"
    assert result["effects"] == INSTALLER.EXPECTED_EFFECTS
    assert result["moduleCount"] == 8
    assert result["runtimeMemberCount"] == 3


def test_apply_requires_exact_explicit_isolated_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, build, qualification = _fixture(tmp_path)
    monkeypatch.setattr(INSTALLER, "_verify_source_revision", lambda head: head)
    args = INSTALLER.parse_args(
        [
            "--apply",
            "--database-name",
            "aos_meta",
            "--build-dir",
            str(output),
            "--build-receipt",
            str(build),
            "--qualification-receipt",
            str(qualification),
        ]
    )
    with pytest.raises(INSTALLER.FirstInstallBlocked) as captured:
        INSTALLER.run(args)
    assert captured.value.reason_code == "EXPLICIT_ISOLATED_DATABASE_REQUIRED"


def test_tampered_build_tree_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output, build, qualification = _fixture(tmp_path)
    monkeypatch.setattr(INSTALLER, "_verify_source_revision", lambda head: head)
    target = output / "domain.ecommerce.core/1.1.0/bundle.yaml"
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(INSTALLER.FirstInstallBlocked) as captured:
        INSTALLER.verify_v4_inputs(
            build_dir=output,
            build_receipt_path=build,
            qualification_receipt_path=qualification,
        )
    assert captured.value.reason_code == "BUILD_RECEIPT_MISMATCH"
