"""Bundle-backed six-role Analyst query template catalog.

Definitions are shared SolutionPack assets. Readiness is evaluated per tenant
against installed ontology visibility; the catalog never creates runtime data.
"""
from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from aos_api.aip_analyst_contracts import (
    AnalystQueryKind,
    AnalystRoleQueryTemplate,
    AnalystRoleQueryTemplateList,
    QueryBlocker,
)
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.db import connect as db_connect
from aos_api.errors import ApiError
from aos_api.ontology_compose import assert_object_type_visible
from aos_api.tenant_scope import TenantScope


_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DOCUMENT = (
    _REPOSITORY_ROOT
    / "bundles/solutions/ecommerce-growth/content/logic/"
    "ecommerce-analyst-query-templates.json"
)
_EXPECTED_LOGICS = {
    "ecommerce.data_advisor": {f"D{i:02d}" for i in range(1, 7)},
    "ecommerce.content_officer": {f"C{i:02d}" for i in range(1, 9)},
    "ecommerce.shopping_advisor": {f"G{i:02d}" for i in range(1, 7)},
    "ecommerce.customer_service": {f"S{i:02d}" for i in range(1, 7)},
    "ecommerce.private_domain_manager": {f"P{i:02d}" for i in range(1, 6)},
    "ecommerce.campaign_planner": {f"A{i:02d}" for i in range(1, 7)},
}
_DOCUMENT_ADAPTER = TypeAdapter(dict[str, Any])


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


class AnalystTemplateCatalogInvalid(ValueError):
    pass


class AnalystTemplateCatalog:
    def __init__(
        self,
        *,
        document_path: Path | None = None,
        connect_factory=None,
        assert_visible: Callable[..., None] = assert_object_type_visible,
    ) -> None:
        self._path = document_path or _DEFAULT_DOCUMENT
        self._connect_factory = connect_factory or db_connect
        self._assert_visible = assert_visible

    def list(self, scope: TenantScope) -> AnalystRoleQueryTemplateList:
        document = self._read_document()
        templates = document["templates"]
        visible = self._visible_types(scope, templates)
        items: list[AnalystRoleQueryTemplate] = []
        for raw in templates:
            missing = [
                object_type
                for object_type in raw["requiredObjectTypes"]
                if object_type not in visible
            ]
            blockers = [
                QueryBlocker(
                    code="OBJECT_TYPE_NOT_INSTALLED",
                    message=f"required Object Type is not installed: {object_type}",
                    dependency_ref=ResourceRef(
                        resource_type="ObjectType",
                        resource_id=object_type,
                        revision="required",
                        authority="ontology",
                    ),
                    retryable=False,
                )
                for object_type in missing
            ]
            items.append(
                AnalystRoleQueryTemplate(
                    **raw,
                    readiness="blocked" if blockers else "ready",
                    blockers=blockers,
                )
            )
        return AnalystRoleQueryTemplateList(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            bundle_ref=ResourceRef(
                resource_type="SolutionPack",
                resource_id="solution.ecommerce.growth",
                revision="1.3.0",
                authority="asset-registry",
            ),
            content_hash=sha256(_canonical(document)).hexdigest(),
            items=items,
            count=6,
        )

    def _read_document(self) -> dict[str, Any]:
        try:
            document = _DOCUMENT_ADAPTER.validate_python(
                json.loads(self._path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise AnalystTemplateCatalogInvalid(
                "analyst query template document is unavailable or invalid"
            ) from exc
        if set(document) != {"schemaVersion", "bundleRef", "templates"}:
            raise AnalystTemplateCatalogInvalid("template document fields drifted")
        if document["schemaVersion"] != 1:
            raise AnalystTemplateCatalogInvalid("template schema version is unsupported")
        if document["bundleRef"] != "bundle://aos/solution.ecommerce.growth@1.3.0":
            raise AnalystTemplateCatalogInvalid("template bundle reference drifted")
        templates = document["templates"]
        if not isinstance(templates, list) or len(templates) != 6:
            raise AnalystTemplateCatalogInvalid("exactly six role templates are required")
        if any(not isinstance(item, dict) for item in templates):
            raise AnalystTemplateCatalogInvalid("template entry must be an object")
        roles = [item.get("roleId") for item in templates]
        template_ids = [item.get("templateId") for item in templates]
        if set(roles) != set(_EXPECTED_LOGICS) or len(set(roles)) != 6:
            raise AnalystTemplateCatalogInvalid("six-role template crosswalk drifted")
        if len(set(template_ids)) != 6:
            raise AnalystTemplateCatalogInvalid("template ids must be unique")
        for raw in templates:
            if raw.get("queryKind") != AnalystQueryKind.SEMANTIC.value:
                raise AnalystTemplateCatalogInvalid("R17 templates must use semantic reads")
            if raw.get("policy") != "canonical-read-only":
                raise AnalystTemplateCatalogInvalid("template policy must be read-only")
            if set(raw.get("requiredLogicIds") or ()) != _EXPECTED_LOGICS[raw["roleId"]]:
                raise AnalystTemplateCatalogInvalid("role Logic crosswalk drifted")
            if raw.get("defaultObjectType") not in (raw.get("requiredObjectTypes") or ()):
                raise AnalystTemplateCatalogInvalid(
                    "default Object Type must be an explicit dependency"
                )
        return document

    def _visible_types(
        self, scope: TenantScope, templates: list[dict[str, Any]]
    ) -> set[str]:
        required = {
            item
            for template in templates
            for item in template["requiredObjectTypes"]
        }
        visible: set[str] = set()
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                "SELECT id FROM meta_object_type WHERE published AND id = ANY(%s)",
                (sorted(required),),
            ).fetchall()
            published = {str(row["id"]) for row in rows}
            for object_type in sorted(required & published):
                try:
                    self._assert_visible(conn, scope, object_type)
                except ApiError:
                    continue
                visible.add(object_type)
        return visible


__all__ = ["AnalystTemplateCatalog", "AnalystTemplateCatalogInvalid"]
