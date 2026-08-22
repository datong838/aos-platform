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
_ALLOWED_FIELD_TYPES = {"bool", "date", "datetime", "decimal", "float", "int", "json", "string", "text", "timestamp"}


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

    def mapping_proposal(self, adapter_pack_ref: str, data_types: list[str]) -> dict[str, Any]:
        """Return normalized static mappings; never execute mapping expressions."""
        inspection = self.inspect(adapter_pack_ref, data_types)
        if inspection.get("packStatus") != "probed":
            return {
                "adapterPackRef": adapter_pack_ref,
                "mappingStatus": "unknown",
                "mappings": [],
                "missingDataTypes": list(data_types),
                "blockers": ["FDE_ADAPTER_PACK_UNKNOWN"],
            }

        proposals: list[dict[str, Any]] = []
        blockers: list[str] = []
        for data_type in data_types:
            filename = _MAPPINGS.get(data_type)
            if filename is None:
                continue
            path = self._root / "content/mappings" / filename
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                blockers.append(f"FDE_MAPPING_INVALID:{data_type}")
                continue
            field_mappings = raw.get("field_mappings")
            if not isinstance(field_mappings, list):
                blockers.append(f"FDE_MAPPING_FIELDS_MISSING:{data_type}")
                continue
            normalized_fields: list[dict[str, str]] = []
            for row in field_mappings:
                if not isinstance(row, dict):
                    blockers.append(f"FDE_MAPPING_FIELD_INVALID:{data_type}")
                    continue
                source = row.get("source")
                target = row.get("target")
                field_type = row.get("type")
                if not all(isinstance(value, str) and value.strip() == value and value for value in (source, target, field_type)):
                    blockers.append(f"FDE_MAPPING_FIELD_INVALID:{data_type}")
                    continue
                if field_type not in _ALLOWED_FIELD_TYPES:
                    blockers.append(f"FDE_MAPPING_TYPE_UNSUPPORTED:{data_type}:{field_type}")
                normalized_fields.append({"source": source, "target": target, "type": field_type})

            targets = [row["target"] for row in normalized_fields]
            duplicate_targets = sorted({target for target in targets if targets.count(target) > 1})
            primary_key = raw.get("primary_key")
            primary_target = next(
                (row["target"] for row in normalized_fields if row["source"] == primary_key),
                None,
            )
            if duplicate_targets:
                blockers.append(f"FDE_MAPPING_TARGET_CONFLICT:{data_type}")
            if primary_target is None:
                blockers.append(f"FDE_MAPPING_PRIMARY_TARGET_MISSING:{data_type}")
            proposals.append(
                {
                    "dataType": data_type,
                    "pipelineId": raw.get("pipeline_id"),
                    "sourceTable": raw.get("source_table"),
                    "targetObjectType": raw.get("target_ot"),
                    "primaryKey": primary_key,
                    "primaryTarget": primary_target,
                    "siteFilter": raw.get("site_filter"),
                    "incrementalStrategy": raw.get("incremental_strategy"),
                    "incrementalCursor": raw.get("incremental_cursor"),
                    "piiExclusion": list(raw.get("pii_exclusion") or []),
                    "fieldMappings": normalized_fields,
                    "mappingRef": f"bundle://platforms/ecommerce-niushop/content/mappings/{filename}",
                    "contentHash": _sha(path),
                    "coverage": 1.0 if normalized_fields else 0.0,
                    "duplicateTargets": duplicate_targets,
                }
            )
        result = {
            "adapterPackRef": adapter_pack_ref,
            "mappingStatus": "proposed" if proposals and not blockers else "partial",
            "mappings": proposals,
            "missingDataTypes": inspection.get("missingDataTypes", []),
            "blockers": sorted(set(blockers)),
            "allowedFieldTypes": sorted(_ALLOWED_FIELD_TYPES),
            "expressionExecution": False,
        }
        result["proposalHash"] = hashlib.sha256(
            json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return result
