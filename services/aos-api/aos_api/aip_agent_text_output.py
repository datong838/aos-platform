"""Private retained output body, outside timeline metadata and receipts."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from aos_api.aip_contracts import ArtifactRef
from aos_api.tenant_scope import TenantScope


def validate_agent_text(text: str, content_hash: str, marking: list[str]) -> None:
    if (not isinstance(text, str) or len(text.encode("utf-8")) > 2097152
            or sha256(text.encode("utf-8")).hexdigest() != content_hash):
        raise ValueError("retained output text must be bounded and match exact hash")
    if (not isinstance(marking, list) or not marking
            or any(not isinstance(value, str) or value not in {"public", "internal", "confidential"} for value in marking)):
        raise ValueError("retained output requires explicit classification")


def write_agent_text(conn: Any, scope: TenantScope, artifact_id: str, text: str,
                     content_hash: str, marking: list[str]) -> None:
    """Append in the caller's artifact transaction; never commit independently."""
    validate_agent_text(text, content_hash, marking)
    row = conn.execute(
        """INSERT INTO aip_agent_text_output(org_id,project_id,artifact_id,content_text,content_hash,marking)
        SELECT org_id,project_id,artifact_id,%s,%s,%s::jsonb FROM aip_artifact
        WHERE org_id=%s AND project_id=%s AND artifact_id=%s
          AND artifact_type='agent_text_output' AND content_hash=%s AND marking=%s::jsonb
        RETURNING artifact_id""",
        (text, content_hash, json.dumps(marking), *scope.key, artifact_id, content_hash, json.dumps(marking)),
    ).fetchone()
    if row is None:
        raise ValueError("retained text does not match artifact authority")


def read_agent_text(conn: Any, scope: TenantScope, ref: ArtifactRef, *, markings: list[str]) -> str:
    if not isinstance(markings, list) or not markings or any(not isinstance(value, str) for value in markings):
        raise ValueError("explicit allowed markings required")
    if ref.artifact_type != "agent_text_output" or ref.revision != "1" or not ref.content_hash:
        raise ValueError("exact agent text artifact required")
    row = conn.execute(
        """SELECT body.content_text,body.content_hash,body.marking,
           artifact.content_hash AS artifact_hash,artifact.artifact_type,artifact.marking AS artifact_marking
        FROM aip_agent_text_output body JOIN aip_artifact artifact
          ON artifact.org_id=body.org_id AND artifact.project_id=body.project_id AND artifact.artifact_id=body.artifact_id
        WHERE body.org_id=%s AND body.project_id=%s AND body.artifact_id=%s""", (*scope.key, ref.artifact_id),
    ).fetchone()
    if (row is None or row["content_hash"] != ref.content_hash or row["artifact_hash"] != ref.content_hash
            or row["artifact_type"] != "agent_text_output" or row["marking"] != row["artifact_marking"]):
        raise ValueError("retained output unavailable in scope")
    validate_agent_text(row["content_text"], row["content_hash"], row["marking"])
    if not set(row["marking"]).issubset(set(markings)):
        raise ValueError("retained output unavailable in scope")
    return row["content_text"]
