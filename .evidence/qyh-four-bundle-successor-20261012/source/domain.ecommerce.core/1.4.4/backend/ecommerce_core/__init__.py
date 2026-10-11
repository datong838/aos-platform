"""Ecommerce core registration skeleton; inactive until an authorized cutover."""

_OPERATIONS = (
    ("ecommerce_core_product_event_windows", "POST", "/ecommerce/core/events/windows"),
    ("ecommerce_core_object_describe", "POST", "/ecommerce/core/objects/describe"),
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
        raise ValueError("unregistered ecommerce core operation")
    if operation_id == "ecommerce_core_product_event_windows":
        from .product_source_event_window_operation import calculate_windows
        return calculate_windows(_payload)
    raise PermissionError("ecommerce core runtime is registration-only in AR2-1")
