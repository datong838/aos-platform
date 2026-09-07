"""Deterministically verify the AR2 N1-N8 migration fixed point."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
MANIFEST = Path(__file__).with_name("closure-manifest.md")
PHASES = Path(__file__).with_name("dynamic-reference-phases.json")
SOURCE_ROOTS = (
    (REPO / "services/aos-api/aos_api", "aos_api"),
    (REPO / "bundles/domains/ecommerce-core/backend", ""),
    (REPO / "bundles/solutions/ecommerce-growth/backend", ""),
    (REPO / "bundles/platforms/ecommerce-niushop/backend", ""),
)
DOMAIN_MARKERS = (
    "business_investigation",
    "ecommerce_analyst",
    "ecommerce_workshop",
    "ecommerce_content_campaign",
)


def module_name(root: Path, prefix: str, path: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    local = ".".join(parts)
    return ".".join(part for part in (prefix, local) if part)


def collect_modules() -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for root, prefix in SOURCE_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            name = module_name(root, prefix, path)
            if name in modules:
                raise ValueError(f"duplicate module name: {name}")
            modules[name] = path
    return modules


def imported_modules(module: str, path: Path, known: set[str]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
    result: set[str] = set()
    for node in ast.walk(tree):
        candidates: list[str] = []
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                if node.level > len(base):
                    continue
                parent = base[: len(base) - node.level + 1]
                imported = ".".join(parent + ([node.module] if node.module else []))
                candidates.append(imported)
                candidates.extend(f"{imported}.{alias.name}" for alias in node.names)
            elif node.module:
                candidates.append(node.module)
                candidates.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            candidates.extend(alias.name for alias in node.names)
        for candidate in candidates:
            if candidate in known:
                result.add(candidate)
    return result


def modules_in_cell(cell: str, modules: dict[str, Path]) -> list[str]:
    found: list[str] = []
    patterns = (
        (r"services/aos-api/aos_api/([a-zA-Z0-9_/]+)\.py", "aos_api."),
        (r"bundles/[^` ]+/backend/([a-zA-Z0-9_/]+)\.py", ""),
    )
    for pattern, prefix in patterns:
        for match in re.finditer(pattern, cell):
            candidate = prefix + match.group(1).replace("/", ".")
            if candidate in modules and candidate not in found:
                found.append(candidate)
    if found:
        return found
    for match in re.finditer(r"(?:^|[ `])([a-zA-Z0-9_/]+)\.py", cell):
        relative = match.group(1).replace("/", ".")
        candidates = [relative, f"aos_api.{relative}"]
        candidates.extend(
            name for name in modules if name.rsplit(".", 1)[-1] == relative
        )
        unique = [name for name in dict.fromkeys(candidates) if name in modules]
        if len(unique) == 1 and unique[0] not in found:
            found.append(unique[0])
    return found


def verify_dynamic_phase(phase_name: str) -> list[str]:
    phase_manifest = json.loads(PHASES.read_text(encoding="utf-8"))
    phase = phase_manifest["phases"][phase_name]
    errors: list[str] = []
    for relative, expected in phase.get("exactHashes", {}).items():
        path = REPO / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != expected:
            errors.append(f"{relative}:sha256:{expected}!={actual}")
    for relative in phase.get("requiredPaths", []):
        if not (REPO / relative).is_file():
            errors.append(f"{relative}:required-path-missing")
    for relative, markers in phase.get("contains", {}).items():
        path = REPO / relative
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        for marker in markers:
            if marker not in content:
                errors.append(f"{relative}:required-marker:{marker}")
    for relative, markers in phase.get("notContains", {}).items():
        path = REPO / relative
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        for marker in markers:
            if marker in content:
                errors.append(f"{relative}:forbidden-marker:{marker}")
    return sorted(set(errors))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase", choices=("ar2-0", "ar2-1", "ar2-7"), default="ar2-0"
    )
    args = parser.parse_args()
    text = MANIFEST.read_text(encoding="utf-8")
    modules = collect_modules()
    classified: set[str] = set()
    migrated: set[str] = set()
    hash_errors: list[str] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        resolved = [modules_in_cell(cell, modules) for cell in cells[:3]]
        row_modules = [module for group in resolved for module in group]
        if not row_modules:
            continue
        classified.update(row_modules)
        if "迁入" in line:
            migrated.update(row_modules)
        elif "/backend/" in line:
            migrated.update(module for group in resolved[1:] for module in group)
        hashes = re.findall(r"`([0-9a-f]{64})`", line)
        if hashes and args.phase == "ar2-0":
            primary = row_modules[0]
            actual = hashlib.sha256(modules[primary].read_bytes()).hexdigest()
            if actual != hashes[-1]:
                hash_errors.append(f"{primary}:{hashes[-1]}!={actual}")

    graph = {
        name: imported_modules(name, path, set(modules))
        for name, path in modules.items()
    }
    is_domain = lambda name: any(
        marker in name for marker in DOMAIN_MARKERS
    ) or name.endswith("aip_stage_template_authority")
    missing_forward = sorted(
        dependency
        for module in migrated
        for dependency in graph[module]
        if is_domain(dependency) and dependency not in classified
    )
    missing_reverse = sorted(
        module
        for module, dependencies in graph.items()
        if module not in classified and dependencies.intersection(migrated)
    )
    bundle_cross_layer = sorted(
        f"{module}->{dependency}"
        for module, dependencies in graph.items()
        if module.startswith(("ecommerce_core", "ecommerce_growth", "ecommerce_niushop"))
        for dependency in dependencies
        if dependency.startswith("aos_api")
    )
    result = {
        "phase": args.phase,
        "scannedPythonModules": len(modules),
        "classifiedModules": len(classified),
        "migratedModules": len(migrated),
        "hashErrors": sorted(set(hash_errors)),
        "unclassifiedForwardDependencies": sorted(set(missing_forward)),
        "unclassifiedReverseCallers": sorted(set(missing_reverse)),
        "bundleCrossLayerImports": bundle_cross_layer,
        "dynamicReferenceErrors": verify_dynamic_phase(args.phase),
    }
    print(result)
    checked = (
        "hashErrors",
        "unclassifiedForwardDependencies",
        "unclassifiedReverseCallers",
        "bundleCrossLayerImports",
        "dynamicReferenceErrors",
    )
    if any(result[key] for key in checked):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
