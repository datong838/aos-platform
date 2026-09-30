"""Independent growth 1.12 build profile; keeps current 1.11 profile intact."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CURRENT_GROWTH = ("solution.ecommerce.growth/1.11.0", "solution.ecommerce.growth", "1.11.0", "ecommerce_growth")
NEW_GROWTH = ("solution.ecommerce.growth/1.12.0", "solution.ecommerce.growth", "1.12.0", "ecommerce_growth")
BASE_SBOM = ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.11.0/evidence/sbom.json"
BASE_SBOM_HASH = "ac64aec9f5d0d3535d1174026f3d9ed0bdeb11eef7fd76bb93e220cd1f079d5e"


def _load_current_builder():
    path = ROOT / "scripts/build_ecommerce_current_candidates.py"
    spec = importlib.util.spec_from_file_location("growth_1_12_current_builder", path)
    if spec is None or spec.loader is None:
        raise ValueError("current profile unavailable")
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    return profile.load_builder()


def load_builder():
    builder = _load_current_builder()
    if (builder.RUNTIME_CASES.count(CURRENT_GROWTH) != 1
            or builder.ALL_CASES.count(CURRENT_GROWTH) != 1
            or builder.EXPECTED_RUNTIME_OPERATION_COUNT != 15):
        raise ValueError("current profile drifted")
    builder.RUNTIME_CASES = tuple(
        NEW_GROWTH if item == CURRENT_GROWTH else item for item in builder.RUNTIME_CASES)
    builder.ALL_CASES = tuple(
        NEW_GROWTH if item == CURRENT_GROWTH else item for item in builder.ALL_CASES)
    original_augment = builder._augment_sbom

    def augment_sbom(bundle: Path, *, sdk_hash: str, base_config_digest: str) -> None:
        if bundle.name == "1.12.0" and bundle.parent.name == "solution.ecommerce.growth":
            raw = BASE_SBOM.read_bytes()
            if hashlib.sha256(raw).hexdigest() != BASE_SBOM_HASH:
                raise ValueError("SBOM baseline drifted")
            path = bundle / "evidence/sbom.json"
            if path.exists():
                raise ValueError("growth SBOM already exists")
            document = json.loads(raw)
            components = document.get("components")
            if not isinstance(components, list) or any(
                    item.get("name") == "business-investigation.readonly"
                    for item in components if isinstance(item, dict)):
                raise ValueError("SBOM components drifted")
            components.append({"type": "data", "name": "business-investigation.readonly", "version": "1"})
            path.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")) + "\n")
        original_augment(bundle, sdk_hash=sdk_hash, base_config_digest=base_config_digest)

    builder._augment_sbom = augment_sbom
    return builder


if __name__ == "__main__":
    raise SystemExit(load_builder().main())
