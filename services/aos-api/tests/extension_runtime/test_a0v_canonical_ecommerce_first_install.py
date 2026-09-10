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
    output.mkdir()
    for index, (relative, bundle_id, _version, package) in enumerate(
        builder.ALL_CASES, start=1
    ):
        target = output / relative
        shutil.copytree(builder.CANDIDATE_ROOT / relative, target)
        if package is None:
            continue
        artifacts = target / "artifacts"
        (artifacts / "python-dependencies.lock").write_bytes(builder.RUNTIME_LOCK)
        builder._augment_sbom(
            target,
            sdk_hash="sha256:" + "d" * 64,
            base_config_digest="sha256:" + "e" * 64,
        )
        (artifacts / "runtime-image-index.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "images": [
                        {
                            "platform": builder.PLATFORM,
                            "imageDigest": "sha256:" + f"{index:064x}",
                            "configDigest": "sha256:" + f"{index + 10:064x}",
                            "dependencyLockHash": builder._sha256(builder.RUNTIME_LOCK),
                            "sbomPath": "evidence/sbom.json",
                        }
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
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


def test_persistent_signing_tree_replays_with_same_key_and_revision(tmp_path: Path) -> None:
    output, _build, _qualification = _fixture(tmp_path)
    state = tmp_path / "state"
    first = INSTALLER.prepare_persistent_signed_tree(build_dir=output, state_dir=state)
    second = INSTALLER.prepare_persistent_signed_tree(build_dir=output, state_dir=state)
    assert second == first
    assert first["privateKeyMode"] == "0600"
    assert Path(first["privateKeyPath"]).stat().st_mode & 0o777 == 0o600
    assert not list(output.rglob("bundle.signature.json"))
    assert len(list(Path(first["signedBundleRoot"]).rglob("bundle.signature.json"))) == 4


def test_backup_rejects_noncanonical_target_before_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        INSTALLER.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("called")),
    )
    with pytest.raises(INSTALLER.FirstInstallBlocked) as captured:
        INSTALLER.create_pre_mutation_backup(
            context=INSTALLER.DOCKER_CONTEXT,
            container=INSTALLER.DATABASE_CONTAINER,
            database_name="aos_meta",
            state_dir=tmp_path,
        )
    assert captured.value.reason_code == "BACKUP_TARGET_MISMATCH"


def test_container_connection_rejects_noncanonical_target_before_inspect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        INSTALLER.subprocess,
        "check_output",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("called")),
    )
    with pytest.raises(INSTALLER.FirstInstallBlocked) as captured:
        INSTALLER.container_database_connect_factory(
            context=INSTALLER.DOCKER_CONTEXT,
            container=INSTALLER.DATABASE_CONTAINER,
            database_name="aos_meta",
        )
    assert captured.value.reason_code == "DATABASE_TARGET_MISMATCH"


def test_existing_registry_version_drift_fails_closed() -> None:
    expected = {
        "sourceRef": "bundle://a0v-canonical/example/1.0.0",
        "contentHash": "sha256:" + "1" * 64,
        "manifestHash": "sha256:" + "2" * 64,
        "artifacts": [
            {
                "relativePath": "artifact.json",
                "artifactRef": "bundle://a0v-canonical/example/1.0.0/artifact.json",
                "digest": "sha256:" + "3" * 64,
            }
        ],
    }
    INSTALLER.assert_registry_version_exact(expected, expected)
    with pytest.raises(INSTALLER.FirstInstallBlocked) as captured:
        INSTALLER.assert_registry_version_exact(
            {**expected, "contentHash": "sha256:" + "4" * 64}, expected
        )
    assert captured.value.reason_code == "EXISTING_VERSION_DRIFT"


def test_runtime_configuration_authority_reports_every_missing_source() -> None:
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _query, params):
            assert params == (INSTALLER.ORG_ID, INSTALLER.PROJECT_ID) * 8
            return self

        def fetchone(self):
            return {
                "responsibility_plans": 1,
                "runtime_policies": 0,
                "data_policies": 0,
                "egress_policies": 2,
                "network_policies": 0,
                "quota_policies": 0,
                "budget_policies": 0,
                "budgets": 0,
            }

    result = INSTALLER.inspect_runtime_configuration_authority(lambda: Connection())
    assert result == {
        "counts": {
            "responsibility_plans": 1,
            "runtime_policies": 0,
            "data_policies": 0,
            "egress_policies": 2,
            "network_policies": 0,
            "quota_policies": 0,
            "budget_policies": 0,
            "budgets": 0,
        },
        "blockers": [
            "runtime_policies",
            "data_policies",
            "network_policies",
            "quota_policies",
            "budget_policies",
            "budgets",
        ],
        "ready": False,
    }
