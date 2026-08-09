"""Expose frozen O1 common contracts as named OpenAPI components.

The DTOs are shared contracts before the authoritative UX3 query endpoint is
introduced. Registering them as components keeps Python, TypeScript and
OpenAPI reviewable without inventing a temporary production route.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from aos_api.ontology_explorer_contracts import (
    EvidenceRefDTO,
    GraphEdgeDTO,
    GraphQueryDTO,
    GraphSnapshotDTO,
    KnowledgeSubjectRefDTO,
    LinkRefDTO,
    ObjectRefDTO,
    TaskRefDTO,
)


_MODELS: tuple[type[BaseModel], ...] = (
    ObjectRefDTO,
    LinkRefDTO,
    KnowledgeSubjectRefDTO,
    TaskRefDTO,
    EvidenceRefDTO,
    GraphQueryDTO,
    GraphEdgeDTO,
    GraphSnapshotDTO,
)


def install_ontology_contract_openapi(application: FastAPI) -> None:
    base_openapi: Callable[[], dict[str, Any]] = application.openapi

    def openapi_with_ontology_contracts() -> dict[str, Any]:
        if application.openapi_schema is not None:
            return application.openapi_schema
        schema = base_openapi()
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in _MODELS:
            model_schema = model.model_json_schema(
                ref_template="#/components/schemas/{model}"
            )
            definitions = model_schema.pop("$defs", {})
            components.update(definitions)
            components[model.__name__] = model_schema
        application.openapi_schema = schema
        return schema

    application.openapi = openapi_with_ontology_contracts
