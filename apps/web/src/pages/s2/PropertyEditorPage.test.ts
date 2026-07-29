import { describe, expect, it } from "vitest";
import {
  emptyProperty,
  validateProperty,
  isValidPropertyName,
  autoMapColumnName,
  summarizeProperties,
  filterProperties,
  typeIcon,
  typeLabel,
  statusLabel,
  statusColor,
  PROPERTY_TYPES,
  PROPERTY_STATUSES,
  mapDatatypeToUiType,
  mapApiPropertyToField,
  mapFieldToAddRequest,
  buildMappingSaveBody,
  applyMappingsToProperties,
  countMappedColumns,
  isNewPropertyId,
  type PropertyField,
  type ColumnMappingRow,
} from "./PropertyEditorPage";

describe("PropertyEditorPage · emptyProperty", () => {
  it("creates a property with default values", () => {
    const p = emptyProperty();
    expect(p.name).toBe("");
    expect(p.type).toBe("STRING");
    expect(p.status).toBe("experimental");
    expect(p.isRequired).toBe(false);
  });

  it("creates with prefix in id", () => {
    const p = emptyProperty("order_");
    expect(p.id).toContain("order_");
  });
});

describe("PropertyEditorPage · isValidPropertyName", () => {
  it("accepts valid identifiers", () => {
    expect(isValidPropertyName("order_id")).toBe(true);
    expect(isValidPropertyName("_private")).toBe(true);
    expect(isValidPropertyName("CamelCase")).toBe(true);
    expect(isValidPropertyName("field123")).toBe(true);
  });

  it("rejects invalid identifiers", () => {
    expect(isValidPropertyName("")).toBe(false);
    expect(isValidPropertyName("123abc")).toBe(false);
    expect(isValidPropertyName("has space")).toBe(false);
    expect(isValidPropertyName("has-dash")).toBe(false);
    expect(isValidPropertyName("has.dot")).toBe(false);
  });
});

describe("PropertyEditorPage · validateProperty", () => {
  it("passes for valid property", () => {
    const p: PropertyField = { ...emptyProperty(), name: "order_amount", type: "DECIMAL" };
    const errors = validateProperty(p);
    expect(errors).toHaveLength(0);
  });

  it("catches empty name", () => {
    const p: PropertyField = { ...emptyProperty(), name: "" };
    expect(validateProperty(p)).toContain("name 不能为空");
  });

  it("catches invalid name format", () => {
    const p: PropertyField = { ...emptyProperty(), name: "123bad" };
    expect(validateProperty(p)).toContain(
      "name 必须以字母或下划线开头，只允许字母、数字、下划线",
    );
  });

  it("catches whitespace-only name", () => {
    const p: PropertyField = { ...emptyProperty(), name: "   " };
    expect(validateProperty(p)).toContain("name 不能为空");
  });

  it("catches PK + Title mutual exclusivity", () => {
    const p: PropertyField = { ...emptyProperty(), name: "test", isPrimaryKey: true, isTitleKey: true };
    expect(validateProperty(p)).toContain(
      "同一属性不能同时为 primaryKey 和 titleKey",
    );
  });

  it("catches DECIMAL min/max when min > max", () => {
    const p: PropertyField = {
      ...emptyProperty(),
      name: "price",
      type: "DECIMAL",
      minValue: "100",
      maxValue: "50",
    };
    expect(validateProperty(p)).toContain("minValue 不能大于 maxValue");
  });

  it("allows DECIMAL with valid min/max", () => {
    const p: PropertyField = {
      ...emptyProperty(),
      name: "price",
      type: "DECIMAL",
      minValue: "10",
      maxValue: "100",
    };
    const errors = validateProperty(p);
    expect(errors).not.toContain("minValue 不能大于 maxValue");
  });

  it("catches BOOLEAN as primary key", () => {
    const p: PropertyField = { ...emptyProperty(), name: "active", type: "BOOLEAN", isPrimaryKey: true };
    expect(validateProperty(p)).toContain("BOOLEAN 类型不能作为主键");
  });

  it("catches non-integer INTEGER default value", () => {
    const p: PropertyField = { ...emptyProperty(), name: "count", type: "INTEGER", defaultValue: "abc" };
    expect(validateProperty(p)).toContain("INTEGER 类型的 defaultValue 必须是整数");
  });
});

describe("PropertyEditorPage · autoMapColumnName", () => {
  it("converts camelCase to snake_lower", () => {
    expect(autoMapColumnName("orderAmount")).toBe("order_amount");
  });

  it("handles already snake_case names", () => {
    expect(autoMapColumnName("order_amount")).toBe("order_amount");
  });

  it("handles PascalCase names", () => {
    expect(autoMapColumnName("OrderAmount")).toBe("order_amount");
  });

  it("handles empty string", () => {
    expect(autoMapColumnName("")).toBe("");
  });
});

describe("PropertyEditorPage · summarizeProperties", () => {
  it("counts types correctly", () => {
    const props: PropertyField[] = [
      { ...emptyProperty(), type: "STRING" as const },
      { ...emptyProperty(), type: "STRING" as const },
      { ...emptyProperty(), type: "INTEGER" as const },
      { ...emptyProperty(), type: "BOOLEAN" as const },
    ];
    const s = summarizeProperties(props);
    expect(s.byType.STRING).toBe(2);
    expect(s.byType.INTEGER).toBe(1);
    expect(s.byType.BOOLEAN).toBe(1);
  });

  it("returns empty counts for empty list", () => {
    const s = summarizeProperties([]);
    expect(s.total).toBe(0);
    expect(s.pkCount).toBe(0);
  });

  it("counts pk and titleKey", () => {
    const props = [
      { ...emptyProperty(), isPrimaryKey: true },
      { ...emptyProperty(), isTitleKey: true },
    ];
    const s = summarizeProperties(props);
    expect(s.pkCount).toBe(1);
    expect(s.titleKeyCount).toBe(1);
  });
});

describe("PropertyEditorPage · filterProperties", () => {
  it("filters by search text in name", () => {
    const props = [
      { ...emptyProperty(), name: "order_amount" },
      { ...emptyProperty(), name: "customer_name" },
    ];
    const filtered = filterProperties(props, "order", false);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].name).toBe("order_amount");
  });

  it("filters by type when query matches type", () => {
    const props: PropertyField[] = [
      { ...emptyProperty(), name: "a", type: "STRING" as const },
      { ...emptyProperty(), name: "b", type: "INTEGER" as const },
    ];
    const filtered = filterProperties(props, "integer", false);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].name).toBe("b");
  });

  it("filters showMappedOnly=true", () => {
    const props = [
      { ...emptyProperty(), name: "a", columnMapping: "col_a" },
      { ...emptyProperty(), name: "b", columnMapping: "" },
    ];
    const filtered = filterProperties(props, "", true);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].name).toBe("a");
  });

  it("returns all when no filters", () => {
    const props = [
      { ...emptyProperty(), name: "a" },
      { ...emptyProperty(), name: "b" },
    ];
    expect(filterProperties(props, "", false)).toHaveLength(2);
  });
});

describe("PropertyEditorPage · label helpers", () => {
  it("typeLabel returns correct labels", () => {
    expect(typeLabel("STRING")).toBe("String");
    expect(typeLabel("INTEGER")).toBe("Integer");
    expect(typeLabel("JSON")).toBe("JSON");
  });

  it("typeIcon returns icon for each type", () => {
    expect(typeIcon("STRING")).toBeTruthy();
    expect(typeIcon("GEOMETRY")).toBeTruthy();
  });

  it("statusLabel returns correct labels", () => {
    expect(statusLabel("active")).toBe("Active");
    expect(statusLabel("deprecated")).toBe("Deprecated");
  });

  it("statusColor returns CSS values", () => {
    expect(statusColor("active")).toBeTruthy();
    expect(statusColor("experimental")).toContain("var");
  });
});

describe("PropertyEditorPage · constants", () => {
  it("PROPERTY_TYPES has 8 types", () => {
    expect(PROPERTY_TYPES).toHaveLength(8);
  });

  it("PROPERTY_STATUSES has 3 statuses", () => {
    expect(PROPERTY_STATUSES).toHaveLength(3);
  });

  it("all PROPERTY_TYPES have value and label", () => {
    for (const t of PROPERTY_TYPES) {
      expect(t.value).toBeTruthy();
      expect(t.label).toBeTruthy();
    }
  });
});

describe("PropertyEditorPage · C3 mapping helpers", () => {
  it("mapDatatypeToUiType covers common API types", () => {
    expect(mapDatatypeToUiType("string")).toBe("STRING");
    expect(mapDatatypeToUiType("int")).toBe("INTEGER");
    expect(mapDatatypeToUiType("double")).toBe("DECIMAL");
    expect(mapDatatypeToUiType("boolean")).toBe("BOOLEAN");
  });

  it("mapApiPropertyToField maps pk/title/required", () => {
    const f = mapApiPropertyToField({
      id: "prop-1",
      name: "order_id",
      datatype: "string",
      is_primary_key: true,
      is_display_name: false,
      nullable: false,
      description: "pk",
    });
    expect(f.isPrimaryKey).toBe(true);
    expect(f.isRequired).toBe(true);
    expect(f.type).toBe("STRING");
  });

  it("mapApiPropertyToField applies columnByProp", () => {
    const f = mapApiPropertyToField(
      { id: "p1", name: "amount", datatype: "double" },
      { amount: "order_amount" },
    );
    expect(f.columnMapping).toBe("order_amount");
  });

  it("buildMappingSaveBody strips ids", () => {
    const body = buildMappingSaveBody([
      {
        id: "cm-1",
        object_type_id: "ot-1",
        source_column: "col_a",
        target_property: "a",
        confidence: 0.9,
        auto: true,
        status: "mapped",
      },
    ]);
    expect(body.mappings).toHaveLength(1);
    expect(body.mappings[0].source_column).toBe("col_a");
    expect(body.mappings[0].target_property).toBe("a");
  });

  it("applyMappingsToProperties writes columnMapping", () => {
    const props = [
      { ...emptyProperty(), name: "a", columnMapping: "" },
      { ...emptyProperty(), name: "b", columnMapping: "" },
    ];
    const rows: ColumnMappingRow[] = [
      {
        id: "1",
        object_type_id: "ot",
        source_column: "col_a",
        target_property: "a",
        confidence: 1,
        auto: true,
        status: "mapped",
      },
    ];
    const next = applyMappingsToProperties(props, rows);
    expect(next[0].columnMapping).toBe("col_a");
    expect(next[1].columnMapping).toBe("");
  });

  it("countMappedColumns counts non-skipped", () => {
    const s = countMappedColumns([
      {
        id: "1",
        object_type_id: "ot",
        source_column: "a",
        target_property: "A",
        confidence: 1,
        auto: false,
        status: "mapped",
      },
      {
        id: "2",
        object_type_id: "ot",
        source_column: "b",
        target_property: "",
        confidence: 0,
        auto: false,
        status: "skipped",
      },
    ]);
    expect(s.mapped).toBe(1);
    expect(s.total).toBe(2);
  });

  it("isNewPropertyId detects local ids", () => {
    expect(isNewPropertyId("new-123")).toBe(true);
    expect(isNewPropertyId("prop-abc")).toBe(false);
  });

  it("mapFieldToAddRequest uses API field names", () => {
    const body = mapFieldToAddRequest({
      ...emptyProperty(),
      name: "sku",
      type: "STRING",
      isPrimaryKey: true,
      isRequired: true,
    });
    expect(body.name).toBe("sku");
    expect(body.datatype).toBe("string");
    expect(body.is_primary_key).toBe(true);
    expect(body.nullable).toBe(false);
  });
});
