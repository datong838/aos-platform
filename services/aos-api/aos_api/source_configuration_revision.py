"""Read configuration-row revision identities without reading connection secrets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class SourceConfigurationRevision:
    source_id: str
    revision_id: UUID
    prior_revision_id: UUID | None
    source_type: str
    status: str
    plugin_id: str | None
    ref: InvestigationExactRef
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class SourceConnectionInput:
    revision: SourceConfigurationRevision
    props: dict[str, Any] = field(repr=False)


class SourceConfigurationRevisionStore:
    def __init__(self, transaction: HostTransaction, scope: TenantScope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("source revision requires HostTransaction and TenantScope")
        self._transaction, self._scope = transaction, scope

    def read_current(self, source_id: str) -> SourceConfigurationRevision | None:
        if type(source_id) is not str or not source_id or source_id.strip() != source_id:
            raise ValueError("canonical source identity required")
        row = self._transaction.execute("""SELECT r.* FROM public.meta_source s
            JOIN public.data_source_configuration_revision r ON r.org_id=s.org_id
            AND r.project_id=s.project_id AND r.source_id=s.id
            AND r.revision_id=s.configuration_revision
            WHERE s.org_id=%s AND s.project_id=%s AND s.id=%s""",
            (*self._scope.key, source_id)).fetchone()
        item = self._decode(row) if row is not None else None
        if item is not None and item.source_id != source_id:
            raise ValueError("current source configuration identity drifted")
        return item

    def read_connection_input(self, source_id: str) -> SourceConnectionInput | None:
        """Load configuration inputs and their identity from one SQL snapshot."""
        if type(source_id) is not str or not source_id or source_id.strip() != source_id:
            raise ValueError("canonical source identity required")
        row = self._transaction.execute("""SELECT r.*,s.props AS connection_props
            FROM public.meta_source s JOIN public.data_source_configuration_revision r
            ON (r.org_id,r.project_id,r.source_id,r.revision_id)=
               (s.org_id,s.project_id,s.id,s.configuration_revision)
            WHERE s.org_id=%s AND s.project_id=%s AND s.id=%s""",
            (*self._scope.key, source_id)).fetchone()
        if row is None:
            return None
        item = self._decode(row)
        if item.source_id != source_id or type(row["connection_props"]) is not dict:
            raise ValueError("source configuration input unavailable")
        return SourceConnectionInput(item, row["connection_props"])

    def read_exact(self, ref: InvestigationExactRef) -> SourceConfigurationRevision | None:
        ref = InvestigationExactRef.model_validate(ref.model_dump())
        if (ref.resource_type != "DataSourceConfigurationRevision" or type(ref.revision) is not int
            or ref.revision != 1 or ref.receipt_id is not None):
            raise ValueError("exact source configuration reference required")
        try:
            revision_id = UUID(ref.resource_id.removeprefix("source-config-"))
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid source configuration identity") from exc
        if ref.resource_id != "source-config-" + str(revision_id):
            raise ValueError("noncanonical source configuration identity")
        row = self._transaction.execute("""SELECT * FROM public.data_source_configuration_revision
            WHERE org_id=%s AND project_id=%s AND revision_id=%s""",
            (*self._scope.key, revision_id)).fetchone()
        if row is None:
            return None
        item = self._decode(row)
        if item.ref != ref:
            raise ValueError("source configuration reference drifted")
        return item

    def _decode(self, row: dict[str, Any]) -> SourceConfigurationRevision:
        revision_id = UUID(str(row["revision_id"]))
        prior = UUID(str(row["prior_revision_id"])) if row["prior_revision_id"] is not None else None
        body = {
            "schemaVersion": "aos.source-configuration-identity/v1",
            "tenant": {"orgId": self._scope.org_id, "projectId": self._scope.project_id},
            "sourceId": row["source_id"], "revisionId": str(revision_id),
            "priorRevisionId": str(prior) if prior else None,
            "type": row["source_type"], "status": row["status"], "pluginId": row["plugin_id"],
            "configurationIdentityOnly": True, "secretMaterialVersionKnown": False,
        }
        for name in ("source_id", "source_type", "status"):
            if type(row[name]) is not str:
                raise ValueError("invalid source configuration metadata")
        if row["plugin_id"] is not None and type(row["plugin_id"]) is not str:
            raise ValueError("invalid source plugin identity")
        digest = canonical_hash(body)
        if ((row["org_id"], row["project_id"]) != self._scope.key
            or row["authority"] != body or canonical_hash(row["authority"]) != digest or row["content_hash"] != digest
            or not isinstance(row["recorded_at"], datetime) or row["recorded_at"].utcoffset() is None):
            raise ValueError("source configuration authority drifted")
        ref = InvestigationExactRef(resource_type="DataSourceConfigurationRevision",
            resource_id="source-config-" + str(revision_id), revision=1, content_hash="sha256:" + digest)
        return SourceConfigurationRevision(row["source_id"], revision_id, prior, row["source_type"],
            row["status"], row["plugin_id"], ref, row["recorded_at"])
