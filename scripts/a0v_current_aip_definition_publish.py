#!/usr/bin/env python3
"""One-intent current signed AIP definition publication; defaults to read-only."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from psycopg import connect
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
INTENT_NAME = "aip-definition-publication-1.11.0-intent.json"


class PublicationBlocked(RuntimeError):
    pass


def _load_script(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    if spec is None or spec.loader is None:
        raise PublicationBlocked("PREFLIGHT_MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _definition_rows(parameters):
    from aos_api.aip_current_definition_publication_gate import DefinitionRow

    statements = (
        ("agent", "SELECT template_id AS asset_id,revision,source_ref->>'revision' AS source_revision,content_hash FROM aip_agent_template_revision"),
        ("skill", "SELECT skill_id AS asset_id,revision,source_ref->>'revision' AS source_revision,content_hash FROM aip_skill_template_revision"),
        ("capability", "SELECT capability_id AS asset_id,revision,source_ref->>'revision' AS source_revision,content_hash FROM aip_capability_revision"),
    )
    rows = []
    with connect(**parameters, row_factory=dict_row) as conn:
        if conn.info.dbname != "aos_current_preview_20260927":
            raise PublicationBlocked("DATABASE_TARGET_DRIFT")
        conn.execute("SET TRANSACTION READ ONLY")
        for kind, statement in statements:
            rows.extend(DefinitionRow(kind=kind, **row) for row in conn.execute(statement).fetchall())
    return rows


def _write_intent(path: Path, payload: dict[str, object]) -> None:
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise PublicationBlocked("INTENT_ALREADY_EXISTS_FREEZE") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception as exc:
        raise PublicationBlocked("INTENT_DURABILITY_UNKNOWN_FREEZE") from exc


def _exact_readback(parameters, publication) -> None:
    from aos_api.aip_current_definition_publication_gate import (
        DefinitionWriteState, classify_definition_rows,
    )

    rows = _definition_rows(parameters)
    if classify_definition_rows(rows) is not DefinitionWriteState.COMPLETE:
        raise PublicationBlocked("DEFINITION_READBACK_INCOMPLETE_FREEZE")
    actual = {(row.kind, row.asset_id, row.revision): row.content_hash for row in rows}
    expected = {
        (kind, ref.asset_id, ref.revision): ref.content_hash
        for kind, refs in (
            ("agent", publication.agent_refs),
            ("skill", publication.skill_refs),
            ("capability", publication.capability_refs),
        )
        for ref in refs
    }
    if actual != expected or len(expected) != 53:
        raise PublicationBlocked("DEFINITION_READBACK_HASH_DRIFT_FREEZE")


def run(*, signed_receipt: Path, execute: bool = False, intent_id: str | None = None) -> dict[str, object]:
    os.environ["AOS_DOTENV_DISABLED"] = "1"
    sys.path.insert(0, str(API_ROOT))
    from aos_api.aip_current_definition_publication_gate import (
        DefinitionWriteState, classify_definition_rows,
    )
    from aos_api.aip_agent_registry_store import AipAgentRegistryStore
    from aos_api.aip_capability_registry import AipCapabilityRegistry
    from aos_api.aip_skill_registry import AipSkillRegistry
    from aos_api.aip_solution_pack_publisher import AipSolutionPackPublisher
    from aos_api.aip_solution_pack_signed_preflight import inspect_current_signed_source
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.asset_registry.signature import FileTrustRootProvider

    receipt_path = signed_receipt.resolve(strict=True)
    if receipt_path.name != "signing-receipt.json":
        raise PublicationBlocked("SIGNING_RECEIPT_PATH_DRIFT")
    parameters, report = _load_script("a0v_current_preview_http.py", "definition_preview").preflight(
        signed_receipt=receipt_path,
    )
    def factory():
        return connect(**parameters, row_factory=dict_row)

    trust_roots = FileTrustRootProvider(Path(str(report["trustRoots"])))
    reader = RegistrySnapshotReader(
        release_policy=ReleasePolicy(trust_roots=trust_roots), connect_factory=factory,
    )
    signed_root = Path(str(report["signedRoot"]))
    loader = ManifestLoader({"a0v-current": signed_root}, trust_roots=trust_roots)
    proof = inspect_current_signed_source(reader=reader, loader=loader, signed_root=signed_root)
    state = classify_definition_rows(_definition_rows(parameters))
    intent_path = receipt_path.parent / INTENT_NAME
    if not execute:
        return {"outcome": "CURRENT_DEFINITION_PUBLISH_READ_ONLY", "state": state.value,
                "database": report["database"], "sourceRef": proof.source_ref,
                "contentHash": proof.content_hash, "intentExists": intent_path.exists(), "writes": 0}
    if state is not DefinitionWriteState.EMPTY:
        raise PublicationBlocked("DEFINITION_ROWS_NOT_EMPTY_FREEZE")
    if not intent_id or str(UUID(intent_id)) != intent_id:
        raise PublicationBlocked("EXACT_INTENT_UUID_REQUIRED")
    _write_intent(intent_path, {
        "intentId": intent_id, "database": report["database"], "sourceRef": proof.source_ref,
        "contentHash": proof.content_hash, "signatureFingerprint": proof.signature_fingerprint,
        "snapshotHash": proof.registry_snapshot_hash, "expected": {"agents": 6, "skills": 37, "capabilities": 10},
        "startedAt": datetime.now(UTC).isoformat(),
    })
    if classify_definition_rows(_definition_rows(parameters)) is not DefinitionWriteState.EMPTY:
        raise PublicationBlocked("POST_INTENT_ROWS_NOT_EMPTY_FREEZE")
    fresh_parameters, fresh_report = _load_script(
        "a0v_current_preview_http.py", "definition_preview_at_write",
    ).preflight(signed_receipt=receipt_path)
    if fresh_parameters != parameters or fresh_report != report:
        raise PublicationBlocked("POST_INTENT_PREVIEW_DRIFT_FREEZE")
    fresh_proof = inspect_current_signed_source(reader=reader, loader=loader, signed_root=signed_root)
    if fresh_proof != proof:
        raise PublicationBlocked("POST_INTENT_SIGNED_SOURCE_DRIFT_FREEZE")
    publisher = AipSolutionPackPublisher(
        agent_store=AipAgentRegistryStore(connect_factory=factory),
        skill_store=AipSkillRegistry(connect_factory=factory),
        capability_store=AipCapabilityRegistry(connect_factory=factory),
    )
    bundle_dir = signed_root / "solution.ecommerce.growth" / "1.11.0"
    publication = publisher.publish_current_verified(
        bundle_dir, actor=f"a0v-current-definition:{intent_id}", source_proof=proof,
    )
    _exact_readback(parameters, publication)
    return {"outcome": "CURRENT_DEFINITION_PUBLISHED_EXACT", "intentId": intent_id,
            "database": report["database"], "sourceRef": proof.source_ref,
            "agents": 6, "skills": 37, "capabilities": 10, "runtimeBindings": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signed-receipt", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--intent-id")
    args = parser.parse_args()
    try:
        print(json.dumps(run(signed_receipt=args.signed_receipt, execute=args.execute,
                             intent_id=args.intent_id), sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"outcome": "SAFE_BLOCKED", "errorType": type(exc).__name__,
                          "reasonCode": str(exc) if isinstance(exc, PublicationBlocked) else "UNKNOWN_FREEZE"},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
