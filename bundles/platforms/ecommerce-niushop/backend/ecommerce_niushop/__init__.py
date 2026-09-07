"""Niushop adapter registration skeleton; inactive until an authorized cutover."""

_OPERATIONS = (
    ("ecommerce_niushop_source_describe", "POST", "/ecommerce/niushop/source/describe"),
    ("ecommerce_niushop_facts_read", "POST", "/ecommerce/niushop/facts/read"),
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
        raise ValueError("unregistered Niushop operation")
    raise PermissionError("Niushop runtime is registration-only in AR2-1")
