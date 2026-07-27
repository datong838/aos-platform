import { describe, expect, it } from "vitest";
import {
  emptyFunction,
  emptyParam,
  validateFunction,
  isValidFunctionName,
  modeLabel,
  statusLabel,
  statusColor,
  simulateTestRun,
  filterFunctions,
  defaultPayloadFromParams,
  MOCK_FUNCTIONS,
  type FunctionDef,
} from "./FunctionEditorPage";

describe("FunctionEditorPage · emptyFunction", () => {
  it("creates a function with default values", () => {
    const fn = emptyFunction();
    expect(fn.name).toBe("");
    expect(fn.mode).toBe("SQL");
    expect(fn.status).toBe("draft");
    expect(fn.params).toEqual([]);
  });

  it("creates with id prefix fn-new-", () => {
    const fn = emptyFunction();
    expect(fn.id).toContain("fn-new-");
  });
});

describe("FunctionEditorPage · emptyParam", () => {
  it("creates a param with default values", () => {
    const p = emptyParam();
    expect(p.name).toBe("");
    expect(p.type).toBe("string");
    expect(p.required).toBe(false);
  });
});

describe("FunctionEditorPage · isValidFunctionName", () => {
  it("accepts valid function names", () => {
    expect(isValidFunctionName("calculateRisk")).toBe(true);
    expect(isValidFunctionName("get_age")).toBe(true);
    expect(isValidFunctionName("fn123")).toBe(true);
  });

  it("rejects invalid function names", () => {
    expect(isValidFunctionName("")).toBe(false);
    expect(isValidFunctionName("123fn")).toBe(false);
    expect(isValidFunctionName("has space")).toBe(false);
    expect(isValidFunctionName("has-dash")).toBe(false);
  });
});

describe("FunctionEditorPage · validateFunction", () => {
  it("passes for valid SQL function", () => {
    const fn: FunctionDef = {
      ...emptyFunction(),
      id: "fn-test",
      name: "testFunction",
      mode: "SQL",
      code: "SELECT 1",
      params: [],
      outputType: "Integer",
    };
    expect(validateFunction(fn)).toHaveLength(0);
  });

  it("catches empty name", () => {
    const fn: FunctionDef = { ...emptyFunction(), id: "fn-test", code: "SELECT 1", outputType: "X" };
    expect(validateFunction(fn)).toContain("函数名不能为空");
  });

  it("catches empty code", () => {
    const fn: FunctionDef = {
      ...emptyFunction(),
      id: "fn-test",
      name: "testFn",
      code: "",
      outputType: "X",
    };
    expect(validateFunction(fn)).toContain("代码不能为空");
  });

  it("catches invalid function name", () => {
    const fn: FunctionDef = {
      ...emptyFunction(),
      id: "fn-test",
      name: "123bad",
      code: "SELECT 1",
      outputType: "X",
    };
    expect(validateFunction(fn)).toContain("函数名只允许字母、数字、下划线，且不以数字开头");
  });

  it("catches SQL function without SELECT", () => {
    const fn: FunctionDef = {
      ...emptyFunction(),
      id: "fn-test",
      name: "testFn",
      mode: "SQL",
      code: "DELETE FROM table",
      outputType: "X",
    };
    expect(validateFunction(fn)).toContain("SQL 函数必须包含 SELECT 语句");
  });

  it("catches Python function without def/class", () => {
    const fn: FunctionDef = {
      ...emptyFunction(),
      id: "fn-test",
      name: "testFn",
      mode: "PYTHON",
      code: "print('hello')",
      outputType: "X",
    };
    expect(validateFunction(fn)).toContain("Python 函数必须包含 def 或 class 定义");
  });

  it("catches missing outputType", () => {
    const fn: FunctionDef = {
      ...emptyFunction(),
      id: "fn-test",
      name: "testFn",
      code: "SELECT 1",
      outputType: "",
    };
    expect(validateFunction(fn)).toContain("输出类型不能为空");
  });
});

describe("FunctionEditorPage · simulateTestRun", () => {
  it("returns ok=true when all required params provided", () => {
    const fn: FunctionDef = {
      ...emptyFunction(),
      id: "fn-test",
      name: "testFn",
      code: "SELECT 1",
      params: [
        { id: "p1", name: "orderId", type: "string", required: true, defaultValue: "", description: "" },
      ],
    };
    const result = simulateTestRun(fn, { orderId: "ORD-001" });
    expect(result.ok).toBe(true);
    expect(result.output).toBeTruthy();
  });

  it("returns ok=false when required param missing", () => {
    const fn: FunctionDef = {
      ...emptyFunction(),
      id: "fn-test",
      name: "testFn",
      code: "SELECT 1",
      params: [
        { id: "p1", name: "orderId", type: "string", required: true, defaultValue: "", description: "" },
      ],
    };
    const result = simulateTestRun(fn, {});
    expect(result.ok).toBe(false);
    expect(result.errorRows).toBeDefined();
    expect(result.errorRows!.length).toBeGreaterThan(0);
    expect(result.errorRows![0].param).toBe("orderId");
  });

  it("passes when optional params are missing", () => {
    const fn: FunctionDef = {
      ...emptyFunction(),
      id: "fn-test",
      name: "testFn",
      code: "SELECT 1",
      params: [
        { id: "p1", name: "optional", type: "string", required: false, defaultValue: "default", description: "" },
      ],
    };
    const result = simulateTestRun(fn, {});
    expect(result.ok).toBe(true);
  });

  it("handles null payload values", () => {
    const fn: FunctionDef = {
      ...emptyFunction(),
      id: "fn-test",
      name: "testFn",
      code: "SELECT 1",
      params: [
        { id: "p1", name: "req", type: "string", required: true, defaultValue: "", description: "" },
      ],
    };
    const result = simulateTestRun(fn, { req: null });
    expect(result.ok).toBe(false);
  });
});

describe("FunctionEditorPage · filterFunctions", () => {
  it("filters by search text", () => {
    const filtered = filterFunctions(MOCK_FUNCTIONS, "risk", "all");
    expect(filtered.length).toBeGreaterThanOrEqual(1);
  });

  it("filters by mode", () => {
    const sql = filterFunctions(MOCK_FUNCTIONS, "", "SQL");
    expect(sql.every((f) => f.mode === "SQL")).toBe(true);
  });

  it("returns all when no filters", () => {
    expect(filterFunctions(MOCK_FUNCTIONS, "", "all")).toHaveLength(MOCK_FUNCTIONS.length);
  });
});

describe("FunctionEditorPage · defaultPayloadFromParams", () => {
  it("builds payload with default values", () => {
    const params = [
      { id: "p1", name: "id", type: "string", required: true, defaultValue: "", description: "" },
      { id: "p2", name: "amount", type: "decimal", required: false, defaultValue: "100", description: "" },
    ];
    const payload = defaultPayloadFromParams(params);
    const parsed = JSON.parse(payload);
    expect(parsed.id).toBe("sample");
    expect(parsed.amount).toBe("100");
  });

  it("uses type-based defaults", () => {
    const params = [
      { id: "p1", name: "count", type: "integer", required: false, defaultValue: "", description: "" },
    ];
    const payload = defaultPayloadFromParams(params);
    const parsed = JSON.parse(payload);
    expect(parsed.count).toBe("0");
  });
});

describe("FunctionEditorPage · label helpers", () => {
  it("modeLabel returns correct labels", () => {
    expect(modeLabel("SQL")).toBe("SQL 查询");
    expect(modeLabel("PYTHON")).toBe("Python 脚本");
  });

  it("statusLabel returns correct labels", () => {
    expect(statusLabel("draft")).toBe("草稿");
    expect(statusLabel("published")).toBe("已发布");
    expect(statusLabel("error")).toBe("错误");
  });

  it("statusColor returns CSS values", () => {
    expect(statusColor("draft")).toBeTruthy();
    expect(statusColor("error")).toBeTruthy();
  });
});

describe("FunctionEditorPage · MOCK_FUNCTIONS", () => {
  it("has at least 2 mock functions", () => {
    expect(MOCK_FUNCTIONS.length).toBeGreaterThanOrEqual(2);
  });

  it("all mock functions have valid names", () => {
    for (const fn of MOCK_FUNCTIONS) {
      expect(fn.name).toBeTruthy();
      expect(fn.code).toBeTruthy();
    }
  });
});
