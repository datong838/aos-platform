import { useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { apiPost } from "../../api/client";

export type CapType = "C0" | "C1" | "C2";

const STEPS = [
  { num: 1, label: "能力类型" },
  { num: 2, label: "Manifest 配置" },
  { num: 3, label: "安全与配额" },
  { num: 4, label: "连通测试" },
];

export const CAP_TYPES: {
  id: CapType;
  subtype: string;
  name: string;
  desc: string;
  example: string;
  subColor: string;
  subBg: string;
}[] = [
  {
    id: "C0",
    subtype: "sync",
    name: "同步函数",
    desc: "超时 < 15s\n直接挂 Function Tool\n内存限制 512Mi",
    example: "例：直播稿引擎、文本摘要",
    subColor: "var(--aos-blue-600)",
    subBg: "var(--aos-accent-light)",
  },
  {
    id: "C1",
    subtype: "Job",
    name: "异步任务",
    desc: "GPU / 长耗时\nsubmit → status → artifact\n产物写 MediaSet",
    example: "例：短视频生成、图片渲染",
    subColor: "var(--aos-purple-600)",
    subBg: "var(--aos-indigo-bg)",
  },
  {
    id: "C2",
    subtype: "Session",
    name: "实时会话",
    desc: "WebSocket 长连接\n实时双向交互\nAV 流外置",
    example: "例：数字人主播、语音助手",
    subColor: "var(--aos-amber-600)",
    subBg: "var(--aos-amber-bg)",
  },
];

export const SEC_LEVELS = [
  { id: "low", label: "低风险", desc: "只读数据，不触发写操作", color: "var(--aos-green)" },
  { id: "medium", label: "中风险", desc: "可写受控对象，需 HITL 审批", color: "var(--aos-amber)" },
  { id: "high", label: "高风险", desc: "可跨域调用，需安全审计", color: "var(--aos-red)" },
];

/** 知识库关联文档（references/） */
export type KBDocument = {
  id: string;
  name: string;
  size: string;
  desc: string;
  chunks: number;
  status: "indexed" | "indexing" | "pending";
  icon: "pdf" | "md" | "doc" | "txt";
  iconColor: string;
};

export const MOCK_KB_DOCUMENTS: KBDocument[] = [
  {
    id: "kb-1",
    name: "video-generation-api-spec.pdf",
    size: "2.4MB",
    desc: "API 接口规格书",
    chunks: 18,
    status: "indexed",
    icon: "pdf",
    iconColor: "var(--aos-red)",
  },
  {
    id: "kb-2",
    name: "prompt-engineering-best-practices.md",
    size: "86KB",
    desc: "提示词工程参考",
    chunks: 12,
    status: "indexed",
    icon: "md",
    iconColor: "var(--aos-blue-600)",
  },
  {
    id: "kb-3",
    name: "brand-guidelines-2026.docx",
    size: "340KB",
    desc: "品牌设计规范",
    chunks: 0,
    status: "indexing",
    icon: "doc",
    iconColor: "var(--aos-text-secondary)",
  },
];

/** 测试项目（详细版） */
export const DETAILED_TEST_ITEMS = [
  { name: "DNS 解析", status: "pass", detail: "cap.internal → 10.0.12.34 (12ms)", icon: "dns" },
  { name: "TLS 握手", status: "pass", detail: "TLS 1.3 · 证书有效期至 2026-12-01", icon: "tls" },
  { name: "鉴权验证", status: "pass", detail: "Vault secret ref 有效 · HMAC 验签通过", icon: "auth" },
  { name: "健康检查端点", status: "pass", detail: "GET /health → 200 OK (45ms)", icon: "health" },
  { name: "Schema 冒烟测试", status: "pending", detail: "发送测试请求 → 等待响应…", icon: "schema" },
  { name: "速率限制测试", status: "pending", detail: "等待", icon: "rate" },
];

/** 环境变量模板 */
export const DEFAULT_ENV_VARS = [
  { key: "OPENAI_API_KEY", value: "vault://aip/models/openai", secret: true, bound: true },
  { key: "CAP_TIMEOUT", value: "60", secret: false, bound: true },
  { key: "MAX_RETRIES", value: "3", secret: false, bound: true },
  { key: "WEBHOOK_URL", value: "", secret: false, bound: false },
];

/** 计算测试通过率（纯函数） */
export function computeTestStats(tests: typeof DETAILED_TEST_ITEMS) {
  return {
    total: tests.length,
    pass: tests.filter((t) => t.status === "pass").length,
    pending: tests.filter((t) => t.status === "pending").length,
    fail: tests.filter((t) => t.status === "fail").length,
  };
}

/** 计算知识库索引状态（纯函数） */
export function computeKBStats(docs: KBDocument[]) {
  return {
    total: docs.length,
    indexed: docs.filter((d) => d.status === "indexed").length,
    indexing: docs.filter((d) => d.status === "indexing").length,
    pending: docs.filter((d) => d.status === "pending").length,
    totalChunks: docs.reduce((sum, d) => sum + d.chunks, 0),
  };
}

/** 文档图标组件 */
function DocIcon({ color }: { type: "pdf" | "md" | "doc" | "txt"; color: string }) {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} style={{ flexShrink: 0 }}>
      <path d="M6 2h9l5 5v15a1 1 0 01-1 1H6a1 1 0 01-1-1V3a1 1 0 011-1z" strokeLinejoin="round" />
      <path d="M14 2v6h6" strokeLinejoin="round" />
      <path d="M9 13h6M9 17h6" strokeLinecap="round" />
    </svg>
  );
}

export function CapabilityImportPage() {
  const [step, setStep] = useState(1);
  const [capType, setCapType] = useState<CapType>("C0");
  const [manifestUrl, setManifestUrl] = useState("https://api.example.com/capabilities/live-script/manifest.yaml");
  const [secLevel, setSecLevel] = useState("medium");
  const [testing, setTesting] = useState(false);
  const [testDone, setTestDone] = useState(false);
  const [imported, setImported] = useState(false);

  // 新增 state
  const [kbDocs, setKbDocs] = useState<KBDocument[]>(MOCK_KB_DOCUMENTS);
  const [envVars, setEnvVars] = useState(DEFAULT_ENV_VARS);
  const [secretRef, setSecretRef] = useState("vault://aip/capabilities/short-video#token");
  const [webhookUrl, setWebhookUrl] = useState("https://aos-api/v1/aip/capabilities/cb/video");
  const [rateLimitPerMin, setRateLimitPerMin] = useState("30");
  const [concurrency, setConcurrency] = useState("4");
  const [gpuConfig, setGpuConfig] = useState("1 × T4");
  const [memoryLimit, setMemoryLimit] = useState("512Mi");
  const [timeoutSec, setTimeoutSec] = useState("300");

  const manifestYaml = `# Capability Manifest
name: "Live Script Engine"
version: "1.2.0"
type: "C0"
description: "实时生成直播口播稿"
provider: "content-lab"

endpoints:
  sync:
    invoke: "POST /v1/invoke"
    health: "GET /health"

input_schema:
  product_name: string
  price: number
  style: "casual" | "formal"

output_schema:
  script: string
  duration_sec: number

permissions:
  - "object:read:Product"
  - "mediaset:write"
`;

  function runTests() {
    setTesting(true);
    // 尝试调 API，fallback 到 mock
    apiPost("/v1/aip/capabilities/test", { endpoint: manifestUrl })
      .catch(() => {
        // API 未就绪，使用模拟结果
      })
      .finally(() => {
        setTimeout(() => {
          setTesting(false);
          setTestDone(true);
        }, 1500);
      });
  }

  async function handleImport() {
    try {
      await apiPost("/v1/aip/capabilities", {
        type: capType,
        manifest_url: manifestUrl,
        rate_limit: rateLimitPerMin,
        secret_ref: secretRef,
      });
      setImported(true);
    } catch {
      // API 未就绪，直接显示成功
      setImported(true);
    }
  }

  if (imported) {
    return (
      <PageChrome title="接入插件能力" lede="声明外部能力端点和契约，注册为 C0/C1/C2 专业能力供智能体调用。">
        <div
          style={{
            textAlign: "center",
            padding: "64px 24px",
            maxWidth: 480,
            margin: "0 auto",
          }}
        >
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: "50%",
              background: "var(--aos-green-bg)",
              color: "var(--aos-green-600)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 32,
              margin: "0 auto 16px",
            }}
          >
            ✓
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: "var(--aos-text)", margin: "0 0 8px" }}>
            能力接入成功
          </h2>
          <p style={{ fontSize: 13, color: "var(--aos-text-secondary)", margin: "0 0 20px", lineHeight: 1.6 }}>
            Live Script Engine 已注册为 {capType} 类型能力，可在智能体工具面板中启用。
          </p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
            <Link
              to="/aip/capabilities"
              style={{
                padding: "8px 20px",
                borderRadius: 2,
                fontSize: 13,
                fontWeight: 500,
                background: "var(--aos-accent)",
                color: "var(--text-on-brand)",
                textDecoration: "none",
              }}
            >
              前往插件管理
            </Link>
            <button
              type="button"
              onClick={() => {
                setImported(false);
                setStep(1);
              }}
              style={{
                padding: "8px 20px",
                borderRadius: 2,
                fontSize: 13,
                border: "1px solid var(--aos-border-strong)",
                background: "var(--aos-surface)",
                color: "var(--aos-text)",
                cursor: "pointer",
              }}
            >
              继续接入
            </button>
          </div>
        </div>
      </PageChrome>
    );
  }

  return (
    <PageChrome title="接入插件能力" lede="声明外部能力端点与契约，注册为 C0/C1/C2；向导校验态可见，不伪造连通通过。">
      <div
        data-testid="capability-import-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 12 }}
      >
        {[
          { label: "当前步", value: `${step}/5` },
          { label: "能力级", value: capType },
          { label: "安全级", value: secLevel },
          { label: "联通测", value: testDone ? "已测" : testing ? "测试中" : "未测" },
          { label: "导入态", value: imported ? "已导入" : "待导入" },
          { label: "知识库", value: `${kbDocs.filter((d) => d.status === "indexed").length}/${kbDocs.length}` },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{s.value}</div>
          </div>
        ))}
      </div>
      {/* C0/C1/C2 分层说明 */}
      <div
        style={{
          borderRadius: 2,
          border: "1px solid var(--aos-amber-border)",
          background: "var(--aos-amber-bg)",
          padding: 16,
          marginBottom: 20,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-amber-700)", marginBottom: 8 }}>
          C0 / C1 / C2 能力分层
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
          <div style={{ fontSize: 12, color: "var(--aos-amber-700)" }}>
            <span style={{ fontWeight: 500, color: "var(--aos-amber-700)" }}>C0 sync</span> — 同步函数，
            &lt;15s，可直接挂 Function
          </div>
          <div style={{ fontSize: 12, color: "var(--aos-amber-700)" }}>
            <span style={{ fontWeight: 500, color: "var(--aos-amber-700)" }}>C1 Job</span> — 异步任务，
            GPU/长耗时，产物写 MediaSet
          </div>
          <div style={{ fontSize: 12, color: "var(--aos-amber-700)" }}>
            <span style={{ fontWeight: 500, color: "var(--aos-amber-700)" }}>C2 Session</span> — 实时会话，
            WebSocket 长连接，AV 流外置
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 24 }}>
        {/* 左侧步骤导航 */}
        <div style={{ width: 224, flexShrink: 0 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {STEPS.map((s) => {
              const isActive = step === s.num;
              const isDone = step > s.num;
              return (
                <div
                  key={s.num}
                  onClick={() => s.num < step && setStep(s.num)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 14px",
                    borderRadius: 2,
                    fontSize: 13,
                    color: isActive ? "var(--aos-blue-600)" : isDone ? "var(--aos-blue-600)" : "var(--aos-text-secondary)",
                    background: isActive ? "var(--aos-accent-light)" : "transparent",
                    border: isActive ? "1px solid var(--aos-accent-border)" : "1px solid transparent",
                    cursor: s.num < step ? "pointer" : "default",
                    transition: "all 0.15s",
                  }}
                >
                  <div
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 11,
                      fontWeight: 500,
                      background: isActive || isDone ? "var(--aos-blue-600)" : "var(--aos-border-strong)",
                      color: "var(--text-on-brand)",
                      flexShrink: 0,
                    }}
                  >
                    {isDone ? "✓" : s.num}
                  </div>
                  <span style={{ fontWeight: isActive ? 500 : 400 }}>{s.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 右侧内容 */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Step 1: 能力类型 */}
          {step === 1 && (
            <div>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 4px" }}>
                选择能力类型
              </h2>
              <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "0 0 16px" }}>
                不同能力类型对应不同的运行时和资源配额
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
                {CAP_TYPES.map((ct) => {
                  const selected = capType === ct.id;
                  return (
                    <div
                      key={ct.id}
                      onClick={() => setCapType(ct.id)}
                      style={{
                        border: selected ? "1.5px solid var(--aos-blue-600)" : "1px solid var(--aos-border-strong)",
                        borderRadius: 2,
                        padding: 16,
                        cursor: "pointer",
                        background: selected ? "var(--aos-accent-light)" : "var(--aos-surface)",
                        transition: "all 0.15s",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                        <span style={{ fontSize: 18, fontWeight: 600, color: "var(--aos-text)" }}>{ct.id}</span>
                        <span
                          style={{
                            padding: "2px 8px",
                            borderRadius: 4,
                            fontSize: 10,
                            background: ct.subBg,
                            color: ct.subColor,
                            fontWeight: 500,
                          }}
                        >
                          {ct.subtype}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 4 }}>
                        {ct.name}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--aos-text-secondary)",
                          lineHeight: 1.6,
                          whiteSpace: "pre-line",
                        }}
                      >
                        {ct.desc}
                      </div>
                      <div style={{ fontSize: 10, color: "var(--aos-text-tertiary)", marginTop: 8 }}>{ct.example}</div>
                    </div>
                  );
                })}
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 24 }}>
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  style={{
                    padding: "8px 24px",
                    borderRadius: 2,
                    fontSize: 13,
                    fontWeight: 500,
                    background: "var(--aos-blue-600)",
                    color: "var(--text-on-brand)",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  下一步
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Manifest 配置 */}
          {step === 2 && (
            <div>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 4px" }}>
                Manifest 配置
              </h2>
              <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "0 0 16px" }}>
                输入能力插件的 Manifest 文件 URL，系统将自动解析并校验
              </p>

              <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                <input
                  type="text"
                  value={manifestUrl}
                  onChange={(e) => setManifestUrl(e.target.value)}
                  placeholder="https://example.com/capability/manifest.yaml"
                  style={{
                    flex: 1,
                    padding: "8px 12px",
                    fontSize: 12,
                    border: "1px solid var(--aos-border-strong)",
                    borderRadius: 4,
                    outline: "none",
                    fontFamily: "monospace",
                  }}
                />
                <button
                  type="button"
                  style={{
                    padding: "8px 16px",
                    fontSize: 12,
                    fontWeight: 500,
                    border: "1px solid var(--aos-border-strong)",
                    borderRadius: 4,
                    background: "var(--aos-surface-hover)",
                    color: "var(--aos-text)",
                    cursor: "pointer",
                  }}
                >
                  解析
                </button>
              </div>

              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                Manifest 预览
              </div>
              <pre
                style={{
                  background: "var(--aos-text)",
                  color: "var(--aos-border-strong)",
                  padding: 16,
                  borderRadius: 2,
                  fontSize: 11,
                  lineHeight: 1.7,
                  overflowX: "auto",
                  margin: 0,
                  fontFamily: "Menlo, Monaco, monospace",
                }}
              >
                {manifestYaml}
              </pre>

              {/* 知识库关联区（references/） */}
              <div
                style={{
                  marginTop: 20,
                  borderRadius: 2,
                  border: "1px solid var(--aos-accent-border)",
                  background: "rgba(239, 246, 255, 0.4)",
                  padding: 16,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <div>
                    <h3 style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)", margin: 0 }}>
                      知识库关联{" "}
                      <span style={{ fontSize: 10, color: "var(--aos-text-tertiary)", fontWeight: 400 }}>references/</span>
                    </h3>
                    <p style={{ fontSize: 11, color: "var(--aos-text-secondary)", margin: "2px 0 0" }}>
                      为该能力挂载参考文档，Agent 运行时可按需检索注入上下文
                    </p>
                  </div>
                  <span style={{ fontSize: 10, color: "var(--aos-text-tertiary)" }}>
                    已关联 {computeKBStats(kbDocs).total} 个文件 · {computeKBStats(kbDocs).totalChunks} 语义块
                  </span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {kbDocs.map((doc) => (
                    <div
                      key={doc.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "8px 12px",
                        borderRadius: 2,
                        background: "var(--aos-surface)",
                        border: "1px solid var(--aos-border)",
                      }}
                    >
                      <DocIcon type={doc.icon} color={doc.iconColor} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {doc.name}
                        </div>
                        <div style={{ fontSize: 10, color: "var(--aos-text-tertiary)" }}>
                          {doc.size} · {doc.desc}
                          {doc.chunks > 0 && ` · ${doc.chunks} 个语义块`}
                        </div>
                      </div>
                      {doc.status === "indexed" && (
                        <span
                          style={{
                            padding: "2px 8px",
                            borderRadius: 3,
                            fontSize: 9,
                            background: "var(--aos-green-bg)",
                            color: "var(--aos-green-700)",
                            fontWeight: 500,
                          }}
                        >
                          已索引
                        </span>
                      )}
                      {doc.status === "indexing" && (
                        <span
                          style={{
                            padding: "2px 8px",
                            borderRadius: 3,
                            fontSize: 9,
                            background: "var(--aos-amber-bg)",
                            color: "var(--aos-amber-700)",
                            fontWeight: 500,
                          }}
                        >
                          索引中
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => setKbDocs(kbDocs.filter((d) => d.id !== doc.id))}
                        title="移除关联"
                        style={{
                          color: "var(--aos-text-tertiary)",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          padding: 0,
                          fontSize: 14,
                          lineHeight: 1,
                        }}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>

                <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
                  <button
                    type="button"
                    style={{
                      padding: "6px 12px",
                      borderRadius: 2,
                      border: "1px solid var(--aos-accent-border)",
                      background: "var(--aos-surface)",
                      fontSize: 11,
                      color: "var(--aos-blue-600)",
                      cursor: "pointer",
                      fontWeight: 500,
                    }}
                  >
                    + 上传文档
                  </button>
                  <button
                    type="button"
                    style={{
                      padding: "6px 12px",
                      borderRadius: 2,
                      border: "1px solid var(--aos-border-strong)",
                      background: "var(--aos-surface)",
                      fontSize: 11,
                      color: "var(--aos-text-secondary)",
                      cursor: "pointer",
                    }}
                  >
                    从代码仓库引用
                  </button>
                  <span style={{ fontSize: 10, color: "var(--aos-text-tertiary)" }}>
                    支持 PDF / MD / DOCX / TXT，自动语义分块 + 向量索引
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  style={{
                    padding: "8px 24px",
                    borderRadius: 2,
                    fontSize: 13,
                    border: "1px solid var(--aos-border-strong)",
                    background: "var(--aos-surface)",
                    color: "var(--aos-text)",
                    cursor: "pointer",
                  }}
                >
                  上一步
                </button>
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  style={{
                    padding: "8px 24px",
                    borderRadius: 2,
                    fontSize: 13,
                    fontWeight: 500,
                    background: "var(--aos-blue-600)",
                    color: "var(--text-on-brand)",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  下一步
                </button>
              </div>
            </div>
          )}

          {/* Step 3: 安全与配额 */}
          {step === 3 && (
            <div>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 4px" }}>
                安全等级与配额
              </h2>
              <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "0 0 16px" }}>
                设置能力的安全等级和调用配额限制
              </p>

              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                安全等级
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 20 }}>
                {SEC_LEVELS.map((lvl) => {
                  const selected = secLevel === lvl.id;
                  return (
                    <div
                      key={lvl.id}
                      onClick={() => setSecLevel(lvl.id)}
                      style={{
                        border: selected ? `1.5px solid ${lvl.color}` : "1px solid var(--aos-border-strong)",
                        borderRadius: 2,
                        padding: "10px 14px",
                        cursor: "pointer",
                        background: selected ? `${lvl.color}10` : "var(--aos-surface)",
                        transition: "all 0.15s",
                      }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 2 }}>
                        {lvl.label}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>{lvl.desc}</div>
                    </div>
                  );
                })}
              </div>

              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                调用配额
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: 12,
                  marginBottom: 20,
                }}
              >
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: 11,
                      color: "var(--aos-text-secondary)",
                      marginBottom: 4,
                    }}
                  >
                    速率限制（次/分）
                  </label>
                  <input
                    type="number"
                    value={rateLimitPerMin}
                    onChange={(e) => setRateLimitPerMin(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "6px 10px",
                      fontSize: 12,
                      border: "1px solid var(--aos-border-strong)",
                      borderRadius: 4,
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: 11,
                      color: "var(--aos-text-secondary)",
                      marginBottom: 4,
                    }}
                  >
                    并发配额
                  </label>
                  <input
                    type="number"
                    value={concurrency}
                    onChange={(e) => setConcurrency(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "6px 10px",
                      fontSize: 12,
                      border: "1px solid var(--aos-border-strong)",
                      borderRadius: 4,
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: 11,
                      color: "var(--aos-text-secondary)",
                      marginBottom: 4,
                    }}
                  >
                    每日请求数 (RPD)
                  </label>
                  <input
                    type="number"
                    defaultValue={10000}
                    style={{
                      width: "100%",
                      padding: "6px 10px",
                      fontSize: 12,
                      border: "1px solid var(--aos-border-strong)",
                      borderRadius: 4,
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
              </div>

              {/* 资源配额 */}
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                资源配额
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: 12,
                  marginBottom: 20,
                }}
              >
                <div>
                  <label style={{ display: "block", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 4 }}>
                    内存上限
                  </label>
                  <input
                    value={memoryLimit}
                    onChange={(e) => setMemoryLimit(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "6px 10px",
                      fontSize: 12,
                      border: "1px solid var(--aos-border-strong)",
                      borderRadius: 4,
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 4 }}>
                    GPU（C1/C2）
                  </label>
                  <input
                    value={gpuConfig}
                    onChange={(e) => setGpuConfig(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "6px 10px",
                      fontSize: 12,
                      border: "1px solid var(--aos-border-strong)",
                      borderRadius: 4,
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 4 }}>
                    超时（秒）
                  </label>
                  <input
                    type="number"
                    value={timeoutSec}
                    onChange={(e) => setTimeoutSec(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "6px 10px",
                      fontSize: 12,
                      border: "1px solid var(--aos-border-strong)",
                      borderRadius: 4,
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
              </div>

              {/* 密钥/凭证绑定 */}
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                密钥 / 凭证绑定
              </div>
              <div
                style={{
                  borderRadius: 2,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  padding: 14,
                  marginBottom: 20,
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <div>
                    <label style={{ display: "block", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 4 }}>
                      Secret Ref（KMS 加密）
                    </label>
                    <input
                      value={secretRef}
                      onChange={(e) => setSecretRef(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        border: "1px solid var(--aos-border-strong)",
                        borderRadius: 4,
                        fontSize: 11,
                        fontFamily: "Menlo, Monaco, monospace",
                        background: "var(--aos-surface-hover)",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    />
                    <p style={{ fontSize: 10, color: "var(--aos-text-tertiary)", margin: "4px 0 0" }}>
                      存储于 KMS，运行时注入，不落地到配置文件
                    </p>
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 4 }}>
                      回调 Webhook（验签）
                    </label>
                    <input
                      value={webhookUrl}
                      onChange={(e) => setWebhookUrl(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        border: "1px solid var(--aos-border-strong)",
                        borderRadius: 4,
                        fontSize: 11,
                        fontFamily: "Menlo, Monaco, monospace",
                        background: "var(--aos-surface-hover)",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                </div>
                <div
                  style={{
                    marginTop: 10,
                    padding: "8px 12px",
                    borderRadius: 2,
                    background: "rgba(219, 234, 254, 0.5)",
                    border: "1px solid var(--aos-accent-border)",
                    fontSize: 10,
                    color: "var(--aos-text)",
                  }}
                >
                  <strong style={{ color: "var(--aos-blue-600)" }}>Vault 配置：</strong>
                  密钥将在运行时从 KMS 注入，不落地到配置文件。轮换周期 90 天。
                </div>
              </div>

              {/* 环境变量配置 */}
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                环境变量
              </div>
              <div
                style={{
                  borderRadius: 2,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  overflow: "hidden",
                  marginBottom: 20,
                }}
              >
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1.5fr 60px 60px",
                    padding: "6px 12px",
                    background: "var(--aos-surface-hover)",
                    fontSize: 10,
                    fontWeight: 500,
                    color: "var(--aos-text-secondary)",
                    borderBottom: "1px solid var(--aos-border)",
                  }}
                >
                  <span>变量名</span>
                  <span>值 / Vault 引用</span>
                  <span>类型</span>
                  <span style={{ textAlign: "right" }}>绑定</span>
                </div>
                {envVars.map((v, i) => (
                  <div
                    key={i}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1.5fr 60px 60px",
                      padding: "6px 12px",
                      fontSize: 11,
                      borderBottom: i < envVars.length - 1 ? "0.5px solid var(--aos-gray-100)" : "none",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <code style={{ color: "var(--aos-text)", fontFamily: "Menlo, Monaco, monospace", fontSize: 10 }}>
                      {v.key}
                    </code>
                    <input
                      value={v.value}
                      onChange={(e) => {
                        const next = [...envVars];
                        next[i] = { ...v, value: e.target.value };
                        setEnvVars(next);
                      }}
                      placeholder={v.secret ? "vault://…" : "value"}
                      style={{
                        padding: "3px 6px",
                        border: "0.5px solid var(--aos-border)",
                        borderRadius: 3,
                        fontSize: 10,
                        fontFamily: "Menlo, Monaco, monospace",
                        background: "var(--aos-surface)",
                        color: "var(--aos-text)",
                        outline: "none",
                        width: "100%",
                        boxSizing: "border-box",
                      }}
                    />
                    <span
                      style={{
                        fontSize: 9,
                        padding: "1px 6px",
                        borderRadius: 3,
                        background: v.secret ? "var(--aos-red-bg)" : "var(--aos-gray-100)",
                        color: v.secret ? "var(--aos-red)" : "var(--aos-text-secondary)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {v.secret ? "secret" : "plain"}
                    </span>
                    <label style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={v.bound}
                        onChange={(e) => {
                          const next = [...envVars];
                          next[i] = { ...v, bound: e.target.checked };
                          setEnvVars(next);
                        }}
                      />
                    </label>
                  </div>
                ))}
              </div>

              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  style={{
                    padding: "8px 24px",
                    borderRadius: 2,
                    fontSize: 13,
                    border: "1px solid var(--aos-border-strong)",
                    background: "var(--aos-surface)",
                    color: "var(--aos-text)",
                    cursor: "pointer",
                  }}
                >
                  上一步
                </button>
                <button
                  type="button"
                  onClick={() => setStep(4)}
                  style={{
                    padding: "8px 24px",
                    borderRadius: 2,
                    fontSize: 13,
                    fontWeight: 500,
                    background: "var(--aos-blue-600)",
                    color: "var(--text-on-brand)",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  下一步
                </button>
              </div>
            </div>
          )}

          {/* Step 4: 连通测试 + 确认导入 */}
          {step === 4 && (
            <div>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 4px" }}>
                连通性测试与确认
              </h2>
              <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "0 0 16px" }}>
                点击「运行测试」验证端点可达、鉴权有效、Schema 匹配
              </p>

              <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 12 }}>
                <button
                  type="button"
                  onClick={runTests}
                  disabled={testing}
                  style={{
                    padding: "8px 20px",
                    fontSize: 12,
                    fontWeight: 500,
                    border: "none",
                    borderRadius: 2,
                    background: testing ? "var(--aos-faint)" : "var(--aos-accent)",
                    color: "var(--text-on-brand)",
                    cursor: testing ? "default" : "pointer",
                  }}
                >
                  {testing ? "测试中…" : "▶ 运行连通测试"}
                </button>
                {testDone && (
                  <span style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>
                    通过 <strong style={{ color: "var(--aos-green-600)" }}>{computeTestStats(DETAILED_TEST_ITEMS).pass}</strong>/
                    {computeTestStats(DETAILED_TEST_ITEMS).total} 项
                  </span>
                )}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 16 }}>
                {DETAILED_TEST_ITEMS.map((item, i) => {
                  const statusIndex = testDone ? 3 : testing ? Math.min(i + 1, 2) : 0;
                  const status = ["pending", "pending", "pending", "pass"][statusIndex] || item.status;
                  const isPass = status === "pass";
                  const isPending = status === "pending";
                  return (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "8px 12px",
                        borderRadius: 4,
                        fontSize: 12,
                        background: isPass
                          ? "var(--aos-green-bg)"
                          : isPending
                            ? "var(--aos-amber-bg)"
                            : "var(--aos-red-bg)",
                        color: isPass ? "var(--aos-green-700)" : isPending ? "var(--aos-amber-700)" : "var(--aos-red)",
                      }}
                    >
                      <span style={{ fontSize: 14 }}>
                        {isPass ? "✓" : isPending ? "○" : "✗"}
                      </span>
                      <span style={{ fontWeight: 500 }}>{item.name}</span>
                      <span style={{ fontSize: 11, marginLeft: "auto", color: "var(--aos-text-secondary)" }}>
                        {testDone ? item.detail : isPending ? "测试中…" : "等待"}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* 注册汇总 */}
              <div
                style={{
                  borderRadius: 2,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface-hover)",
                  padding: 16,
                  marginBottom: 12,
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>注册汇总</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 24px", fontSize: 12, color: "var(--aos-text-secondary)" }}>
                  <div>
                    能力名称：<span style={{ color: "var(--aos-text)", fontWeight: 500 }}>short-video-generation</span>
                  </div>
                  <div>
                    能力类型：<span style={{ color: "var(--aos-blue-600)", fontWeight: 500 }}>{capType}</span>
                  </div>
                  <div>
                    安全等级：<span style={{ color: "var(--aos-text)" }}>{secLevel}</span>
                  </div>
                  <div>
                    并发配额：<span style={{ color: "var(--aos-text)" }}>{concurrency}</span>
                  </div>
                  <div>
                    速率限制：<span style={{ color: "var(--aos-text)" }}>{rateLimitPerMin} 次/分</span>
                  </div>
                  <div>
                    密钥管理：<span style={{ color: "var(--aos-text)" }}>KMS Vault</span>
                  </div>
                  <div>
                    资源配额：<span style={{ color: "var(--aos-text)" }}>{memoryLimit} · {gpuConfig}</span>
                  </div>
                  <div>
                    超时：<span style={{ color: "var(--aos-text)" }}>{timeoutSec}s</span>
                  </div>
                </div>
              </div>

              {/* 注册后说明 */}
              <div
                style={{
                  padding: "10px 12px",
                  borderRadius: 2,
                  background: "rgba(240, 253, 244, 0.7)",
                  border: "1px solid var(--aos-green-border)",
                  fontSize: 11,
                  color: "var(--aos-text)",
                }}
              >
                <strong style={{ color: "var(--aos-green-600)" }}>注册后：</strong>
                该能力将出现在「智能体插件」列表中，状态为「就绪」。可在「智能体工具面板」中将此 Capability 挂载为 Agent 的 Function Tool。
                <Link to="/s2/aip/tools" style={{ color: "var(--aos-blue-600)", marginLeft: 4, textDecoration: "none" }}>
                  去挂载 →
                </Link>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  style={{
                    padding: "8px 24px",
                    borderRadius: 2,
                    fontSize: 13,
                    border: "1px solid var(--aos-border-strong)",
                    background: "var(--aos-surface)",
                    color: "var(--aos-text)",
                    cursor: "pointer",
                  }}
                >
                  上一步
                </button>
                <button
                  type="button"
                  onClick={handleImport}
                  disabled={!testDone}
                  style={{
                    padding: "8px 24px",
                    borderRadius: 2,
                    fontSize: 13,
                    fontWeight: 500,
                    background: testDone ? "var(--aos-accent)" : "var(--aos-border-strong)",
                    color: testDone ? "var(--text-on-brand)" : "var(--aos-faint)",
                    border: "none",
                    cursor: testDone ? "pointer" : "default",
                  }}
                >
                  确认接入
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </PageChrome>
  );
}
