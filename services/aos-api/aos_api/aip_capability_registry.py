"""Immutable AIP capability catalog and canonical alias resolver."""
from __future__ import annotations

from typing import Any

from aos_api.aip_agent_registry_contracts import (
    CapabilityRevision,
    PublishCapabilityRevisionRequest,
    TemplateLifecycle,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryError,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryStore,
)


class AipCapabilityRegistry(AipAgentRegistryStore):
    def publish(
        self, request: PublishCapabilityRevisionRequest, *, actor: str
    ) -> CapabilityRevision:
        if not actor.strip():
            raise ValueError("actor is required")
        try:
            with self._connect_factory() as conn:
                row = conn.execute(
                    """INSERT INTO aip_capability_revision
                       (capability_id,revision,display_name,lifecycle,parent_ref,aliases,
                        input_schema_ref,output_schema_ref,risk_level,required_data_refs,
                        required_tool_refs,required_capability_refs,eval_pack_ref,
                        memory_policy_ref,handoff_policy_ref,effect_review_schema_ref,
                        license_policy_ref,readiness_policy_ref,readiness,readiness_reasons,
                        source_ref,source_license,content_hash,created_by)
                       VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,
                        %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                        %s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                       ON CONFLICT (capability_id,revision) DO NOTHING RETURNING *""",
                    (
                        request.capability_id,
                        request.revision,
                        request.display_name,
                        request.lifecycle.value,
                        self._json(request.parent_ref) if request.parent_ref else None,
                        self._json(request.aliases),
                        self._json(request.input_schema_ref),
                        self._json(request.output_schema_ref),
                        request.risk_level,
                        self._json(request.required_data_refs),
                        self._json(request.required_tool_refs),
                        self._json(request.required_capability_refs),
                        self._json(request.eval_pack_ref) if request.eval_pack_ref else None,
                        self._json(request.memory_policy_ref),
                        self._json(request.handoff_policy_ref),
                        self._json(request.effect_review_schema_ref),
                        self._json(request.license_policy_ref),
                        self._json(request.readiness_policy_ref),
                        request.readiness.value,
                        self._json(request.readiness_reasons),
                        self._json(request.source_ref),
                        request.source_license,
                        request.content_hash,
                        actor.strip(),
                    ),
                ).fetchone()
                if row is None:
                    row = self._row(conn, request.capability_id, request.revision)
                    if row is None or self._content(row) != request.model_dump(mode="json"):
                        raise AipAgentRegistryConflict(
                            "capability revision already has different content"
                        )
                for alias in request.aliases:
                    alias_row = conn.execute(
                        """INSERT INTO aip_capability_alias
                           (alias,capability_id,capability_revision)
                           VALUES (%s,%s,%s) ON CONFLICT (alias) DO NOTHING RETURNING *""",
                        (alias, request.capability_id, request.revision),
                    ).fetchone()
                    if alias_row is None:
                        existing = conn.execute(
                            "SELECT * FROM aip_capability_alias WHERE alias=%s", (alias,)
                        ).fetchone()
                        if existing is None or existing["capability_id"] != request.capability_id:
                            raise AipAgentRegistryConflict(
                                "capability alias already resolves to another revision"
                            )
                conn.commit()
                return self._from_row(row)
        except AipAgentRegistryError:
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError(
                "capability revision persistence failed"
            ) from exc

    def get(self, capability_id: str, revision: int) -> CapabilityRevision:
        try:
            with self._connect_factory() as conn:
                row = self._row(conn, capability_id, revision)
            if row is None:
                raise AipAgentRegistryNotFound("capability revision not found")
            return self._from_row(row)
        except AipAgentRegistryError:
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("capability revision read failed") from exc

    def resolve_alias(self, alias: str) -> CapabilityRevision:
        cleaned = alias.strip()
        if not cleaned:
            raise ValueError("alias is required")
        try:
            with self._connect_factory() as conn:
                row = conn.execute(
                    """SELECT c.* FROM aip_capability_alias a
                       JOIN LATERAL (
                         SELECT * FROM aip_capability_revision r
                         WHERE r.capability_id=a.capability_id
                           AND r.lifecycle='published'
                         ORDER BY r.revision DESC LIMIT 1
                       ) c ON true WHERE a.alias=%s""",
                    (cleaned,),
                ).fetchone()
            if row is None:
                raise AipAgentRegistryNotFound("capability alias not found")
            return self._from_row(row)
        except AipAgentRegistryError:
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("capability alias read failed") from exc

    def list_capabilities(
        self,
        *,
        source_resource_id: str | None = None,
        source_revision: str | None = None,
        lifecycle: TemplateLifecycle | None = None,
        limit: int = 100,
    ) -> list[CapabilityRevision]:
        if limit < 1 or limit > 200:
            raise ValueError("list limit must be between 1 and 200")
        try:
            with self._connect_factory() as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_capability_revision
                       WHERE (%s::text IS NULL OR source_ref->>'resourceId'=%s)
                         AND (%s::text IS NULL OR source_ref->>'revision'=%s)
                         AND (%s::text IS NULL OR lifecycle=%s)
                       ORDER BY capability_id,revision DESC LIMIT %s""",
                    (
                        source_resource_id,
                        source_resource_id,
                        source_revision,
                        source_revision,
                        lifecycle.value if lifecycle else None,
                        lifecycle.value if lifecycle else None,
                        limit,
                    ),
                ).fetchall()
            return [self._from_row(row) for row in rows]
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("capability revision list failed") from exc

    @staticmethod
    def _row(conn: Any, capability_id: str, revision: int):
        return conn.execute(
            """SELECT * FROM aip_capability_revision
               WHERE capability_id=%s AND revision=%s""",
            (capability_id, revision),
        ).fetchone()

    @staticmethod
    def _from_row(row: Any) -> CapabilityRevision:
        return CapabilityRevision(
            capability_id=row["capability_id"],
            revision=row["revision"],
            display_name=row["display_name"],
            lifecycle=row["lifecycle"],
            parent_ref=row["parent_ref"],
            aliases=row["aliases"],
            input_schema_ref=row["input_schema_ref"],
            output_schema_ref=row["output_schema_ref"],
            risk_level=row["risk_level"],
            required_data_refs=row["required_data_refs"],
            required_tool_refs=row["required_tool_refs"],
            required_capability_refs=row["required_capability_refs"],
            eval_pack_ref=row["eval_pack_ref"],
            memory_policy_ref=row["memory_policy_ref"],
            handoff_policy_ref=row["handoff_policy_ref"],
            effect_review_schema_ref=row["effect_review_schema_ref"],
            license_policy_ref=row["license_policy_ref"],
            readiness_policy_ref=row["readiness_policy_ref"],
            readiness=row["readiness"],
            readiness_reasons=row["readiness_reasons"],
            source_ref=row["source_ref"],
            source_license=row["source_license"],
            content_hash=row["content_hash"],
            created_by=row["created_by"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _content(row: Any) -> dict[str, Any]:
        return AipCapabilityRegistry._from_row(row).model_dump(
            mode="json", exclude={"created_by", "created_at"}
        )
