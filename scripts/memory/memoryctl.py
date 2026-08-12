#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MemoryErrorBase(RuntimeError):
    pass


class RevisionConflict(MemoryErrorBase):
    pass


class LeaseConflict(MemoryErrorBase):
    pass


class SecretDetected(MemoryErrorBase):
    pass


class MemoryPaths:
    def __init__(
        self,
        *,
        ai_root: Path,
        context_root: Path,
        codex_memory_root: Path,
        prime_harness_state: Path,
    ) -> None:
        self.ai_root = Path(ai_root)
        self.context_root = Path(context_root)
        self.codex_memory_root = Path(codex_memory_root)
        self.prime_harness_state = Path(prime_harness_state)

    @property
    def authority_path(self) -> Path:
        return self.context_root / "memory" / "authority.json"

    @property
    def manifest_path(self) -> Path:
        return self.context_root / "memory" / "projection-manifest.json"

    @property
    def leases_path(self) -> Path:
        return self.context_root / "memory" / "leases.json"

    @property
    def receipts_path(self) -> Path:
        return self.context_root / "memory" / "receipts"

    @property
    def events_path(self) -> Path:
        return self.context_root / "memory" / "events"

    @property
    def lock_path(self) -> Path:
        return self.context_root / "memory" / ".memoryctl.lock"

    @property
    def prime_version_state_path(self) -> Path:
        return self.context_root / "memory" / "prime-version-state.json"

    @property
    def prime_lock_path(self) -> Path:
        return self.prime_harness_state.parent / ".aos-memory-sync.lock"


DEFAULT_PATHS = MemoryPaths(
    ai_root=Path("/Users/ddt/work/projects/ai_agent"),
    context_root=Path("/Users/ddt/work/projects/ai_agent/docs/palantier/AOS项目开发上下文"),
    codex_memory_root=Path("/Users/ddt/.codex/memories"),
    prime_harness_state=Path("/Users/ddt/.prime/agent/harness/harness_state.json"),
)

REVISION_PATTERN = re.compile(r"^AOS-(\d{6})$")
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MARKER_PATTERN = re.compile(r"<!-- AOS_MEMORY_PROJECTION (\{.*?\}) -->")
MANAGED_PATTERN = re.compile(
    r"<!-- AOS_MEMORY_MANAGED_BEGIN -->.*?<!-- AOS_MEMORY_MANAGED_END -->\n?",
    re.DOTALL,
)
PRIME_MANAGED_PATTERN = re.compile(
    r"<!-- AOS_PRIME_PROJECTION_BEGIN -->.*?<!-- AOS_PRIME_PROJECTION_END -->\n?",
    re.DOTALL,
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(
        r"\b(?:api[_-]?key|token|password|cookie|secret)\s*[:=]\s*[\"']?"
        r"(?!AGNES_API_KEY\b|[A-Z][A-Z0-9_]{4,}\b)[A-Za-z0-9_./+:-]{12,}",
        re.IGNORECASE,
    ),
)

REQUIRED_AUTHORITY_FIELDS = {
    "schema",
    "project",
    "project_revision",
    "authority_owner",
    "current_phase",
    "delivery_status",
    "last_green_gate",
    "next_gate",
    "source_commits",
    "source_files",
    "hard_boundaries",
    "completed",
    "incomplete",
    "next_steps",
    "evidence",
    "evidence_cutoff",
    "updated_at",
}

REQUIRED_MANIFEST_FIELDS = {"schema", "authority", "projections"}
REQUIRED_TASK_RECEIPT_FIELDS = {
    "schema",
    "task_id",
    "owner",
    "base_revision",
    "scope",
    "excluded_scope",
    "expected_outputs",
    "lease_expires_at",
    "status",
    "created_at",
}
REQUIRED_DELIVERY_RECEIPT_FIELDS = {
    "schema",
    "task_id",
    "base_revision",
    "completed_revision",
    "result",
    "changed_files",
    "commits",
    "verification",
    "risks",
    "blockers",
    "completed_at",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def scan_secrets(value: Any) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise SecretDetected("potential credential detected; refusing shared-memory operation")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise MemoryErrorBase(f"required file is unavailable: {path}") from error
    except json.JSONDecodeError as error:
        raise MemoryErrorBase(f"invalid JSON: {path}") from error
    if not isinstance(payload, dict):
        raise MemoryErrorBase(f"JSON root must be an object: {path}")
    return payload


def validate_json_schema(value: Any, schema: dict[str, Any], *, source: str, pointer: str = "$") -> None:
    expected_type = schema.get("type")
    type_checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if expected_type and (expected_type not in type_checks or not type_checks[expected_type](value)):
        raise MemoryErrorBase(f"schema validation failed at {source}:{pointer}: expected {expected_type}")
    if "const" in schema and value != schema["const"]:
        raise MemoryErrorBase(f"schema validation failed at {source}:{pointer}: const mismatch")
    if "enum" in schema and value not in schema["enum"]:
        raise MemoryErrorBase(f"schema validation failed at {source}:{pointer}: enum mismatch")
    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            raise MemoryErrorBase(f"schema validation failed at {source}:{pointer}: string is too short")
        if schema.get("pattern") and not re.search(str(schema["pattern"]), value):
            raise MemoryErrorBase(f"schema validation failed at {source}:{pointer}: pattern mismatch")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise MemoryErrorBase(f"schema validation failed at {source}:{pointer}: invalid date-time") from error
    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            raise MemoryErrorBase(f"schema validation failed at {source}:{pointer}: array is too short")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                validate_json_schema(item, item_schema, source=source, pointer=f"{pointer}[{index}]")
    if isinstance(value, dict):
        required = set(schema.get("required", []))
        missing = required - value.keys()
        if missing:
            raise MemoryErrorBase(
                f"schema validation failed at {source}:{pointer}: missing {', '.join(sorted(missing))}"
            )
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                validate_json_schema(item, properties[key], source=source, pointer=f"{pointer}.{key}")
            elif schema.get("additionalProperties") is False:
                raise MemoryErrorBase(f"schema validation failed at {source}:{pointer}: unexpected key {key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                validate_json_schema(
                    item,
                    schema["additionalProperties"],
                    source=source,
                    pointer=f"{pointer}.{key}",
                )


def atomic_write_text(path: Path, content: str, *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_json(path: Path, payload: dict[str, Any], *, mode: int = 0o644) -> None:
    scan_secrets(payload)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", mode=mode)


def file_content_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


@contextmanager
def memory_lock(paths: MemoryPaths, *, exclusive: bool):
    paths.lock_path.parent.mkdir(parents=True, exist_ok=True)
    with paths.lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def prime_lock(paths: MemoryPaths):
    paths.prime_lock_path.parent.mkdir(parents=True, exist_ok=True)
    with paths.prime_lock_path.open("a+", encoding="utf-8") as handle:
        os.chmod(paths.prime_lock_path, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_authority(paths: MemoryPaths = DEFAULT_PATHS) -> dict[str, Any]:
    authority = read_json(paths.authority_path)
    missing = REQUIRED_AUTHORITY_FIELDS - authority.keys()
    if missing:
        raise MemoryErrorBase(f"authority is missing fields: {', '.join(sorted(missing))}")
    if authority.get("schema") != "aos-memory-authority/v1":
        raise MemoryErrorBase("unsupported authority schema")
    if not REVISION_PATTERN.fullmatch(str(authority.get("project_revision", ""))):
        raise MemoryErrorBase("invalid project_revision")
    scan_secrets(authority)
    return authority


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def authority_content_hash(authority: dict[str, Any]) -> str:
    stable = {key: value for key, value in authority.items() if key not in {"updated_at", "evidence_cutoff"}}
    return "sha256:" + hashlib.sha256(canonical_json(stable).encode()).hexdigest()


def canonical_projection(authority: dict[str, Any]) -> dict[str, Any]:
    return {
        "projection_schema": "aos-memory-projection/v1",
        "project": authority["project"],
        "project_revision": authority["project_revision"],
        "content_hash": authority_content_hash(authority),
        "current_phase": authority["current_phase"],
        "delivery_status": authority["delivery_status"],
        "last_green_gate": authority["last_green_gate"],
        "next_gate": authority["next_gate"],
        "source_commits": authority["source_commits"],
        "source_files": authority["source_files"],
        "hard_boundaries": authority["hard_boundaries"],
        "completed": authority["completed"],
        "incomplete": authority["incomplete"],
        "next_steps": authority["next_steps"],
        "evidence": authority["evidence"],
        "generated_at": authority["updated_at"],
    }


def projection_marker(projection: dict[str, Any]) -> str:
    marker = {
        "schema": projection["projection_schema"],
        "project_revision": projection["project_revision"],
        "content_hash": projection["content_hash"],
    }
    return f"<!-- AOS_MEMORY_PROJECTION {canonical_json(marker)} -->"


def load_manifest(paths: MemoryPaths = DEFAULT_PATHS) -> dict[str, Any]:
    manifest = read_json(paths.manifest_path)
    missing = REQUIRED_MANIFEST_FIELDS - manifest.keys()
    if missing:
        raise MemoryErrorBase(f"manifest is missing fields: {', '.join(sorted(missing))}")
    if manifest.get("schema") != "aos-memory-projection-manifest/v1":
        raise MemoryErrorBase("unsupported projection manifest schema")
    if not isinstance(manifest.get("projections"), list):
        raise MemoryErrorBase("manifest projections must be a list")
    return manifest


def load_prime_version_state(paths: MemoryPaths) -> dict[str, Any]:
    state = read_json(paths.prime_version_state_path)
    if state.get("schema") != "aos-memory-prime-version-state/v1":
        raise MemoryErrorBase("unsupported Prime version-state schema")
    if not isinstance(state.get("entries"), dict):
        raise MemoryErrorBase("Prime version-state entries must be an object")
    return state


def expand_path(raw: str, paths: MemoryPaths) -> Path:
    expanded = raw.replace("${CONTEXT_ROOT}", str(paths.context_root))
    expanded = expanded.replace("${AI_ROOT}", str(paths.ai_root))
    expanded = expanded.replace("${CODEX_MEMORY_ROOT}", str(paths.codex_memory_root))
    return Path(expanded)


def compare_revision(actual: str, expected: str) -> str:
    actual_match = REVISION_PATTERN.fullmatch(actual)
    expected_match = REVISION_PATTERN.fullmatch(expected)
    if not actual_match or not expected_match:
        return "UNVERSIONED"
    left, right = int(actual_match.group(1)), int(expected_match.group(1))
    if left < right:
        return "STALE"
    if left > right:
        return "AHEAD"
    return "CURRENT"


def parse_marker(text: str) -> dict[str, Any] | None:
    match = MARKER_PATTERN.search(text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def classify_marker(marker: dict[str, Any] | None, expected: dict[str, Any]) -> str:
    if not marker:
        return "UNVERSIONED"
    revision_status = compare_revision(str(marker.get("project_revision", "")), expected["project_revision"])
    if revision_status != "CURRENT":
        return revision_status
    return "CURRENT" if marker.get("content_hash") == expected["content_hash"] else "DRIFTED"


def read_projection_status(item: dict[str, Any], expected: dict[str, Any], paths: MemoryPaths) -> tuple[str, str]:
    adapter = item.get("adapter")
    if adapter in {"json_file", "authority_frontmatter"}:
        path = expand_path(str(item.get("path", "")), paths)
        if not path.exists():
            return "UNAVAILABLE", str(path)
        try:
            if adapter == "json_file":
                payload = read_json(path)
                marker = {
                    "project_revision": payload.get("project_revision"),
                    "content_hash": payload.get("content_hash"),
                }
            else:
                text = path.read_text(encoding="utf-8")
                marker = parse_marker(text)
        except (MemoryErrorBase, OSError):
            return "UNAVAILABLE", str(path)
        status = classify_marker(marker, expected)
        if status == "CURRENT" and adapter == "json_file" and payload != expected:
            status = "DRIFTED"
        if status == "CURRENT" and adapter == "authority_frontmatter" and render_frontmatter(text, expected) != text:
            status = "DRIFTED"
        return status, str(path)
    if adapter == "prime_harness":
        if not paths.prime_harness_state.exists() or not paths.prime_version_state_path.exists():
            return "UNAVAILABLE", str(paths.prime_harness_state)
        try:
            harness = read_json(paths.prime_harness_state)
            version_state = load_prime_version_state(paths)
            entry_id = str(item.get("entry_id"))
            entry = harness.get("entries", {}).get("memory", {}).get(entry_id)
            expected_entry = version_state.get("entries", {}).get(entry_id)
            marker = parse_marker(entry.get("content", "")) if isinstance(entry, dict) else None
        except (MemoryErrorBase, OSError):
            return "UNAVAILABLE", str(paths.prime_harness_state)
        marker_status = classify_marker(marker, expected)
        if marker_status != "CURRENT":
            return marker_status, entry_id
        if not isinstance(entry, dict) or not isinstance(expected_entry, dict):
            return "UNVERSIONED", entry_id
        version = entry.get("version")
        tracked_version = expected_entry.get("version")
        content = entry.get("content")
        if not isinstance(version, int) or not isinstance(tracked_version, int) or not isinstance(content, str):
            return "UNVERSIONED", entry_id
        if version != tracked_version:
            return "DRIFTED", entry_id
        if expected_entry.get("project_revision") != expected["project_revision"]:
            return "DRIFTED", entry_id
        if expected_entry.get("authority_content_hash") != expected["content_hash"]:
            return "DRIFTED", entry_id
        if expected_entry.get("entry_content_hash") != file_content_hash(content):
            return "DRIFTED", entry_id
        return "CURRENT", entry_id
    if adapter == "codex_ad_hoc":
        directory = expand_path(str(item.get("path", "")), paths)
        if not directory.exists():
            return "UNAVAILABLE", str(directory)
        candidates = sorted(directory.glob("*aos-memory-projection*.md"), reverse=True)
        if not candidates:
            return "PENDING_ASYNC", str(directory)
        marker = parse_marker(candidates[0].read_text(encoding="utf-8"))
        status = classify_marker(marker, expected)
        return ("PENDING_ASYNC" if status == "CURRENT" else status), str(candidates[0])
    return "UNAVAILABLE", f"unknown adapter: {adapter}"


def memory_status(paths: MemoryPaths = DEFAULT_PATHS) -> dict[str, Any]:
    with memory_lock(paths, exclusive=False):
        return _memory_status_locked(paths)


def _memory_status_locked(paths: MemoryPaths) -> dict[str, Any]:
    authority = load_authority(paths)
    expected = canonical_projection(authority)
    manifest = load_manifest(paths)
    results = []
    blocking_bad = False
    warning = False
    for item in manifest["projections"]:
        status, location = read_projection_status(item, expected, paths)
        consistency = item.get("consistency", "strong")
        results.append({"id": item.get("id"), "consistency": consistency, "status": status, "location": location})
        if consistency == "strong" and status != "CURRENT":
            blocking_bad = True
        elif status != "CURRENT":
            warning = True
    overall = "RED" if blocking_bad else "GREEN_WITH_WARNINGS" if warning else "GREEN"
    return {
        "project_revision": authority["project_revision"],
        "content_hash": expected["content_hash"],
        "delivery_status": authority["delivery_status"],
        "overall": overall,
        "projections": results,
    }


def render_frontmatter(original: str, projection: dict[str, Any]) -> str:
    marker = projection_marker(projection)
    managed = managed_projection_block(projection)
    block = (
        "---\n"
        "memory_schema: aos-memory-authority-ref/v1\n"
        f"project_revision: {projection['project_revision']}\n"
        f"authority_content_hash: {projection['content_hash']}\n"
        "---\n"
        f"{marker}\n"
        f"{managed}"
    )
    if original.startswith("---\n"):
        closing = original.find("\n---\n", 4)
        if closing != -1:
            rest = original[closing + 5 :]
            rest = MARKER_PATTERN.sub("", rest, count=1)
            rest = MANAGED_PATTERN.sub("", rest, count=1).lstrip("\n")
            return block + rest
    cleaned = MARKER_PATTERN.sub("", original, count=1)
    cleaned = MANAGED_PATTERN.sub("", cleaned, count=1).lstrip("\n")
    return block + cleaned


def managed_projection_block(projection: dict[str, Any]) -> str:
    def bullets(values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values) if values else "- 无"

    return (
        "<!-- AOS_MEMORY_MANAGED_BEGIN -->\n"
        "## Authority 管理状态（自动生成，请勿手改）\n\n"
        f"- 项目版本：`{projection['project_revision']}`\n"
        f"- 当前阶段：`{projection['current_phase']}`\n"
        f"- 交付状态：`{projection['delivery_status']}`\n"
        f"- 最后 GREEN 门：`{projection['last_green_gate']}`\n"
        f"- 下一门：`{projection['next_gate']}`\n\n"
        "### 已完成\n\n"
        f"{bullets(projection['completed'])}\n\n"
        "### 未完成\n\n"
        f"{bullets(projection['incomplete'])}\n\n"
        "### 下一步\n\n"
        f"{bullets(projection['next_steps'])}\n"
        "<!-- AOS_MEMORY_MANAGED_END -->\n"
    )


def projection_document(projection: dict[str, Any]) -> dict[str, Any]:
    return projection


def codex_note(projection: dict[str, Any]) -> str:
    return (
        "# AOS shared-memory projection candidate\n\n"
        f"{projection_marker(projection)}\n\n"
        f"- project_revision: `{projection['project_revision']}`\n"
        f"- current_phase: `{projection['current_phase']}`\n"
        f"- delivery_status: `{projection['delivery_status']}`\n"
        f"- last_green_gate: `{projection['last_green_gate']}`\n"
        f"- next_gate: `{projection['next_gate']}`\n"
        f"- hard_boundaries: {json.dumps(projection['hard_boundaries'], ensure_ascii=False)}\n"
        "- This is an ingestion candidate. Codex internal memory remains eventual until independently absorbed.\n"
    )


def sync_projections(paths: MemoryPaths = DEFAULT_PATHS, *, apply: bool, include_prime: bool = False) -> dict[str, Any]:
    if apply:
        with memory_lock(paths, exclusive=True):
            _validate_installation_locked(paths)
            return _sync_projections_locked(paths, apply=True, include_prime=include_prime)
    with memory_lock(paths, exclusive=False):
        _validate_installation_locked(paths)
        return _sync_projections_locked(paths, apply=False, include_prime=False)


def _sync_projections_locked(
    paths: MemoryPaths,
    *,
    apply: bool,
    include_prime: bool,
) -> dict[str, Any]:
    authority = load_authority(paths)
    projection = canonical_projection(authority)
    manifest = load_manifest(paths)
    changes: list[dict[str, Any]] = []
    prime_items: list[dict[str, Any]] = []
    for item in manifest["projections"]:
        adapter = item.get("adapter")
        if adapter == "prime_harness":
            prime_items.append(item)
            status, location = read_projection_status(item, projection, paths)
            if status != "CURRENT":
                changes.append({"id": item["id"], "status": status, "location": location})
            continue
        if adapter == "authority_frontmatter":
            path = expand_path(item["path"], paths)
            original = path.read_text(encoding="utf-8") if path.exists() else ""
            desired = render_frontmatter(original, projection)
        elif adapter == "json_file":
            path = expand_path(item["path"], paths)
            desired = json.dumps(projection_document(projection), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        elif adapter == "codex_ad_hoc":
            directory = expand_path(item["path"], paths)
            path = directory / f"{projection['project_revision'].lower()}-aos-memory-projection.md"
            desired = codex_note(projection)
        else:
            continue
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != desired:
            changes.append({"id": item["id"], "status": "CHANGE", "location": str(path)})
            if apply:
                scan_secrets(desired)
                atomic_write_text(path, desired)
    if apply and include_prime and prime_items:
        sync_prime(paths, projection, prime_items)
    return {"apply": apply, "changed": len(changes), "changes": changes, "project_revision": projection["project_revision"]}


def sync_prime(paths: MemoryPaths, projection: dict[str, Any], items: list[dict[str, Any]]) -> None:
    with prime_lock(paths):
        _sync_prime_locked(paths, projection, items)


def prime_projection_block(projection: dict[str, Any]) -> str:
    facts = {
        "project_revision": projection["project_revision"],
        "current_phase": projection["current_phase"],
        "delivery_status": projection["delivery_status"],
        "last_green_gate": projection["last_green_gate"],
        "next_gate": projection["next_gate"],
        "completed": projection["completed"],
        "incomplete": projection["incomplete"],
        "next_steps": projection["next_steps"],
        "hard_boundaries": projection["hard_boundaries"],
        "source_commits": projection["source_commits"],
        "evidence": projection["evidence"],
    }
    return (
        "<!-- AOS_PRIME_PROJECTION_BEGIN -->\n"
        "## AOS 权威投影（自动生成，请勿手改）\n\n"
        f"```json\n{json.dumps(facts, ensure_ascii=False, indent=2, sort_keys=True)}\n```\n\n"
        f"{projection_marker(projection)}\n"
        "<!-- AOS_PRIME_PROJECTION_END -->\n"
    )


def strip_prime_projection(content: str) -> str:
    cleaned = PRIME_MANAGED_PATTERN.sub("", content)
    cleaned = MARKER_PATTERN.sub("", cleaned)
    legacy_marker = cleaned.rfind("\n\n[2026-08-12 权威投影]")
    if legacy_marker >= 0:
        cleaned = cleaned[:legacy_marker]
    return cleaned.rstrip()


def _sync_prime_locked(paths: MemoryPaths, projection: dict[str, Any], items: list[dict[str, Any]]) -> None:
    if not paths.prime_harness_state.exists():
        raise MemoryErrorBase("Prime global harness state is unavailable")
    harness_raw = paths.prime_harness_state.read_text(encoding="utf-8")
    version_raw = paths.prime_version_state_path.read_text(encoding="utf-8")
    original_mtime = paths.prime_harness_state.stat().st_mtime_ns
    harness = read_json(paths.prime_harness_state)
    version_state = load_prime_version_state(paths)
    memories = harness.setdefault("entries", {}).setdefault("memory", {})
    if not isinstance(memories, dict):
        raise MemoryErrorBase("Prime harness memory entries must be an object")
    tracked_entries = version_state["entries"]
    changed_ids: list[str] = []

    for item in items:
        entry_id = str(item["entry_id"])
        existing = memories.get(entry_id)
        tracked = tracked_entries.get(entry_id, {})
        existing_version = existing.get("version", 0) if isinstance(existing, dict) else 0
        tracked_version = tracked.get("version", 0) if isinstance(tracked, dict) else 0
        if not isinstance(existing_version, int) or not isinstance(tracked_version, int):
            raise MemoryErrorBase(f"Prime projection version is invalid: {entry_id}")
        if isinstance(existing, dict) and isinstance(existing.get("content"), str):
            marker_status = classify_marker(parse_marker(existing["content"]), projection)
            is_current = (
                marker_status == "CURRENT"
                and existing_version == tracked_version
                and tracked.get("project_revision") == projection["project_revision"]
                and tracked.get("authority_content_hash") == projection["content_hash"]
                and tracked.get("entry_content_hash") == file_content_hash(existing["content"])
            )
            if is_current:
                continue
            history = strip_prime_projection(existing["content"])
            created_at = existing.get("created_at", utc_now())
        else:
            history = ""
            created_at = utc_now()
            existing = {}
        new_content = (history + "\n\n" if history else "") + prime_projection_block(projection)
        scan_secrets(new_content)
        new_version = max(existing_version, tracked_version) + 1
        metadata = existing.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        memories[entry_id] = {
            **existing,
            "id": entry_id,
            "kind": "memory",
            "title": str(item.get("title") or existing.get("title") or entry_id),
            "content": new_content,
            "path": str(item.get("path") or existing.get("path") or "aos/authority"),
            "scope": "global",
            "reference": existing.get("reference", {}),
            "arguments": existing.get("arguments", {}),
            "metadata": {**metadata, "aos_projection": True, "project_revision": projection["project_revision"]},
            "source": "aos-memory-sync",
            "created_at": created_at,
            "updated_at": utc_now(),
            "version": new_version,
        }
        tracked_entries[entry_id] = {
            "version": new_version,
            "project_revision": projection["project_revision"],
            "authority_content_hash": projection["content_hash"],
            "entry_content_hash": file_content_hash(new_content),
        }
        changed_ids.append(entry_id)

    if not changed_ids:
        return
    if paths.prime_harness_state.stat().st_mtime_ns != original_mtime:
        raise MemoryErrorBase("Prime harness changed concurrently; refusing to overwrite")

    backup_directory = paths.prime_harness_state.parent / "backups"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_directory / f"{timestamp}-before-{projection['project_revision']}.json"
    atomic_write_text(backup_path, harness_raw, mode=0o600)
    version_state["updated_at"] = utc_now()
    try:
        atomic_write_text(
            paths.prime_harness_state,
            json.dumps(harness, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            mode=0o600,
        )
        atomic_write_json(paths.prime_version_state_path, version_state)
        for item in items:
            status, _ = read_projection_status(item, projection, paths)
            if status != "CURRENT":
                raise MemoryErrorBase(f"Prime projection write-back verification failed: {item['id']}={status}")
    except Exception:
        atomic_write_text(paths.prime_harness_state, harness_raw, mode=0o600)
        atomic_write_text(paths.prime_version_state_path, version_raw)
        raise


def increment_revision(revision: str) -> str:
    match = REVISION_PATTERN.fullmatch(revision)
    if not match:
        raise MemoryErrorBase("invalid project_revision")
    return f"AOS-{int(match.group(1)) + 1:06d}"


def update_authority(
    paths: MemoryPaths = DEFAULT_PATHS,
    *,
    expected_revision: str,
    current_phase: str,
    delivery_status: str,
    last_green_gate: str,
    next_gate: str,
    completed: list[str] | None = None,
    incomplete: list[str] | None = None,
    next_steps: list[str] | None = None,
    source_commits: dict[str, str] | None = None,
    evidence: list[dict[str, str]] | None = None,
    evidence_cutoff: str | None = None,
) -> dict[str, Any]:
    with memory_lock(paths, exclusive=True):
        _validate_installation_locked(paths)
        authority = load_authority(paths)
        if authority["project_revision"] != expected_revision:
            raise RevisionConflict(f"expected {expected_revision}, found {authority['project_revision']}")
        updated = {
            **authority,
            "project_revision": increment_revision(expected_revision),
            "current_phase": current_phase,
            "delivery_status": delivery_status,
            "last_green_gate": last_green_gate,
            "next_gate": next_gate,
            "updated_at": utc_now(),
        }
        if completed is not None:
            updated["completed"] = completed
        if incomplete is not None:
            updated["incomplete"] = incomplete
        if next_steps is not None:
            updated["next_steps"] = next_steps
        if source_commits is not None:
            updated["source_commits"] = source_commits
        if evidence is not None:
            updated["evidence"] = evidence
        if evidence_cutoff is not None:
            updated["evidence_cutoff"] = evidence_cutoff
        atomic_write_json(paths.authority_path, updated)
        append_event(paths, {"type": "AUTHORITY_UPDATED", "project_revision": updated["project_revision"]})
        return updated


def load_leases(paths: MemoryPaths) -> dict[str, Any]:
    return read_json(paths.leases_path) if paths.leases_path.exists() else {"schema": "aos-memory-leases/v1", "leases": []}


def scopes_overlap(left: list[str], right: list[str]) -> bool:
    def normalized(value: str) -> str:
        return value.strip().strip("/")

    return any(
        a == b or a.startswith(b + "/") or b.startswith(a + "/")
        for a in map(normalized, left)
        for b in map(normalized, right)
    )


def validate_scope(scope: list[str]) -> None:
    if not scope:
        raise MemoryErrorBase("at least one scope is required")
    for value in scope:
        if not value.strip() or value.startswith("/") or "\\" in value:
            raise MemoryErrorBase("scope must be a non-empty repository-relative POSIX path")
        parts = value.strip("/").split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise MemoryErrorBase("scope cannot contain empty, dot or parent path segments")


def append_event(paths: MemoryPaths, event: dict[str, Any]) -> None:
    payload = {"schema": "aos-memory-event/v1", "occurred_at": utc_now(), **event}
    scan_secrets(payload)
    paths.events_path.mkdir(parents=True, exist_ok=True)
    day = datetime.now().astimezone().date().isoformat()
    path = paths.events_path / f"{day}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(payload) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def start_task(
    paths: MemoryPaths,
    *,
    task_id: str,
    owner: str,
    expected_revision: str,
    scope: list[str],
    excluded_scope: list[str],
    expected_outputs: list[str],
    lease_expires_at: str,
) -> dict[str, Any]:
    with memory_lock(paths, exclusive=True):
        _validate_installation_locked(paths)
        return _start_task_locked(
            paths,
            task_id=task_id,
            owner=owner,
            expected_revision=expected_revision,
            scope=scope,
            excluded_scope=excluded_scope,
            expected_outputs=expected_outputs,
            lease_expires_at=lease_expires_at,
        )


def _start_task_locked(
    paths: MemoryPaths,
    *,
    task_id: str,
    owner: str,
    expected_revision: str,
    scope: list[str],
    excluded_scope: list[str],
    expected_outputs: list[str],
    lease_expires_at: str,
) -> dict[str, Any]:
    if not TASK_ID_PATTERN.fullmatch(task_id):
        raise MemoryErrorBase("task_id must be path-safe and use letters, digits, dot, underscore or hyphen")
    if not owner.strip():
        raise MemoryErrorBase("owner is required")
    validate_scope(scope)
    if excluded_scope:
        validate_scope(excluded_scope)
    authority = load_authority(paths)
    if authority["project_revision"] != expected_revision:
        raise RevisionConflict(f"expected {expected_revision}, found {authority['project_revision']}")
    leases = load_leases(paths)
    now = datetime.now(timezone.utc)
    try:
        requested_expiry = datetime.fromisoformat(lease_expires_at).astimezone(timezone.utc)
    except ValueError as error:
        raise MemoryErrorBase("lease_expires_at must be an ISO-8601 date-time") from error
    if requested_expiry <= now:
        raise MemoryErrorBase("lease_expires_at must be in the future")
    active = []
    for lease in leases["leases"]:
        expiry = datetime.fromisoformat(lease["lease_expires_at"])
        if expiry.astimezone(timezone.utc) > now:
            active.append(lease)
            if scopes_overlap(scope, lease["scope"]):
                raise LeaseConflict(f"scope conflicts with active task {lease['task_id']}")
    receipt = {
        "schema": "aos-memory-task-receipt/v1",
        "task_id": task_id,
        "owner": owner,
        "base_revision": expected_revision,
        "scope": scope,
        "excluded_scope": excluded_scope,
        "expected_outputs": expected_outputs,
        "lease_expires_at": lease_expires_at,
        "status": "ACTIVE",
        "created_at": utc_now(),
    }
    scan_secrets(receipt)
    if any(item.get("task_id") == task_id for item in active):
        raise LeaseConflict(f"task already has an active lease: {task_id}")
    active.append(receipt)
    atomic_write_json(paths.leases_path, {"schema": "aos-memory-leases/v1", "leases": active})
    atomic_write_json(paths.receipts_path / "tasks" / f"{task_id}.json", receipt)
    append_event(paths, {"type": "TASK_STARTED", "task_id": task_id, "base_revision": expected_revision})
    return receipt


def complete_task(
    paths: MemoryPaths,
    *,
    task_id: str,
    expected_revision: str,
    result: str,
    changed_files: list[str],
    commits: list[str],
    verification: list[str],
    risks: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    with memory_lock(paths, exclusive=True):
        _validate_installation_locked(paths)
        return _complete_task_locked(
            paths,
            task_id=task_id,
            expected_revision=expected_revision,
            result=result,
            changed_files=changed_files,
            commits=commits,
            verification=verification,
            risks=risks,
            blockers=blockers,
        )


def _complete_task_locked(
    paths: MemoryPaths,
    *,
    task_id: str,
    expected_revision: str,
    result: str,
    changed_files: list[str],
    commits: list[str],
    verification: list[str],
    risks: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    if not TASK_ID_PATTERN.fullmatch(task_id):
        raise MemoryErrorBase("task_id must be path-safe and use letters, digits, dot, underscore or hyphen")
    authority = load_authority(paths)
    if authority["project_revision"] != expected_revision:
        raise RevisionConflict(f"expected {expected_revision}, found {authority['project_revision']}")
    leases = load_leases(paths)
    matching = [item for item in leases["leases"] if item.get("task_id") == task_id]
    if len(matching) != 1:
        raise LeaseConflict(f"no unique active lease for task: {task_id}")
    task_receipt = matching[0]
    receipt = {
        "schema": "aos-memory-delivery-receipt/v1",
        "task_id": task_id,
        "base_revision": task_receipt["base_revision"],
        "completed_revision": expected_revision,
        "result": result,
        "changed_files": changed_files,
        "commits": commits,
        "verification": verification,
        "risks": risks,
        "blockers": blockers,
        "completed_at": utc_now(),
    }
    scan_secrets(receipt)
    atomic_write_json(paths.receipts_path / "deliveries" / f"{task_id}.json", receipt)
    remaining = [item for item in leases["leases"] if item.get("task_id") != task_id]
    atomic_write_json(paths.leases_path, {"schema": "aos-memory-leases/v1", "leases": remaining})
    append_event(paths, {"type": "TASK_COMPLETED", "task_id": task_id, "result": result})
    return receipt


def validate_record(payload: dict[str, Any], *, schema: str, required: set[str], source: Path) -> None:
    if payload.get("schema") != schema:
        raise MemoryErrorBase(f"unexpected schema in {source}: {payload.get('schema')}")
    missing = required - payload.keys()
    if missing:
        raise MemoryErrorBase(f"{source} is missing fields: {', '.join(sorted(missing))}")
    scan_secrets(payload)


def validate_installation(paths: MemoryPaths = DEFAULT_PATHS) -> dict[str, Any]:
    with memory_lock(paths, exclusive=False):
        return _validate_installation_locked(paths)


def _validate_installation_locked(paths: MemoryPaths) -> dict[str, Any]:
    authority = load_authority(paths)
    manifest = load_manifest(paths)
    ids = [str(item.get("id", "")) for item in manifest["projections"]]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise MemoryErrorBase("projection ids must be non-empty and unique")
    allowed_adapters = {"json_file", "authority_frontmatter", "prime_harness", "codex_ad_hoc"}
    allowed_consistency = {"strong", "eventual"}
    for item in manifest["projections"]:
        if item.get("adapter") not in allowed_adapters:
            raise MemoryErrorBase(f"unsupported adapter in manifest: {item.get('adapter')}")
        if item.get("consistency") not in allowed_consistency:
            raise MemoryErrorBase(f"unsupported consistency in manifest: {item.get('consistency')}")
        if item.get("adapter") == "prime_harness" and not item.get("entry_id"):
            raise MemoryErrorBase(f"prime projection is missing entry_id: {item.get('id')}")
        if item.get("adapter") != "prime_harness" and not item.get("path"):
            raise MemoryErrorBase(f"file projection is missing path: {item.get('id')}")

    schema_names = {
        "authority.schema.json",
        "event.schema.json",
        "health.schema.json",
        "leases.schema.json",
        "projection.schema.json",
        "projection-manifest.schema.json",
        "task-receipt.schema.json",
        "delivery-receipt.schema.json",
        "prime-version-state.schema.json",
    }
    schema_directory = paths.context_root / "memory" / "schemas"
    schemas: dict[str, dict[str, Any]] = {}
    for name in sorted(schema_names):
        source = schema_directory / name
        schema_payload = read_json(source)
        if schema_payload.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise MemoryErrorBase(f"unsupported JSON Schema declaration: {source}")
        schemas[name] = schema_payload

    validate_json_schema(authority, schemas["authority.schema.json"], source=str(paths.authority_path))
    validate_json_schema(manifest, schemas["projection-manifest.schema.json"], source=str(paths.manifest_path))
    prime_version_state = load_prime_version_state(paths)
    validate_json_schema(
        prime_version_state,
        schemas["prime-version-state.schema.json"],
        source=str(paths.prime_version_state_path),
    )
    validate_json_schema(
        canonical_projection(authority),
        schemas["projection.schema.json"],
        source="canonical_projection(authority)",
    )
    leases = load_leases(paths)
    validate_json_schema(leases, schemas["leases.schema.json"], source=str(paths.leases_path))

    task_template_path = paths.context_root / "memory" / "templates" / "task-receipt-template.json"
    task_template = read_json(task_template_path)
    validate_record(
        task_template,
        schema="aos-memory-task-receipt/v1",
        required=REQUIRED_TASK_RECEIPT_FIELDS,
        source=task_template_path,
    )
    validate_json_schema(task_template, schemas["task-receipt.schema.json"], source=str(task_template_path))
    delivery_template_path = paths.context_root / "memory" / "templates" / "delivery-receipt-template.json"
    delivery_template = read_json(delivery_template_path)
    validate_record(
        delivery_template,
        schema="aos-memory-delivery-receipt/v1",
        required=REQUIRED_DELIVERY_RECEIPT_FIELDS,
        source=delivery_template_path,
    )
    validate_json_schema(
        delivery_template,
        schemas["delivery-receipt.schema.json"],
        source=str(delivery_template_path),
    )

    task_count = 0
    for source in sorted((paths.receipts_path / "tasks").glob("*.json")):
        receipt = read_json(source)
        validate_record(
            receipt,
            schema="aos-memory-task-receipt/v1",
            required=REQUIRED_TASK_RECEIPT_FIELDS,
            source=source,
        )
        validate_json_schema(receipt, schemas["task-receipt.schema.json"], source=str(source))
        task_count += 1
    delivery_count = 0
    for source in sorted((paths.receipts_path / "deliveries").glob("*.json")):
        receipt = read_json(source)
        validate_record(
            receipt,
            schema="aos-memory-delivery-receipt/v1",
            required=REQUIRED_DELIVERY_RECEIPT_FIELDS,
            source=source,
        )
        validate_json_schema(receipt, schemas["delivery-receipt.schema.json"], source=str(source))
        delivery_count += 1
    event_count = 0
    for source in sorted(paths.events_path.glob("*.jsonl")):
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise MemoryErrorBase(f"invalid JSONL event: {source}:{line_number}") from error
            if not isinstance(event, dict) or event.get("schema") != "aos-memory-event/v1":
                raise MemoryErrorBase(f"invalid event schema: {source}:{line_number}")
            validate_json_schema(event, schemas["event.schema.json"], source=f"{source}:{line_number}")
            scan_secrets(event)
            event_count += 1
    return {
        "status": "GREEN",
        "project_revision": authority["project_revision"],
        "projection_count": len(ids),
        "schema_count": len(schema_names),
        "task_receipt_count": task_count,
        "delivery_receipt_count": delivery_count,
        "event_count": event_count,
    }


def monitor_once(
    paths: MemoryPaths = DEFAULT_PATHS,
    *,
    output_path: Path | None = None,
) -> dict[str, Any]:
    with memory_lock(paths, exclusive=False):
        status = _memory_status_locked(paths)
        gate = evaluate_gate(load_authority(paths), status)
    payload = {
        "schema": "aos-memory-health/v1",
        "observed_at": utc_now(),
        "project_revision": status["project_revision"],
        "delivery_status": gate["delivery_status"],
        "memory_health": gate["memory_health"],
        "can_change_state": gate["can_change_state"],
        "projections": status["projections"],
    }
    target = output_path or Path("/Users/ddt/.prime/agent/memory-health.json")
    health_schema_path = paths.context_root / "memory" / "schemas" / "health.schema.json"
    if health_schema_path.exists():
        validate_json_schema(payload, read_json(health_schema_path), source="monitor health snapshot")
    atomic_write_json(target, payload, mode=0o600)
    return payload


def evaluate_gate(authority: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    return {
        "delivery_status": authority["delivery_status"],
        "memory_health": status["overall"],
        "can_change_state": status["overall"] in {"GREEN", "GREEN_WITH_WARNINGS"},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AOS shared-memory authority and projection control")
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("--json", action="store_true", dest="as_json")
    sync = subparsers.add_parser("sync")
    sync.add_argument("--json", action="store_true", dest="as_json")
    sync.add_argument("--apply", action="store_true")
    sync.add_argument("--prime", action="store_true")
    gate = subparsers.add_parser("gate")
    gate.add_argument("--json", action="store_true", dest="as_json")
    validate = subparsers.add_parser("validate")
    validate.add_argument("--json", action="store_true", dest="as_json")
    monitor = subparsers.add_parser("monitor")
    monitor.add_argument("--json", action="store_true", dest="as_json")
    monitor.add_argument("--quiet", action="store_true")
    update = subparsers.add_parser("authority-update")
    update.add_argument("--json", action="store_true", dest="as_json")
    update.add_argument("--expected-revision", required=True)
    update.add_argument("--current-phase", required=True)
    update.add_argument("--delivery-status", required=True)
    update.add_argument("--last-green-gate", required=True)
    update.add_argument("--next-gate", required=True)
    update.add_argument("--completed", action="append")
    update.add_argument("--incomplete", action="append")
    update.add_argument("--next-step", action="append")
    update.add_argument("--source-commit", action="append")
    update.add_argument("--evidence", action="append")
    update.add_argument("--evidence-cutoff")
    start = subparsers.add_parser("task-start")
    start.add_argument("--json", action="store_true", dest="as_json")
    start.add_argument("--task-id", required=True)
    start.add_argument("--owner", required=True)
    start.add_argument("--expected-revision", required=True)
    start.add_argument("--scope", action="append", required=True)
    start.add_argument("--excluded-scope", action="append", default=[])
    start.add_argument("--expected-output", action="append", default=[])
    start.add_argument("--lease-expires-at", required=True)
    complete = subparsers.add_parser("task-complete")
    complete.add_argument("--json", action="store_true", dest="as_json")
    complete.add_argument("--task-id", required=True)
    complete.add_argument("--expected-revision", required=True)
    complete.add_argument("--result", required=True)
    complete.add_argument("--changed-file", action="append", default=[])
    complete.add_argument("--commit", action="append", default=[])
    complete.add_argument("--verification", action="append", default=[])
    complete.add_argument("--risk", action="append", default=[])
    complete.add_argument("--blocker", action="append", default=[])
    return parser


def print_result(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def parse_pairs(values: list[str] | None, *, option: str) -> dict[str, str] | None:
    if values is None:
        return None
    parsed: dict[str, str] = {}
    for value in values:
        key, separator, item = value.partition("=")
        if not separator or not key or not item:
            raise MemoryErrorBase(f"{option} must use key=value")
        parsed[key] = item
    return parsed


def parse_evidence(values: list[str] | None) -> list[dict[str, str]] | None:
    if values is None:
        return None
    parsed: list[dict[str, str]] = []
    for value in values:
        kind, separator, ref = value.partition("=")
        if not separator or not kind or not ref:
            raise MemoryErrorBase("--evidence must use kind=ref")
        parsed.append({"kind": kind, "ref": ref})
    return parsed


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            result = memory_status()
        elif args.command == "sync":
            result = sync_projections(apply=args.apply, include_prime=args.prime)
        elif args.command == "gate":
            authority = load_authority()
            result = evaluate_gate(authority, memory_status())
        elif args.command == "validate":
            result = validate_installation()
        elif args.command == "monitor":
            result = monitor_once()
        elif args.command == "authority-update":
            result = update_authority(
                expected_revision=args.expected_revision,
                current_phase=args.current_phase,
                delivery_status=args.delivery_status,
                last_green_gate=args.last_green_gate,
                next_gate=args.next_gate,
                completed=args.completed,
                incomplete=args.incomplete,
                next_steps=args.next_step,
                source_commits=parse_pairs(args.source_commit, option="--source-commit"),
                evidence=parse_evidence(args.evidence),
                evidence_cutoff=args.evidence_cutoff,
            )
        elif args.command == "task-start":
            result = start_task(
                DEFAULT_PATHS,
                task_id=args.task_id,
                owner=args.owner,
                expected_revision=args.expected_revision,
                scope=args.scope,
                excluded_scope=args.excluded_scope,
                expected_outputs=args.expected_output,
                lease_expires_at=args.lease_expires_at,
            )
        else:
            result = complete_task(
                DEFAULT_PATHS,
                task_id=args.task_id,
                expected_revision=args.expected_revision,
                result=args.result,
                changed_files=args.changed_file,
                commits=args.commit,
                verification=args.verification,
                risks=args.risk,
                blockers=args.blocker,
            )
        if not (args.command == "monitor" and args.quiet):
            print_result(result, args.as_json)
        if args.command in {"gate", "monitor"} and not result["can_change_state"]:
            return 2
        return 0
    except MemoryErrorBase as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
