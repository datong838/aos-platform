"""Ecommerce growth registration; inactive until an authorized cutover."""

_OPERATIONS = (
    ("ecommerce_growth_investigation_describe", "POST", "/ecommerce/growth/investigations/describe"),
    ("ecommerce_growth_case_put", "POST", "/ecommerce/growth/investigations/cases"),
    ("ecommerce_growth_schedule_put", "POST", "/ecommerce/growth/investigations/schedules"),
    ("ecommerce_growth_schedule_trigger", "POST", "/ecommerce/growth/investigations/schedules/trigger"),
    ("ecommerce_growth_data_fulfill", "POST", "/ecommerce/growth/investigations/data/fulfill"),
)


def register(_context):
    return {
        "contributions": [
            {"kind": "api", "operationId": operation, "method": method, "path": path, "mode": "exclusive"}
            for operation, method, path in _OPERATIONS
        ]
    }


def handle(operation_id, _payload, _context):
    if operation_id not in {item[0] for item in _OPERATIONS}:
        raise ValueError("unregistered ecommerce growth operation")
    raise PermissionError("ecommerce growth runtime is registration-only before AR2-7 cutover")
