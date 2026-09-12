"""Fail-closed tests for the local ecommerce Candidate OCI builder."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/build_ecommerce_runtime_candidates.py"
SPEC = importlib.util.spec_from_file_location("ecommerce_runtime_candidate_builder", SCRIPT)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def test_default_preflight_never_calls_docker(monkeypatch) -> None:
    monkeypatch.setattr(
        BUILDER,
        "_docker",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Docker called")),
    )
    result = BUILDER.preflight()
    assert result["outcome"] == "PREFLIGHT_GREEN"
    assert (result["bundleCount"], result["runtimeMemberCount"]) == (4, 3)
    assert (result["moduleCount"], result["operationCount"]) == (8, 12)
    assert all(
        item["schemaCompatibilityHash"].startswith("sha256:")
        for item in result["bundles"]
        if item["runtimeOperations"]
    )


@pytest.mark.parametrize("change", ["missing", "method", "path", "mode", "duplicate"])
def test_registration_rejects_manifest_drift_before_docker(tmp_path, change):
    source = BUILDER.CANDIDATE_ROOT / BUILDER.RUNTIME_CASES[0][0]
    target = tmp_path / "candidate"
    shutil.copytree(source, target)
    path = target / "bundle.yaml"
    manifest = yaml.safe_load(path.read_text())
    contributions = manifest["spec"]["contributions"]
    if change == "missing":
        contributions.clear()
    elif change == "duplicate":
        contributions.append(dict(contributions[0]))
    else:
        contributions[0][change] = {"method": "GET", "path": "/wrong", "mode": "shared"}[change]
    path.write_text(yaml.safe_dump(manifest))
    with pytest.raises(BUILDER.CandidateBuildBlocked, match="ecommerce_core"):
        BUILDER._runtime_registration(target, "ecommerce_core")


def test_build_rejects_repository_output_before_engine_access(monkeypatch) -> None:
    monkeypatch.setattr(
        BUILDER,
        "_require_isolated_engine",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("engine accessed")),
    )
    with pytest.raises(BUILDER.CandidateBuildBlocked) as captured:
        BUILDER.build(
            context="colima-aos-extension",
            port=18436,
            output=BUILDER.REPOSITORY_ROOT / "forbidden-output",
        )
    assert captured.value.reason_code == "OUTPUT_MUST_BE_OUTSIDE_REPOSITORY"


def test_sbom_augmentation_is_deterministic_and_deduplicated(tmp_path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    path = evidence / "sbom.json"
    path.write_text(
        json.dumps({"bomFormat": "CycloneDX", "components": []}), encoding="utf-8"
    )
    arguments = {"sdk_hash": "sha256:" + "a" * 64, "base_config_digest": "sha256:" + "b" * 64}
    BUILDER._augment_sbom(tmp_path, **arguments)
    first = path.read_bytes()
    BUILDER._augment_sbom(tmp_path, **arguments)
    assert path.read_bytes() == first
    document = json.loads(first)
    assert [item["name"] for item in document["components"]] == [
        "aos-extension-sdk",
        BUILDER.BASE_IMAGE,
    ]


def test_tree_hash_ignores_python_cache(tmp_path) -> None:
    (tmp_path / "source.py").write_text("value = 1\n", encoding="utf-8")
    before = BUILDER._tree_hash(tmp_path)
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "source.pyc").write_bytes(b"unstable")
    assert BUILDER._tree_hash(tmp_path) == before


def _qualification_fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, dict[str, str]]]:
    output = tmp_path / "built"
    identities: dict[str, dict[str, str]] = {}
    for index, (relative, bundle_id, _version, package) in enumerate(
        BUILDER.ALL_CASES, start=1
    ):
        target = output / relative
        shutil.copytree(BUILDER.CANDIDATE_ROOT / relative, target)
        if package is None:
            continue
        artifacts = target / "artifacts"
        artifacts.mkdir(exist_ok=True)
        (artifacts / "python-dependencies.lock").write_bytes(BUILDER.RUNTIME_LOCK)
        BUILDER._augment_sbom(
            target,
            sdk_hash="sha256:" + "d" * 64,
            base_config_digest="sha256:" + "e" * 64,
        )
        identity = {
            "imageDigest": "sha256:" + f"{index:064x}",
            "configDigest": "sha256:" + f"{index + 10:064x}",
        }
        identities[bundle_id] = identity
        (artifacts / "runtime-image-index.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "images": [
                        {
                            "platform": BUILDER.PLATFORM,
                            **identity,
                            "dependencyLockHash": BUILDER._sha256(BUILDER.RUNTIME_LOCK),
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
    receipt = tmp_path / "build.json"
    receipt.write_text(
        json.dumps(
            {
                "outcome": "BUILD_GREEN",
                "gitHead": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    cwd=BUILDER.REPOSITORY_ROOT,
                    text=True,
                ).strip(),
                "output": str(output),
                "outputTreeHash": BUILDER._tree_hash(output),
                "contentHashes": BUILDER._content_hashes(output),
                "engine": {"platform": BUILDER.PLATFORM},
                "images": {
                    bundle_id.replace(".", "-"): identity
                    for bundle_id, identity in identities.items()
                },
                "effects": {
                    "registryPublishCount": 0,
                    "installationMutationCount": 0,
                    "providerInvocationCount": 0,
                    "externalPublicationCount": 0,
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return output, receipt, identities


def test_qualification_uses_ephemeral_signing_policy_admission_and_resolver(
    tmp_path: Path, monkeypatch,
) -> None:
    sessions = []
    def qualify_session(**kwargs):
        sessions.append(kwargs)
        return {"registration": "exact", "heartbeat": "alive", "cleanup": "released"}
    monkeypatch.setattr(BUILDER, "_qualify_session", qualify_session)
    output, receipt, identities = _qualification_fixture(tmp_path)
    by_config = {item["configDigest"]: item for item in identities.values()}

    class Driver:
        def _run(self, *_arguments: str) -> str:
            config_digest = _arguments[-1]
            identity = by_config[config_digest]
            return json.dumps(
                [
                    {
                        "Id": config_digest,
                        "RepoDigests": ["local@" + identity["imageDigest"]],
                        "Os": "linux",
                        "Architecture": "arm64",
                    }
                ]
            )

    result = BUILDER.qualify(
        output=output,
        build_receipt=receipt,
        context="unused-in-injected-test",
        driver=Driver(),
    )

    assert result["outcome"] == "QUALIFICATION_GREEN"
    assert len(sessions) == 3
    assert len(result["runtimeSessions"]) == 3
    assert [item["id"] for item in result["resolved"]] == [
        "domain.ecommerce.core",
        "platform.ecommerce.niushop",
        "solution.ecommerce.growth",
        "solution.ecommerce.operations-base",
    ]
    assert result["moduleCount"] == 8
    assert result["runtimeMemberCount"] == 3
    assert len(result["schemaRequirements"]) == 3
    for bundle_id, requirement in result["schemaRequirements"].items():
        assert requirement["packageId"].startswith("bundle-")
        assert requirement["schemaVersion"] == "aos-platform-a0v-001"
        assert requirement["migrationHash"] == next(
            item["schemaCompatibilityHash"]
            for item in BUILDER.preflight()["bundles"]
            if item["id"] == bundle_id
        )
    assert result["tamperRejections"] == [
        "imageIndexBytes",
        "imageDigest",
        "dependencyLock",
        "sbom",
        "backend",
        "schemaCompatibility",
        "schemaRequirements",
    ]
    assert result["ephemeralSignaturePersisted"] is False
    assert not list(output.rglob("bundle.signature.json"))


def test_qualification_rejects_receipt_from_another_git_head(tmp_path: Path) -> None:
    output, receipt, _identities = _qualification_fixture(tmp_path)
    document = json.loads(receipt.read_text(encoding="utf-8"))
    document["gitHead"] = "0" * 40
    receipt.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(BUILDER.CandidateBuildBlocked) as captured:
        BUILDER.qualify(
            output=output,
            build_receipt=receipt,
            context="unused",
            driver=object(),
        )
    assert captured.value.reason_code == "BUILD_RECEIPT_GIT_HEAD_MISMATCH"
