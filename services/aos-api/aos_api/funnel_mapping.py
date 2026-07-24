"""W1-3 · Funnel 可视化映射编辑器。

源 Schema → 目标 Schema 的字段映射 + 自动映射 + Lint 门控 + 行业模板 + 预览转换。

详见 docs/palantier/20_tech/220tech_funnel-mapping-editor.md。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .function_engine import FunctionError, evaluate, parse


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return "fm-" + uuid.uuid4().hex[:12]


FieldType = Literal["string", "number", "boolean", "date"]

_COMPAT: dict[str, set[str]] = {
    "string": {"string", "number", "boolean", "date"},
    "number": {"string", "number"},
    "boolean": {"string", "boolean"},
    "date": {"string", "date"},
}


def _type_compatible(source_type: str, target_type: str) -> bool:
    return target_type in _COMPAT.get(source_type, set())


class SchemaField(BaseModel):
    name: str
    type: FieldType = "string"
    nullable: bool = True


class MappingRule(BaseModel):
    source_field: str | None = None
    target_field: str
    transform_expr: str | None = None
    default: Any = None


class MappingSpec(BaseModel):
    id: str
    name: str
    source_schema: list[SchemaField] = Field(default_factory=list)
    target_schema: list[SchemaField] = Field(default_factory=list)
    rules: list[MappingRule] = Field(default_factory=list)
    template: str | None = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class LintResult(BaseModel):
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unmapped_targets: list[str] = Field(default_factory=list)
    type_mismatches: list[str] = Field(default_factory=list)


class FunnelMappingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


TEMPLATES: dict[str, dict[str, Any]] = {
    "ecommerce": {
        "target_schema": [
            SchemaField(name="order_id", type="string", nullable=False),
            SchemaField(name="customer_id", type="string", nullable=False),
            SchemaField(name="product_id", type="string"),
            SchemaField(name="quantity", type="number"),
            SchemaField(name="price", type="number"),
            SchemaField(name="total", type="number"),
        ],
        "patterns": [
            ("order", "order_id"), ("customer", "customer_id"), ("product", "product_id"),
            ("qty", "quantity"), ("price", "price"), ("total", "total"),
        ],
    },
    "manufacturing": {
        "target_schema": [
            SchemaField(name="workorder_id", type="string", nullable=False),
            SchemaField(name="part_id", type="string"),
            SchemaField(name="station_id", type="string"),
            SchemaField(name="operator_id", type="string"),
            SchemaField(name="quantity", type="number"),
            SchemaField(name="defect_rate", type="number"),
        ],
        "patterns": [
            ("workorder", "workorder_id"), ("part", "part_id"), ("station", "station_id"),
            ("operator", "operator_id"), ("qty", "quantity"), ("defect", "defect_rate"),
        ],
    },
    "finance": {
        "target_schema": [
            SchemaField(name="transaction_id", type="string", nullable=False),
            SchemaField(name="account_id", type="string", nullable=False),
            SchemaField(name="amount", type="number"),
            SchemaField(name="currency", type="string"),
            SchemaField(name="timestamp", type="date"),
            SchemaField(name="status", type="string"),
        ],
        "patterns": [
            ("transaction", "transaction_id"), ("account", "account_id"), ("amount", "amount"),
            ("currency", "currency"), ("time", "timestamp"), ("status", "status"),
        ],
    },
}


class FunnelMappingEditor:
    def __init__(self) -> None:
        self._specs: dict[str, MappingSpec] = {}

    def create(
        self, name: str, source_schema: list[SchemaField], target_schema: list[SchemaField]
    ) -> MappingSpec:
        spec = MappingSpec(
            id=_new_id(), name=name,
            source_schema=source_schema, target_schema=target_schema,
        )
        self._specs[spec.id] = spec
        return spec

    def list_all(self) -> list[MappingSpec]:
        return list(self._specs.values())

    def get(self, spec_id: str) -> MappingSpec:
        if spec_id not in self._specs:
            raise FunnelMappingError("NOT_FOUND", f"映射 {spec_id!r} 不存在")
        return self._specs[spec_id]

    def delete(self, spec_id: str) -> None:
        if spec_id not in self._specs:
            raise FunnelMappingError("NOT_FOUND", f"映射 {spec_id!r} 不存在")
        del self._specs[spec_id]

    def add_rule(self, spec_id: str, rule: MappingRule) -> MappingSpec:
        spec = self.get(spec_id)
        self._validate_rule(spec, rule)
        spec.rules = [r for r in spec.rules if r.target_field != rule.target_field] + [rule]
        spec.updated_at = _now()
        return spec

    def remove_rule(self, spec_id: str, target_field: str) -> MappingSpec:
        spec = self.get(spec_id)
        before = len(spec.rules)
        spec.rules = [r for r in spec.rules if r.target_field != target_field]
        if len(spec.rules) == before:
            raise FunnelMappingError("RULE_NOT_FOUND", f"目标字段 {target_field!r} 无映射规则")
        spec.updated_at = _now()
        return spec

    def auto_map(self, spec_id: str) -> MappingSpec:
        spec = self.get(spec_id)
        source_by_name = {f.name: f for f in spec.source_schema}
        rules: list[MappingRule] = []
        for target in spec.target_schema:
            source = source_by_name.get(target.name)
            if source and _type_compatible(source.type, target.type):
                rules.append(MappingRule(source_field=source.name, target_field=target.name))
        spec.rules = rules
        spec.updated_at = _now()
        return spec

    def lint(self, spec_id: str) -> LintResult:
        spec = self.get(spec_id)
        errors: list[str] = []
        warnings: list[str] = []
        unmapped: list[str] = []
        mismatches: list[str] = []
        source_names = {f.name for f in spec.source_schema}
        target_by_name = {f.name: f for f in spec.target_schema}
        mapped_targets: set[str] = set()
        for rule in spec.rules:
            if rule.target_field not in target_by_name:
                errors.append(f"RULE_BAD_TARGET: 目标字段 {rule.target_field!r} 不在 target_schema")
                continue
            if rule.target_field in mapped_targets:
                errors.append(f"RULE_DUP_TARGET: 目标字段 {rule.target_field!r} 重复映射")
            mapped_targets.add(rule.target_field)
            if rule.source_field and rule.source_field not in source_names:
                errors.append(f"RULE_BAD_SOURCE: 源字段 {rule.source_field!r} 不在 source_schema")
            elif rule.source_field:
                src = next(f for f in spec.source_schema if f.name == rule.source_field)
                tgt = target_by_name[rule.target_field]
                if not _type_compatible(src.type, tgt.type):
                    mismatches.append(f"{rule.source_field}({src.type})→{rule.target_field}({tgt.type})")
                    errors.append(f"TYPE_MISMATCH: {rule.source_field}({src.type}) 不兼容 {rule.target_field}({tgt.type})")
            target = target_by_name[rule.target_field]
            if not target.nullable and rule.source_field is None and rule.default is None:
                warnings.append(f"NULLABLE_VIOLATION: {rule.target_field!r} 非空但无 source/default")
        for target in spec.target_schema:
            if target.name not in mapped_targets:
                unmapped.append(target.name)
                if not target.nullable:
                    errors.append(f"UNMAPPED_REQUIRED: 必填目标字段 {target.name!r} 未映射")
        return LintResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            unmapped_targets=unmapped,
            type_mismatches=mismatches,
        )

    def apply_template(self, spec_id: str, template_name: str) -> MappingSpec:
        if template_name not in TEMPLATES:
            raise FunnelMappingError("BAD_TEMPLATE", f"未知模板 {template_name!r}，可用：{list(TEMPLATES.keys())}")
        spec = self.get(spec_id)
        template = TEMPLATES[template_name]
        spec.target_schema = list(template["target_schema"])
        source_names = {f.name: f for f in spec.source_schema}
        rules: list[MappingRule] = []
        for pattern, target_name in template["patterns"]:
            matched = next((n for n in source_names if pattern.lower() in n.lower()), None)
            if matched:
                rules.append(MappingRule(source_field=matched, target_field=target_name))
        spec.rules = rules
        spec.template = template_name
        spec.updated_at = _now()
        return spec

    def preview(self, spec_id: str, source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        spec = self.get(spec_id)
        result: list[dict[str, Any]] = []
        for row in source_rows:
            out: dict[str, Any] = {}
            for rule in spec.rules:
                if rule.source_field and rule.source_field in row:
                    val = row[rule.source_field]
                    if rule.transform_expr:
                        try:
                            val = evaluate(parse(rule.transform_expr), {rule.source_field: val, "row": row})
                        except FunctionError as exc:
                            raise FunnelMappingError("TRANSFORM_ERROR", f"字段 {rule.target_field!r} 表达式失败: {exc.message}") from exc
                else:
                    val = rule.default
                out[rule.target_field] = val
            result.append(out)
        return result

    def _validate_rule(self, spec: MappingSpec, rule: MappingRule) -> None:
        target_names = {f.name for f in spec.target_schema}
        if rule.target_field not in target_names:
            raise FunnelMappingError("RULE_BAD_TARGET", f"目标字段 {rule.target_field!r} 不在 target_schema")

    def list_templates(self) -> list[str]:
        return list(TEMPLATES.keys())


_editor = FunnelMappingEditor()


def get_editor() -> FunnelMappingEditor:
    return _editor
