"""Fail-closed byte reads for same-tenant research artifacts.

The root comes from AOS_RESEARCH_ARTIFACT_ROOT. An unset, blank, or non-directory
root leaves every caller on its existing rejection path.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from aos_api.tenant_scope import TenantScope

_MAX_BYTES = 2_097_152
_CONTENT_REF = re.compile(r"\Aaos://research/([^/]+)/([^/]+)/(.+)\Z")


class ResearchArtifactStorageBlocked(ValueError):
    pass


class ResolvedResearchArtifact:
    def __init__(self, reference, value: str) -> None:
        self.reference = reference
        self.value = value


class ResearchArtifactStorage:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def content_hash(self, scope: TenantScope, content_ref: str) -> str:
        text = self.read_text(scope, content_ref)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def read_text(self, scope: TenantScope, content_ref: str) -> str:
        path = self._path(scope, content_ref)
        size = path.stat().st_size
        if size > _MAX_BYTES:
            raise ResearchArtifactStorageBlocked("research artifact is too large")
        data = path.read_bytes()
        if len(data) > _MAX_BYTES:
            raise ResearchArtifactStorageBlocked("research artifact is too large")
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ResearchArtifactStorageBlocked("research artifact is not utf-8") from exc

    def resolve_memo(self, scope: TenantScope, artifact_ref, *, lookup) -> ResolvedResearchArtifact:
        content_ref, recorded_hash = lookup(scope, artifact_ref.artifact_id)
        text = self.read_text(scope, content_ref)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        presented = artifact_ref.content_hash
        if digest != recorded_hash or (presented is not None and presented != digest):
            raise ResearchArtifactStorageBlocked("research artifact content hash drifted")
        return ResolvedResearchArtifact(artifact_ref, text)

    def _path(self, scope: TenantScope, content_ref: str) -> Path:
        parts = _relative_parts(scope, content_ref)
        root = self._root.resolve()
        base = (self._root / scope.org_id / scope.project_id).resolve()
        if not base.is_relative_to(root):
            raise ResearchArtifactStorageBlocked("research artifact tenant root escaped")
        target = base.joinpath(*parts).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            raise ResearchArtifactStorageBlocked("research artifact is outside the tenant root")
        return target


def configured_root() -> Path | None:
    raw = os.environ.get("AOS_RESEARCH_ARTIFACT_ROOT", "")
    if raw.strip() == "":
        return None
    root = Path(raw)
    if not root.is_dir():
        return None
    return root


def configured_artifact_hash_resolver():
    root = configured_root()
    if root is None:
        return None
    return ResearchArtifactStorage(root).content_hash


def lookup_recorded_artifact(scope: TenantScope, artifact_id: str) -> tuple[str, str]:
    from aos_api.db import connect_read_only

    with connect_read_only(scope) as conn:
        row = conn.execute(
            """SELECT content_ref, content_hash
               FROM aip_artifact
               WHERE org_id=%s AND project_id=%s AND artifact_id=%s""",
            (scope.org_id, scope.project_id, artifact_id),
        ).fetchone()
    if row is None or not row["content_ref"] or not row["content_hash"]:
        raise ResearchArtifactStorageBlocked("research artifact is not visible")
    return row["content_ref"], row["content_hash"]


def configured_memo_resolver():
    root = configured_root()
    if root is None:
        return None
    storage = ResearchArtifactStorage(root)

    def resolve(scope, artifact_ref):
        return storage.resolve_memo(scope, artifact_ref, lookup=lookup_recorded_artifact)

    return resolve


def _relative_parts(scope: TenantScope, content_ref: str) -> tuple[str, ...]:
    if not isinstance(content_ref, str) or "\\" in content_ref or "\x00" in content_ref:
        raise ResearchArtifactStorageBlocked("research artifact ref is closed")
    match = _CONTENT_REF.fullmatch(content_ref)
    if match is None:
        raise ResearchArtifactStorageBlocked("research artifact ref is closed")
    org, project, relative = match.groups()
    if org != scope.org_id or project != scope.project_id:
        raise ResearchArtifactStorageBlocked("research artifact tenant does not match")
    if "/" in scope.org_id or "/" in scope.project_id:
        raise ResearchArtifactStorageBlocked("research artifact tenant does not match")
    parts = tuple(relative.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise ResearchArtifactStorageBlocked("research artifact ref is closed")
    return parts
