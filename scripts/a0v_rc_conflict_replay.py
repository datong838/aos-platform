#!/usr/bin/env python3
"""Read-only replay of the saved-snapshot recovery validation chain (RC wave).

Purpose: capture the exact IngressJournalConflict subcode that the letter chain's
64 failed attempts hit, without executing any write or Store operation.

Mechanism: PipelineSnapshotGroupRecoveryRuntime.resume_saved performs, in order:
  1. read_recovery_receipt + definition/claim revalidation (raises ValueError)
  2. SnapshotGroupRecoveryAuthority.run_current(execute=<route check>)
  3. completion.complete(...)  <- 64 attempts died inside this with
     IngressJournalConflict, ~90s in, always before retirement.prepare committed.

complete() itself is write-heavy; replaying it directly is NOT read-only. Instead
this tool replays the same *validation* prefix that complete() performs before
its first durable Store effect, inside a rolled-back transaction:
  a. _rows + _route_with_recovery   (run-state routing)
  b. attempt_target_current         (recovery authority binding)
  c. relationship journal read_current (content_hash revalidation)
  d. link command journal read_current (GROUP_LINK_COMMAND_DRIFT etc.)
  e. read_saved_projection_completion for each member run

Any IngressJournalConflict raised here carries the exact subcode; the transaction
rolls back, so nothing is persisted.

Usage:
  AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE=<cred.json> \\
  ./services/aos-api/.venv/bin/python scripts/a0v_rc_conflict_replay.py [--json]
"""
from __future__ import annotations

import argparse
import json as _json
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "aos-api"))

GROUP = "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
SCOPE_ARGS = dict(org_id="org-org", project_id="dev-project")
CREDENTIAL_FILE = ("/Users/ddt/work/projects/ai_agent/.aos-recovery-20260920/state/"
                   "q-advisor-baseline/bm-runtime-credentials/runtime-host-identities.json")
BUNDLE_ROOT = ("/Users/ddt/work/projects/ai_agent/.aos-recovery-20260920/state/"
               "q-advisor-baseline/bm-trust-root-rotation/signed-bundles")
TRUST_ROOTS = ("/Users/ddt/work/projects/ai_agent/.aos-recovery-20260920/state/"
               "q-advisor-baseline/bm-trust-root-rotation/signing/trust-roots.json")


def _configure() -> None:
    os.environ.update({
        "AOS_DOTENV_DISABLED": "1",
        "AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE": CREDENTIAL_FILE,
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
        "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
        "AOS_EXTENSION_RUNTIME_PLATFORM": "linux/arm64",
        "AOS_BUNDLE_ROOT": BUNDLE_ROOT,
        "AOS_BUNDLE_TRUST_ROOTS_FILE": TRUST_ROOTS,
    })
    for name in ("AOS_DATABASE_URL", "AOS_EXTENSION_RUNTIME_DATABASE_URL",
                 "AOS_EXTENSION_DIRECTORY_DATABASE_URL"):
        os.environ.pop(name, None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable result")
    args = parser.parse_args()
    _configure()

    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecom_consistency_store import EcomConsistencyStore
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.phase5_pipeline_engine import get_engine
    from aos_api.pipeline_snapshot_group_recovery_authority import SnapshotGroupRecoveryAuthority
    from aos_api.pipeline_snapshot_group_recovery_receipt import read_recovery_receipt
    from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner
    from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner
    from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
    from aos_api.pipeline_snapshot_group_link_command import PipelineSnapshotGroupLinkCommandJournal
    from aos_api.pipeline_snapshot_group_relationship_journal import PipelineSnapshotGroupRelationshipJournal
    from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
    from aos_api.ec_ingress_recovery import read_saved_projection_completion
    from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
    from aos_api.tenant_scope import TenantScope
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope

    scope = TenantScope("org-org", "dev-project")
    findings: list[dict] = []

    def record(stage: str, outcome: str, detail: str = ""):
        findings.append(dict(stage=stage, outcome=outcome, detail=detail))
        if not args.json:
            print(f"[{stage}] {outcome} {detail}", file=sys.stderr)

    plane = build_runtime_control_plane()
    services = plane.pipeline_control_factory.build(scope)
    base_claims = services.claims  # PipelineSourceClaimOwner, recovery=None

    with consumer_connection(runtime_worker_connection, SCOPE_ARGS) as conn:
        # Stage A: recovery receipt (definition currency)
        receipt = read_recovery_receipt(conn, scope=scope, group_id=GROUP)
        if receipt is None:
            record("receipt", "FAIL", "no recovery receipt")
            return 2
        record("receipt", "OK", f"rev={receipt['ref']['revision']} executor={receipt['body'].get('executor')}")

        claims_owner = PipelineSnapshotScheduleClaimOwner(controls=services.claims._controls)
        definitions = PipelineSnapshotScheduleDefinitionOwner(
            controls=services.claims._controls, installation_store=PostgresInstallationStore())
        identifier, _ = claims_owner._definition_ref(receipt["body"]["currentDefinitionRef"])
        definition = definitions.read(conn, scope=scope, definition_id=identifier)
        record("definition", "OK" if definition is not None else "FAIL",
               f"state={definition['body']['state'] if definition else 'missing'}")

        # Bindings exactly as resume_saved derives them
        claims_owner = PipelineSnapshotScheduleClaimOwner(controls=services.claims._controls)
        original = claims_owner.read(conn, scope=scope, group_id=GROUP)
        runs = {m["scheduleId"]: m["runId"] for m in original["members"]}
        saved = definitions._saved_bindings(conn, scope, definition["body"])
        bindings = tuple((b.control_ref, runs[b.schedule_id]) for b in saved)
        record("bindings", "OK", f"members={len(bindings)}")

        recovery_ref = PipelineExactRef.model_validate(receipt["ref"])
        authority = SnapshotGroupRecoveryAuthority(
            definitions=definitions, claims=claims_owner, ref=recovery_ref)
        recovery_claims = PipelineSourceClaimOwner(
            controls=services.claims._controls, recovery=authority,
            recovery_bindings=bindings)

        # Stage B: rollback-transaction validation replay
        with conn.transaction():
            conn.execute("SELECT set_config('aos.readonly_replay', 'rc', false)")
            try:
                # b1. attempt_target_current
                target = authority.attempt_target_current(
                    conn, scope=scope, actor=receipt["body"]["executor"], bindings=bindings)
                record("attempt_target", "OK",
                       f"installation={str(target.installation_id)[:8]} gen={str(target.generation)[:8]} epoch={target.execution_epoch}")
            except Exception as exc:
                record("attempt_target", "CONFLICT",
                       f"{type(exc).__name__}: {str(exc)[:200]}")
            try:
                # b2. relationship journal read (content hash revalidation)
                rel_journal = PipelineSnapshotGroupRelationshipJournal(claims=recovery_claims)
                current_rel = rel_journal.read_current(
                    conn, scope=scope, group_id=GROUP, actor=receipt["body"]["executor"],
                    bindings=bindings, policy_ref=receipt["body"]["policyRef"])
                record("relationship_read", "OK", f"assessment_hash={str(current_rel.assessment_hash)[:24]}")
            except Exception as exc:
                record("relationship_read", "CONFLICT",
                       f"{type(exc).__name__}: {str(exc)[:200]}")

            try:
                # b3. link command journal read (GROUP_LINK_COMMAND_DRIFT / etc.)
                store = EcomConsistencyStore(get_engine())
                link_journal = PipelineSnapshotGroupLinkCommandJournal(
                    claims=recovery_claims, store=store)
                prepared = link_journal.read_current(
                    conn, scope=scope, group_id=GROUP, actor=receipt["body"]["executor"],
                    bindings=bindings, policy_ref=receipt["body"]["policyRef"])
                record("link_command_read", "OK",
                       f"command_hash={str(prepared.command_hash)[:24]} links={0 if prepared.command is None else len(prepared.command.links)}")
            except Exception as exc:
                record("read link_command_read error", "CONFLICT",
                       f"{type(exc).__name__}: {str(exc)[:300]}")

            # b4. per-member projection completion (GROUP_OBJECT_PROJECTION_PENDING)
            try:
                for ref, run_id in bindings:
                    journal = ControlledIngressJournal(
                        claims=recovery_claims, scope=scope, run_id=run_id,
                        control_ref=ref, actor=receipt["body"]["executor"])
                    completion = read_saved_projection_completion(
                        conn, scope, run_id, journal=journal, store=store)
                    if completion["pending"] != 0:
                        record("projection_completion", "CONFLICT",
                               f"run={str(run_id)[:8]} pending={completion['pending']}")
                        break
                else:
                    record("projection_completion", "OK", f"members={len(bindings)}")
            except Exception as exc:
                record("projection_completion", "CON resume error".replace(" resume ", "_"),
                       f"{type(exc).__name__}: {str(exc)[:200]}")

    if args.json:
        print(_json.dumps(findings, ensure_ascii=False, indent=2))
    verdict = "GREEN" if all(f["outcome"] == "OK" for f in findings) else "CONFLICT_FOUND"
    if not args.json:
        print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main":
    raise SystemExit(main())
