#!/usr/bin/env python3
"""Create an unsigned BI-template successor without changing current bundles."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from prepare_ecommerce_growth_1_5_candidate import tree_hash


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.11.0"
TARGET = BASE.parent / "1.12.0"
BASE_HASH = "47b1b5ff4093ba76606b8a54867dde312d94ee3565eff959087225b4157e6b4c"
TEMPLATE = "content/responsibility-templates/business-investigation.readonly.json"


def _replace_once(raw: str, old: str, new: str) -> str:
    if raw.count(old) != 1:
        raise ValueError("exact candidate marker drifted")
    return raw.replace(old, new, 1)


def _bi_template_bytes() -> bytes:
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    try:
        from aos_api.aip_business_investigation_responsibility_template import (
            BI_ROLE_BLUEPRINTS, BI_TEMPLATE_ID, BI_TEMPLATE_SCHEMA,
            BIResponsibilityTemplate,
        )
        payload = {
            "schema": BI_TEMPLATE_SCHEMA,
            "templateId": BI_TEMPLATE_ID,
            "revision": 1,
            "profile": BI_TEMPLATE_ID,
            "safetyMode": "read-only",
            "slots": [
                {"slotId": slot_id, "responsibilityType": role,
                 "requiredCapabilityIds": list(capabilities), "returnStage": stage}
                for slot_id, role, _instance_id, capabilities, stage in BI_ROLE_BLUEPRINTS
            ],
        }
        BIResponsibilityTemplate.model_validate(payload)
        return (json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n").encode("utf-8")
    finally:
        sys.path.remove(str(ROOT / "services/aos-api"))


def prepare(target: Path = TARGET) -> dict[str, object]:
    if not isinstance(target, Path) or target.exists() or target.is_symlink():
        raise ValueError("immutable candidate target already exists")
    if tree_hash(BASE) != BASE_HASH:
        raise ValueError("reviewed 1.11.0 baseline drifted")
    template_bytes = _bi_template_bytes()
    with tempfile.TemporaryDirectory(prefix=".growth-1-12-", dir=target.parent) as temp:
        staged = Path(temp) / target.name
        shutil.copytree(BASE, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        manifest = staged / "bundle.yaml"
        raw = _replace_once(manifest.read_text(),
                            "  version: 1.11.0\n", "  version: 1.12.0\n")
        raw = _replace_once(raw,
                            "      - content/media-production-templates/\n",
                            "      - content/media-production-templates/\n"
                            "      - content/responsibility-templates/\n")
        manifest.write_text(raw)
        old_ref = "bundle://aos/solution.ecommerce.growth@1.11.0"
        new_ref = "bundle://aos/solution.ecommerce.growth@1.12.0"
        changed = []
        for path in sorted((staged / "content/workshops").glob("*.json")):
            original = path.read_text()
            if old_ref in original:
                path.write_text(_replace_once(original, old_ref, new_ref))
                changed.append(str(path.relative_to(staged)))
        if len(changed) != 8:
            raise ValueError("candidate self-reference inventory drifted")
        template_path = staged / TEMPLATE
        template_path.parent.mkdir(parents=True)
        template_path.write_bytes(template_bytes)
        for relative in (
            "evidence/bundle-evals.json", "evidence/sbom.json", "bundle.signature.json",
            "artifacts/runtime-image-index.json", "artifacts/python-dependencies.lock",
        ):
            path = staged / relative
            if path.exists():
                path.unlink()
        (staged / "evidence/content-source-provenance.json").write_text(
            json.dumps({
                "status": "UNBUILT_UNSIGNED",
                "baseVersion": "1.11.0",
                "baseTreeHash": BASE_HASH,
                "biTemplateSha256": "sha256:" + hashlib.sha256(template_bytes).hexdigest(),
                "buildEvidenceRequired": ["runtime-image-index", "dependency-lock",
                                          "sbom-validation", "bundle-evals", "signature"],
            }, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        if target.exists() or target.is_symlink() or tree_hash(BASE) != BASE_HASH:
            raise ValueError("candidate target or historical baseline changed")
        os.rename(staged, target)
    return {"version": "1.12.0", "state": "UNBUILT_UNSIGNED",
            "treeHash": tree_hash(target), "changedSelfReferences": changed}


if __name__ == "__main__":
    print(json.dumps(prepare(), ensure_ascii=False, sort_keys=True, indent=2))
