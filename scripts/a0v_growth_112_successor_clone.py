#!/usr/bin/env python3
"""Clone-only growth 1.12 successor rehearsal; default mode never writes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
CONTEXT = "colima-aos-a0v-test-only"
CONTAINER = "aos-bg00dl-isolated-pg"
VOLUME = "aos-bg00dl-isolated-pg-data"
DATABASE = "aos_current_preview_20260927"
PORT = 18440
ORG_ID = "org-org"
PROJECT_ID = "dev-project"
GROWTH_ID = "solution.ecommerce.growth"
GROWTH_VERSION = "1.12.0"
CLONE_ENV = ROOT.parent / ".aos-bg00dl-clone-state-20260930/postgres.env"
BASELINE_DIGESTS = ROOT.parent / ".aos-bg00dl-clone-state-20260930/source-clone-digests.json"
EXPECTED_BASELINE = {
    "alembic_version": 1,
    "asset_bundle_version": 4,
    "bundle_composition_lock": 1,
    "bundle_installation": 1,
    "extension_runtime_host_identity": 0,
    "extension_runtime_host_assignment": 0,
    "extension_runtime_operation": 0,
    "extension_runtime_binding": 0,
    "extension_runtime_configuration": 0,
}


class SuccessorBlocked(RuntimeError):
    pass


def check_clone_target(*, context: str, container: str, volume: str, port: int,
                       database: str, org_id: str, project_id: str) -> None:
    if (context, container, volume, port, database, org_id, project_id) != (
        CONTEXT, CONTAINER, VOLUME, PORT, DATABASE, ORG_ID, PROJECT_ID
    ):
        raise SuccessorBlocked("CLONE_TARGET_DRIFT")


def check_clone_actors(maker: str, checker: str) -> None:
    if not maker or not checker or maker == checker:
        raise SuccessorBlocked("DUTY_SEPARATION_REQUIRED")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SuccessorBlocked("MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_signed_receipt(path: Path, *, expected_growth: str) -> dict[str, object]:
    if expected_growth not in {"1.11.0", GROWTH_VERSION}:
        raise SuccessorBlocked("GROWTH_VERSION_DRIFT")
    successor = expected_growth == GROWTH_VERSION
    key_id = ("a0v-local-ecommerce-growth-1-12-v1" if successor
              else "a0v-local-ecommerce-current-v1")
    profile_path = ("build_ecommerce_growth_1_12_candidates.py" if successor
                    else "build_ecommerce_current_candidates.py")
    source_alias = "a0v-growth-112" if successor else "a0v-current"
    try:
        receipt = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SuccessorBlocked("SIGNING_RECEIPT_DRIFT") from exc
    content = receipt.get("contentHashes")
    if (receipt.get("outcome") != "SIGNED_TREE_GREEN"
            or receipt.get("keyId") != key_id
            or not isinstance(content, dict) or set(content) != {
                "domain.ecommerce.core", "platform.ecommerce.niushop",
                GROWTH_ID, "solution.ecommerce.operations-base",
            } or not all(isinstance(value, str) and value.startswith("sha256:")
                         for value in content.values())):
        raise SuccessorBlocked("SIGNING_RECEIPT_DRIFT")
    signed_tree = Path(str(receipt.get("signedTree", "")))
    trust_path = signed_tree.parent / "trust-roots.json"
    if (not signed_tree.is_absolute() or not signed_tree.is_dir()
            or signed_tree.is_relative_to(ROOT) or not trust_path.is_file()):
        raise SuccessorBlocked("SIGNED_TREE_UNAVAILABLE")
    builder = _load(ROOT / "scripts" / profile_path, "successor_build_profile").load_builder()
    if receipt.get("signedTreeHash") != builder._tree_hash(signed_tree):
        raise SuccessorBlocked("SIGNED_TREE_HASH_DRIFT")
    if {item[1]: item[2] for item in builder.ALL_CASES}.get(GROWTH_ID) != expected_growth:
        raise SuccessorBlocked("GROWTH_VERSION_DRIFT")
    sys.path.insert(0, str(API_ROOT))
    try:
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.asset_registry.signature import FileTrustRootProvider

        trust = FileTrustRootProvider(trust_path).snapshot()
        root = trust.get_trust_root(publisher="aos", key_id=str(receipt["keyId"]))
        if root is None or root.revision != receipt.get("trustRootRevision"):
            raise SuccessorBlocked("TRUST_ROOT_REVISION_DRIFT")
        loader = ManifestLoader({source_alias: signed_tree}, trust_roots=trust)
        policy = ReleasePolicy(trust_roots=trust)
        for relative, bundle_id, _, _ in builder.ALL_CASES:
            loaded = loader.load(f"bundle://{source_alias}/{relative}")
            policy.evaluate(builder._release_record(loaded), checked_at=datetime.now(UTC))
            if loaded.content_hash != content[bundle_id]:
                raise SuccessorBlocked("SIGNED_CONTENT_DRIFT")
    finally:
        sys.path.remove(str(API_ROOT))
    return {"receipt": receipt, "signed_tree": signed_tree, "trust_path": trust_path,
            "builder": builder, "source_alias": source_alias}


def _clone_connection_parameters() -> dict[str, object]:
    raw = CLONE_ENV.read_text(encoding="utf-8").splitlines()
    values = dict(line.split("=", 1) for line in raw if line and not line.startswith("#"))
    if values.get("POSTGRES_USER") != "bg00dl_admin" or not values.get("POSTGRES_PASSWORD"):
        raise SuccessorBlocked("CLONE_CREDENTIAL_DRIFT")
    return {"host": "127.0.0.1", "port": PORT, "dbname": DATABASE,
            "user": values["POSTGRES_USER"], "password": values["POSTGRES_PASSWORD"]}


def check_live_clone() -> dict[str, object]:
    inspected = subprocess.run(
        ["docker", "--context", CONTEXT, "inspect", CONTAINER],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(inspected.stdout)[0]
    mounts = info.get("Mounts") or []
    ports = (info.get("NetworkSettings") or {}).get("Ports") or {}
    binding = ports.get("5432/tcp") or []
    if (info.get("State", {}).get("Running") is not True
            or len(mounts) != 1 or mounts[0].get("Name") != VOLUME
            or len(binding) != 1 or binding[0].get("HostIp") != "127.0.0.1"
            or binding[0].get("HostPort") != str(PORT)):
        raise SuccessorBlocked("CLONE_CONTAINER_DRIFT")
    from psycopg import connect
    with connect(**_clone_connection_parameters()) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        version = conn.execute("SELECT version_num FROM alembic_version").fetchall()
        if version != [("a0v_118",)]:
            raise SuccessorBlocked("CLONE_SCHEMA_DRIFT")
        counts = {table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                  for table in EXPECTED_BASELINE}
        if counts != EXPECTED_BASELINE:
            raise SuccessorBlocked("CLONE_BASELINE_DRIFT")
        old = conn.execute("""SELECT v.version,v.content_hash FROM asset_bundle_version v
            JOIN asset_bundle b ON b.bundle_pk=v.bundle_pk
            WHERE b.bundle_id=%s ORDER BY v.version""", (GROWTH_ID,)).fetchall()
        if old != [("1.11.0", "sha256:3d8817e01f53690adbd58698951c226e8c3917304a9ec4d7eee37d64bf02b328")]:
            raise SuccessorBlocked("OLD_GROWTH_DRIFT")
        baseline = json.loads(BASELINE_DIGESTS.read_text(encoding="utf-8"))
        if baseline.get("matched") is not True:
            raise SuccessorBlocked("CLONE_BASELINE_DIGEST_DRIFT")
        for table, expected in baseline["tables"].items():
            if table not in EXPECTED_BASELINE and table not in {
                "asset_bundle_version_event", "bundle_installation_command",
                "bundle_installation_decision", "bundle_installation_event",
                "bundle_installation_revision", "extension_runtime_configuration_stage_request",
                "extension_runtime_host_assignment_revision", "extension_runtime_host_identity_revision",
            }:
                raise SuccessorBlocked("CLONE_BASELINE_DIGEST_DRIFT")
            n, digest = conn.execute(
                f"SELECT count(*),coalesce(md5(string_agg(md5(row_to_json(t)::text),'' "
                f"ORDER BY md5(row_to_json(t)::text))),'EMPTY') FROM public.{table} t"
            ).fetchone()
            if (n, digest) != (expected["count"], expected["digest"]):
                raise SuccessorBlocked("CLONE_BASELINE_DIGEST_DRIFT")
    return {"database": DATABASE, "schema": "a0v_118", "counts": counts,
            "oldGrowthVersion": old[0][0], "oldGrowthHash": old[0][1]}


@contextmanager
def _connect_factory():
    from psycopg import connect
    from psycopg.rows import dict_row
    with connect(**_clone_connection_parameters(), row_factory=dict_row) as conn:
        if conn.info.dbname != DATABASE or conn.info.host != "127.0.0.1":
            raise SuccessorBlocked("CLONE_CONNECTION_DRIFT")
        yield conn


def _write_private(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _clone_backup(state: Path) -> dict[str, object]:
    command = ["docker", "--context", CONTEXT, "exec", CONTAINER,
               "pg_dump", "-U", "bg00dl_admin", "-d", DATABASE,
               "-Fc", "--serializable-deferrable"]
    with (state / "pre-successor.dump").open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        result = subprocess.run(command, stdout=handle, stderr=subprocess.PIPE)
    if result.returncode:
        raise SuccessorBlocked("CLONE_BACKUP_FAILED")
    path = state / "pre-successor.dump"
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _frozen_old_rows() -> dict[str, tuple[str, ...]]:
    with _connect_factory() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        return {table: tuple(sorted(row["row_json"] for row in conn.execute(
            f"SELECT row_to_json(t)::text AS row_json FROM public.{table} t"
        ))) for table in (
            "asset_bundle_version", "bundle_composition_lock", "bundle_installation",
            "bundle_installation_revision", "bundle_installation_event",
        )}


def _assert_old_rows_preserved(before: dict[str, tuple[str, ...]]) -> None:
    after = _frozen_old_rows()
    for table, rows in before.items():
        if not set(rows).issubset(after[table]):
            raise SuccessorBlocked(f"OLD_{table.upper()}_MUTATED")


def _assert_post_state(installation_id: str, growth_hash: str) -> dict[str, int]:
    with _connect_factory() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        counts = {table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
                  for table in EXPECTED_BASELINE}
        expected = dict(EXPECTED_BASELINE, asset_bundle_version=5,
                        bundle_composition_lock=2, bundle_installation=2)
        if counts != expected:
            raise SuccessorBlocked("POST_CLONE_COUNTS_DRIFT")
        growth = conn.execute("""SELECT v.content_hash,v.status FROM asset_bundle_version v
            JOIN asset_bundle b ON b.bundle_pk=v.bundle_pk
            WHERE b.bundle_id=%s AND v.version=%s""",
            (GROWTH_ID, GROWTH_VERSION)).fetchall()
        if len(growth) != 1 or growth[0]["content_hash"] != growth_hash or growth[0]["status"] != "published":
            raise SuccessorBlocked("POST_GROWTH_RELEASE_DRIFT")
        installation = conn.execute("""SELECT i.org_id,i.project_id,i.etag_version,
            i.active_revision,r.state FROM bundle_installation i
            JOIN bundle_installation_revision r ON r.installation_pk=i.installation_pk
            AND r.revision=i.current_revision WHERE i.installation_id=%s""",
            (installation_id,)).fetchall()
        if len(installation) != 1 or dict(installation[0]) != {
            "org_id": ORG_ID, "project_id": PROJECT_ID, "etag_version": 3,
            "active_revision": None, "state": "approved",
        }:
            raise SuccessorBlocked("POST_INSTALLATION_DRIFT")
        canary = conn.execute("SELECT count(*) AS n FROM bundle_installation WHERE org_id='dev-org'").fetchone()["n"]
        if canary:
            raise SuccessorBlocked("CANARY_INSTALLATION_FORBIDDEN")
    return counts


def _combined_trust_file(current: dict[str, object], successor: dict[str, object],
                         state: Path) -> Path:
    roots = []
    for evidence in (current, successor):
        payload = json.loads(evidence["trust_path"].read_text(encoding="utf-8"))
        if set(payload) != {"trustRoots"} or len(payload["trustRoots"]) != 1:
            raise SuccessorBlocked("TRUST_ROOT_SET_DRIFT")
        roots.extend(payload["trustRoots"])
    if len({(item["publisher"], item["keyId"]) for item in roots}) != 2:
        raise SuccessorBlocked("TRUST_ROOT_SET_DRIFT")
    path = state / "clone-only-trust-roots.json"
    _write_private(path, (json.dumps({"trustRoots": roots}, sort_keys=True) + "\n").encode())
    return path


def apply_clone(*, successor: dict[str, object], current: dict[str, object],
                state: Path, maker: str, checker: str) -> dict[str, object]:
    check_clone_actors(maker, checker)
    state = state.resolve()
    if state == ROOT or state.is_relative_to(ROOT) or state.exists():
        raise SuccessorBlocked("STATE_MUST_BE_NEW_OUTSIDE_REPOSITORY")
    check_live_clone()
    state.mkdir(mode=0o700)
    old_rows = _frozen_old_rows()
    intent = {"outcome": "CLONE_ONLY_INTENT", "database": DATABASE,
              "successorTreeHash": successor["receipt"]["signedTreeHash"],
              "currentTreeHash": current["receipt"]["signedTreeHash"],
              "maker": maker, "checker": checker, "createdAt": datetime.now(UTC).isoformat()}
    _write_private(state / "intent.json", (json.dumps(intent, sort_keys=True) + "\n").encode())
    backup = _clone_backup(state)
    trust_path = _combined_trust_file(current, successor, state)
    sys.path.insert(0, str(API_ROOT))
    try:
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.registry_service import RegistryService
        from aos_api.asset_registry.registry_store import PostgresRegistryStore
        from aos_api.asset_registry.signature import FileTrustRootProvider
        from aos_api.asset_registry.errors import AssetNotFoundError

        trust = FileTrustRootProvider(trust_path).snapshot()
        loader = ManifestLoader({successor["source_alias"]: successor["signed_tree"]},
                                trust_roots=trust)
        store = PostgresRegistryStore(connect_factory=_connect_factory)
        def database_clock():
            with _connect_factory() as conn:
                return conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        registry = RegistryService(store=store, loader=loader, clock=database_clock,
                                   trust_roots=trust)
        relative = next(item[0] for item in successor["builder"].ALL_CASES
                        if item[1] == GROWTH_ID)
        source_ref = f"bundle://{successor['source_alias']}/{relative}"
        loaded = loader.load(source_ref)
        if loaded.content_hash != successor["receipt"]["contentHashes"][GROWTH_ID]:
            raise SuccessorBlocked("SIGNED_CONTENT_DRIFT")
        try:
            store.get_version(GROWTH_ID, GROWTH_VERSION, publisher="aos")
        except AssetNotFoundError:
            registry.create_version(publisher="aos", bundle_id=GROWTH_ID,
                                    source_ref=source_ref, actor="bg00dm-growth-creator",
                                    roles={"asset-publisher"}, publisher_scopes={"aos"})
        else:
            raise SuccessorBlocked("SUCCESSOR_VERSION_ALREADY_EXISTS")
        registry.validate(publisher="aos", bundle_id=GROWTH_ID,
                          version=GROWTH_VERSION, actor="bg00dm-growth-validator",
                          roles={"asset-publisher"}, publisher_scopes={"aos"})
        registry.publish(publisher="aos", bundle_id=GROWTH_ID,
                         version=GROWTH_VERSION, actor="bg00dm-growth-publisher",
                         roles={"asset-publisher"}, publisher_scopes={"aos"})
        helper = _load(ROOT / "scripts/a0v_canonical_ecommerce_first_install.py", "bg00dm_install_helper")
        installed = helper.create_approved_first_installation(
            connect_factory=_connect_factory, state_dir=state,
            core_version="1.4.0", adapter_version="1.23.0",
            growth_version=GROWTH_VERSION, operations_version="1.2.0",
            idempotency_prefix="bg00dm-clone-growth-112-v1",
            trust_path=trust_path, overlay_revision="bg00dm-clone-growth-112-v1",
            display_name="栖月汇 growth 1.12 独立克隆安装候选",
            maker_actor=maker, checker_actor=checker,
        )
    finally:
        sys.path.remove(str(API_ROOT))
    _assert_old_rows_preserved(old_rows)
    if installed["installationState"] != "approved" or installed["installationEtag"] != 3:
        raise SuccessorBlocked("SUCCESSOR_INSTALLATION_DRIFT")
    counts = _assert_post_state(installed["installationId"], loaded.content_hash)
    result = {"outcome": "CLONE_SUCCESSOR_APPROVED_RUNTIME_BLOCKED",
              "database": DATABASE, "backup": backup, "installation": installed,
              "growthHash": loaded.content_hash, "runtimeHostStarted": False,
              "providerInvocationCount": 0, "externalPublicationCount": 0,
              "postCounts": counts}
    _write_private(state / "result.json", (json.dumps(result, sort_keys=True, indent=2) + "\n").encode())
    return result


def main() -> int:
    os.environ["AOS_DOTENV_DISABLED"] = "1"
    parser = argparse.ArgumentParser()
    parser.add_argument("--signed-receipt", type=Path, required=True)
    parser.add_argument("--current-signed-receipt", type=Path)
    parser.add_argument("--apply-clone", action="store_true")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--maker", default="bg00dm-clone-install-maker")
    parser.add_argument("--checker", default="bg00dm-clone-install-checker")
    parser.add_argument("--context", default=CONTEXT)
    parser.add_argument("--container", default=CONTAINER)
    parser.add_argument("--volume", default=VOLUME)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--database", default=DATABASE)
    parser.add_argument("--org-id", default=ORG_ID)
    parser.add_argument("--project-id", default=PROJECT_ID)
    args = parser.parse_args()
    check_clone_target(context=args.context, container=args.container, volume=args.volume,
                       port=args.port, database=args.database, org_id=args.org_id,
                       project_id=args.project_id)
    signed = check_signed_receipt(args.signed_receipt, expected_growth=GROWTH_VERSION)
    baseline = check_live_clone()
    if args.apply_clone:
        if args.current_signed_receipt is None or args.state_dir is None:
            raise SuccessorBlocked("APPLY_INPUTS_REQUIRED")
        current = check_signed_receipt(args.current_signed_receipt, expected_growth="1.11.0")
        result = apply_clone(successor=signed, current=current, state=args.state_dir,
                             maker=args.maker, checker=args.checker)
        print(json.dumps(result, sort_keys=True))
        return 0
    print(json.dumps({"outcome": "CLONE_SUCCESSOR_READONLY_PREFLIGHT_GREEN",
                      "signedTreeHash": signed["receipt"]["signedTreeHash"],
                      "trustRootRevision": signed["receipt"]["trustRootRevision"],
                      "baseline": baseline, "effects": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"outcome": "SAFE_BLOCKED", "reasonCode":
                          str(exc) if isinstance(exc, SuccessorBlocked) else type(exc).__name__}))
        raise SystemExit(2) from None
