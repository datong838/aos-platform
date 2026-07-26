"""Workshop Phase 1 combined router.

Aggregates all 9 workshop sub-routers into one APIRouter to avoid
excessive include_router calls (which build a lifespan merge chain).
"""
from __future__ import annotations

from fastapi import APIRouter

from aos_api.routers import (
    modules_config,
    modules_deployments,
    modules_interface,
    modules_queries,
    modules_variables,
    modules_widgets,
    themes,
    widgets_registry,
)

router = APIRouter()
for _sub in (
    modules_config.router,
    modules_widgets.router,
    modules_queries.router,
    modules_variables.router,
    modules_interface.router,
    modules_deployments.router,
    widgets_registry.router,
    themes.router,
):
    router.include_router(_sub)
