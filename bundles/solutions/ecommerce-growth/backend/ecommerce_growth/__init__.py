"""Ecommerce growth registration skeleton; inactive until an authorized cutover."""

_OPERATIONS = (
    ("ecommerce_growth_investigation_describe", "POST", "/ecommerce/growth/investigations/describe"),
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
    raise PermissionError("ecommerce growth runtime is registration-only in AR2-1")
