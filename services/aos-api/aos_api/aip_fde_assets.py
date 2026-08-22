"""Read-only, allowlisted FDE AdapterPack inspection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

_PACK_REF = "platform.ecommerce.niushop@1.0.0"
_MAPPINGS = {
    "shops": "p01-shop.yaml",
    "products": "p02-product.yaml",
    "product_skus": "p03-product-sku.yaml",
    "categories": "p04-category.yaml",
    "orders": "p05-order.yaml",
    "order_lines": "p06-order-line.yaml",
    "shipments": "p07-shipment.yaml",
    "customers": "p08-customer-lite.yaml",
    "weapps": "p09-weapp.yaml",
    "system_config": "p10-system-config.yaml",
    "product_reviews": "p11-product-review.yaml",
    "payments": "p12-payment.yaml",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FdeAdapterPackInspector:
    def __init__(self, repo_root: Path | None = None) -> None:
        root = repo_root or Path(__file__).resolve().parents[3]
        self._root = root / "bundles/platforms/ecommerce-niushop"

    def inspect(self, adapter_pack_ref: str, data_types: list[str]) -> dict[str, Any]:
        if adapter_pack_ref != _PACK_REF:
            return {
                "adapterPackRef": adapter_pack_ref,
                "packStatus": "unknown",
                "mappingRefs": [],
                "schemaRefs": [],
                "connectorRefs": [],
                "missingDataTypes": list(data_types),
            }
        manifest_path = self._root / "bundle.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        metadata = manifest.get("metadata") if isinstance(manifest, dict) else None
        if not isinstance(metadata, dict) or metadata.get("id") != "platform.ecommerce.niushop" or metadata.get("version") != "1.0.0":
            raise ValueError("AdapterPack manifest identity mismatch")

        mapping_refs: list[dict[str, str]] = []
        missing: list[str] = []
        for data_type in data_types:
            filename = _MAPPINGS.get(data_type)
            path = self._root / "content/mappings" / filename if filename else None
            if path is None or not path.is_file():
                missing.append(data_type)
                continue
            mapping_refs.append(
                {
                    "dataType": data_type,
                    "ref": f"bundle://platforms/ecommerce-niushop/content/mappings/{filename}",
                    "contentHash": _sha(path),
                }
            )
        schemas = sorted((self._root / "content/schemas").glob("*"))
        connectors = sorted((self._root / "content/connectors").glob("*"))
        result = {
            "adapterPackRef": _PACK_REF,
            "packStatus": "probed",
            "manifestHash": _sha(manifest_path),
            "mappingRefs": mapping_refs,
            "schemaRefs": [
                {
                    "ref": f"bundle://platforms/ecommerce-niushop/content/schemas/{path.name}",
                    "contentHash": _sha(path),
                }
                for path in schemas
                if path.is_file()
            ],
            "connectorRefs": [
                {
                    "ref": f"bundle://platforms/ecommerce-niushop/content/connectors/{path.name}",
                    "contentHash": _sha(path),
                }
                for path in connectors
                if path.is_file()
            ],
            "missingDataTypes": missing,
        }
        result["snapshotHash"] = hashlib.sha256(
            json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return result
