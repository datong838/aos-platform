#!/usr/bin/env python3
"""Generate domain router aggregates from the committed router manifest."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = (
    ROOT
    / "services"
    / "aos-api"
    / "aos_api"
    / "routers"
    / "domain_manifest.json"
)
OUTPUT = (
    ROOT
    / "services"
    / "aos-api"
    / "aos_api"
    / "routers"
    / "domain_aggregates.py"
)

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
DOMAIN_TAGS = {
    "infra": "Infra",
    "admin": "Admin",
    "system": "System",
    "agent": "Agent",
    "workshop": "Workshop",
    "ontology": "Ontology",
    "aip": "AIP",
    "data": "Data",
    "model": "Model",
    "apollo": "Apollo",
}


def load_manifest(path: Path = MANIFEST) -> list[dict[str, Any]]:
    """Load and validate the ordered router manifest."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise ValueError("router manifest version must be 1")
    routers = payload.get("routers")
    if not isinstance(routers, list) or not routers:
        raise ValueError("router manifest must contain a non-empty routers list")

    expected_orders = list(range(len(routers)))
    actual_orders = [entry.get("order") for entry in routers]
    if actual_orders != expected_orders:
        raise ValueError("router manifest order values must be contiguous and sorted")

    keys: list[tuple[str, str]] = []
    for entry in routers:
        if set(entry) != {"domain", "module", "attribute", "order"}:
            raise ValueError(f"invalid router manifest entry: {entry!r}")
        domain = entry["domain"]
        module = entry["module"]
        attribute = entry["attribute"]
        if domain not in DOMAIN_ORDER:
            raise ValueError(f"unknown router domain: {domain!r}")
        if not isinstance(module, str) or not module.startswith("aos_api."):
            raise ValueError(f"invalid router module: {module!r}")
        if not isinstance(attribute, str) or not attribute.isidentifier():
            raise ValueError(f"invalid router attribute: {attribute!r}")
        keys.append((module, attribute))

    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate router manifest entries: {duplicates!r}")
    return routers


def render(routers: list[dict[str, Any]]) -> str:
    """Render deterministic Python source without importing application modules."""
    by_domain = {
        domain: [entry for entry in routers if entry["domain"] == domain]
        for domain in DOMAIN_ORDER
    }
    lines = [
        '"""Domain router aggregates generated from domain_manifest.json.',
        "",
        "Run ``python scripts/generate_domain_aggregates.py --check`` to detect drift.",
        "DO NOT EDIT MANUALLY — edit the manifest and regenerate instead.",
        '"""',
        "from __future__ import annotations",
        "",
        "from importlib import import_module",
        "",
        "from fastapi import APIRouter",
        "",
        "",
        "ROUTER_SPECS: dict[str, tuple[tuple[str, str], ...]] = {",
    ]
    for domain in DOMAIN_ORDER:
        lines.append(f'    "{domain}": (')
        for entry in by_domain[domain]:
            lines.append(
                f'        ({entry["module"]!r}, {entry["attribute"]!r}),'
            )
        lines.append("    ),")
    lines.extend(
        [
            "}",
            "",
            "",
            "def _create_domain_router(domain: str, tag: str) -> APIRouter:",
            '    """Import every child before registration, preserving manifest order."""',
            '    aggregate = APIRouter(prefix="", tags=[tag])',
            "    children = [",
            "        getattr(import_module(module), attribute)",
            "        for module, attribute in ROUTER_SPECS[domain]",
            "    ]",
            "    for child in children:",
            "        aggregate.include_router(child)",
            "    return aggregate",
            "",
            "",
        ]
    )
    for domain in DOMAIN_ORDER:
        tag = DOMAIN_TAGS[domain]
        lines.extend(
            [
                f"def create_{domain}_router() -> APIRouter:",
                f'    """Create the {tag} aggregate in manifest order."""',
                f'    return _create_domain_router("{domain}", "{tag}")',
                "",
                "",
            ]
        )
    lines.extend(
        [
            "DOMAIN_ROUTERS = {",
            *[
                f'    "{domain}": create_{domain}_router,'
                for domain in DOMAIN_ORDER
            ],
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="fail if the generated file differs from the manifest",
    )
    mode.add_argument(
        "--stdout",
        action="store_true",
        help="print generated source without writing files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    routers = load_manifest()
    generated = render(routers)
    if args.stdout:
        sys.stdout.write(generated)
        return 0
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != generated:
            print(f"FAIL generated router aggregate is stale: {OUTPUT}", file=sys.stderr)
            return 1
        print(f"OK router aggregate matches {len(routers)} manifest entries")
        return 0
    OUTPUT.write_text(generated, encoding="utf-8")
    print(f"wrote {OUTPUT} from {len(routers)} manifest entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
