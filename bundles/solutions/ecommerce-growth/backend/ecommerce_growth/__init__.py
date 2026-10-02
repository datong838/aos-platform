"""Ecommerce growth registration; inactive until an authorized cutover."""

_OPERATIONS = (
    ("ecommerce_growth_event_control", "POST", "/ecommerce/growth/investigations/events/control"),
    ("ecommerce_growth_investigation_describe", "POST", "/ecommerce/growth/investigations/describe"),
    ("ecommerce_growth_case_put", "POST", "/ecommerce/growth/investigations/cases"),
    ("ecommerce_growth_schedule_put", "POST", "/ecommerce/growth/investigations/schedules"),
    ("ecommerce_growth_schedule_trigger", "POST", "/ecommerce/growth/investigations/schedules/trigger"),
    ("ecommerce_growth_data_fulfill", "POST", "/ecommerce/growth/investigations/data/fulfill"),
    ("ecommerce_growth_analysis_advance", "POST", "/ecommerce/growth/investigations/analysis/advance"),
    ("ecommerce_growth_review_advance", "POST", "/ecommerce/growth/investigations/review/advance"),
    ("ecommerce_growth_content_generate", "POST", "/ecommerce/growth/content/generate"),
    ("ecommerce_growth_content_review", "POST", "/ecommerce/growth/content/review"),
    ("analyst_workspace_view_v1", "POST", "/ecommerce/growth/workspace/view"),
)


def register(_context):
    return {
        "contributions": [dict(item) for item in _STATIC_CONTRIBUTIONS] + [
            {"kind": "api", "operationId": operation, "method": method, "path": path, "mode": "exclusive"}
            for operation, method, path in _OPERATIONS
        ]
    }


def handle(operation_id, _payload, _context):
    if operation_id not in {item[0] for item in _OPERATIONS}:
        raise ValueError("unregistered ecommerce growth operation")
    if (operation_id == "ecommerce_growth_analysis_advance"
            and type(_payload) is dict and _payload.get("kind") == "build_analysis_start"):
        from .analysis_start_operation import build_analysis_start

        return build_analysis_start(_payload)
    if (operation_id == "ecommerce_growth_analysis_advance"
            and type(_payload) is dict and _payload.get("kind") == "build_analysis_compilation_blueprint"):
        from .analysis_compilation_blueprint import build_analysis_compilation_blueprint

        return build_analysis_compilation_blueprint(_payload)
    if operation_id == "analyst_workspace_view_v1":
        if type(_payload) is not dict or set(_payload) != {"snapshot"}:
            raise ValueError("invalid analyst workspace read payload")
        from .analyst_workspace_view import project_workspace

        return project_workspace(_payload["snapshot"])
    if (operation_id == "ecommerce_growth_analysis_advance"
            and type(_payload) is dict and _payload.get("kind") == "evaluate_stage_structure"):
        from .analyst_structure_eval_operation import evaluate_stage_structure

        return evaluate_stage_structure(_payload)
    if (
        operation_id == "ecommerce_growth_analysis_advance"
        and type(_payload) is dict
        and set(_payload) == {"kind", "query", "stage"}
        and _payload.get("kind") == "derive_structure_case"
    ):
        from .analyst_structure_case import structure_case_from_query

        return structure_case_from_query(_payload.get("query"), stage=_payload.get("stage"))
    if (
        operation_id == "ecommerce_growth_review_advance"
        and type(_payload) is dict
        and _payload.get("kind")
        in {
            "validate_command_identity",
            "validate_review_slot",
            "validate_runtime",
            "validate_eval_proof",
            "validate_structure_case",
        }
    ):
        from .analyst_stage_review_runtime_operation import handle_stage_review_message

        return handle_stage_review_message(_payload)
    raise PermissionError("ecommerce growth runtime is registration-only before AR2-7 cutover")


_STATIC_CONTRIBUTIONS = (
    {"kind": "navigation", "route": "/workshop/cockpit", "mode": "exclusive"},
    {"kind": "ui", "slot": "workshop.primary.ecommerce", "id": "ecommerce.task-cockpit", "mode": "exclusive"},
    {"kind": "navigation", "route": "/workshop/content-campaign", "mode": "exclusive"},
    {"kind": "ui", "slot": "workshop.primary.ecommerce", "id": "ecommerce.content-campaign", "mode": "exclusive"},
    {"kind": "navigation", "route": "/workshop/creator-growth", "mode": "exclusive"},
    {"kind": "ui", "slot": "workshop.primary.ecommerce", "id": "ecommerce.creator-growth", "mode": "exclusive"},
    {"kind": "navigation", "route": "/workshop/media-studio", "mode": "exclusive"},
    {"kind": "ui", "slot": "workshop.primary.ecommerce", "id": "ecommerce.media-studio", "mode": "exclusive"},
    {"kind": "navigation", "route": "/workshop/analyst", "mode": "exclusive"},
    {"kind": "ui", "slot": "workshop.primary.ecommerce", "id": "ecommerce.analyst", "mode": "exclusive"},
    {"kind": "navigation", "route": "/workshop/price-governance", "mode": "exclusive"},
    {"kind": "ui", "slot": "workshop.primary.ecommerce", "id": "ecommerce.price-governance", "mode": "exclusive"},
    {"kind": "navigation", "route": "/workshop/customer", "mode": "exclusive"},
    {"kind": "ui", "slot": "workshop.primary.ecommerce", "id": "ecommerce.customer", "mode": "exclusive"},
)
