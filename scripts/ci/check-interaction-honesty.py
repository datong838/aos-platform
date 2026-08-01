#!/usr/bin/env python3
"""High-confidence interaction-honesty checks for the 36 audited web pages."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


EXPECTED_PAGE_COUNT = 36
ALLOWED_SOURCE_MODES = {"live", "mixed", "static"}
ALLOWED_WRITE_MODES = {"server", "demo", "none"}


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    detail: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.detail}"


def load_manifest(path: Path) -> list[dict[str, object]]:
    source = path.read_text(encoding="utf-8")
    marker = "export const INTERACTION_HONESTY_MANIFEST = "
    start = source.find(marker)
    if start < 0:
        raise ValueError(f"manifest marker missing: {marker.strip()}")
    start = source.find("[", start + len(marker))
    end_marker = "] as const satisfies readonly InteractionHonestyEntry[];"
    end = source.find(end_marker, start)
    if start < 0 or end < 0:
        raise ValueError("manifest array must remain strict JSON followed by the expected type assertion")
    payload = json.loads(source[start : end + 1])
    if not isinstance(payload, list):
        raise ValueError("manifest payload must be an array")
    return payload


def line_at(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _scan_source(path: str, source: str, writes: str) -> list[Finding]:
    findings: list[Finding] = []
    rules: tuple[tuple[str, re.Pattern[str], str], ...] = (
        (
            "IH001",
            re.compile(r"onClick\s*=\s*\{\s*\(\s*\)\s*=>\s*(?:undefined|\{\s*\})\s*\}"),
            "no-op onClick is forbidden on an audited production page",
        ),
        (
            "IH002",
            re.compile(r"href\s*=\s*[\"']#[\"']"),
            "placeholder href='#' must be a real route or explicit disabled control",
        ),
        (
            "IH003",
            re.compile(
                r"(?:const\s+(?:handle|on)[A-Z][\w$]*\s*=\s*(?:async\s*)?\([^)]*\)\s*=>|"
                r"function\s+(?:handle|on)[A-Z][\w$]*\s*\([^)]*\))\s*\{\s*\}",
                re.MULTILINE,
            ),
            "empty named interaction handler is forbidden",
        ),
    )
    for rule, pattern, detail in rules:
        for match in pattern.finditer(source):
            findings.append(Finding(rule, path, line_at(source, match.start()), detail))

    for match in re.finditer(r"<button\b(?P<attrs>[^>]*)>", source, re.DOTALL | re.IGNORECASE):
        attrs = match.group("attrs")
        interactive = re.search(r"\bon(?:Click|Pointer|Mouse|Key|Drag|Drop)\s*=", attrs)
        submit = re.search(r"\btype\s*=\s*(?:[\"']submit[\"']|\{[^}]*submit[^}]*\})", attrs)
        disabled = re.search(r"\b(?:disabled|aria-disabled)\b", attrs)
        delegated = re.search(r"\{\s*\.\.\.", attrs)
        if not (interactive or submit or disabled or delegated):
            findings.append(
                Finding(
                    "IH004",
                    path,
                    line_at(source, match.start()),
                    "button has no handler, submit behavior, disabled state, or delegated props",
                )
            )

    fallback_symbol = re.search(r"\b(?:MOCK|DEMO|FALLBACK)_[A-Z0-9_]+\b", source)
    fallback_label = re.search(
        r"[\"'`](?:[^\"'`]*(?:演示|示例|回落|降级|fallback|demo|mock)[^\"'`]*)[\"'`]",
        source,
        re.IGNORECASE,
    )
    if fallback_symbol and not fallback_label:
        findings.append(
            Finding(
                "IH005",
                path,
                line_at(source, fallback_symbol.start()),
                "fallback constant is not accompanied by explicit demo/source copy",
            )
        )

    if writes == "server":
        has_local_success = re.search(
            r"(?:localStorage|sessionStorage)[\s\S]{0,500}(?:成功|已保存|已发布|完成)|"
            r"(?:成功|已保存|已发布|完成)[\s\S]{0,500}(?:localStorage|sessionStorage)",
            source,
        )
        has_server_write = re.search(
            r"\b(?:apiPost|apiPut|apiPatch|apiDelete)(?:<[^;()]+>)?\s*\(|"
            r"fetch\s*\([^)]*\b(?:POST|PUT|PATCH|DELETE)\b",
            source,
        )
        if has_local_success and not has_server_write:
            findings.append(
                Finding(
                    "IH006",
                    path,
                    line_at(source, has_local_success.start()),
                    "server-write page has local-only success copy and no server write call",
                )
            )
    return findings


def load_allowlist(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("allowlist must be a JSON array")
    today = dt.date.today()
    for item in payload:
        if not all(str(item.get(key, "")).strip() for key in ("rule", "path", "reason", "expires")):
            raise ValueError("each allowlist entry requires rule, path, reason and expires")
        expiry = dt.date.fromisoformat(item["expires"])
        if expiry < today:
            raise ValueError(f"expired allowlist entry: {item['rule']} {item['path']} ({expiry})")
    return payload


def apply_allowlist(findings: Iterable[Finding], allowlist: list[dict[str, str]]) -> list[Finding]:
    return [
        finding
        for finding in findings
        if not any(
            item["rule"] == finding.rule
            and item["path"] == finding.path
            and (not item.get("line") or int(item["line"]) == finding.line)
            for item in allowlist
        )
    ]


def _check_explicit_app_binding(root: Path, entry: dict[str, object]) -> list[Finding]:
    """Guard audited root routes whose component is bound directly in App.tsx."""
    if entry.get("route") != "/apollo":
        return []
    app_path = root / "apps/web/src/App.tsx"
    app_source = app_path.read_text(encoding="utf-8")
    component = str(entry["component"])
    source_file = str(entry["sourceFile"])
    prefix = "apps/web/src/"
    if not source_file.startswith(prefix) or not source_file.endswith(".tsx"):
        return [Finding("IH020", str(app_path.relative_to(root)), 1, "invalid /apollo sourceFile")]
    import_path = "./" + source_file[len(prefix) : -4]
    lazy_binding = re.compile(
        rf"const\s+{re.escape(component)}\s*=\s*lazy\([\s\S]*?"
        rf"import\([\"']{re.escape(import_path)}[\"']\)[\s\S]*?default:\s*m\.{re.escape(component)}",
    )
    route_binding = re.compile(
        rf"<Route[\s\S]*?path=[\"']apollo[\"'][\s\S]*?<{re.escape(component)}\s*/>",
    )
    findings: list[Finding] = []
    if not lazy_binding.search(app_source):
        findings.append(
            Finding(
                "IH020",
                str(app_path.relative_to(root)),
                1,
                f"/apollo manifest expects {component} from {import_path}, but App.tsx binds another source",
            )
        )
    if not route_binding.search(app_source):
        findings.append(
            Finding(
                "IH020",
                str(app_path.relative_to(root)),
                1,
                f"/apollo is not routed to manifest component {component}",
            )
        )
    return findings


def check(root: Path, manifest_path: Path, allowlist_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        entries = load_manifest(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [Finding("IH000", str(manifest_path), 1, str(exc))]

    if len(entries) != EXPECTED_PAGE_COUNT:
        findings.append(
            Finding("IH010", str(manifest_path), 1, f"expected {EXPECTED_PAGE_COUNT} pages, found {len(entries)}")
        )
    routes = [str(entry.get("route", "")) for entry in entries]
    duplicates = sorted({route for route in routes if routes.count(route) > 1})
    if duplicates:
        findings.append(Finding("IH011", str(manifest_path), 1, f"duplicate routes: {', '.join(duplicates)}"))

    required = {"route", "component", "sourceFile", "sourceMode", "writes", "fallbackPolicy", "tests"}
    for index, entry in enumerate(entries, start=1):
        missing = sorted(key for key in required if not entry.get(key))
        if missing:
            findings.append(Finding("IH012", str(manifest_path), index, f"missing fields: {', '.join(missing)}"))
            continue
        if entry["sourceMode"] not in ALLOWED_SOURCE_MODES:
            findings.append(Finding("IH013", str(manifest_path), index, f"invalid sourceMode: {entry['sourceMode']}"))
        if entry["writes"] not in ALLOWED_WRITE_MODES:
            findings.append(Finding("IH014", str(manifest_path), index, f"invalid writes: {entry['writes']}"))
        tests = entry["tests"]
        if not isinstance(tests, list) or not tests:
            findings.append(Finding("IH015", str(manifest_path), index, "tests must be a non-empty array"))
            continue

        source_path = root / str(entry["sourceFile"])
        if not source_path.is_file():
            findings.append(Finding("IH016", str(entry["sourceFile"]), 1, "registered source file does not exist"))
        else:
            source = source_path.read_text(encoding="utf-8")
            component_pattern = re.compile(rf"\b{re.escape(str(entry['component']))}\b")
            if not component_pattern.search(source):
                findings.append(
                    Finding("IH017", str(entry["sourceFile"]), 1, f"component {entry['component']} not found in source")
                )
            findings.extend(_scan_source(str(entry["sourceFile"]), source, str(entry["writes"])))

        for test_path in tests:
            if not (root / str(test_path)).is_file():
                findings.append(Finding("IH018", str(test_path), 1, "registered acceptance test does not exist"))
        findings.extend(_check_explicit_app_binding(root, entry))

    try:
        allowlist = load_allowlist(allowlist_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings.append(Finding("IH019", str(allowlist_path), 1, str(exc)))
        allowlist = []
    return apply_allowlist(findings, allowlist)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--allowlist", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = args.manifest or root / "apps/web/src/interactionHonestyManifest.ts"
    allowlist = args.allowlist or root / "scripts/ci/interaction-honesty-allowlist.json"
    findings = check(root, manifest, allowlist)
    if findings:
        print("INTERACTION_HONESTY: FAIL", file=sys.stderr)
        for finding in findings:
            print(finding.render(), file=sys.stderr)
        return 1
    print(f"INTERACTION_HONESTY: PASS ({EXPECTED_PAGE_COUNT} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
