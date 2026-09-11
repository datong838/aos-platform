"""Fail-closed tests for the ecommerce growth 1.5 Registry successor."""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ecommerce_growth_1_5_registry_successor.py"
SPEC = importlib.util.spec_from_file_location("growth_1_5_successor", SCRIPT)
assert SPEC and SPEC.loader
SUCCESSOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUCCESSOR)


def _runtime_artifacts(builder, target: Path, index: int) -> None:
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


def _build_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    builder = SUCCESSOR._builder()
    output = tmp_path / "built"
    output.mkdir()
    for index, (relative, _bundle_id, _version, package) in enumerate(
        builder.ALL_CASES, start=1
    ):
        target = output / relative
        shutil.copytree(builder.CANDIDATE_ROOT / relative, target)
        if package is not None:
            _runtime_artifacts(builder, target, index)
    build = {
        "outcome": "BUILD_GREEN",
        "gitHead": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "output": str(output),
        "outputTreeHash": builder._tree_hash(output),
        "contentHashes": builder._content_hashes(output),
        "engine": {"platform": SUCCESSOR.PLATFORM},
        "effects": SUCCESSOR.EXPECTED_EFFECTS,
    }
    build_path = tmp_path / "build.json"
    build_path.write_text(json.dumps(build, sort_keys=True), encoding="utf-8")
    runtime_ids = {bundle_id for _, bundle_id, _ in SUCCESSOR.CURRENT_COORDINATES[:3]}
    qualification = {
        "outcome": "QUALIFICATION_GREEN",
        "gitHead": build["gitHead"],
        "buildReceipt": str(build_path),
        "buildReceiptHash": SUCCESSOR._sha256(build_path.read_bytes()),
        "outputTreeHash": build["outputTreeHash"],
        "moduleCount": 8,
        "runtimeMemberCount": 3,
        "ephemeralSignaturePersisted": False,
        "effects": SUCCESSOR.EXPECTED_EFFECTS,
        "tamperRejections": list(SUCCESSOR.EXPECTED_TAMPER_REJECTIONS),
        "resolved": [
            {"id": bundle_id, "version": version}
            for _, bundle_id, version in SUCCESSOR.CURRENT_COORDINATES
        ],
        "runtimeAdmissions": {item: {} for item in runtime_ids},
        "schemaRequirements": {item: {} for item in runtime_ids},
    }
    qualification_path = tmp_path / "qualification.json"
    qualification_path.write_text(
        json.dumps(qualification, sort_keys=True), encoding="utf-8"
    )
    return output, build_path, qualification_path


def _first_state(tmp_path: Path, build_output: Path) -> Path:
    builder = SUCCESSOR._builder()
    state = tmp_path / "first-state"
    signing = state / "signing"
    signing.mkdir(parents=True)
    key = Ed25519PrivateKey.generate()
    key_path = signing / "registry-ed25519.pem"
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    os.chmod(key_path, 0o600)
    public = base64.b64encode(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    sys_path_added = str(SUCCESSOR.API_ROOT)
    import sys

    sys.path.insert(0, sys_path_added)
    try:
        from aos_api.asset_registry.canonical_json import canonical_sha256
        from aos_api.asset_registry.manifest_loader import ManifestLoader

        root = {
            "publisher": "aos",
            "keyId": SUCCESSOR.SIGNING_KEY_ID,
            "algorithm": "Ed25519",
            "publicKey": public,
            "notBefore": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            "notAfter": datetime(2036, 1, 1, tzinfo=UTC).isoformat(),
            "revokedAt": None,
        }
        root["revision"] = canonical_sha256(root)
        (signing / "trust-roots.json").write_text(
            json.dumps({"trustRoots": [root]}, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )
        signed = state / "signed-bundles-v4"
        for index, (relative, _bundle_id, _version) in enumerate(
            SUCCESSOR.HISTORICAL_COORDINATES, start=20
        ):
            target = signed / relative
            built = build_output / relative
            if built.is_dir():
                shutil.copytree(built, target)
            else:
                shutil.copytree(builder.CANDIDATE_ROOT / relative, target)
                manifest = builder._load_manifest(target)
                if (manifest.get("spec") or {}).get("runtime") is not None:
                    _runtime_artifacts(builder, target, index)
        loader = ManifestLoader({SUCCESSOR.SOURCE_ALIAS: signed})
        for relative, _bundle_id, _version in SUCCESSOR.HISTORICAL_COORDINATES:
            loaded = loader.load(f"bundle://{SUCCESSOR.SOURCE_ALIAS}/{relative}")
            (signed / relative / "bundle.signature.json").write_text(
                json.dumps(
                    {
                        "algorithm": "Ed25519",
                        "keyId": SUCCESSOR.SIGNING_KEY_ID,
                        "signature": base64.b64encode(
                            key.sign(builder._signature_payload(loaded))
                        ).decode("ascii"),
                        "signedAt": datetime.now(UTC).isoformat(),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
    finally:
        sys.path.remove(sys_path_added)
    return state


def test_preflight_is_read_only_and_bound_to_growth_1_5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, build, qualification = _build_fixture(tmp_path)
    first_state = _first_state(tmp_path, output)
    successor_state = tmp_path / "successor-state"
    monkeypatch.setattr(SUCCESSOR, "_verify_source_revision", lambda head: head)
    result = SUCCESSOR.run(
        SUCCESSOR.parse_args(
            [
                "--build-dir", str(output),
                "--build-receipt", str(build),
                "--qualification-receipt", str(qualification),
                "--first-state", str(first_state),
                "--state-dir", str(successor_state),
            ]
        )
    )
    assert result["outcome"] == "PREFLIGHT_GREEN"
    assert result["effects"] == SUCCESSOR.EXPECTED_EFFECTS
    assert not (successor_state / "signed-bundles-v5").exists()


def test_successor_tree_preserves_v4_and_replays_exactly(tmp_path: Path) -> None:
    output, _build, _qualification = _build_fixture(tmp_path)
    first_state = _first_state(tmp_path, output)
    state = tmp_path / "successor-state"
    builder = SUCCESSOR._builder()
    historical = first_state / "signed-bundles-v4"
    before = builder._tree_hash(historical)

    first = SUCCESSOR.prepare_successor_signed_tree(
        build_dir=output, first_state=first_state, state_dir=state
    )
    second = SUCCESSOR.prepare_successor_signed_tree(
        build_dir=output, first_state=first_state, state_dir=state
    )

    assert second == first
    assert builder._tree_hash(historical) == before
    assert len(first["coordinates"]) == 5
    assert first["coordinates"][f"{SUCCESSOR.TARGET_ID}@1.4.0"] != first[
        "coordinates"
    ][f"{SUCCESSOR.TARGET_ID}@1.5.0"]


def test_runtime_env_is_idempotent_and_rejects_drift(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("EXISTING=value\n", encoding="utf-8")
    state = tmp_path / "state"
    signed = tmp_path / "signed"
    trust = tmp_path / "trust.json"
    signed.mkdir()
    trust.write_text("{}\n", encoding="utf-8")

    first = SUCCESSOR.configure_runtime_env(
        env_path=env_path, signed_root=signed, trust_path=trust, state_dir=state
    )
    second = SUCCESSOR.configure_runtime_env(
        env_path=env_path, signed_root=signed, trust_path=trust, state_dir=state
    )
    assert first["addedKeys"] == sorted(
        ["AOS_BUNDLE_ROOT", "AOS_BUNDLE_TRUST_ROOTS_FILE", "AOS_EXTENSION_RUNTIME_PLATFORM"]
    )
    assert second["addedKeys"] == []
    assert env_path.read_text(encoding="utf-8").startswith("EXISTING=value\n")

    env_path.write_text(
        env_path.read_text(encoding="utf-8").replace(str(signed.resolve()), "/drift"),
        encoding="utf-8",
    )
    with pytest.raises(SUCCESSOR.SuccessorBlocked) as captured:
        SUCCESSOR.configure_runtime_env(
            env_path=env_path, signed_root=signed, trust_path=trust, state_dir=state
        )
    assert captured.value.reason_code == "RUNTIME_ENV_DRIFT"


def test_apply_requires_exact_database_before_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, build, qualification = _build_fixture(tmp_path)
    first_state = _first_state(tmp_path, output)
    monkeypatch.setattr(SUCCESSOR, "_verify_source_revision", lambda head: head)
    args = SUCCESSOR.parse_args(
        [
            "--apply", "--database-name", "aos_meta",
            "--build-dir", str(output), "--build-receipt", str(build),
            "--qualification-receipt", str(qualification),
            "--first-state", str(first_state),
        ]
    )
    with pytest.raises(SUCCESSOR.SuccessorBlocked) as captured:
        SUCCESSOR.run(args)
    assert captured.value.reason_code == "EXPLICIT_ISOLATED_DATABASE_REQUIRED"
