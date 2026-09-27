#!/usr/bin/env python3
"""Publish exact current signed ecommerce releases to the isolated preview Registry."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from psycopg import connect
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
TARGET = "aos_current_preview_20260927"
EXPECTED_SCHEMA_HEAD = "a0v_107"
REGISTRY_CREATE_ROLES = frozenset({"asset-publisher", "asset-registry-admin", "developer"})
REGISTRY_PUBLISH_ROLES = frozenset({"asset-publisher", "asset-registry-admin"})
PUBLISHER_SCOPES = frozenset({"aos"})


class PublishBlocked(RuntimeError):
    pass


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PublishBlocked("MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _connect_factory():
    bootstrap = _load(ROOT / "scripts/a0v_current_preview_bootstrap.py", "current_preview_bootstrap")
    parameters = bootstrap._connection_parameters()

    @contextmanager
    def factory():
        with connect(**parameters, row_factory=dict_row) as conn:
            if conn.info.dbname != TARGET:
                raise PublishBlocked("DATABASE_TARGET_DRIFT")
            yield conn

    return factory


def preflight(*, signed_receipt: Path):
    signed_receipt = signed_receipt.resolve(strict=True)
    state_root = signed_receipt.parent / "signing-state"
    signed_root = state_root / "signed-bundles"
    trust_path = state_root / "trust-roots.json"
    if not signed_root.is_dir() or not trust_path.is_file() or signed_root.is_relative_to(ROOT):
        raise PublishBlocked("SIGNED_TREE_UNAVAILABLE")
    receipt = json.loads(signed_receipt.read_text(encoding="utf-8"))
    if receipt.get("outcome") != "SIGNED_TREE_GREEN" or receipt.get("signedTree") != str(signed_root):
        raise PublishBlocked("SIGNING_RECEIPT_DRIFT")
    builder = _load(ROOT / "scripts/build_ecommerce_current_candidates.py", "current_ecommerce_profile").load_builder()
    if receipt.get("signedTreeHash") != builder._tree_hash(signed_root):
        raise PublishBlocked("SIGNED_TREE_HASH_DRIFT")
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.asset_registry.signature import FileTrustRootProvider

    trust = FileTrustRootProvider(trust_path).snapshot()
    loader = ManifestLoader({"a0v-current": signed_root}, trust_roots=trust)
    policy = ReleasePolicy(trust_roots=trust)
    content = {}
    for relative, bundle_id, _, _ in builder.ALL_CASES:
        loaded = loader.load(f"bundle://a0v-current/{relative}")
        policy.evaluate(builder._release_record(loaded), checked_at=datetime.now(UTC))
        content[bundle_id] = loaded.content_hash
    if content != receipt.get("contentHashes"):
        raise PublishBlocked("SIGNED_CONTENT_DRIFT")
    factory = _connect_factory()
    with factory() as conn:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchall()
        registry_count = conn.execute("SELECT count(*) AS n FROM asset_bundle_version").fetchone()["n"]
        install_count = conn.execute("SELECT count(*) AS n FROM bundle_installation").fetchone()["n"]
    if [row["version_num"] for row in version] != [EXPECTED_SCHEMA_HEAD] or registry_count or install_count:
        raise PublishBlocked("DATABASE_BASELINE_DRIFT")
    return builder, loader, trust, factory, content


def publish(*, signed_receipt: Path, state: Path) -> dict[str, object]:
    state = state.resolve()
    if state == ROOT or state.is_relative_to(ROOT) or state.exists():
        raise PublishBlocked("STATE_MUST_BE_NEW_OUTSIDE_REPOSITORY")
    builder, loader, trust, factory, content = preflight(signed_receipt=signed_receipt)
    state.mkdir(mode=0o700)
    (state / "registry-intent.json").write_text(json.dumps({
        "database": TARGET, "versions": [
            {"id": bundle_id, "version": version} for _, bundle_id, version, _ in builder.ALL_CASES],
        "createdAt": datetime.now(UTC).isoformat(),
    }, sort_keys=True) + "\n", encoding="utf-8")
    from aos_api.asset_registry.errors import AssetNotFoundError
    from aos_api.asset_registry.registry_service import RegistryService
    from aos_api.asset_registry.registry_store import PostgresRegistryStore
    old = _load(ROOT / "scripts/a0v_canonical_ecommerce_first_install.py", "a0v_canonical_install_helpers")

    store = PostgresRegistryStore(connect_factory=factory)

    def database_clock():
        with factory() as conn:
            return conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]

    service = RegistryService(store=store, loader=loader, clock=database_clock, trust_roots=trust)
    published = []
    for relative, bundle_id, version, _ in builder.ALL_CASES:
        source_ref = f"bundle://a0v-current/{relative}"
        loaded = loader.load(source_ref)
        manifest = loaded.manifest
        try:
            store.get_bundle(bundle_id, publisher="aos")
        except AssetNotFoundError:
            service.create_bundle(publisher="aos", bundle_id=bundle_id, kind=manifest.kind,
                                  display_name=manifest.metadata.display_name,
                                  actor=f"current-preview-{bundle_id}-creator",
                                  roles=REGISTRY_CREATE_ROLES, publisher_scopes=PUBLISHER_SCOPES)
        try:
            store.get_version(bundle_id, version, publisher="aos")
        except AssetNotFoundError:
            service.create_version(publisher="aos", bundle_id=bundle_id, source_ref=source_ref,
                                   actor=f"current-preview-{bundle_id}-version-creator",
                                   roles=REGISTRY_CREATE_ROLES, publisher_scopes=PUBLISHER_SCOPES)
        current = store.get_version(bundle_id, version, publisher="aos")
        old.assert_registry_version_exact(current, old._expected_registry_version(loaded))
        if str(current["status"]).lower() == "draft":
            service.validate(publisher="aos", bundle_id=bundle_id, version=version,
                             actor=f"current-preview-{bundle_id}-validator",
                             roles=REGISTRY_CREATE_ROLES, publisher_scopes=PUBLISHER_SCOPES)
        current = store.get_version(bundle_id, version, publisher="aos")
        if str(current["status"]).lower() == "validated":
            service.publish(publisher="aos", bundle_id=bundle_id, version=version,
                            actor=f"current-preview-{bundle_id}-publisher",
                            roles=REGISTRY_PUBLISH_ROLES, publisher_scopes=PUBLISHER_SCOPES)
        final = store.get_version(bundle_id, version, publisher="aos")
        old.assert_registry_version_exact(final, old._expected_registry_version(loaded))
        if str(final["status"]).lower() != "published":
            raise PublishBlocked("VERSION_NOT_PUBLISHED")
        published.append({"id": bundle_id, "version": version, "contentHash": loaded.content_hash})
    if {item["id"]: item["contentHash"] for item in published} != content:
        raise PublishBlocked("FINAL_CONTENT_DRIFT")
    with factory() as conn:
        version_count = conn.execute("SELECT count(*) AS n FROM asset_bundle_version").fetchone()["n"]
        install_count = conn.execute("SELECT count(*) AS n FROM bundle_installation").fetchone()["n"]
    if version_count != 4 or install_count != 0:
        raise PublishBlocked("FINAL_DATABASE_DRIFT")
    result = {"outcome": "CURRENT_REGISTRY_FOUR_PUBLISHED", "database": TARGET,
              "published": published, "installationCount": 0, "providerInvocationCount": 0,
              "externalPublicationCount": 0}
    (state / "registry-result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    os.environ["AOS_DOTENV_DISABLED"] = "1"
    sys.path.insert(0, str(API_ROOT))
    parser = argparse.ArgumentParser()
    parser.add_argument("--signed-receipt", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--state-dir", type=Path)
    args = parser.parse_args()
    if args.publish:
        if args.state_dir is None:
            raise PublishBlocked("STATE_DIR_REQUIRED")
        result = publish(signed_receipt=args.signed_receipt, state=args.state_dir)
    else:
        _, _, _, _, content = preflight(signed_receipt=args.signed_receipt)
        result = {"outcome": "CURRENT_REGISTRY_PREFLIGHT_GREEN", "database": TARGET,
                  "contentHashes": content, "effects": 0}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        original = getattr(exc, "orig", exc)
        diagnostic = getattr(original, "diag", None)
        print(json.dumps({"outcome": "SAFE_BLOCKED", "errorType": type(exc).__name__,
                          "reasonCode": str(exc) if isinstance(exc, PublishBlocked) else None,
                          "sqlstate": getattr(original, "sqlstate", None),
                          "databaseError": getattr(diagnostic, "message_primary", None)}))
        raise SystemExit(2) from None
