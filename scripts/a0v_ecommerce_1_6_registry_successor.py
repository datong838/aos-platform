#!/usr/bin/env python3
"""Bounded local registry successor for qualified complete registrations."""
from __future__ import annotations

import argparse
import base64
from datetime import UTC, datetime
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services/aos-api"
RECOVERY = ROOT.parent / ".aos-recovery-20260912"
BUILD = RECOVERY / "state/ecommerce-runtime-1.6.0-build-v1"
BUILD_RECEIPT = RECOVERY / "logs/ecommerce-runtime-1.6.0-build-v1.json"
QUALIFICATION = RECOVERY / "logs/ecommerce-runtime-1.6.0-qualification-v1.json"
STATE = RECOVERY / "state/ecommerce-1.6-registry"
OLD_ROOT = RECOVERY / "state/ecommerce-growth-1.5.0-registry-successor-v2/signed-bundles-v5"
NEW_ROOT = STATE / "signed-bundles-v6"
VERSIONS = {"domain.ecommerce.core": "1.2.0", "platform.ecommerce.niushop": "1.2.0",
            "solution.ecommerce.growth": "1.6.0", "solution.ecommerce.operations-base": "1.2.0"}


def legacy():
    spec = importlib.util.spec_from_file_location("registry_successor_helpers", ROOT / "scripts/a0v_ecommerce_growth_1_5_registry_successor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_sessions(document):
    expected = {"domain.ecommerce.core": 1, "platform.ecommerce.niushop": 2, "solution.ecommerce.growth": 23}
    sessions = document.get("runtimeSessions") or {}
    if set(sessions) != set(expected):
        raise ValueError("three actual session receipts required")
    for key, count in expected.items():
        item = sessions[key]
        if any(item.get(k) != v for k, v in {"registration": "exact", "heartbeat": "alive", "cleanup": "released", "contributionCount": count}.items()):
            raise ValueError("runtime session qualification is incomplete")


def verify_inputs(helper):
    builder = helper._builder()
    build = json.loads(BUILD_RECEIPT.read_text())
    qualified = json.loads(QUALIFICATION.read_text())
    require_sessions(qualified)
    if (build.get("outcome") != "BUILD_GREEN" or build.get("output") != str(BUILD)
            or build.get("outputTreeHash") != builder._tree_hash(BUILD)
            or build.get("contentHashes") != builder._content_hashes(BUILD)
            or build.get("effects") != helper.EXPECTED_EFFECTS):
        raise ValueError("build receipt does not match current bytes")
    expected = {"outcome": "QUALIFICATION_GREEN", "gitHead": build["gitHead"],
                "buildReceipt": str(BUILD_RECEIPT), "buildReceiptHash": helper._sha256(BUILD_RECEIPT.read_bytes()),
                "outputTreeHash": build["outputTreeHash"], "effects": helper.EXPECTED_EFFECTS,
                "moduleCount": 8, "runtimeMemberCount": 3, "ephemeralSignaturePersisted": False}
    if any(qualified.get(k) != v for k, v in expected.items()):
        raise ValueError("qualification receipt does not match build")
    if qualified.get("tamperRejections") != list(helper.EXPECTED_TAMPER_REJECTIONS):
        raise ValueError("tamper qualification missing")
    if {(r["id"], r["version"]) for r in qualified["resolved"]} != set(VERSIONS.items()):
        raise ValueError("qualified coordinates differ")
    helper._git("merge-base", "--is-ancestor", build["gitHead"], "HEAD")
    paths = ["scripts/build_ecommerce_runtime_candidates.py", "packages/aos-extension-sdk/python/aos_extension_sdk"]
    paths += [f"bundles/candidates/ecommerce/{key}/{value}" for key, value in VERSIONS.items()]
    if (helper._git("diff", "--name-only", build["gitHead"], "--", *paths)
            or helper._git("status", "--porcelain", "--", *paths)):
        raise ValueError("qualified source advanced or dirty")
    return build


def signed_tree(helper, build):
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.asset_registry.release_policy import ReleasePolicy
    builder = helper._builder()
    key, trust_path, _ = helper._persistent_signer(helper.FIRST_INSTALL_STATE)
    trust = FileTrustRootProvider(trust_path).snapshot()
    policy = ReleasePolicy(trust_roots=trust)
    def read_all(root):
        loader = ManifestLoader({"a0v-canonical": root}, trust_roots=trust)
        result = {}
        for path in sorted(root.glob("*/*/bundle.yaml")):
            relative = str(path.parent.relative_to(root))
            bundle = loader.load("bundle://a0v-canonical/" + relative)
            policy.evaluate(builder._release_record(bundle), checked_at=datetime.now(UTC))
            result[relative] = bundle.content_hash
        return result
    before = read_all(OLD_ROOT)
    if len(before) != 5:
        raise ValueError("historical signed root differs")
    STATE.mkdir(parents=True, exist_ok=True)
    if not NEW_ROOT.exists():
        temp = Path(tempfile.mkdtemp(dir=STATE, prefix="signing-"))
        try:
            shutil.copytree(OLD_ROOT, temp, dirs_exist_ok=True)
            for bundle_id, version in VERSIONS.items():
                relative = bundle_id + "/" + version
                if relative in before:
                    if before[relative] != build["contentHashes"][bundle_id]:
                        raise ValueError("historical content changed")
                    continue
                shutil.copytree(BUILD / relative, temp / relative)
                loaded = ManifestLoader({"a0v-canonical": temp}).load("bundle://a0v-canonical/" + relative)
                signature = {"algorithm": "Ed25519", "keyId": helper.SIGNING_KEY_ID,
                    "signature": base64.b64encode(key.sign(builder._signature_payload(loaded))).decode(),
                    "signedAt": datetime.now(UTC).isoformat()}
                (temp / relative / "bundle.signature.json").write_text(json.dumps(signature, sort_keys=True) + "\n")
            temp.replace(NEW_ROOT)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    after = read_all(NEW_ROOT)
    if len(after) != 8 or any(after.get(k) != v for k, v in before.items()):
        raise ValueError("historical content changed in successor")
    for key, version in VERSIONS.items():
        if after.get(key + "/" + version) != build["contentHashes"][key]:
            raise ValueError("new signed content differs from qualification")
    return trust_path, after


def publish(helper, connect, trust_path):
    from aos_api.asset_registry.errors import AssetNotFoundError
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.registry_service import RegistryService
    from aos_api.asset_registry.registry_store import PostgresRegistryStore
    from aos_api.asset_registry.signature import FileTrustRootProvider
    trust = FileTrustRootProvider(trust_path).snapshot()
    loader = ManifestLoader({"a0v-canonical": NEW_ROOT}, trust_roots=trust)
    store = PostgresRegistryStore(connect_factory=connect)
    service = RegistryService(store=store, loader=loader, clock=lambda: helper._database_clock(connect), trust_roots=trust)
    first = helper._first_installer()
    results = []
    for bundle_id, version in VERSIONS.items():
        source = f"bundle://a0v-canonical/{bundle_id}/{version}"
        expected = first._expected_registry_version(loader.load(source))
        counts = {"create": 0, "validate": 0, "publish": 0}
        try:
            row = store.get_version(bundle_id, version, publisher="aos")
        except AssetNotFoundError:
            row = service.create_version(publisher="aos", bundle_id=bundle_id, source_ref=source,
                actor="a0v-ecommerce-1.6-creator", roles=helper.CREATE_ROLES, publisher_scopes=helper.PUBLISHER_SCOPES)
            counts["create"] = 1
        first.assert_registry_version_exact(row, expected)
        if row["status"] == "draft":
            row = service.validate(publisher="aos", bundle_id=bundle_id, version=version,
                actor="a0v-ecommerce-1.6-validator", roles=helper.CREATE_ROLES, publisher_scopes=helper.PUBLISHER_SCOPES)
            counts["validate"] = 1
        if row["status"] == "validated":
            row = service.publish(publisher="aos", bundle_id=bundle_id, version=version,
                actor="a0v-ecommerce-1.6-publisher", roles=helper.PUBLISH_ROLES, publisher_scopes=helper.PUBLISHER_SCOPES)
            counts["publish"] = 1
        if row["status"] != "published":
            raise ValueError("new version did not reach published")
        first.assert_registry_version_exact(store.get_version(bundle_id, version, publisher="aos"), expected)
        results.append({"bundleId": bundle_id, "version": version, "mutations": counts})
    return results


def switch_root(env_path):
    raw = env_path.read_bytes()
    lines = raw.decode().splitlines()
    indices = [i for i, line in enumerate(lines) if line.startswith("AOS_BUNDLE_ROOT=")]
    if len(indices) != 1:
        raise ValueError("runtime root must occur exactly once")
    index = indices[0]
    current = lines[index].split("=", 1)[1].strip().strip('"').strip("'")
    if current == str(NEW_ROOT):
        return False
    if current != str(OLD_ROOT):
        raise ValueError("runtime root CAS drift")
    backup = STATE / "env-before-v6"
    if not backup.exists():
        with os.fdopen(os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as f:
            f.write(raw)
    lines[index] = "AOS_BUNDLE_ROOT=" + str(NEW_ROOT)
    with tempfile.NamedTemporaryFile(dir=env_path.parent, delete=False) as f:
        temp = Path(f.name)
        f.write(("\n".join(lines) + "\n").encode()); f.flush(); os.fsync(f.fileno())
    os.chmod(temp, env_path.stat().st_mode & 0o777)
    temp.replace(env_path)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(API))
    helper = legacy()
    build = verify_inputs(helper)
    result = {"outcome": "PREFLIGHT_GREEN", "outputTreeHash": build["outputTreeHash"]}
    if args.apply:
        trust_path, hashes = signed_tree(helper, build)
        backup = helper._database_backup(context=helper.DOCKER_CONTEXT, container=helper.DATABASE_CONTAINER, state_dir=STATE)
        connect = helper._first_installer().container_database_connect_factory(
            context=helper.DOCKER_CONTEXT, container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
        before = helper._database_counts(connect)
        if before["canary"] != 0:
            raise ValueError("canary state drift")
        releases = publish(helper, connect, trust_path)
        after = helper._database_counts(connect)
        if before != after:
            raise ValueError("installation or historical version counts changed")
        switched = switch_root(ROOT / ".env")
        result.update(outcome="ECOMMERCE_1_6_REGISTRY_GREEN", releases=releases, signedContent=hashes,
            backup=backup, before=before, after=after, rootChanged=switched,
            installationMutationCount=0, providerInvocationCount=0, externalPublicationCount=0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
