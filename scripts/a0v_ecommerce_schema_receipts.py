#!/usr/bin/env python3
"""Record exact signed schema compatibility only after physical DB verification."""
import argparse
from datetime import UTC, datetime
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services/aos-api"


def verify_physical(conn, compatibility, revisions):
    if compatibility.get("noPackageOwnedMigration") is not True:
        raise ValueError("package migration requires a separate executor")
    revision = compatibility.get("alembicRevision")
    row = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(row) != 1 or revision not in revisions(row[0]["version_num"]):
        raise ValueError("required Alembic revision is not installed")
    relations = compatibility.get("requiredRelations")
    if not isinstance(relations, list) or not relations or len(relations) != len(set(relations)):
        raise ValueError("exact nonempty schema relations required")
    for relation in relations:
        if not isinstance(relation, str) or not relation.startswith("public."):
            raise ValueError("invalid schema relation")
        present = conn.execute("SELECT to_regclass(%s) IS NOT NULL AS present", (relation,)).fetchone()
        if present["present"] is not True:
            raise ValueError("required physical relation is missing: " + relation)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(API))
    spec = importlib.util.spec_from_file_location("successor", ROOT / "scripts/a0v_ecommerce_1_6_registry_successor.py")
    successor = importlib.util.module_from_spec(spec); spec.loader.exec_module(successor)
    helper = successor.legacy()
    builder = helper._builder()
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.extension_runtime.schema_conditions import admit_schema_requirements
    from aos_api.extension_runtime.schema_registry import apply_once
    config = Config(str(API / "alembic.ini"))
    config.set_main_option("script_location", str(API / "alembic"))
    graph = ScriptDirectory.from_config(config)
    def revisions(head):
        return {node.revision for node in graph.walk_revisions(base="base", head=head)}
    _, trust_path, _ = helper._persistent_signer(helper.FIRST_INSTALL_STATE)
    trust = FileTrustRootProvider(trust_path).snapshot()
    policy = ReleasePolicy(trust_roots=trust)
    loader = ManifestLoader({"a0v-canonical": successor.NEW_ROOT}, trust_roots=trust)
    first = helper._first_installer()
    connect = first.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    bundles = {relative: loader.load("bundle://a0v-canonical/" + relative)
               for relative, _, _, _ in builder.ALL_CASES}
    now = datetime.now(UTC)
    results = []
    with connect() as conn:
        with conn.transaction():
            if conn.execute("SELECT current_database() AS name").fetchone()["name"] != "aos_meta_head":
                raise ValueError("isolated database required")
            for relative, bundle_id, version, _ in builder.RUNTIME_CASES:
                bundle = bundles[relative]
                record = builder._release_record(bundle)
                # Use the canonical resolver, so selected-release inputs have the same shape as runtime.
                from aos_api.asset_registry.composition_contracts import RegistrySnapshot, CompositionRequest
                from aos_api.asset_registry.resolver import resolve
                candidates = []
                for rel, _, _, _ in builder.ALL_CASES:
                    item = bundles[rel]
                    candidates.append(builder._snapshot_candidate(item, policy.evaluate(builder._release_record(item), checked_at=now)))
                snapshot = RegistrySnapshot.build(candidates=candidates, checked_at=now)
                request = CompositionRequest.model_validate({"requested": [{"publisher": "aos", "id": bundle_id, "version": version}],
                    "platformApiVersion": "1.7.0", "platformRelease": "aos-platform/1.7.0", "environment": "dev",
                    "registrySnapshotHash": snapshot.snapshot_hash, "currentInstallationRef": None})
                selected = next(item for item in resolve(request, snapshot, None).resolved if item.id == bundle_id)
                root = successor.NEW_ROOT / relative
                requirements = admit_schema_requirements(record=record, selected=selected, policy=policy,
                    checked_at=now, read_artifact=lambda path, limit: (root / path).read_bytes())
                raw = (root / "artifacts/schema-compatibility.json").read_bytes()
                compatibility = json.loads(raw)
                if len(requirements) != 1 or requirements[0].migration_hash != helper._sha256(raw):
                    raise ValueError("compatibility digest differs from signed requirement")
                if compatibility.get("bundleId") != bundle_id:
                    raise ValueError("compatibility bundle identity differs")
                verify_physical(conn, compatibility, revisions)
                for requirement in requirements:
                    changed = apply_once(conn, requirement, lambda connection: verify_physical(connection, compatibility, revisions)) if args.apply else False
                    results.append({"bundleId": bundle_id, "packageId": requirement.package_id,
                        "schemaVersion": requirement.schema_version, "migrationHash": requirement.migration_hash,
                        "recorded": changed, "physicalRelations": len(compatibility["requiredRelations"])})
    result = {"outcome": "SCHEMA_RECEIPTS_GREEN" if args.apply else "SCHEMA_PHYSICAL_PREFLIGHT_GREEN", "requirements": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
