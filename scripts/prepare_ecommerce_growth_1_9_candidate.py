#!/usr/bin/env python3
"""Freeze the reviewed ProductEvent runtime into an immutable growth 1.9 candidate."""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

from prepare_ecommerce_growth_1_5_candidate import tree_hash

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.8.0"
AUTHOR = ROOT / "bundles/solutions/ecommerce-growth"
TARGET = BASE.parent / "1.9.0"
BASE_HASH = "718548ad92a3715891b4b84060f0a2f22ad4baf6e492195573738e49c40ac8c4"
AUTHOR_ENTRY_HASH = "ccda1d493b9177124c51977bd578223cf38c92c45c9f26e5e0b795204946c905"
COPY_SOURCES = {
    "backend/ecommerce_growth/analysis_compilation_blueprint.py": "efad9be76309d29cd8d4987f72c4b1625829257cde5416fab1b87dfc287512a8",
    "backend/ecommerce_growth/analysis_start_operation.py": "c324568193aab81ef5cb2495ec332d22b77e842c7c7433a2e6e17f0cd4684d48",
    "backend/ecommerce_growth/ecommerce_business_investigation_application.py": "828bdac469a72f3a99776539655df0e358858b4ad09f0d5eda380d3740544a9f",
    "backend/ecommerce_growth/ecommerce_product_event_binding.py": "f5daff339d18214864a78a01767d6dc7b8f2a6fdd9edfb8ad6d40e45e6abe011",
    "backend/ecommerce_growth/ecommerce_product_event_command.py": "44b216eee44d4dceb6700e242c5630bd9b2320f4e8ef4f01ce973e7fcbb371d3",
    "backend/ecommerce_growth/ecommerce_product_event_control.py": "b7b392d3f85dc85cc0b96d84b8ee8517239da312d85a8576197dda76c288b82b",
    "backend/ecommerce_growth/ecommerce_product_event_schedule.py": "07cc9387bee74bcc9f66cdcfead0fb39ca621689058abfb6a408f736285e51ed",
}

_BASE_OPERATION = (
    '    ("ecommerce_growth_investigation_describe", "POST", '
    '"/ecommerce/growth/investigations/describe"),\n'
)
_CONTROL_OPERATION = (
    '    ("ecommerce_growth_event_control", "POST", '
    '"/ecommerce/growth/investigations/events/control"),\n'
)
_HANDLER_MARKER = '    if operation_id == "analyst_workspace_view_v1":\n'
_ANALYSIS_HANDLERS = '''    if (operation_id == "ecommerce_growth_analysis_advance"
            and type(_payload) is dict and _payload.get("kind") == "build_analysis_start"):
        from .analysis_start_operation import build_analysis_start

        return build_analysis_start(_payload)
    if (operation_id == "ecommerce_growth_analysis_advance"
            and type(_payload) is dict and _payload.get("kind") == "build_analysis_compilation_blueprint"):
        from .analysis_compilation_blueprint import build_analysis_compilation_blueprint

        return build_analysis_compilation_blueprint(_payload)
'''
_MANIFEST_OPERATION = """    - kind: api
      operationId: ecommerce_growth_investigation_describe
      method: POST
      path: /ecommerce/growth/investigations/describe
      mode: exclusive
"""
_MANIFEST_CONTROL = """    - kind: api
      operationId: ecommerce_growth_event_control
      method: POST
      path: /ecommerce/growth/investigations/events/control
      mode: exclusive
"""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def prepare(target: Path = TARGET):
    if not isinstance(target, Path) or target.exists() or target.is_symlink():
        raise ValueError("new candidate target must not exist")
    if tree_hash(BASE) != BASE_HASH:
        raise ValueError("immutable 1.8 baseline drifted")
    author_entry = (AUTHOR / "backend/ecommerce_growth/__init__.py").read_bytes()
    if _sha256(author_entry) != AUTHOR_ENTRY_HASH:
        raise ValueError("reviewed author registration drifted")
    sources = {path: (AUTHOR / path).read_bytes() for path in COPY_SOURCES}
    if any(_sha256(raw) != COPY_SOURCES[path] for path, raw in sources.items()):
        raise ValueError("reviewed author source drifted")

    parsed = ast.parse((BASE / "backend/ecommerce_growth/__init__.py").read_text())
    declarations = [
        ast.literal_eval(node.value)
        for node in parsed.body
        if isinstance(node, ast.Assign)
        and any(isinstance(name, ast.Name) and name.id == "_STATIC_CONTRIBUTIONS" for name in node.targets)
    ]
    if len(declarations) != 1 or len(declarations[0]) != 14:
        raise ValueError("baseline static registration differs")

    shutil.copytree(BASE, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    try:
        for relative, raw in sources.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

        entry = target / "backend/ecommerce_growth/__init__.py"
        code = entry.read_text()
        if code.count(_BASE_OPERATION) != 1 or code.count(_HANDLER_MARKER) != 1:
            raise ValueError("baseline runtime entry markers differ")
        code = code.replace(_BASE_OPERATION, _CONTROL_OPERATION + _BASE_OPERATION, 1)
        code = code.replace(_HANDLER_MARKER, _ANALYSIS_HANDLERS + _HANDLER_MARKER, 1)
        entry.write_text(code)

        manifest = target / "bundle.yaml"
        body = manifest.read_text()
        substitutions = {
            "  version: 1.8.0\n": "  version: 1.9.0\n",
            _MANIFEST_OPERATION: _MANIFEST_CONTROL + _MANIFEST_OPERATION,
        }
        for old, new in substitutions.items():
            if body.count(old) != 1:
                raise ValueError("baseline manifest marker differs")
            body = body.replace(old, new, 1)
        manifest.write_text(body)

        changed_refs = []
        for path in sorted((target / "content/workshops").glob("*.json")):
            raw = path.read_bytes()
            old = b"bundle://aos/solution.ecommerce.growth@1.8.0"
            if old in raw:
                if raw.count(old) != 1:
                    raise ValueError("ambiguous self reference")
                path.write_bytes(raw.replace(old, b"bundle://aos/solution.ecommerce.growth@1.9.0"))
                changed_refs.append(str(path.relative_to(target)))
        if len(changed_refs) != 8 or tree_hash(BASE) != BASE_HASH:
            raise ValueError("baseline or self references drifted")
        return {
            "coordinate": "aos/solution.ecommerce.growth@1.9.0",
            "treeHash": "sha256:" + tree_hash(target),
            "updatedSelfReferences": changed_refs,
            "sourceHashes": COPY_SOURCES,
            "authorEntryHash": AUTHOR_ENTRY_HASH,
        }
    except BaseException:
        shutil.rmtree(target)
        raise


if __name__ == "__main__":
    print(json.dumps(prepare(), ensure_ascii=False, indent=2))
