"""Deterministic, non-executing Skill source scanner for AIP-6 A6G-0."""
from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef

MAX_FILES = 256
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024
SCANNER_ID = "aos.deterministic-skill-scan"
SCANNER_VERSION = "1.0.0"


class ScanSeverity(StrEnum):
    BLOCK = "block"
    WARN = "warn"


class ScanStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"


class SkillSourceFile(AipContractModel):
    path: str = Field(min_length=1, max_length=512)
    content: str

    @field_validator("path")
    @classmethod
    def _safe_relative_path(cls, value: str) -> str:
        normalized = value.strip().replace("\\", "/")
        path = PurePosixPath(normalized)
        if (
            not normalized
            or normalized.startswith("./")
            or "//" in normalized
            or path.is_absolute()
            or ".." in path.parts
            or "." in path.parts
            or str(path) != normalized
        ):
            raise ValueError("skill source path must be a normalized relative path")
        return normalized

    @model_validator(mode="after")
    def _bounded_utf8_text(self) -> SkillSourceFile:
        try:
            encoded = self.content.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("skill source content must be valid UTF-8 text") from exc
        if "\x00" in self.content:
            raise ValueError("skill source content must not contain NUL bytes")
        if len(encoded) > MAX_FILE_BYTES:
            raise ValueError("skill source file exceeds the byte limit")
        return self


class SkillSourceSnapshot(AipContractModel):
    source_ref: ResourceRef
    source_commit: str = Field(pattern=r"^[0-9a-f]{7,64}$")
    license_id: str = Field(min_length=1, max_length=120)
    sbom_ref: ResourceRef
    files: list[SkillSourceFile] = Field(min_length=1, max_length=MAX_FILES)

    @field_validator("license_id")
    @classmethod
    def _normalized_license(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _unique_bounded_files(self) -> SkillSourceSnapshot:
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("skill source paths must be unique")
        total = sum(len(item.content.encode("utf-8")) for item in self.files)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("skill source snapshot exceeds the total byte limit")
        return self


class ScanFinding(AipContractModel):
    rule_id: str
    category: str
    severity: ScanSeverity
    path: str
    line: int = Field(ge=1)
    message: str
    evidence_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ScanArtifact(AipContractModel):
    scanner_id: str
    scanner_version: str
    rule_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_ref: ResourceRef
    source_commit: str
    source_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    license_id: str
    sbom_ref: ResourceRef
    findings: list[ScanFinding]
    status: ScanStatus
    accepted: bool
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _status_matches_findings(self) -> ScanArtifact:
        blocked = any(item.severity is ScanSeverity.BLOCK for item in self.findings)
        if self.accepted == blocked:
            raise ValueError("accepted must be false when a blocking finding exists")
        expected = ScanStatus.BLOCKED if blocked else ScanStatus.PASSED
        if self.status is not expected:
            raise ValueError("scan status does not match findings")
        return self


_RULE_DEFINITIONS: tuple[tuple[str, str, str, str], ...] = (
    ("SKILL.DYNAMIC_EXEC", "execution", r"\b(?:eval|exec)\s*\(", "动态执行被禁止"),
    ("SKILL.SHELL_EXEC", "execution", r"(?:\bos\.system\s*\(|\bsubprocess\.|\bshell\s*=\s*True\b|\bchild_process\.exec\s*\(|\brm\s+-rf\b|\bcurl\b[^|\n]*\|\s*(?:sh|bash)\b)", "Shell 或子进程执行被禁止"),
    ("SKILL.PATH_ESCAPE", "filesystem", r"(?:\.\./|~/\.ssh|[\"']/(?:etc|root|Users|private|var)/)", "越权或逃逸路径被禁止"),
    ("SKILL.NETWORK_ACCESS", "network", r"(?:\bimport\s+(?:requests|httpx|socket|urllib)|\bfrom\s+(?:requests|httpx|socket|urllib)\b|\bfetch\s*\(|\baxios\.|\bnew\s+WebSocket\s*\()", "未声明网络外联被禁止"),
    ("SKILL.SECRET_ACCESS", "secret", r"(?:\bos\.getenv\s*\(|\bos\.environ\b|\bprocess\.env\b|~/\.(?:aws|config/gcloud)|[\"']/(?:run/secrets|var/run/secrets)/)", "直接读取环境或凭据被禁止"),
    ("SKILL.PROMPT_INJECTION", "prompt", r"(?i)(?:ignore\s+(?:all\s+)?previous\s+instructions|reveal\s+(?:the\s+)?system\s+prompt|忽略(?:以上|之前|先前).{0,12}(?:指令|规则)|泄露.{0,8}系统提示词)", "提示注入内容被禁止"),
)

_PERMISSIVE_LICENSES = frozenset({"MIT", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "ISC"})


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _rule_set_hash() -> str:
    return _canonical_hash({"rules": _RULE_DEFINITIONS, "licenses": sorted(_PERMISSIVE_LICENSES)})


def _source_payload(snapshot: SkillSourceSnapshot) -> dict[str, object]:
    return {
        "sourceRef": snapshot.source_ref.model_dump(mode="json", by_alias=True),
        "sourceCommit": snapshot.source_commit,
        "licenseId": snapshot.license_id,
        "sbomRef": snapshot.sbom_ref.model_dump(mode="json", by_alias=True),
        "files": [
            {"path": item.path, "contentHash": hashlib.sha256(item.content.encode("utf-8")).hexdigest()}
            for item in sorted(snapshot.files, key=lambda value: value.path)
        ],
    }


def _finding(rule_id: str, category: str, message: str, path: str, line: int, evidence: str) -> ScanFinding:
    return ScanFinding(
        rule_id=rule_id,
        category=category,
        severity=ScanSeverity.BLOCK,
        path=path,
        line=line,
        message=message,
        evidence_hash=hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
    )


def scan_skill_snapshot(snapshot: SkillSourceSnapshot) -> ScanArtifact:
    """Scan a caller-supplied immutable snapshot without I/O or code execution."""
    findings: list[ScanFinding] = []
    for source_file in sorted(snapshot.files, key=lambda value: value.path):
        for line_number, line in enumerate(source_file.content.splitlines() or [""], start=1):
            for rule_id, category, expression, message in _RULE_DEFINITIONS:
                if re.search(expression, line):
                    findings.append(_finding(rule_id, category, message, source_file.path, line_number, line))

    normalized_license = snapshot.license_id.upper()
    if normalized_license not in _PERMISSIVE_LICENSES:
        findings.append(
            _finding(
                "SKILL.LICENSE_NOT_ALLOWED",
                "license",
                "许可证不在交付允许清单",
                "<manifest>",
                1,
                normalized_license,
            )
        )

    findings.sort(key=lambda item: (item.path, item.line, item.rule_id))
    blocked = bool(findings)
    source_payload = _source_payload(snapshot)
    source_content_hash = _canonical_hash(source_payload)
    artifact_payload = {
        "scannerId": SCANNER_ID,
        "scannerVersion": SCANNER_VERSION,
        "ruleSetHash": _rule_set_hash(),
        **source_payload,
        "sourceContentHash": source_content_hash,
        "findings": [item.model_dump(mode="json", by_alias=True) for item in findings],
        "status": ScanStatus.BLOCKED.value if blocked else ScanStatus.PASSED.value,
        "accepted": not blocked,
    }
    return ScanArtifact(
        scanner_id=SCANNER_ID,
        scanner_version=SCANNER_VERSION,
        rule_set_hash=_rule_set_hash(),
        source_ref=snapshot.source_ref,
        source_commit=snapshot.source_commit,
        source_content_hash=source_content_hash,
        license_id=snapshot.license_id,
        sbom_ref=snapshot.sbom_ref,
        findings=findings,
        status=ScanStatus.BLOCKED if blocked else ScanStatus.PASSED,
        accepted=not blocked,
        artifact_hash=_canonical_hash(artifact_payload),
    )


__all__ = [
    "MAX_FILE_BYTES",
    "MAX_FILES",
    "MAX_TOTAL_BYTES",
    "SCANNER_ID",
    "SCANNER_VERSION",
    "ScanArtifact",
    "ScanFinding",
    "ScanSeverity",
    "ScanStatus",
    "SkillSourceFile",
    "SkillSourceSnapshot",
    "scan_skill_snapshot",
]
