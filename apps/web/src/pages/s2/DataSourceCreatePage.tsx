import { useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../../api/client";
import {
  BpBanner,
  BpMetricGrid,
} from "./blueprintUi";
import { S2Chrome } from "./shared";

// ── Types ──────────────────────────────────────────────────────

export type ConnectorType = {
  id: string;
  name: string;
  category: "database" | "saas" | "api" | "file" | "stream";
  description: string;
  capabilities: string[];
};

export type ConnectionConfig = {
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
  apiKey: string;
  apiUrl: string;
  filePath: string;
};

export type TableSelection = {
  name: string;
  selected: boolean;
  rowCount: number;
};

export type TestResult = {
  status: "idle" | "testing" | "success" | "failed";
  message: string;
  latencyMs?: number;
  tables?: number;
};

export type WizardStep = 0 | 1 | 2 | 3 | 4;

// ── Step metadata ──────────────────────────────────────────────

export const WIZARD_STEPS = [
  { id: 0, label: "选择类型", short: "类型" },
  { id: 1, label: "配置连接", short: "连接" },
  { id: 2, label: "选择表", short: "选表" },
  { id: 3, label: "测试连接", short: "测试" },
  { id: 4, label: "完成", short: "完成" },
] as const;

export const CONNECTOR_TYPES: ConnectorType[] = [
  {
    id: "postgresql",
    name: "PostgreSQL",
    category: "database",
    description: "开源关系型数据库 · 支持批量同步与流式 CDC",
    capabilities: ["Batch syncs", "Streaming syncs", "Virtual tables"],
  },
  {
    id: "mysql",
    name: "MySQL",
    category: "database",
    description: "常用关系型数据库 · 适合订单/用户数据",
    capabilities: ["Batch syncs", "Virtual tables"],
  },
  {
    id: "snowflake",
    name: "Snowflake",
    category: "database",
    description: "云数据仓库 · 高性能分析查询",
    capabilities: ["Batch syncs", "Virtual tables"],
  },
  {
    id: "shopify",
    name: "Shopify",
    category: "saas",
    description: "电商平台 · 商品/订单/客户数据",
    capabilities: ["Batch syncs", "Webhooks"],
  },
  {
    id: "salesforce",
    name: "Salesforce",
    category: "saas",
    description: "CRM 系统 · 客户/商机/合同",
    capabilities: ["Batch syncs", "Streaming syncs"],
  },
  {
    id: "rest-api",
    name: "REST API",
    category: "api",
    description: "通用 REST API 拉取",
    capabilities: ["Batch syncs", "Webhooks"],
  },
  {
    id: "kafka",
    name: "Kafka",
    category: "stream",
    description: "事件流平台 · 实时数据管道",
    capabilities: ["Streaming syncs"],
  },
  {
    id: "file-csv",
    name: "CSV 文件",
    category: "file",
    description: "本地/上传 CSV 文件接入",
    capabilities: ["Batch syncs", "Media syncs"],
  },
  {
    id: "s3",
    name: "S3 对象存储",
    category: "file",
    description: "Amazon S3 · 数据湖/归档",
    capabilities: ["Batch syncs", "Media syncs", "File exports"],
  },
];

// ── Pure functions ─────────────────────────────────────────────

export function filterConnectorTypes(category: string, query: string): ConnectorType[] {
  const q = query.trim().toLowerCase();
  return CONNECTOR_TYPES.filter((t) => {
    if (category !== "all" && t.category !== category) return false;
    if (q && !t.name.toLowerCase().includes(q) && !t.description.toLowerCase().includes(q)) return false;
    return true;
  });
}

export function validateConnectionConfig(
  type: ConnectorType | null,
  config: ConnectionConfig,
): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!type) {
    errors.type = "请先选择连接器类型";
    return errors;
  }
  if (type.category === "database") {
    if (!config.host.trim()) errors.host = "主机不能为空";
    if (!config.port.trim()) errors.port = "端口不能为空";
    else if (!/^\d+$/.test(config.port)) errors.port = "端口必须为数字";
    else if (Number(config.port) < 1 || Number(config.port) > 65535) errors.port = "端口范围 1-65535";
    if (!config.database.trim()) errors.database = "数据库名不能为空";
    if (!config.username.trim()) errors.username = "用户名不能为空";
    if (!config.password.trim()) errors.password = "密码不能为空";
  } else if (type.category === "api") {
    if (!config.apiUrl.trim()) errors.apiUrl = "API URL 不能为空";
    else if (!config.apiUrl.startsWith("http")) errors.apiUrl = "URL 需以 http:// 或 https:// 开头";
    if (!config.apiKey.trim()) errors.apiKey = "API Key 不能为空";
  } else if (type.category === "file" && type.id === "file-csv") {
    if (!config.filePath.trim()) errors.filePath = "文件路径不能为空";
  }
  return errors;
}

export function hasConfigErrors(errors: Record<string, string>): boolean {
  return Object.keys(errors).length > 0;
}

export function selectedTableCount(tables: TableSelection[]): number {
  return tables.filter((t) => t.selected).length;
}

export function selectedTableRowCount(tables: TableSelection[]): number {
  return tables.filter((t) => t.selected).reduce((sum, t) => sum + t.rowCount, 0);
}

export function toggleTableSelection(tables: TableSelection[], name: string): TableSelection[] {
  return tables.map((t) => (t.name === name ? { ...t, selected: !t.selected } : t));
}

export function selectAllTables(tables: TableSelection[], select: boolean): TableSelection[] {
  return tables.map((t) => ({ ...t, selected: select }));
}

export function canAdvance(step: WizardStep, conditions: boolean[]): boolean {
  return conditions[step] === true;
}

export function stepProgress(step: WizardStep): number {
  return Math.round(((step + 1) / WIZARD_STEPS.length) * 100);
}

// ── Mock table list for Step 2 ─────────────────────────────────

const MOCK_TABLES: TableSelection[] = [
  { name: "orders", selected: true, rowCount: 125000 },
  { name: "order_items", selected: true, rowCount: 480000 },
  { name: "products", selected: false, rowCount: 8500 },
  { name: "customers", selected: true, rowCount: 32000 },
  { name: "inventory", selected: false, rowCount: 15600 },
  { name: "payments", selected: false, rowCount: 89000 },
  { name: "shipping", selected: false, rowCount: 45000 },
  { name: "reviews", selected: false, rowCount: 234000 },
];

// ── Page Component ─────────────────────────────────────────────

export function DataSourceCreatePage() {
  const [step, setStep] = useState<WizardStep>(0);
  const [selectedType, setSelectedType] = useState<ConnectorType | null>(null);
  const [typeCategory, setTypeCategory] = useState("all");
  const [typeQuery, setTypeQuery] = useState("");
  const [config, setConfig] = useState<ConnectionConfig>({
    host: "", port: "", database: "", username: "", password: "",
    apiKey: "", apiUrl: "", filePath: "",
  });
  const [configErrors, setConfigErrors] = useState<Record<string, string>>({});
  const [tables, setTables] = useState<TableSelection[]>(MOCK_TABLES);
  const [testResult, setTestResult] = useState<TestResult>({ status: "idle", message: "" });
  const [createdId, setCreatedId] = useState("");
  const [msg, setMsg] = useState("");

  const filteredTypes = filterConnectorTypes(typeCategory, typeQuery);
  const selectedCount = selectedTableCount(tables);
  const selectedRows = selectedTableRowCount(tables);

  function updateConfig<K extends keyof ConnectionConfig>(key: K, value: string) {
    setConfig({ ...config, [key]: value });
  }

  function handleNext() {
    if (step === 1) {
      const errs = validateConnectionConfig(selectedType, config);
      setConfigErrors(errs);
      if (hasConfigErrors(errs)) {
        setMsg("表单有错误 · 请修正");
        return;
      }
    }
    setMsg("");
    setStep(Math.min(4, step + 1) as WizardStep);
  }

  function handlePrev() {
    setMsg("");
    setStep(Math.max(0, step - 1) as WizardStep);
  }

  async function handleTest() {
    setTestResult({ status: "testing", message: "正在测试连接…" });
    try {
      const r = await apiPost<{ ok?: boolean; latencyMs?: number; tables?: number; error?: string }>(
        "/v1/sources/test",
        { type: selectedType?.id, ...config },
      );
      if (r.ok) {
        setTestResult({
          status: "success",
          message: `连接成功 · 发现 ${r.tables ?? "?"} 张表`,
          latencyMs: r.latencyMs,
          tables: r.tables,
        });
      } else {
        setTestResult({ status: "failed", message: r.error || "连接失败" });
      }
    } catch (e) {
      setTestResult({ status: "failed", message: String((e as Error).message || e) });
    }
  }

  async function handleCreate() {
    setMsg("");
    try {
      const r = await apiPost<{ id: string }>("/v1/sources", {
        type: selectedType?.id,
        config,
        tables: tables.filter((t) => t.selected).map((t) => t.name),
      });
      setCreatedId(r.id || `source-${Date.now().toString(36)}`);
      setStep(4);
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title="新建数据源向导" lede={`5 步创建连接器 · 当前进度 ${stepProgress(step)}%`}>
      {/* Progress indicator */}
      <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: "1.5rem" }}>
        {WIZARD_STEPS.map((s, i) => (
          <div key={s.id} style={{ display: "flex", alignItems: "center", flex: 1 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "0.25rem 0.5rem",
                borderRadius: 4,
                fontSize: "0.75rem",
                fontWeight: i === step ? 700 : 400,
                background: i < step ? "#d1fae5" : i === step ? "#dbeafe" : "#f1f5f9",
                color: i < step ? "#065f46" : i === step ? "#1e40af" : "#64748b",
              }}
            >
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  background: i < step ? "#10b981" : i === step ? "#3b82f6" : "#cbd5e1",
                  color: "#fff",
                  fontSize: "0.65rem",
                }}
              >
                {i < step ? "✓" : i + 1}
              </span>
              {s.short}
            </div>
            {i < WIZARD_STEPS.length - 1 && (
              <div style={{ flex: 1, height: 2, background: i < step ? "#10b981" : "#e2e8f0", margin: "0 4px" }} />
            )}
          </div>
        ))}
      </div>

      {msg && <p className="error">{msg}</p>}

      {/* Step 0: Select Type */}
      {step === 0 && (
        <div>
          <h2 className="aos-text" style={{ fontSize: "0.95rem" }}>选择连接器类型</h2>
          <div className="filter-bar" style={{ marginBottom: "0.75rem" }}>
            <input
              type="search"
              placeholder="搜索连接器…"
              value={typeQuery}
              onChange={(e) => setTypeQuery(e.target.value)}
              style={{ minWidth: 180 }}
            />
            <select value={typeCategory} onChange={(e) => setTypeCategory(e.target.value)}>
              <option value="all">全部分类</option>
              <option value="database">数据库</option>
              <option value="saas">SaaS</option>
              <option value="api">API</option>
              <option value="file">文件</option>
              <option value="stream">流式</option>
            </select>
          </div>
          <div className="bp-discover-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))" }}>
            {filteredTypes.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`bp-discover-card${selectedType?.id === t.id ? " is-selected" : ""}`}
                style={{
                  cursor: "pointer",
                  textAlign: "left",
                  border: selectedType?.id === t.id ? "2px solid #2563eb" : "1px solid #e2e8f0",
                  padding: "0.75rem",
                  borderRadius: 6,
                  background: "#fff",
                }}
                onClick={() => setSelectedType(t)}
              >
                <div className="bp-discover-head">
                  <span className="bp-discover-title">{t.name}</span>
                  <span className="bp-tag bp-tag-warn">{t.category}</span>
                </div>
                <p className="bp-discover-meta">{t.description}</p>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
                  {t.capabilities.map((c) => (
                    <span key={c} className="muted" style={{ fontSize: "0.65rem", background: "#f1f5f9", padding: "1px 4px", borderRadius: 3 }}>
                      {c}
                    </span>
                  ))}
                </div>
              </button>
            ))}
          </div>
          {filteredTypes.length === 0 && <p className="muted">无匹配类型</p>}
        </div>
      )}

      {/* Step 1: Configure Connection */}
      {step === 1 && selectedType && (
        <div className="bp-object-panel">
          <h2 className="aos-text" style={{ fontSize: "0.95rem" }}>
            配置 {selectedType.name} 连接
          </h2>
          {selectedType.category === "database" && (
            <>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4 }}>
                主机地址
                <input value={config.host} onChange={(e) => updateConfig("host", e.target.value)} placeholder="localhost" style={{ display: "block", width: "100%", marginTop: 4 }} />
                {configErrors.host && <span className="error" style={{ fontSize: "0.7rem" }}>{configErrors.host}</span>}
              </label>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4, marginTop: 8 }}>
                端口
                <input value={config.port} onChange={(e) => updateConfig("port", e.target.value)} placeholder="5432" style={{ display: "block", width: "100%", marginTop: 4 }} />
                {configErrors.port && <span className="error" style={{ fontSize: "0.7rem" }}>{configErrors.port}</span>}
              </label>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4, marginTop: 8 }}>
                数据库名
                <input value={config.database} onChange={(e) => updateConfig("database", e.target.value)} placeholder="mydb" style={{ display: "block", width: "100%", marginTop: 4 }} />
                {configErrors.database && <span className="error" style={{ fontSize: "0.7rem" }}>{configErrors.database}</span>}
              </label>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4, marginTop: 8 }}>
                用户名
                <input value={config.username} onChange={(e) => updateConfig("username", e.target.value)} style={{ display: "block", width: "100%", marginTop: 4 }} />
                {configErrors.username && <span className="error" style={{ fontSize: "0.7rem" }}>{configErrors.username}</span>}
              </label>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4, marginTop: 8 }}>
                密码
                <input type="password" value={config.password} onChange={(e) => updateConfig("password", e.target.value)} style={{ display: "block", width: "100%", marginTop: 4 }} />
                {configErrors.password && <span className="error" style={{ fontSize: "0.7rem" }}>{configErrors.password}</span>}
              </label>
            </>
          )}
          {selectedType.category === "api" && (
            <>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4 }}>
                API URL
                <input value={config.apiUrl} onChange={(e) => updateConfig("apiUrl", e.target.value)} placeholder="https://api.example.com/v1" style={{ display: "block", width: "100%", marginTop: 4 }} />
                {configErrors.apiUrl && <span className="error" style={{ fontSize: "0.7rem" }}>{configErrors.apiUrl}</span>}
              </label>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4, marginTop: 8 }}>
                API Key
                <input type="password" value={config.apiKey} onChange={(e) => updateConfig("apiKey", e.target.value)} style={{ display: "block", width: "100%", marginTop: 4 }} />
                {configErrors.apiKey && <span className="error" style={{ fontSize: "0.7rem" }}>{configErrors.apiKey}</span>}
              </label>
            </>
          )}
          {selectedType.category === "file" && selectedType.id === "file-csv" && (
            <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4 }}>
              文件路径
              <input value={config.filePath} onChange={(e) => updateConfig("filePath", e.target.value)} placeholder="/data/orders.csv" style={{ display: "block", width: "100%", marginTop: 4 }} />
              {configErrors.filePath && <span className="error" style={{ fontSize: "0.7rem" }}>{configErrors.filePath}</span>}
            </label>
          )}
          {selectedType.category === "saas" && (
            <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4 }}>
              API Key / OAuth Token
              <input type="password" value={config.apiKey} onChange={(e) => updateConfig("apiKey", e.target.value)} placeholder="粘贴授权凭据" style={{ display: "block", width: "100%", marginTop: 4 }} />
            </label>
          )}
          {selectedType.category === "stream" && (
            <>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4 }}>
                Broker 地址
                <input value={config.host} onChange={(e) => updateConfig("host", e.target.value)} placeholder="broker:9092" style={{ display: "block", width: "100%", marginTop: 4 }} />
              </label>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4, marginTop: 8 }}>
                Topic
                <input value={config.database} onChange={(e) => updateConfig("database", e.target.value)} placeholder="events-topic" style={{ display: "block", width: "100%", marginTop: 4 }} />
              </label>
            </>
          )}
        </div>
      )}

      {/* Step 2: Select Tables */}
      {step === 2 && (
        <div>
          <h2 className="aos-text" style={{ fontSize: "0.95rem" }}>选择要同步的表</h2>
          <BpMetricGrid
            items={[
              { label: "已选表", value: selectedCount, tone: "ok" },
              { label: "已选行数", value: selectedRows, tone: "muted" },
              { label: "全部表", value: tables.length, tone: "muted" },
            ]}
          />
          <div style={{ display: "flex", gap: 8, marginBottom: "0.5rem" }}>
            <button type="button" className="btn" onClick={() => setTables(selectAllTables(tables, true))}>
              全选
            </button>
            <button type="button" className="btn" onClick={() => setTables(selectAllTables(tables, false))}>
              全不选
            </button>
          </div>
          {tables.map((t) => (
            <label
              key={t.name}
              className="card"
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "0.5rem 0.75rem", marginBottom: 4, cursor: "pointer" }}
            >
              <input
                type="checkbox"
                checked={t.selected}
                onChange={() => setTables(toggleTableSelection(tables, t.name))}
              />
              <strong style={{ flex: 1 }}>{t.name}</strong>
              <span className="muted" style={{ fontSize: "0.75rem" }}>{t.rowCount.toLocaleString()} 行</span>
            </label>
          ))}
        </div>
      )}

      {/* Step 3: Test Connection */}
      {step === 3 && (
        <div>
          <h2 className="aos-text" style={{ fontSize: "0.95rem" }}>测试连接</h2>
          <p className="muted" style={{ fontSize: "0.8rem" }}>
            点击「测试连接」验证配置是否正确，发现可用表数量。
          </p>
          <button
            type="button"
            className="btn-primary"
            disabled={testResult.status === "testing"}
            onClick={() => void handleTest()}
          >
            {testResult.status === "testing" ? "测试中…" : "测试连接"}
          </button>
          {testResult.status === "success" && (
            <BpBanner tone="info">
              <strong className="aos-text">✓ {testResult.message}</strong>
              {testResult.latencyMs != null && <span className="muted"> · 延迟 {testResult.latencyMs} ms</span>}
            </BpBanner>
          )}
          {testResult.status === "failed" && (
            <p className="error">✕ {testResult.message}</p>
          )}
          {testResult.status === "success" && (
            <button type="button" className="btn-primary" style={{ marginTop: "0.75rem" }} onClick={() => void handleCreate()}>
              创建数据源
            </button>
          )}
        </div>
      )}

      {/* Step 4: Complete */}
      {step === 4 && (
        <div className="card" style={{ textAlign: "center", padding: "2rem" }}>
          <div style={{ fontSize: "3rem", marginBottom: "0.5rem" }}>✅</div>
          <h2 className="aos-text" style={{ fontSize: "1.1rem" }}>数据源创建成功</h2>
          <p className="muted">
            ID: <code className="mono">{createdId}</code>
          </p>
          <p className="muted" style={{ fontSize: "0.8rem" }}>
            已选择 {selectedCount} 张表 · 共 {selectedRows.toLocaleString()} 行
          </p>
          <div style={{ marginTop: "1rem", display: "flex", gap: 8, justifyContent: "center" }}>
            <Link to={`/data/sources/${encodeURIComponent(createdId)}`} className="btn-primary">
              查看数据源详情 →
            </Link>
            <Link to="/data" className="btn-nav">
              返回连接器列表
            </Link>
          </div>
        </div>
      )}

      {/* Navigation buttons */}
      {step < 4 && (
        <div style={{ display: "flex", gap: 8, marginTop: "1.5rem" }}>
          {step > 0 && (
            <button type="button" className="btn" onClick={() => handlePrev()}>
              ← 上一步
            </button>
          )}
          {step < 3 && (
            <button
              type="button"
              className="btn-primary"
              onClick={() => handleNext()}
              disabled={step === 0 && !selectedType}
            >
              下一步 →
            </button>
          )}
        </div>
      )}

      <BpBanner tone="info">
        新建向导对齐 <code>source-new.html</code> · 5 步流程 · 每步表单验证 ·{" "}
        <Link to="/data">连接器列表</Link> ·{" "}
        <Link to="/data/sync-config">同步配置</Link>
      </BpBanner>
    </S2Chrome>
  );
}
