#!/usr/bin/env python3
"""Deterministically export the runtime OpenAPI document and route inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services" / "aos-api"
CONTRACT_ROOT = ROOT / "packages" / "contracts" / "openapi"
OPENAPI_PATH = CONTRACT_ROOT / "v1.generated.json"
INVENTORY_PATH = CONTRACT_ROOT / "v1.inventory.json"
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
FRAMEWORK_PATHS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
DOMAIN_ORDER = (
    "infra",
    "admin",
    "system",
    "agent",
    "workshop",
    "ontology",
    "aip",
    "data",
    "model",
    "apollo",
)
EXPECTED_DUPLICATES = [
    ["/v1/builds", "GET", 2],
    ["/v1/datasets", "GET", 2],
    ["/v1/ontology/branches", "GET", 2],
    ["/v1/ontology/branches", "POST", 2],
    ["/v1/ontology/graph-health", "GET", 2],
    ["/v1/ontology/object-types", "GET", 2],
    ["/v1/pipelines", "GET", 2],
    ["/v1/pipelines", "POST", 2],
    ["/v1/schedules", "GET", 2],
    ["/v1/schedules", "POST", 2],
]
EXPECTED_ROUTE_ROWS = 4316
EXPECTED_UNIQUE_OPERATION_PAIRS = 4306
EXPECTED_OPENAPI_OPERATIONS = 4306


class ExportError(RuntimeError):
    """Raised when the runtime contract violates an export invariant."""


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def iter_effective_routes(routes: Iterable[Any]) -> Iterable[Any]:
    for route in routes:
        candidates = getattr(route, "effective_candidates", None)
        if callable(candidates):
            yield from iter_effective_routes(candidates())
        else:
            yield route


def _operations(schema: dict[str, Any]) -> Iterable[tuple[str, str, dict[str, Any]]]:
    for path, item in schema.get("paths", {}).items():
        for method, operation in item.items():
            if method.lower() in HTTP_METHODS:
                yield path, method.lower(), operation


def _resolve_local_ref(schema: dict[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise ExportError(f"external $ref is not allowed: {ref}")
    value: Any = schema
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or part not in value:
            raise ExportError(f"unresolved local $ref: {ref}")
        value = value[part]
    return value


def validate_openapi(schema: dict[str, Any]) -> None:
    for key in ("openapi", "info", "paths"):
        if key not in schema:
            raise ExportError(f"OpenAPI missing required top-level key: {key}")
    operation_ids: list[str] = []
    for path, method, operation in _operations(schema):
        operation_id = operation.get("operationId")
        if not operation_id:
            raise ExportError(f"missing operationId: {method.upper()} {path}")
        operation_ids.append(operation_id)
        if not operation.get("responses"):
            raise ExportError(f"missing responses: {method.upper()} {path}")
    duplicates = sorted(
        key for key, count in Counter(operation_ids).items() if count > 1
    )
    if duplicates:
        raise ExportError(f"duplicate operationId values: {duplicates}")

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str):
                _resolve_local_ref(schema, ref)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(schema)


def build_inventory(app: Any, schema_bytes: bytes) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    domain_counts: Counter[str] = Counter()
    for route in iter_effective_routes(app.routes):
        path = getattr(route, "path", None)
        if not path or path in FRAMEWORK_PATHS:
            continue
        tags = list(getattr(route, "tags", None) or ())
        domain = str(tags[0]).lower() if tags else "unassigned"
        if domain not in DOMAIN_ORDER:
            raise ExportError(f"route has no manifest domain tag: {path} tags={tags!r}")
        for method in sorted(
            set(getattr(route, "methods", set())) - {"HEAD", "OPTIONS"}
        ):
            rows.append(
                {
                    "domain": domain,
                    "method": method,
                    "name": getattr(route, "name", ""),
                    "operationId": getattr(route, "operation_id", None)
                    or getattr(route, "unique_id", None),
                    "ordinal": len(rows),
                    "path": path,
                    "tags": tags,
                }
            )
            domain_counts[domain] += 1

    pairs = Counter((row["path"], row["method"]) for row in rows)
    duplicates = sorted(
        [[path, method, count] for (path, method), count in pairs.items() if count > 1]
    )
    if (
        len(rows) != EXPECTED_ROUTE_ROWS
        or len(pairs) != EXPECTED_UNIQUE_OPERATION_PAIRS
    ):
        raise ExportError(
            f"route totals changed: rows={len(rows)} unique_pairs={len(pairs)}"
        )
    if duplicates != EXPECTED_DUPLICATES:
        raise ExportError(f"duplicate route inventory changed: {duplicates!r}")
    aip_duplicates = [item for item in duplicates if item[0].startswith("/v1/aip/")]
    if aip_duplicates:
        raise ExportError(f"AIP duplicate routes are forbidden: {aip_duplicates!r}")
    return {
        "summary": {
            "domains": {domain: domain_counts[domain] for domain in DOMAIN_ORDER},
            "duplicatePairs": duplicates,
            "openapiSha256": hashlib.sha256(schema_bytes).hexdigest(),
            "routeRows": len(rows),
            "uniqueOperationPairs": len(pairs),
        },
        "routes": rows,
        "version": 1,
    }


def generate_payloads() -> tuple[bytes, bytes]:
    sys.path.insert(0, str(API_ROOT))
    from aos_api.main import app

    app.openapi_schema = None
    schema = app.openapi()
    validate_openapi(schema)
    schema_bytes = canonical_json(schema)
    openapi_operation_count = sum(1 for _ in _operations(schema))
    if openapi_operation_count != EXPECTED_OPENAPI_OPERATIONS:
        raise ExportError(f"OpenAPI operation total changed: {openapi_operation_count}")
    inventory = build_inventory(app, schema_bytes)
    return schema_bytes, canonical_json(inventory)


def _worker(output_dir: Path) -> int:
    try:
        openapi_bytes, inventory_bytes = generate_payloads()
        (output_dir / "openapi.json").write_bytes(openapi_bytes)
        (output_dir / "inventory.json").write_bytes(inventory_bytes)
        return 0
    except Exception as exc:  # noqa: BLE001 - worker must report every export failure.
        print(f"ERROR OpenAPI export failed: {exc}", file=sys.stderr)
        return 2


def _clean_process() -> tuple[bytes, bytes]:
    with tempfile.TemporaryDirectory(prefix="aos-openapi-") as temp_dir:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--_worker", temp_dir],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ExportError(
                f"clean export process failed\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        directory = Path(temp_dir)
        return (directory / "openapi.json").read_bytes(), (
            directory / "inventory.json"
        ).read_bytes()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def export(check: bool) -> int:
    first = _clean_process()
    second = _clean_process()
    if first != second:
        print("ERROR two clean OpenAPI exports differ", file=sys.stderr)
        return 2
    outputs = ((OPENAPI_PATH, first[0]), (INVENTORY_PATH, first[1]))
    if check:
        drift = [
            str(path.relative_to(ROOT))
            for path, data in outputs
            if not path.exists() or path.read_bytes() != data
        ]
        if drift:
            print("DRIFT " + ", ".join(drift), file=sys.stderr)
            return 1
        print("PASS OpenAPI and inventory are deterministic and current")
        return 0
    for path, data in outputs:
        _atomic_write(path, data)
        print(f"WROTE {path.relative_to(ROOT)} ({len(data)} bytes)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed artifacts without writing",
    )
    parser.add_argument("--_worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._worker is not None:
        return _worker(args._worker)
    try:
        return export(args.check)
    except ExportError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
