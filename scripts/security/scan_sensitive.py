#!/usr/bin/env python3
"""Scan source and delivery trees for likely secrets and high-confidence PII.

The scanner never prints the matched value. Findings contain only rule id,
relative path, line number, severity, and a short one-way fingerprint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Mapping, Sequence, Set, Tuple


EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vite",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
}

PLACEHOLDER_MARKERS = {
    "change_me",
    "changeme",
    "demo",
    "dummy",
    "example",
    "fake",
    "invalid",
    "local",
    "not-a-real",
    "placeholder",
    "replace_me",
    "sample",
    "synthetic",
    "test-",
    "test_",
    "test-only",
    "your_",
    "xxxxx",
}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: str
    pattern: re.Pattern[str]
    placeholder_aware: bool = False


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    path: str
    line: int
    fingerprint: str


RULES: Tuple[Rule, ...] = (
    Rule(
        "PRIVATE_KEY",
        "critical",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    Rule("AWS_ACCESS_KEY", "critical", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    Rule(
        "KNOWN_TOKEN",
        "critical",
        re.compile(
            r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|"
            r"xox[baprs]-[A-Za-z0-9-]{20,}|"
            r"sk-(?:proj-)?[A-Za-z0-9_-]{24,})\b"
        ),
        placeholder_aware=True,
    ),
    Rule(
        "CREDENTIAL_URL",
        "critical",
        re.compile(
            r"\b[a-z][a-z0-9+.-]{1,20}://"
            r"[^/\s:@]{1,64}:([^/\s@]{8,})@",
            re.IGNORECASE,
        ),
        placeholder_aware=True,
    ),
    Rule(
        "GENERIC_SECRET",
        "warning",
        re.compile(
            r"(?i)\b(?:api[_-]?key|app[_-]?secret|client[_-]?secret|"
            r"access[_-]?token|refresh[_-]?token|password|passwd)\b"
            r"\s*[:=]\s*[\"']?([A-Za-z0-9+/_.:@=-]{8,})"
        ),
        placeholder_aware=True,
    ),
    Rule(
        "CN_MOBILE",
        "warning",
        re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    ),
    Rule(
        "EMAIL",
        "warning",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    Rule(
        "CN_ID",
        "warning",
        re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    ),
)


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _fingerprint(rule_id: str, path: str, line: int) -> str:
    """Return a stable location id without hashing low-entropy secret/PII data."""
    location = f"{rule_id}:{path}:{line}"
    return hashlib.sha256(location.encode("utf-8", errors="replace")).hexdigest()[:12]


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\0" in handle.read(4096)
    except OSError:
        return True


def _walk_explicit(path: Path) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    if not path.is_dir():
        return
    for current_root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        for filename in sorted(files):
            yield Path(current_root, filename)


def _git_tracked_files(root: Path) -> List[Path]:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [
        root / item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    ]


def collect_files(root: Path, paths: Sequence[str]) -> List[Path]:
    candidates: Iterable[Path]
    if paths:
        candidates = (
            file_path
            for raw_path in paths
            for file_path in _walk_explicit(Path(raw_path).expanduser().resolve())
        )
    else:
        candidates = _git_tracked_files(root)

    unique = {
        candidate.resolve()
        for candidate in candidates
        if candidate.is_file()
        and not any(part in EXCLUDED_DIRS for part in candidate.parts)
    }
    return sorted(unique, key=lambda item: item.as_posix())


def load_allowlist(path: Path | None) -> Set[Tuple[str, str]]:
    if path is None:
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("allowlist must be a JSON list")
    entries: Set[Tuple[str, str]] = set()
    for item in payload:
        if not isinstance(item, Mapping):
            raise ValueError("allowlist entry must be an object")
        rule = str(item.get("rule", "")).strip()
        file_path = str(item.get("path", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if not rule or not file_path or not reason:
            raise ValueError("allowlist entry requires rule, path, and reason")
        entries.add((rule, Path(file_path).as_posix()))
    return entries


def scan_file(
    path: Path,
    root: Path,
    allowlist: Set[Tuple[str, str]],
) -> List[Finding]:
    if _is_binary(path):
        return []

    display_path = _display_path(path, root)
    findings: List[Finding] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                for rule in RULES:
                    for match in rule.pattern.finditer(line):
                        captured = match.group(1) if match.lastindex else match.group(0)
                        if rule.placeholder_aware and _looks_like_placeholder(captured):
                            continue
                        if (rule.rule_id, display_path) in allowlist:
                            continue
                        findings.append(
                            Finding(
                                rule_id=rule.rule_id,
                                severity=rule.severity,
                                path=display_path,
                                line=line_number,
                                fingerprint=_fingerprint(
                                    rule.rule_id,
                                    display_path,
                                    line_number,
                                ),
                            )
                        )
    except OSError as exc:
        raise RuntimeError(f"cannot scan {display_path}: {exc}") from exc
    return findings


def scan(
    root: Path,
    paths: Sequence[str],
    allowlist: Set[Tuple[str, str]],
) -> Tuple[List[Finding], int]:
    findings: List[Finding] = []
    files = collect_files(root, paths)
    for path in files:
        findings.extend(scan_file(path, root, allowlist))
    return findings, len(files)


def _build_parser() -> argparse.ArgumentParser:
    default_allowlist = Path(__file__).resolve().with_name("allowlist.json")
    parser = argparse.ArgumentParser(
        description="Scan tracked files or explicit paths without printing secret values."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Explicit files/directories. Defaults to Git tracked files.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Repository root used for git ls-files and relative output paths.",
    )
    parser.add_argument(
        "--allowlist",
        default=str(default_allowlist) if default_allowlist.exists() else None,
        help="JSON allowlist with exact rule/path/reason entries.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Return failure when high-confidence PII warnings are found.",
    )
    parser.add_argument(
        "--report",
        choices=("all", "critical", "summary"),
        default="all",
        help="Control finding detail without changing scan coverage.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.repo_root).expanduser().resolve()
    try:
        allowlist = load_allowlist(
            Path(args.allowlist).expanduser().resolve() if args.allowlist else None
        )
        findings, file_count = scan(root, args.paths, allowlist)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"SCAN_ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    visible_findings = findings
    if args.report == "critical":
        visible_findings = [
            finding for finding in findings if finding.severity == "critical"
        ]
    elif args.report == "summary":
        visible_findings = []

    for finding in visible_findings:
        print(
            f"{finding.severity.upper()} {finding.rule_id} "
            f"{finding.path}:{finding.line} fingerprint={finding.fingerprint}"
        )

    critical_count = sum(item.severity == "critical" for item in findings)
    warning_count = sum(item.severity == "warning" for item in findings)
    print(
        f"SCAN_SUMMARY files={file_count} critical={critical_count} "
        f"warning={warning_count}"
    )
    if critical_count or (args.fail_on_warning and warning_count):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
