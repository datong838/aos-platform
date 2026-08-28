"""XU2: same-observation-cutoff EvidencePack contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "data" / "export_source_readiness_evidence.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("source_readiness_evidence", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evidence_hash_is_canonical_and_payload_fields_are_excluded(monkeypatch) -> None:
    module = _load_module()

    class Envelope:
        def model_dump(self, **_kwargs):
            return {
                "schemaVersion": "aos.source-readiness/v1",
                "tenant": {"orgId": "org-org", "projectId": "dev-project"},
                "checkedAt": "2026-08-21T12:00:00Z",
                "cutoffAt": "2026-08-21T12:00:00Z",
                "status": "blocked",
                "sources": [
                    {
                        "pipelineId": f"P{index:02d}-x-qyh",
                        "blockers": ["QUALITY_POLICY_REF_MISSING"],
                    }
                    for index in range(1, 13)
                ],
            }

    class Service:
        def read(self, **_kwargs):
            return Envelope()

    monkeypatch.setattr(module, "build_source_readiness_service", lambda: Service())
    pack = module.build_evidence_pack(
        org_id="org-org",
        project_id="dev-project",
        source_commit="a" * 40,
    )
    evidence_hash = pack.pop("evidenceHash")
    canonical = json.dumps(
        pack, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert evidence_hash == hashlib.sha256(canonical).hexdigest()
    assert pack["observation"]["pipelineRunTimestampsRewritten"] is False
    serialized = json.dumps(pack, ensure_ascii=False).lower()
    assert "secret" not in serialized
    assert "rawpayload" not in serialized


def test_runtime_bootstrap_keeps_compatible_interpreter(tmp_path: Path) -> None:
    module = _load_module()
    calls: list[tuple[str, list[str]]] = []

    module.ensure_supported_runtime(
        version_info=(3, 11, 9),
        executable=tmp_path / "python",
        candidate=tmp_path / "repository-python",
        argv=["export_source_readiness_evidence.py", "--help"],
        execv=lambda executable, argv: calls.append((executable, argv)),
    )

    assert calls == []


def test_runtime_bootstrap_reexecutes_repository_interpreter(tmp_path: Path) -> None:
    module = _load_module()
    candidate = tmp_path / "repository-python"
    candidate.write_text("", encoding="utf-8")
    calls: list[tuple[str, list[str]]] = []

    module.ensure_supported_runtime(
        version_info=(3, 9, 18),
        executable=tmp_path / "system-python",
        candidate=candidate,
        argv=["export_source_readiness_evidence.py", "--help"],
        execv=lambda executable, argv: calls.append((executable, argv)),
    )

    assert calls == [
        (
            str(candidate),
            [str(candidate), "export_source_readiness_evidence.py", "--help"],
        )
    ]


def test_runtime_bootstrap_fails_closed_without_candidate(tmp_path: Path) -> None:
    module = _load_module()

    with pytest.raises(
        module.RuntimeBootstrapError,
        match="SOURCE_READINESS_PYTHON_RUNTIME_UNAVAILABLE",
    ):
        module.ensure_supported_runtime(
            version_info=(3, 9, 18),
            executable=tmp_path / "system-python",
            candidate=tmp_path / "missing-python",
            argv=["export_source_readiness_evidence.py"],
            execv=os.execv,
        )
