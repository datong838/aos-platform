#!/usr/bin/env python3
"""Create immutable ecommerce runtime candidates with exact API declarations."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "bundles/candidates/ecommerce"
CASES = (
    (
        "domain.ecommerce.core/1.1.0", "domain.ecommerce.core/1.2.0",
        "1.1.0", "1.2.0", "2ceb9a8d02dfac36715c88a366518f238f20e8ffa53c6eb35a9dc02aa217a7a4",
        (("ecommerce_core_object_describe", "POST", "/ecommerce/core/objects/describe"),),
    ),
    (
        "platform.ecommerce.niushop/1.1.0", "platform.ecommerce.niushop/1.2.0",
        "1.1.0", "1.2.0", "e4ceb87b536da90946e24f430c4ab9b67c50e5d5fe997b80d49e499f464bcf6c",
        (
            ("ecommerce_niushop_source_describe", "POST", "/ecommerce/niushop/source/describe"),
            ("ecommerce_niushop_facts_read", "POST", "/ecommerce/niushop/facts/read"),
        ),
    ),
    (
        "solution.ecommerce.growth/1.5.0", "solution.ecommerce.growth/1.6.0",
        "1.5.0", "1.6.0", "34446fcbfc1a8b7239cc44cdb4d801584d618deffbadc9c6bddaf7d69e5b0bd0",
        (
            ("ecommerce_growth_investigation_describe", "POST", "/ecommerce/growth/investigations/describe"),
            ("ecommerce_growth_case_put", "POST", "/ecommerce/growth/investigations/cases"),
            ("ecommerce_growth_schedule_put", "POST", "/ecommerce/growth/investigations/schedules"),
            ("ecommerce_growth_schedule_trigger", "POST", "/ecommerce/growth/investigations/schedules/trigger"),
            ("ecommerce_growth_data_fulfill", "POST", "/ecommerce/growth/investigations/data/fulfill"),
            ("ecommerce_growth_analysis_advance", "POST", "/ecommerce/growth/investigations/analysis/advance"),
            ("ecommerce_growth_review_advance", "POST", "/ecommerce/growth/investigations/review/advance"),
            ("ecommerce_growth_content_generate", "POST", "/ecommerce/growth/content/generate"),
            ("ecommerce_growth_content_review", "POST", "/ecommerce/growth/content/review"),
        ),
    ),
)


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        raw = path.read_bytes()
        digest.update(str(path.relative_to(root)).encode() + b"\0")
        digest.update(str(len(raw)).encode() + b"\0" + raw)
    return digest.hexdigest()


def _api_yaml(operations: tuple[tuple[str, str, str], ...]) -> str:
    return "".join(
        "    - kind: api\n"
        f"      operationId: {operation}\n"
        f"      method: {method}\n"
        f"      path: {path}\n"
        "      mode: exclusive\n"
        for operation, method, path in operations
    )


def prepare() -> dict[str, object]:
    targets = [CANDIDATES / target for _, target, *_ in CASES]
    if any(target.exists() for target in targets):
        raise ValueError("new candidate targets must not exist")
    for base, _target, _old, _new, expected_hash, _operations in CASES:
        if tree_hash(CANDIDATES / base) != expected_hash:
            raise RuntimeError(f"immutable candidate baseline drifted: {base}")
    created: list[Path] = []
    try:
        results = []
        for base, target, old_version, new_version, _hash, operations in CASES:
            source, destination = CANDIDATES / base, CANDIDATES / target
            shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            created.append(destination)
            manifest = destination / "bundle.yaml"
            text = manifest.read_text(encoding="utf-8")
            version_marker = f"  version: {old_version}\n"
            if text.count(version_marker) != 1:
                raise RuntimeError(f"candidate version marker drifted: {base}")
            text = text.replace(version_marker, f"  version: {new_version}\n", 1)
            if target.startswith("platform.ecommerce.niushop/") or target.startswith("solution.ecommerce.growth/"):
                dependency = '      version: ">=1.1.0 <2.0.0"\n'
                if text.count(dependency) != 1:
                    raise RuntimeError(f"domain dependency marker drifted: {base}")
                text = text.replace(dependency, '      version: ">=1.2.0 <2.0.0"\n', 1)
            if "  contributions:\n" not in text:
                text += "  contributions:\n"
            text += _api_yaml(operations)
            manifest.write_text(text, encoding="utf-8")
            if old_version == "1.5.0":
                static = [item for item in yaml.safe_load(text)["spec"]["contributions"] if item["kind"] != "api"]
                entry = destination / "backend/ecommerce_growth/__init__.py"
                code = entry.read_text()
                marker = '        "contributions": [\n'
                if code.count(marker) != 1:
                    raise RuntimeError("growth registration marker drifted")
                code = code.replace(marker, '        "contributions": [dict(item) for item in _STATIC_CONTRIBUTIONS] + [\n', 1)
                code += "\n\n_STATIC_CONTRIBUTIONS = " + repr(tuple(static)) + "\n"
                entry.write_text(code)
                old_ref = b"bundle://aos/solution.ecommerce.growth@1.5.0"
                new_ref = b"bundle://aos/solution.ecommerce.growth@1.6.0"
                changed = 0
                for path in sorted((destination / "content/workshops").glob("*.json")):
                    raw = path.read_bytes()
                    if old_ref in raw:
                        if raw.count(old_ref) != 1:
                            raise RuntimeError("growth self reference is ambiguous")
                        path.write_bytes(raw.replace(old_ref, new_ref)); changed += 1
                if changed != 8:
                    raise RuntimeError("growth self reference set drifted")
            results.append({"coordinate": f"aos/{target.replace('/', '@')}", "treeHash": "sha256:" + tree_hash(destination)})
        return {"outcome": "CANDIDATES_PREPARED", "candidates": results}
    except BaseException:
        for target in created:
            shutil.rmtree(target, ignore_errors=True)
        raise


if __name__ == "__main__":
    print(prepare())
