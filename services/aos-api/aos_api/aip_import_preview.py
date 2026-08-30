"""Deterministic R18 import preview; no fetch, execution, persistence or install."""
from __future__ import annotations

import hashlib
import json

from aos_api.aip_contracts import TenantContext
from aos_api.aip_marketplace_import_contracts import (
    ImportEvidenceStatus,
    ImportPreviewRequest,
    ImportPreviewResponse,
    ImportStepEvidence,
)
from aos_api.aip_skill_scan import SkillSourceSnapshot, scan_skill_snapshot
from aos_api.auth import Principal


def _hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _step(step: str, status: ImportEvidenceStatus, payload: object, summary: str, blockers: list[str] | None = None) -> ImportStepEvidence:
    return ImportStepEvidence(
        step=step,
        status=status,
        content_hash=_hash(payload),
        blocker_codes=sorted(set(blockers or [])),
        summary=summary,
    )


def preview_import(principal: Principal, request: ImportPreviewRequest) -> ImportPreviewResponse:
    snapshot = SkillSourceSnapshot(
        source_ref=request.source.source_ref,
        source_commit=request.source.source_commit,
        license_id=request.source.license_id,
        sbom_ref=request.source.sbom_ref,
        files=request.source.files,
    )
    scan = scan_skill_snapshot(snapshot)
    source_payload = request.source.model_dump(mode="json", by_alias=True, exclude={"files"}) | {
        "fileHashes": {item.path: hashlib.sha256(item.content.encode("utf-8")).hexdigest() for item in request.source.files}
    }
    steps = [
        _step("source", ImportEvidenceStatus.PASSED, source_payload, "来源、版本、签名、许可证、依赖与 SBOM 引用已内容寻址"),
        _step(
            "scan",
            ImportEvidenceStatus.PASSED if scan.accepted else ImportEvidenceStatus.BLOCKED,
            scan.model_dump(mode="json", by_alias=True),
            "确定性扫描通过" if scan.accepted else "确定性扫描发现阻断项",
            [] if scan.accepted else [finding.rule_id for finding in scan.findings],
        ),
    ]
    mapping_payload = request.mapping.model_dump(mode="json", by_alias=True)
    mapping_blockers = []
    if request.kind.value == "capability" and (not request.mapping.input_schema or not request.mapping.output_schema):
        mapping_blockers.append("IMPORT_SCHEMA_MAPPING_REQUIRED")
    steps.append(
        _step(
            "mapping",
            ImportEvidenceStatus.BLOCKED if mapping_blockers else ImportEvidenceStatus.PASSED,
            mapping_payload,
            "映射缺少输入或输出 Schema" if mapping_blockers else "目标标识与映射合同已校验",
            mapping_blockers,
        )
    )
    security_payload = request.security.model_dump(mode="json", by_alias=True)
    security_blockers = []
    if request.security.risk_level in {"high", "critical"} and not request.security.network_policy_ref:
        security_blockers.append("IMPORT_NETWORK_POLICY_REQUIRED")
    if not scan.accepted:
        security_blockers.append("IMPORT_SCAN_BLOCKED")
    steps.append(
        _step(
            "security",
            ImportEvidenceStatus.BLOCKED if security_blockers else ImportEvidenceStatus.PASSED,
            security_payload,
            "安全或许可证门未通过" if security_blockers else "安全声明通过确定性预检",
            security_blockers,
        )
    )
    test_blockers = [] if not any(step.status is ImportEvidenceStatus.BLOCKED for step in steps) else ["IMPORT_PRECONDITION_BLOCKED"]
    steps.append(
        _step(
            "test",
            ImportEvidenceStatus.BLOCKED if test_blockers else ImportEvidenceStatus.EXTERNAL_REQUIRED,
            {"externalConnectivity": "not_run", "providerInvocation": "not_run"},
            "前置门未通过，禁止测试" if test_blockers else "合同预检完成；外部连通与 Provider 测试需要独立授权",
            test_blockers,
        )
    )
    request_payload = request.model_dump(mode="json", by_alias=True)
    content_hash = _hash({"request": request_payload, "steps": [item.model_dump(mode="json", by_alias=True) for item in steps]})
    blocked = any(item.status is ImportEvidenceStatus.BLOCKED for item in steps)
    return ImportPreviewResponse(
        tenant=TenantContext(org_id=principal.org_id, project_id=principal.project_id),
        preview_id=f"import-preview-{content_hash[:16]}",
        kind=request.kind,
        status="blocked" if blocked else "external_required",
        content_hash=content_hash,
        steps=steps,
        scan_artifact=scan,
    )


__all__ = ["preview_import"]
