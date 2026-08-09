#!/usr/bin/env python3
"""O1-D alias migration CLI. Defaults to a read-only versioned manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aos_api.o1_alias_migration import (
    apply_manifest,
    approve_cleanup,
    cleanup,
    deterministic_hash,
    inventory,
    manifest,
    restore_rehearsal,
    seal_report,
    verify_manifest,
)
from aos_api.tenant_scope import TenantScope


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default="org-org")
    parser.add_argument("--workspace", default="dev-project")
    parser.add_argument("--run-id")
    parser.add_argument("--evidence-ref")
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument("--apply", action="store_true")
    commands.add_argument("--verify", action="store_true")
    commands.add_argument("--approve-cleanup", action="store_true")
    commands.add_argument("--cleanup", action="store_true")
    commands.add_argument("--restore-rehearsal", action="store_true")
    commands.add_argument("--seal", action="store_true")
    parser.add_argument("--actor", default="codex-o1d")
    return parser


def _required_run(value: str | None) -> uuid.UUID:
    if not value:
        raise SystemExit("--run-id is required for this command")
    return uuid.UUID(value)


def main() -> int:
    args = _parser().parse_args()
    scope = TenantScope(org_id=args.org, project_id=args.workspace)
    if (args.org, args.workspace) != ("org-org", "dev-project"):
        raise SystemExit("O1-D real migration is locked to org-org/dev-project")
    if args.verify:
        print(json.dumps(verify_manifest(scope, run_id=_required_run(args.run_id)), ensure_ascii=False))
        return 0
    if args.approve_cleanup:
        print(json.dumps({"approved": approve_cleanup(scope, run_id=_required_run(args.run_id), actor=args.actor)}))
        return 0
    if args.cleanup:
        print(json.dumps({"cleaned": cleanup(scope, run_id=_required_run(args.run_id))}))
        return 0
    if args.restore_rehearsal:
        print(json.dumps({"restoredThenRolledBack": restore_rehearsal(scope, run_id=_required_run(args.run_id))}))
        return 0
    if args.seal:
        run_id = _required_run(args.run_id)
        report = seal_report(scope, run_id=run_id)
        report["restoreRehearsalRows"] = restore_rehearsal(scope, run_id=run_id)
        report["generatedAt"] = datetime.now(timezone.utc).isoformat()
        report["gitSha"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            cwd=Path(__file__).resolve().parents[2], check=True,
        ).stdout.strip()
        report.pop("reportHash", None)
        report["reportHash"] = deterministic_hash(report)
        report_dir = Path(__file__).resolve().parents[1] / "tests" / "d5e" / "evidence"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = report_dir / f"O1-D_final_{stamp}.json"
        target.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        print(json.dumps({"evidence": str(target), "status": report["status"]}, ensure_ascii=False))
        return 0 if report["status"] == "GREEN" else 1

    run_id = uuid.UUID(args.run_id) if args.run_id else uuid.uuid4()
    entries = inventory(scope)
    body = manifest(scope, entries, run_id=run_id)
    evidence_dir = Path(__file__).resolve().parents[1] / "tests" / "d5e" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = evidence_dir / f"O1-D_alias_manifest_{stamp}.json"
    target.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    if args.apply:
        if not args.evidence_ref or not args.evidence_ref.startswith("sha256:"):
            raise SystemExit("--apply requires --evidence-ref sha256:<manifest hash>")
        expected = "sha256:" + body["manifestHash"]
        if args.evidence_ref != expected:
            raise SystemExit("--evidence-ref does not match current manifest")
        result = apply_manifest(scope, entries, run_id=run_id, evidence_ref=args.evidence_ref)
        body["applyResult"] = result
        target.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps({"evidence": str(target), "runId": str(run_id), "counts": body["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
