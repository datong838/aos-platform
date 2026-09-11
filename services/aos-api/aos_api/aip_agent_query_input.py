"""Private retained AgentRun query, outside generic Artifact metadata."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from aos_api.aip_contracts import ArtifactRef
from aos_api.tenant_scope import TenantScope


def validate_agent_query(
    query: str,
    content_hash: str,
    request_hash: str,
    marking: list[str],
) -> None:
    if (
        type(query) is not str
        or not query.strip()
        or len(query) > 16_000
        or len(query.encode("utf-8")) > 2_097_152
        or sha256(query.encode("utf-8")).hexdigest() != content_hash
        or type(request_hash) is not str
        or len(request_hash) != 64
        or any(character not in "0123456789abcdef" for character in request_hash)
    ):
        raise ValueError("retained AgentRun query must match exact content and request hashes")
    if (
        type(marking) is not list
        or not marking
        or len(marking) != len(set(marking))
        or any(
            type(value) is not str
            or value not in {"public", "internal", "confidential"}
            for value in marking
        )
    ):
        raise ValueError("retained AgentRun query requires explicit classification")


def write_agent_query(
    conn: Any,
    scope: TenantScope,
    artifact_id: str,
    attempt_id: str,
    query: str,
    content_hash: str,
    request_hash: str,
    marking: list[str],
) -> None:
    """Append within the caller's Artifact transaction; never commit here."""
    validate_agent_query(query, content_hash, request_hash, marking)
    if (
        type(artifact_id) is not str
        or not artifact_id.strip()
        or type(attempt_id) is not str
        or not attempt_id.strip()
    ):
        raise ValueError("exact Artifact and Attempt identities are required")
    row = conn.execute(
        """INSERT INTO aip_agent_query_input(
            org_id,project_id,artifact_id,attempt_id,content_text,content_hash,request_hash,marking)
        SELECT artifact.org_id,artifact.project_id,artifact.artifact_id,attempt.attempt_id,
               %s,%s,%s,%s::jsonb
        FROM aip_artifact artifact JOIN aip_agent_run_execution_attempt attempt
          ON attempt.org_id=artifact.org_id AND attempt.project_id=artifact.project_id
         AND attempt.attempt_id=%s
        WHERE artifact.org_id=%s AND artifact.project_id=%s AND artifact.artifact_id=%s
          AND artifact.artifact_type='agent_query_input' AND artifact.content_hash=%s
          AND artifact.marking=%s::jsonb
          AND artifact.source->>'attemptId'=attempt.attempt_id
          AND artifact.source->>'agentRunId'=attempt.agent_run_id
          AND artifact.source->>'requestHash'=attempt.request_hash
          AND attempt.request_hash=%s
        RETURNING artifact_id""",
        (
            query,
            content_hash,
            request_hash,
            json.dumps(marking),
            attempt_id,
            *scope.key,
            artifact_id,
            content_hash,
            json.dumps(marking),
            request_hash,
        ),
    ).fetchone()
    if row is None:
        raise ValueError("retained AgentRun query does not match Artifact and Attempt authority")


def read_agent_query(
    conn: Any,
    scope: TenantScope,
    ref: ArtifactRef,
    *,
    attempt_id: str,
    request_hash: str,
    markings: list[str],
) -> str:
    if (
        type(attempt_id) is not str
        or not attempt_id.strip()
        or type(request_hash) is not str
        or len(request_hash) != 64
        or any(character not in "0123456789abcdef" for character in request_hash)
        or type(markings) is not list
        or not markings
        or len(markings) != len(set(markings))
        or any(
            type(value) is not str
            or value not in {"public", "internal", "confidential"}
            for value in markings
        )
        or ref.artifact_type != "agent_query_input"
        or ref.revision != "1"
        or not ref.content_hash
    ):
        raise ValueError("exact AgentRun query Artifact and access are required")
    row = conn.execute(
        """SELECT body.content_text,body.content_hash,body.request_hash,body.marking,
                  artifact.content_hash AS artifact_hash,artifact.artifact_type,
                  artifact.marking AS artifact_marking,artifact.source,
                  attempt.agent_run_id,attempt.request_hash AS attempt_request_hash
           FROM aip_agent_query_input body JOIN aip_artifact artifact
             ON artifact.org_id=body.org_id AND artifact.project_id=body.project_id
            AND artifact.artifact_id=body.artifact_id
           JOIN aip_agent_run_execution_attempt attempt
             ON attempt.org_id=body.org_id AND attempt.project_id=body.project_id
            AND attempt.attempt_id=body.attempt_id
           WHERE body.org_id=%s AND body.project_id=%s AND body.artifact_id=%s
             AND body.attempt_id=%s""",
        (*scope.key, ref.artifact_id, attempt_id),
    ).fetchone()
    if (
        row is None
        or row["content_hash"] != ref.content_hash
        or row["artifact_hash"] != ref.content_hash
        or row["artifact_type"] != "agent_query_input"
        or row["marking"] != row["artifact_marking"]
        or row["request_hash"] != request_hash
        or row["attempt_request_hash"] != request_hash
        or type(row["source"]) is not dict
        or row["source"].get("attemptId") != attempt_id
        or row["source"].get("agentRunId") != row["agent_run_id"]
        or row["source"].get("requestHash") != request_hash
    ):
        raise ValueError("retained AgentRun query unavailable in scope")
    validate_agent_query(
        row["content_text"], row["content_hash"], row["request_hash"], row["marking"]
    )
    if not set(row["marking"]).issubset(set(markings)):
        raise ValueError("retained AgentRun query unavailable in scope")
    return row["content_text"]


__all__ = ["read_agent_query", "validate_agent_query", "write_agent_query"]
