#!/usr/bin/env python3
"""Export one same-observation-cutoff SourceReadiness EvidencePack.

This command is read-only with respect to PostgreSQL.  It records real run
timestamps as observed; it never rewrites them to manufacture a same-run
cutoff.  Missing policy/capability/config authority remains BLOCKED.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


MINIMUM_PYTHON = (3, 10)


class RuntimeBootstrapError(RuntimeError):
    """Raised when no compatible repository Python runtime is available."""


def _repository_python() -> Path:
    repository = Path(__file__).resolve().parents[2]
    return repository / "services" / "aos-api" / ".venv" / "bin" / "python"


def ensure_supported_runtime(
    *,
    version_info: tuple[int, ...] | Any = sys.version_info,
    executable: Path | str = sys.executable,
    candidate: Path | None = None,
    argv: list[str] | None = None,
    execv: Any = os.execv,
) -> None:
    """Re-exec with the repository runtime before importing ``aos_api``.

    The macOS system Python can be older than the API's minimum runtime.  A
    deterministic evidence command must not depend on the operator remembering
    to select the virtual environment manually.
    """

    current = tuple(version_info[:2])
    if current >= MINIMUM_PYTHON:
        return
    target = candidate or _repository_python()
    if not target.is_file():
        raise RuntimeBootstrapError(
            "SOURCE_READINESS_PYTHON_RUNTIME_UNAVAILABLE: "
            f"requires Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}+"
        )
    if Path(executable).resolve() == target.resolve():
        raise RuntimeBootstrapError(
            "SOURCE_READINESS_PYTHON_RUNTIME_INCOMPATIBLE: "
            f"requires Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}+"
        )
    command = argv if argv is not None else sys.argv
    execv(str(target), [str(target), *command])


try:
    ensure_supported_runtime()
except RuntimeBootstrapError as exc:
    raise SystemExit(str(exc)) from exc


from aos_api.source_readiness import build_source_readiness_service


SCHEMA_VERSION = "aos.source-readiness-evidence/v1"


def build_evidence_pack(
    *, org_id: str, project_id: str, source_commit: str
) -> dict[str, Any]:
    envelope = build_source_readiness_service().read(
        org_id=org_id,
        project_id=project_id,
    )
    readiness = envelope.model_dump(mode="json", by_alias=True)
    blockers = sorted(
        {
            blocker
            for source in readiness["sources"]
            for blocker in source["blockers"]
        }
    )
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "tenant": readiness["tenant"],
        "sourceCommit": source_commit,
        "observation": {
            "isolation": "repeatable-read-read-only",
            "checkedAt": readiness["checkedAt"],
            "cutoffAt": readiness["cutoffAt"],
            "pipelineRunTimestampsRewritten": False,
        },
        "status": readiness["status"],
        "blockers": blockers,
        "sourceReadiness": readiness,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload["evidenceHash"] = hashlib.sha256(canonical).hexdigest()
    return payload


def _git_state(repository: Path) -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return commit, dirty


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="development-only; evidence records HEAD but is not sealable",
    )
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    commit, dirty = _git_state(repository)
    if dirty and not args.allow_dirty:
        parser.error("worktree is dirty; commit the implementation before sealing evidence")
    payload = build_evidence_pack(
        org_id=args.org_id,
        project_id=args.project_id,
        source_commit=commit,
    )
    payload["sealable"] = not dirty
    _write_atomic(args.output, payload)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "status": payload["status"],
                "sourceCount": len(payload["sourceReadiness"]["sources"]),
                "blockerCount": len(payload["blockers"]),
                "sealable": payload["sealable"],
                "evidenceHash": payload["evidenceHash"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
