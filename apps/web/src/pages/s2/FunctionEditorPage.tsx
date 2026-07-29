/**
 * Phase 6 · Function Editor Page
 * 函数列表 + 代码编辑器 + 参数表格 + 测试运行面板
 * 参考蓝图: ontology-function.html
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "../../api/client";
import { S2Chrome } from "./shared";
import { BpToolbar, BpBanner, BpTabs } from "./blueprintUi";

// ==================== 类型定义 ====================

export type FunctionMode = "SQL" | "PYTHON";
export type FunctionStatus = "draft" | "validated" | "published" | "error";
export type FunctionSourceMode = "loading" | "live" | "demo";

export interface FunctionParam {
  id: string;
  name: string;
  type: string;
  required: boolean;
  defaultValue: string;
  description: string;
}

export interface FunctionDef {
  id: string;
  name: string;
  description: string;
  mode: FunctionMode;
  status: FunctionStatus;
  code: string;
  params: FunctionParam[];
  outputType: string;
  className: string;
  repository: string;
  filePath: string;
  rid: string;
  version: string;
}

export interface TestRunResult {
  ok: boolean;
  output: string;
  duration: number;
  errorRows?: { param: string; message: string }[];
}

export interface ApiFunctionParam {
  name?: string;
  datatype?: string;
  type?: string;
  required?: boolean;
  default?: unknown;
  defaultValue?: string;
  description?: string;
}

export interface ApiFunctionRow {
  id?: string;
  name?: string;
  display_name?: string;
  description?: string;
  body?: string;
  code?: string;
  params?: ApiFunctionParam[];
  return_type?: string;
  status?: string;
  category?: string;
  version?: number | string;
}

// ==================== 常量 ====================

export const MOCK_FUNCTIONS: FunctionDef[] = [
  {
    id: "fn-getAgeBasedVitalThresholds",
    name: "getAgeBasedVitalThresholds",
    description: "Returns age-appropriate vital sign thresholds for a patient",
    mode: "PYTHON",
    status: "published",
    code: "@Function()\npublic getAgeBasedVitalThresholds(patient: Patient): VitalThresholds {\n  const age = this.helper.calculateAge(patient);\n  if (age === undefined) throw new Error('No DOB');\n  return this.thresholds[ageGroup];\n}",
    params: [
      { id: "p1", name: "patient", type: "Patient", required: true, defaultValue: "", description: "The patient object" },
    ],
    outputType: "VitalThresholds",
    className: "VitalThresholdsCalculator",
    repository: "Healthcare Monitoring Functions",
    filePath: "src/vitalThresholdsCalculator.ts",
    rid: "ri.function-registry.main.function.1686f24c",
    version: "1.1.2",
  },
  {
    id: "fn-calculateRiskScore",
    name: "calculateRiskScore",
    description: "Calculate risk score based on order properties",
    mode: "SQL",
    status: "validated",
    code: "SELECT\n  order_id,\n  CASE\n    WHEN amount > 500 THEN 'high'\n    WHEN amount > 100 THEN 'medium'\n    ELSE 'low'\n  END as risk_level\nFROM orders",
    params: [
      { id: "p1", name: "orderId", type: "string", required: true, defaultValue: "", description: "Order ID" },
      { id: "p2", name: "amount", type: "decimal", required: false, defaultValue: "0", description: "Order amount" },
    ],
    outputType: "RiskScore",
    className: "RiskCalculator",
    repository: "Risk Engine",
    filePath: "sql/risk_score.sql",
    rid: "ri.function-registry.main.function.2a8bc16d",
    version: "2.0.1",
  },
];

// ==================== 纯函数 ====================

export function emptyFunction(): FunctionDef {
  return {
    id: `fn-new-${Date.now()}`,
    name: "",
    description: "",
    mode: "SQL",
    status: "draft",
    code: "",
    params: [],
    outputType: "",
    className: "",
    repository: "",
    filePath: "",
    rid: "",
    version: "0.0.1",
  };
}

export function emptyParam(): FunctionParam {
  return {
    id: `p-${Date.now()}`,
    name: "",
    type: "string",
    required: false,
    defaultValue: "",
    description: "",
  };
}

export function validateFunction(fn: FunctionDef): string[] {
  const errors: string[] = [];
  if (!fn.name || !fn.name.trim()) errors.push("函数名不能为空");
  if (fn.name && !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(fn.name))
    errors.push("函数名只允许字母、数字、下划线，且不以数字开头");
  if (!fn.code || !fn.code.trim()) errors.push("代码不能为空");
  if (fn.mode === "SQL" && fn.code && !/select/i.test(fn.code))
    errors.push("SQL 函数必须包含 SELECT 语句");
  if (fn.mode === "PYTHON" && fn.code && !/def\s+\w+/.test(fn.code) && !/class\s+\w+/.test(fn.code) && !/\breturn\b/.test(fn.code) && !/@Function/.test(fn.code))
    errors.push("Python 函数必须包含 def、class、return 或 @Function");
  for (const p of fn.params) {
    if (!p.name || !p.name.trim()) {
      errors.push("参数名不能为空");
      break;
    }
    if (p.name && !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(p.name)) {
      errors.push(`参数名 "${p.name}" 格式无效`);
      break;
    }
  }
  if (!fn.outputType || !fn.outputType.trim())
    errors.push("输出类型不能为空");
  return errors;
}

export function isValidFunctionName(name: string): boolean {
  if (!name || !name.trim()) return false;
  return /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name);
}

export function modeLabel(mode: FunctionMode): string {
  return mode === "SQL" ? "SQL 查询" : "Python 脚本";
}

export function statusLabel(status: FunctionStatus): string {
  return { draft: "草稿", validated: "已验证", published: "已发布", error: "错误" }[status];
}

export function statusColor(status: FunctionStatus): string {
  return {
    draft: "var(--aos-amber)",
    validated: "var(--aos-accent)",
    published: "var(--aos-green)",
    error: "var(--aos-red)",
  }[status];
}

/** 模拟测试运行 */
export function simulateTestRun(fn: FunctionDef, payload: Record<string, unknown>): TestRunResult {
  const errors: { param: string; message: string }[] = [];
  for (const p of fn.params) {
    if (p.required && !(payload[p.name] != null)) {
      errors.push({ param: p.name, message: `缺少必需参数: ${p.name}` });
    }
  }
  if (errors.length > 0) {
    return { ok: false, output: "", duration: 0, errorRows: errors };
  }
  const start = Date.now();
  const output = JSON.stringify(
    { result: `${fn.outputType || "unknown"} result`, payload_summary: Object.keys(payload).length },
    null,
    2,
  );
  return { ok: true, output, duration: Date.now() - start };
}

/** 过滤函数列表 */
export function filterFunctions(
  fns: FunctionDef[],
  query: string,
  modeFilter: FunctionMode | "all",
): FunctionDef[] {
  let result = fns;
  if (modeFilter !== "all") {
    result = result.filter((f) => f.mode === modeFilter);
  }
  if (query.trim()) {
    const q = query.toLowerCase();
    result = result.filter(
      (f) =>
        f.name.toLowerCase().includes(q) ||
        f.description.toLowerCase().includes(q) ||
        f.outputType.toLowerCase().includes(q),
    );
  }
  return result;
}

/** 构建默认测试 payload */
export function defaultPayloadFromParams(params: FunctionParam[]): string {
  const obj: Record<string, string> = {};
  for (const p of params) {
    obj[p.name] = p.defaultValue || (p.type === "string" ? "sample" : "0");
  }
  return JSON.stringify(obj, null, 2);
}

/** API status → UI */
export function mapApiStatusToUi(status: string | undefined): FunctionStatus {
  switch ((status || "").toLowerCase()) {
    case "active":
    case "published":
      return "published";
    case "draft":
      return "draft";
    case "validated":
      return "validated";
    case "deprecated":
    case "error":
      return "error";
    default:
      return "draft";
  }
}

/** UI status → API */
export function mapUiStatusToApi(status: FunctionStatus): string {
  switch (status) {
    case "published":
      return "active";
    case "validated":
      return "active";
    case "error":
      return "deprecated";
    default:
      return "draft";
  }
}

/** 根据 body/code 猜测 mode */
export function inferFunctionMode(code: string): FunctionMode {
  if (/select\s+/i.test(code) && !/def\s+\w+/.test(code)) return "SQL";
  return "PYTHON";
}

export function mapApiParamToUi(p: ApiFunctionParam, index: number): FunctionParam {
  const def =
    p.defaultValue != null
      ? String(p.defaultValue)
      : p.default != null
        ? String(p.default)
        : "";
  return {
    id: `p-${index}-${p.name || "x"}`,
    name: p.name || "",
    type: p.datatype || p.type || "string",
    required: p.required !== false,
    defaultValue: def,
    description: p.description || "",
  };
}

export function mapApiFunctionToDef(row: ApiFunctionRow): FunctionDef {
  const code = row.body || row.code || "";
  const name = row.name || "";
  return {
    id: row.id || `fn-${name || Date.now()}`,
    name,
    description: row.description || row.display_name || "",
    mode: inferFunctionMode(code),
    status: mapApiStatusToUi(row.status),
    code,
    params: (row.params || []).map(mapApiParamToUi),
    outputType: row.return_type || "",
    className: row.display_name || name,
    repository: row.category || "ontology-functions",
    filePath: `functions/${name || "unnamed"}.py`,
    rid: row.id || "",
    version: String(row.version ?? "1"),
  };
}

export function mapDefToUpdateBody(fn: FunctionDef): Record<string, unknown> {
  return {
    display_name: fn.className || fn.name,
    description: fn.description,
    body: fn.code,
    return_type: fn.outputType,
    status: mapUiStatusToApi(fn.status),
    params: fn.params.map((p) => ({
      name: p.name,
      datatype: p.type || "string",
      required: p.required,
      default: p.defaultValue || null,
      description: p.description || "",
    })),
  };
}

/** 将 API 试跑响应归一为 TestRunResult */
export function mapApiTestToResult(raw: Record<string, unknown>): TestRunResult {
  const errorRows = Array.isArray(raw.errorRows)
    ? (raw.errorRows as { param: string; message: string }[])
    : raw.error
      ? [{ param: "_", message: String(raw.error) }]
      : undefined;
  const status = String(raw.status || "");
  const ok =
    typeof raw.ok === "boolean"
      ? raw.ok
      : status === "passed" || status === "ok";
  return {
    ok,
    output:
      raw.output == null
        ? ""
        : typeof raw.output === "string"
          ? raw.output
          : JSON.stringify(raw.output, null, 2),
    duration: typeof raw.duration === "number" ? raw.duration : 0,
    errorRows,
  };
}

// ==================== 组件 ====================

export function FunctionEditorPage() {
  const { functionId: routeFunctionId = "" } = useParams();
  const [functions, setFunctions] = useState<FunctionDef[]>(MOCK_FUNCTIONS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [modeFilter, setModeFilter] = useState<FunctionMode | "all">("all");
  const [sideTab, setSideTab] = useState<string>("overview");
  const [testPayload, setTestPayload] = useState("{}");
  const [testResult, setTestResult] = useState<TestRunResult | null>(null);
  const [testBusy, setTestBusy] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [sourceMode, setSourceMode] = useState<FunctionSourceMode>("loading");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setSourceMode("loading");
        const res = await apiGet<{ items?: ApiFunctionRow[] }>("/v1/ontology/functions");
        if (cancelled) return;
        const items = (res.items || []).map(mapApiFunctionToDef);
        if (items.length > 0) {
          setFunctions(items);
          const prefer =
            (routeFunctionId && items.find((f) => f.id === routeFunctionId || f.name === routeFunctionId)?.id) ||
            items[0].id;
          setSelectedId(prefer);
        } else {
          // 空列表仍为 live
          setFunctions([]);
          setSelectedId(null);
        }
        setSourceMode("live");
      } catch {
        if (cancelled) return;
        setFunctions(MOCK_FUNCTIONS);
        setSelectedId(MOCK_FUNCTIONS[0]?.id ?? null);
        setSourceMode("demo");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [routeFunctionId]);

  const filtered = useMemo(
    () => filterFunctions(functions, searchQuery, modeFilter),
    [functions, searchQuery, modeFilter],
  );

  const selected = functions.find((f) => f.id === selectedId) || filtered[0] || null;

  useEffect(() => {
    if (selected) {
      setTestPayload(defaultPayloadFromParams(selected.params));
      setTestResult(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.id]);

  function patchFunction(id: string, patch: Partial<FunctionDef>) {
    setFunctions((prev) =>
      prev.map((f) => (f.id === id ? { ...f, ...patch } : f)),
    );
  }

  function patchParam(fnId: string, paramId: string, patch: Partial<FunctionParam>) {
    setFunctions((prev) =>
      prev.map((f) =>
        f.id === fnId
          ? {
              ...f,
              params: f.params.map((p) =>
                p.id === paramId ? { ...p, ...patch } : p,
              ),
            }
          : f,
      ),
    );
  }

  function addParam(fnId: string) {
    setFunctions((prev) =>
      prev.map((f) =>
        f.id === fnId ? { ...f, params: [...f.params, emptyParam()] } : f,
      ),
    );
  }

  function removeParam(fnId: string, paramId: string) {
    setFunctions((prev) =>
      prev.map((f) =>
        f.id === fnId
          ? { ...f, params: f.params.filter((p) => p.id !== paramId) }
          : f,
      ),
    );
  }

  async function saveFunction(fn: FunctionDef) {
    setErr("");
    setMsg("");
    const errors = validateFunction(fn);
    if (errors.length > 0) {
      setErr(errors.join("；"));
      return;
    }
    if (sourceMode === "demo") {
      setMsg(`函数 ${fn.name} 已本地保存（演示路径）`);
      return;
    }
    setSaveBusy(true);
    try {
      const res = await apiPut<ApiFunctionRow>(
        `/v1/ontology/functions/${encodeURIComponent(fn.id)}`,
        mapDefToUpdateBody(fn),
      );
      const mapped = mapApiFunctionToDef(res);
      setFunctions((prev) =>
        prev.map((f) => (f.id === fn.id ? { ...mapped, mode: fn.mode } : f)),
      );
      setMsg(`函数 ${fn.name} 已保存`);
    } catch (e) {
      setSourceMode("demo");
      setMsg(`保存失败，已保留本地编辑（演示路径）：${String((e as Error).message || e)}`);
    } finally {
      setSaveBusy(false);
    }
  }

  async function runTest(fn: FunctionDef) {
    setErr("");
    setMsg("");
    setTestBusy(true);
    setTestResult(null);
    try {
      let payload: Record<string, unknown>;
      try {
        payload = JSON.parse(testPayload);
      } catch {
        throw new Error("测试 payload JSON 无效");
      }
      if (sourceMode === "live") {
        try {
          const res = await apiPost<Record<string, unknown>>(
            `/v1/ontology/functions/${encodeURIComponent(fn.id)}/test`,
            { payload },
          );
          const result = mapApiTestToResult(res);
          setTestResult(result);
          setMsg(result.ok ? "测试通过" : "测试失败");
          return;
        } catch {
          // fall through to simulate + demo
          setSourceMode("demo");
        }
      }
      const result = simulateTestRun(fn, payload);
      setTestResult(result);
      setMsg(result.ok ? "测试通过（演示路径）" : "测试失败（演示路径）");
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setTestBusy(false);
    }
  }

  return (
    <S2Chrome
      title="函数编辑器"
      lede="函数列表 · 参数表格 · 测试运行面板 · 保存"
    >
      <div className="ont-page w3-c3c4-page">
        <BpToolbar>
          <Link to="/ontology" className="btn-nav">
            ← 本体
          </Link>
          <Link to="/data/code-repos" className="btn-nav">
            在代码仓库中编辑 →
          </Link>
          {selected && (
            <button
              type="button"
              className="btn-primary"
              disabled={saveBusy}
              onClick={() => void saveFunction(selected)}
            >
              {saveBusy ? "保存中…" : "保存函数"}
            </button>
          )}
        </BpToolbar>

        {sourceMode === "demo" && (
          <div className="w3-c3c4-demo-banner" role="status">
            <span className="w3-c3c4-demo-badge">演示路径</span>
            <span className="w3-c3c4-demo-text">
              函数 API 不可用或试跑降级，当前使用本地 MOCK / simulate。
            </span>
          </div>
        )}
        {sourceMode === "live" && (
          <div className="w3-c3c4-live-banner" role="status">
            <span className="w3-c3c4-live-badge">Live</span>
            <span className="w3-c3c4-demo-text">
              已接 `/v1/ontology/functions` 列表 / 保存 / 试跑
            </span>
          </div>
        )}

        <BpBanner tone="info">
          参数表与试跑面板可编辑。代码主体建议在代码仓库中维护；本页保存写入 ontology functions API。
        </BpBanner>

        {msg && <p className="bp-prop-ok">{msg}</p>}
        {err && sideTab !== "test" && <p className="error">{err}</p>}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "240px 1fr",
            gap: 8,
            marginTop: 12,
          }}
        >
          <aside
            style={{
              border: "1px solid var(--aos-border)",
              borderRadius: 4,
              background: "var(--aos-surface)",
              padding: 8,
            }}
          >
            <input
              type="search"
              placeholder="搜索函数…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="aos-input"
              style={{ width: "100%", marginBottom: 6, fontSize: "0.75rem" }}
            />
            <select
              className="aos-input"
              value={modeFilter}
              onChange={(e) => setModeFilter(e.target.value as FunctionMode | "all")}
              style={{ width: "100%", marginBottom: 6, fontSize: "0.75rem" }}
            >
              <option value="all">全部模式</option>
              <option value="SQL">SQL</option>
              <option value="PYTHON">Python</option>
            </select>
            <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0" }}>
              {filtered.map((f) => (
                <li key={f.id}>
                  <button
                    type="button"
                    className="btn-nav"
                    style={{
                      width: "100%",
                      textAlign: "left",
                      fontSize: "0.75rem",
                      background:
                        selected?.id === f.id ? "var(--aos-accent)" : undefined,
                      color: selected?.id === f.id ? "var(--text-on-brand)" : undefined,
                    }}
                    onClick={() => setSelectedId(f.id)}
                  >
                    <span style={{ fontFamily: "monospace" }}>fx</span>{" "}
                    {f.name}
                    <span style={{ marginLeft: 4, opacity: 0.6 }}>
                      {modeLabel(f.mode)}
                    </span>
                  </button>
                </li>
              ))}
              {filtered.length === 0 && (
                <li className="muted" style={{ fontSize: "0.7rem" }}>无匹配函数</li>
              )}
            </ul>
          </aside>

          <main>
            {!selected && (
              <p className="muted">从左侧选择一个函数</p>
            )}
            {selected && (
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <span style={{ fontFamily: "monospace", fontWeight: 700, fontSize: "1rem" }}>
                    fx {selected.name}
                  </span>
                  <span
                    style={{
                      fontSize: "0.65rem",
                      padding: "2px 6px",
                      borderRadius: 3,
                      background: statusColor(selected.status),
                      color: "var(--text-on-brand)",
                    }}
                  >
                    {statusLabel(selected.status)}
                  </span>
                  <span className="muted" style={{ fontSize: "0.7rem" }}>
                    {selected.version}
                  </span>
                </div>

                <BpTabs
                  tabs={[
                    { id: "overview", label: "概览" },
                    { id: "config", label: "配置" },
                    { id: "code", label: "代码" },
                    { id: "test", label: "测试" },
                  ]}
                  active={sideTab}
                  onChange={setSideTab}
                />

                <div style={{ marginTop: 8 }}>
                  {sideTab === "overview" && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 12 }}>
                      <div>
                        <div className="bp-prop-label">名称</div>
                        <div className="bp-prop-value">{selected.name}</div>
                        <div className="bp-prop-label" style={{ marginTop: 8 }}>文档</div>
                        <div className="bp-prop-value">{selected.description}</div>
                      </div>
                      <div>
                        <div className="bp-prop-label">实现</div>
                        <div className="bp-prop-value">{selected.repository}</div>
                        <div className="bp-prop-label" style={{ marginTop: 8 }}>文件路径</div>
                        <div className="bp-prop-value" style={{ fontFamily: "monospace", fontSize: "0.7rem" }}>
                          {selected.filePath}
                        </div>
                        <div className="bp-prop-label" style={{ marginTop: 8 }}>RID</div>
                        <div className="bp-prop-value" style={{ fontFamily: "monospace", fontSize: "0.65rem" }}>
                          {selected.rid}
                        </div>
                      </div>
                    </div>
                  )}

                  {sideTab === "config" && (
                    <div>
                      <label className="ont-form-field">
                        <span>名称</span>
                        <input
                          className="aos-input"
                          value={selected.name}
                          onChange={(e) => patchFunction(selected.id, { name: e.target.value })}
                        />
                      </label>
                      <label className="ont-form-field">
                        <span>描述</span>
                        <textarea
                          className="aos-input"
                          rows={2}
                          value={selected.description}
                          onChange={(e) => patchFunction(selected.id, { description: e.target.value })}
                        />
                      </label>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                        <label className="ont-form-field">
                          <span>模式</span>
                          <select
                            className="aos-input"
                            value={selected.mode}
                            onChange={(e) => patchFunction(selected.id, { mode: e.target.value as FunctionMode })}
                          >
                            <option value="SQL">SQL</option>
                            <option value="PYTHON">Python</option>
                          </select>
                        </label>
                        <label className="ont-form-field">
                          <span>输出类型</span>
                          <input
                            className="aos-input"
                            value={selected.outputType}
                            onChange={(e) => patchFunction(selected.id, { outputType: e.target.value })}
                          />
                        </label>
                      </div>

                      <div style={{ marginTop: 12 }} className="w3-c3c4-param-table">
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                          <strong style={{ fontSize: "0.8rem" }}>输入参数</strong>
                          <button type="button" className="btn-nav" style={{ fontSize: "0.7rem" }} onClick={() => addParam(selected.id)}>
                            + 添加参数
                          </button>
                        </div>
                        <div className="bp-table-wrap">
                          <table className="data-table bp-table">
                            <thead>
                              <tr>
                                <th>名称</th>
                                <th style={{ width: 100 }}>类型</th>
                                <th style={{ width: 60 }}>必需</th>
                                <th>默认值</th>
                                <th>描述</th>
                                <th style={{ width: 30 }}></th>
                              </tr>
                            </thead>
                            <tbody>
                              {selected.params.map((p) => (
                                <tr key={p.id}>
                                  <td>
                                    <input
                                      className="aos-input"
                                      value={p.name}
                                      style={{ fontSize: "0.75rem" }}
                                      onChange={(e) => patchParam(selected.id, p.id, { name: e.target.value })}
                                    />
                                  </td>
                                  <td>
                                    <input
                                      className="aos-input"
                                      value={p.type}
                                      style={{ fontSize: "0.75rem" }}
                                      onChange={(e) => patchParam(selected.id, p.id, { type: e.target.value })}
                                    />
                                  </td>
                                  <td>
                                    <input
                                      type="checkbox"
                                      checked={p.required}
                                      onChange={(e) => patchParam(selected.id, p.id, { required: e.target.checked })}
                                    />
                                  </td>
                                  <td>
                                    <input
                                      className="aos-input"
                                      value={p.defaultValue}
                                      style={{ fontSize: "0.75rem" }}
                                      onChange={(e) => patchParam(selected.id, p.id, { defaultValue: e.target.value })}
                                    />
                                  </td>
                                  <td>
                                    <input
                                      className="aos-input"
                                      value={p.description}
                                      style={{ fontSize: "0.75rem" }}
                                      onChange={(e) => patchParam(selected.id, p.id, { description: e.target.value })}
                                    />
                                  </td>
                                  <td>
                                    <button
                                      type="button"
                                      className="btn-nav"
                                      style={{ fontSize: "0.6rem", padding: "2px 4px" }}
                                      onClick={() => removeParam(selected.id, p.id)}
                                    >
                                      ✕
                                    </button>
                                  </td>
                                </tr>
                              ))}
                              {selected.params.length === 0 && (
                                <tr>
                                  <td colSpan={6} className="muted" style={{ textAlign: "center", fontSize: "0.75rem" }}>
                                    无参数
                                  </td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}

                  {sideTab === "code" && (
                    <div>
                      <div style={{ marginBottom: 6, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span className="muted" style={{ fontSize: "0.7rem" }}>
                          {selected.filePath}
                        </span>
                        <span className="muted" style={{ fontSize: "0.7rem" }}>
                          {modeLabel(selected.mode)}
                        </span>
                      </div>
                      <textarea
                        className="aos-input w3-c3c4-code-editor"
                        value={selected.code}
                        rows={16}
                        onChange={(e) => patchFunction(selected.id, { code: e.target.value })}
                        style={{
                          fontFamily: "ui-monospace, monospace",
                          fontSize: "0.75rem",
                          width: "100%",
                        }}
                      />
                    </div>
                  )}

                  {sideTab === "test" && (
                    <div className="w3-c3c4-test-panel">
                      {err && <p className="error">{err}</p>}
                      <label className="ont-form-field">
                        <span>测试 payload (JSON)</span>
                        <textarea
                          className="aos-input"
                          rows={6}
                          value={testPayload}
                          onChange={(e) => setTestPayload(e.target.value)}
                          style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.75rem" }}
                        />
                      </label>
                      <button
                        type="button"
                        className="btn-primary"
                        disabled={testBusy}
                        onClick={() => void runTest(selected)}
                      >
                        {testBusy ? "运行中…" : "▶ 运行测试"}
                      </button>
                      {testResult && (
                        <div style={{ marginTop: 12 }}>
                          <div className="bp-prop-label">测试结果</div>
                          <div
                            className="bp-prop-value"
                            style={{
                              color: testResult.ok ? "var(--aos-green)" : "var(--aos-red)",
                            }}
                          >
                            {testResult.ok ? "✓ 通过" : "✗ 失败"}
                            {testResult.duration > 0 && (
                              <span className="muted" style={{ marginLeft: 8, fontSize: "0.7rem" }}>
                                ({testResult.duration}ms)
                              </span>
                            )}
                          </div>
                          {testResult.errorRows && testResult.errorRows.length > 0 && (
                            <ul style={{ color: "var(--aos-red)", fontSize: "0.75rem" }}>
                              {testResult.errorRows.map((e, i) => (
                                <li key={i}>{e.param}: {e.message}</li>
                              ))}
                            </ul>
                          )}
                          {testResult.output && (
                            <pre
                              className="card"
                              style={{
                                marginTop: 8,
                                padding: 8,
                                fontFamily: "ui-monospace, monospace",
                                fontSize: "0.7rem",
                                whiteSpace: "pre-wrap",
                              }}
                            >
                              {testResult.output}
                            </pre>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </S2Chrome>
  );
}
