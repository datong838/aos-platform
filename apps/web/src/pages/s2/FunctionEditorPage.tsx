/**
 * Phase 6 · Function Editor Page
 * 函数列表 + 代码编辑器 + 参数表格 + 测试运行面板
 * 参考蓝图: ontology-function.html
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiPost } from "../../api/client";
import { S2Chrome } from "./shared";
import { BpToolbar, BpBanner, BpTabs } from "./blueprintUi";

// ==================== 类型定义 ====================

export type FunctionMode = "SQL" | "PYTHON";
export type FunctionStatus = "draft" | "validated" | "published" | "error";

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
  if (fn.mode === "PYTHON" && fn.code && !/def\s+\w+/.test(fn.code) && !/class\s+\w+/.test(fn.code))
    errors.push("Python 函数必须包含 def 或 class 定义");
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
    draft: "var(--aos-warn, #d69e2e)",
    validated: "var(--aos-accent, #5b8def)",
    published: "var(--aos-ok, #38a169)",
    error: "var(--aos-bad, #e53e3e)",
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

// ==================== 组件 ====================

export function FunctionEditorPage() {
  const { functionId: _functionId = "" } = useParams();
  const [functions, setFunctions] = useState<FunctionDef[]>(MOCK_FUNCTIONS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [modeFilter, setModeFilter] = useState<FunctionMode | "all">("all");
  const [sideTab, setSideTab] = useState<string>("overview");
  const [testPayload, setTestPayload] = useState("{}");
  const [testResult, setTestResult] = useState<TestRunResult | null>(null);
  const [testBusy, setTestBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const filtered = useMemo(
    () => filterFunctions(functions, searchQuery, modeFilter),
    [functions, searchQuery, modeFilter],
  );

  const selected = functions.find((f) => f.id === selectedId) || filtered[0] || null;

  useEffect(() => {
    if (selected && testPayload === "{}") {
      setTestPayload(defaultPayloadFromParams(selected.params));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

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
      // 尝试调用后端；如果后端不可用，用模拟结果
      try {
        const res = await apiPost<TestRunResult>(
          `/v1/ontology/functions/${encodeURIComponent(fn.id)}/test`,
          { payload },
        );
        setTestResult(res);
        setMsg(res.ok ? "测试通过" : "测试失败");
      } catch {
        // 后端不可用，使用模拟
        const result = simulateTestRun(fn, payload);
        setTestResult(result);
        setMsg(result.ok ? "测试通过（模拟）" : "测试失败（模拟）");
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setTestBusy(false);
    }
  }

  return (
    <S2Chrome
      title="函数编辑器"
      lede="函数列表 · 代码编辑器 · 参数表格 · 测试运行面板"
    >
      <div className="ont-page">
        <BpToolbar>
          <Link to="/ontology" className="btn-nav">
            ← 本体
          </Link>
          <Link to="/data/code-repos" className="btn-nav">
            在代码仓库中编辑 →
          </Link>
        </BpToolbar>

        <BpBanner tone="info">
          本体管理器中的函数为只读视图。要修改函数代码，请在代码仓库应用中操作。
        </BpBanner>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "240px 1fr",
            gap: 8,
            marginTop: 12,
          }}
        >
          {/* 左: 函数列表 */}
          <aside
            style={{
              border: "1px solid var(--aos-border, #2a3540)",
              borderRadius: 4,
              background: "var(--aos-surface, #0f1419)",
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
                        selected?.id === f.id ? "var(--aos-accent, #5b8def)" : undefined,
                      color: selected?.id === f.id ? "#fff" : undefined,
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

          {/* 右: 主区 */}
          <main>
            {!selected && (
              <p className="muted">从左侧选择一个函数</p>
            )}
            {selected && (
              <div>
                {/* 标题行 */}
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
                      color: "#fff",
                    }}
                  >
                    {statusLabel(selected.status)}
                  </span>
                  <span className="muted" style={{ fontSize: "0.7rem" }}>
                    {selected.version}
                  </span>
                </div>

                {/* Tab */}
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

                      {/* 参数表 */}
                      <div style={{ marginTop: 12 }}>
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
                      <pre
                        className="card"
                        style={{
                          padding: 12,
                          fontFamily: "ui-monospace, monospace",
                          fontSize: "0.75rem",
                          whiteSpace: "pre-wrap",
                          overflowX: "auto",
                          maxHeight: 400,
                        }}
                      >
                        {selected.code}
                      </pre>
                    </div>
                  )}

                  {sideTab === "test" && (
                    <div>
                      {err && <p className="error">{err}</p>}
                      {msg && <p className="bp-prop-ok">{msg}</p>}
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
                              color: testResult.ok ? "var(--aos-ok, #38a169)" : "var(--aos-bad, #e53e3e)",
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
                            <ul style={{ color: "var(--aos-bad, #e53e3e)", fontSize: "0.75rem" }}>
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
