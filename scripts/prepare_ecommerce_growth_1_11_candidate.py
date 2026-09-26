#!/usr/bin/env python3
"""Freeze an unbuilt/unsigned growth content successor without touching history."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from prepare_ecommerce_growth_1_5_candidate import tree_hash


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'bundles/candidates/ecommerce/solution.ecommerce.growth/1.10.0'
AUTHOR = ROOT / 'bundles/solutions/ecommerce-growth'
TARGET = BASE.parent / '1.11.0'
BASE_HASH = 'f473d9a452bdac2f5547525672b32cabf53a4f58dcddcfc8d75cd372e06fe688'
SOURCES = {
    'backend/ecommerce_growth/content_capability_runtime.py':
        '3d0dacd00b17c42db646ce363be557611404dd959c738d65baf9eb119c654138',
    'backend/ecommerce_growth/ecommerce_content_campaign_workflow_contracts.py':
        'c775199739469a3a397b7285541ded896925f93f332a56833bf16f61301b9b8d',
    'backend/ecommerce_growth/sales_weapon_brief.py':
        '5c7dc9790ac0fbfbea4b23b78a16e287b0702f56b39fe3022e8dcec32d9dea78',
}


def _replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError('exact candidate marker drifted')
    return text.replace(old, new, 1)


def prepare(target: Path = TARGET) -> dict[str, object]:
    if not isinstance(target, Path) or target.exists() or target.is_symlink():
        raise ValueError('immutable candidate target already exists')
    if tree_hash(BASE) != BASE_HASH:
        raise ValueError('reviewed 1.10.0 baseline drifted')
    values = {relative: (AUTHOR / relative).read_bytes() for relative in SOURCES}
    if any(hashlib.sha256(raw).hexdigest() != SOURCES[relative]
           for relative, raw in values.items()):
        raise ValueError('reviewed content source drifted')
    with tempfile.TemporaryDirectory(prefix='.growth-1-11-', dir=target.parent) as root:
        staged = Path(root) / target.name
        shutil.copytree(BASE, staged, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for relative, raw in values.items():
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        manifest = staged / 'bundle.yaml'
        manifest.write_text(_replace_once(manifest.read_text(),
            '  version: 1.10.0\n', '  version: 1.11.0\n'))
        changed = []
        old_ref = 'bundle://aos/solution.ecommerce.growth@1.10.0'
        new_ref = 'bundle://aos/solution.ecommerce.growth@1.11.0'
        for path in sorted((staged / 'content/workshops').glob('*.json')):
            original = path.read_text()
            if old_ref in original:
                path.write_text(_replace_once(original, old_ref, new_ref))
                changed.append(str(path.relative_to(staged)))
        if len(changed) != 8 or old_ref in manifest.read_text():
            raise ValueError('candidate self-reference inventory drifted')
        # These old build/approval artifacts cannot attest to the changed code.
        for relative in ('evidence/bundle-evals.json', 'bundle.signature.json',
                         'artifacts/runtime-image-index.json',
                         'artifacts/python-dependencies.lock'):
            path = staged / relative
            if path.exists():
                path.unlink()
        provenance = {
            'status': 'UNBUILT_UNSIGNED',
            'baseVersion': '1.10.0',
            'baseTreeHash': BASE_HASH,
            'sourceSha256': SOURCES,
            'buildEvidenceRequired': ['runtime-image-index', 'dependency-lock',
                                      'sbom-validation', 'bundle-evals', 'signature'],
        }
        (staged / 'evidence/content-source-provenance.json').write_text(
            json.dumps(provenance, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')
        if target.exists() or target.is_symlink() or tree_hash(BASE) != BASE_HASH:
            raise ValueError('candidate target or historical baseline changed')
        os.rename(staged, target)
    return {'version': '1.11.0', 'state': 'UNBUILT_UNSIGNED',
            'treeHash': tree_hash(target), 'changedSelfReferences': changed}


if __name__ == '__main__':
    print(json.dumps(prepare(), ensure_ascii=False, sort_keys=True, indent=2))
