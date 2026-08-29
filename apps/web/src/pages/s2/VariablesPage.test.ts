import { describe, expect, it } from "vitest";
import {
  classifyVarType,
  countVariablesByScope,
  filterVariablesByScope,
  formatInitialValue,
  mapApiVariable,
  normalizeScope,
  normalizeVarType,
  parseInitialValueInput,
  toApiVarType,
  VAR_TYPE_GROUP_LABELS,
} from "./VariablesPage";

describe("VariablesPage · classifyVarType", () => {
  it("映射 5 大分组", () => {
    expect(classifyVarType("ObjectSet")).toBe("data");
    expect(classifyVarType("Object")).toBe("data");
    expect(classifyVarType("String")).toBe("scalar");
    expect(classifyVarType("Number")).toBe("scalar");
    expect(classifyVarType("Boolean")).toBe("flag");
    expect(classifyVarType("DateRange")).toBe("time");
    expect(classifyVarType("Array")).toBe("list");
  });

  it("分组标签齐全", () => {
    for (const key of Object.keys(VAR_TYPE_GROUP_LABELS) as Array<keyof typeof VAR_TYPE_GROUP_LABELS>) {
      expect(VAR_TYPE_GROUP_LABELS[key].length).toBeGreaterThan(0);
    }
  });
});

describe("VariablesPage · normalizeVarType / toApiVarType", () => {
  it("API → UI 类型归一化", () => {
    expect(normalizeVarType("string")).toBe("String");
    expect(normalizeVarType("NUMBER")).toBe("Number");
    expect(normalizeVarType("bool")).toBe("Boolean");
    expect(normalizeVarType("object_set")).toBe("ObjectSet");
    expect(normalizeVarType("list")).toBe("Array");
    expect(normalizeVarType(undefined)).toBe("String");
  });

  it("UI → API 往返一致（常见类型）", () => {
    for (const t of ["String", "Number", "Boolean", "Object", "Array", "ObjectSet", "DateRange"] as const) {
      expect(normalizeVarType(toApiVarType(t))).toBe(t);
    }
  });
});

describe("VariablesPage · normalizeScope", () => {
  it("识别 page/app/global 与中文别名", () => {
    expect(normalizeScope("page")).toBe("page");
    expect(normalizeScope("app")).toBe("app");
    expect(normalizeScope("global")).toBe("global");
    expect(normalizeScope("应用级")).toBe("app");
    expect(normalizeScope("全局")).toBe("global");
    expect(normalizeScope("字符串")).toBe("page");
    expect(normalizeScope(null)).toBe("page");
  });
});

describe("VariablesPage · initialValue 编解码", () => {
  it("formatInitialValue", () => {
    expect(formatInitialValue(null)).toBe("");
    expect(formatInitialValue("hi")).toBe("hi");
    expect(formatInitialValue({ a: 1 })).toBe('{"a":1}');
    expect(formatInitialValue([1, 2])).toBe("[1,2]");
  });

  it("parseInitialValueInput 按类型解析", () => {
    expect(parseInitialValueInput("42", "Number")).toBe(42);
    expect(parseInitialValueInput("true", "Boolean")).toBe(true);
    expect(parseInitialValueInput("[1,2]", "Array")).toEqual([1, 2]);
    expect(parseInitialValueInput("hello", "String")).toBe("hello");
  });
});

describe("VariablesPage · mapApiVariable / filter / stats", () => {
  const variables = [
    mapApiVariable({ id: "v-page", name: "query", varType: "string", group: "page", initialValue: "" }),
    mapApiVariable({ id: "v-app", name: "selection", varType: "object", group: "app", initialValue: null }),
    mapApiVariable({ id: "v-global", name: "tenant", varType: "string", group: "global", initialValue: "current" }),
  ];

  it("mapApiVariable 映射字段", () => {
    const v = mapApiVariable({
      id: "v1",
      name: "selectedStatus",
      varType: "string",
      group: "page",
      initialValue: "all",
      description: "状态",
      bindings: ["状态筛选器"],
    });
    expect(v.id).toBe("v1");
    expect(v.name).toBe("selectedStatus");
    expect(v.type).toBe("String");
    expect(v.scope).toBe("page");
    expect(v.initialValue).toBe("all");
    expect(v.bindings).toEqual(["状态筛选器"]);
    expect(v.description).toBe("状态");
  });

  it("缺失服务端标识时不生成随机可写 ID", () => {
    const v = mapApiVariable({ name: "选中状态", description: "当前选择" });
    expect(v.id).toBe("");
    expect(v.bindings).toEqual([]);
    expect(v.readOnlyReason).toBe("标识缺失（只读）");
  });

  it("统计函数覆盖三作用域", () => {
    const stats = countVariablesByScope(variables);
    expect(stats.total).toBe(variables.length);
    expect(stats.page).toBeGreaterThan(0);
    expect(stats.app).toBeGreaterThan(0);
    expect(stats.global).toBeGreaterThan(0);
  });

  it("filterVariablesByScope", () => {
    expect(filterVariablesByScope(variables, "all")).toHaveLength(variables.length);
    expect(filterVariablesByScope(variables, "global").every((v) => v.scope === "global")).toBe(true);
  });
});
