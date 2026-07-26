import { useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";

type CapType = "C0" | "C1" | "C2";

const STEPS = [
  { num: 1, label: "能力类型" },
  { num: 2, label: "Manifest 配置" },
  { num: 3, label: "安全与配额" },
  { num: 4, label: "连通测试" },
];

const CAP_TYPES: {
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
    subColor: "#1D4ED8",
    subBg: "#DBEAFE",
  },
  {
    id: "C1",
    subtype: "Job",
    name: "异步任务",
    desc: "GPU / 长耗时\nsubmit → status → artifact\n产物写 MediaSet",
    example: "例：短视频生成、图片渲染",
    subColor: "#7C3AED",
    subBg: "#EDE9FE",
  },
  {
    id: "C2",
    subtype: "Session",
    name: "实时会话",
    desc: "WebSocket 长连接\n实时双向交互\nAV 流外置",
    example: "例：数字人主播、语音助手",
    subColor: "#EA580C",
    subBg: "#FFEDD5",
  },
];

const SEC_LEVELS = [
  { id: "low", label: "低风险", desc: "只读数据，不触发写操作", color: "#10B981" },
  { id: "medium", label: "中风险", desc: "可写受控对象，需 HITL 审批", color: "#F59E0B" },
  { id: "high", label: "高风险", desc: "可跨域调用，需安全审计", color: "#EF4444" },
];

const TEST_ITEMS = [
  { name: "端点连通性", status: "pass", detail: "200 OK · 32ms" },
  { name: "鉴权 Token 验证", status: "pass", detail: "Bearer 令牌有效" },
  { name: "Schema 校验", status: "pending", detail: "验证中…" },
  { name: "速率限制测试", status: "pending", detail: "等待" },
];

export function CapabilityImportPage() {
  const [step, setStep] = useState(1);
  const [capType, setCapType] = useState<CapType>("C0");
  const [manifestUrl, setManifestUrl] = useState("https://api.example.com/capabilities/live-script/manifest.yaml");
  const [secLevel, setSecLevel] = useState("medium");
  const [testing, setTesting] = useState(false);
  const [testDone, setTestDone] = useState(false);
  const [imported, setImported] = useState(false);

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
    setTimeout(() => {
      setTesting(false);
      setTestDone(true);
    }, 1500);
  }

  function handleImport() {
    setImported(true);
  }

  if (imported) {
    return (
      <PageChrome title="接入插件能力" lede="声明外部能力端点和契约，注册为 C0/C1/C2 Capability 供智能体调用。">
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
              background: "#D1FAE5",
              color: "#059669",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 32,
              margin: "0 auto 16px",
            }}
          >
            ✓
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: "0 0 8px" }}>
            能力接入成功
          </h2>
          <p style={{ fontSize: 13, color: "#6B7280", margin: "0 0 20px", lineHeight: 1.6 }}>
            Live Script Engine 已注册为 {capType} 类型能力，可在智能体工具面板中启用。
          </p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
            <Link
              to="/aip/capabilities"
              style={{
                padding: "8px 20px",
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 500,
                background: "#0F6E56",
                color: "#fff",
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
                borderRadius: 6,
                fontSize: 13,
                border: "1px solid #D1D5DB",
                background: "#fff",
                color: "#374151",
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
    <PageChrome title="接入插件能力" lede="声明外部能力端点和契约，注册为 C0/C1/C2 Capability 供智能体调用。">
      {/* C0/C1/C2 分层说明 */}
      <div
        style={{
          borderRadius: 12,
          border: "1px solid #FDE047",
          background: "#FEFCE8",
          padding: 16,
          marginBottom: 20,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 500, color: "#92400E", marginBottom: 8 }}>
          C0 / C1 / C2 能力分层
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
          <div style={{ fontSize: 12, color: "#78350F" }}>
            <span style={{ fontWeight: 500, color: "#92400E" }}>C0 sync</span> — 同步函数，
            &lt;15s，可直接挂 Function
          </div>
          <div style={{ fontSize: 12, color: "#78350F" }}>
            <span style={{ fontWeight: 500, color: "#92400E" }}>C1 Job</span> — 异步任务，
            GPU/长耗时，产物写 MediaSet
          </div>
          <div style={{ fontSize: 12, color: "#78350F" }}>
            <span style={{ fontWeight: 500, color: "#92400E" }}>C2 Session</span> — 实时会话，
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
                    borderRadius: 6,
                    fontSize: 13,
                    color: isActive ? "#1D4ED8" : isDone ? "#1D4ED8" : "#6B7280",
                    background: isActive ? "#EFF6FF" : "transparent",
                    border: isActive ? "1px solid #93C5FD" : "1px solid transparent",
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
                      background: isActive || isDone ? "#1D4ED8" : "#D1D5DB",
                      color: "#fff",
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
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "#111827", margin: "0 0 4px" }}>
                选择能力类型
              </h2>
              <p style={{ fontSize: 12, color: "#6B7280", margin: "0 0 16px" }}>
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
                        border: selected ? "1.5px solid #1D4ED8" : "1px solid #D1D5DB",
                        borderRadius: 8,
                        padding: 16,
                        cursor: "pointer",
                        background: selected ? "#EFF6FF" : "#fff",
                        transition: "all 0.15s",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                        <span style={{ fontSize: 18, fontWeight: 600, color: "#111827" }}>{ct.id}</span>
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
                      <div style={{ fontSize: 12, fontWeight: 500, color: "#111827", marginBottom: 4 }}>
                        {ct.name}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "#6B7280",
                          lineHeight: 1.6,
                          whiteSpace: "pre-line",
                        }}
                      >
                        {ct.desc}
                      </div>
                      <div style={{ fontSize: 10, color: "#9CA3AF", marginTop: 8 }}>{ct.example}</div>
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
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: 500,
                    background: "#1D4ED8",
                    color: "#fff",
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
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "#111827", margin: "0 0 4px" }}>
                Manifest 配置
              </h2>
              <p style={{ fontSize: 12, color: "#6B7280", margin: "0 0 16px" }}>
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
                    border: "1px solid #D1D5DB",
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
                    border: "1px solid #D1D5DB",
                    borderRadius: 4,
                    background: "#F9FAFB",
                    color: "#374151",
                    cursor: "pointer",
                  }}
                >
                  解析
                </button>
              </div>

              <div style={{ fontSize: 12, fontWeight: 500, color: "#374151", marginBottom: 8 }}>
                Manifest 预览
              </div>
              <pre
                style={{
                  background: "#1E293B",
                  color: "#CBD5E1",
                  padding: 16,
                  borderRadius: 6,
                  fontSize: 11,
                  lineHeight: 1.7,
                  overflowX: "auto",
                  margin: 0,
                  fontFamily: "Menlo, Monaco, monospace",
                }}
              >
                {manifestYaml}
              </pre>

              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  style={{
                    padding: "8px 24px",
                    borderRadius: 6,
                    fontSize: 13,
                    border: "1px solid #D1D5DB",
                    background: "#fff",
                    color: "#374151",
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
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: 500,
                    background: "#1D4ED8",
                    color: "#fff",
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
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "#111827", margin: "0 0 4px" }}>
                安全等级与配额
              </h2>
              <p style={{ fontSize: 12, color: "#6B7280", margin: "0 0 16px" }}>
                设置能力的安全等级和调用配额限制
              </p>

              <div style={{ fontSize: 12, fontWeight: 500, color: "#374151", marginBottom: 8 }}>
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
                        border: selected ? `1.5px solid ${lvl.color}` : "1px solid #D1D5DB",
                        borderRadius: 6,
                        padding: "10px 14px",
                        cursor: "pointer",
                        background: selected ? `${lvl.color}10` : "#fff",
                        transition: "all 0.15s",
                      }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 500, color: "#111827", marginBottom: 2 }}>
                        {lvl.label}
                      </div>
                      <div style={{ fontSize: 11, color: "#6B7280" }}>{lvl.desc}</div>
                    </div>
                  );
                })}
              </div>

              <div style={{ fontSize: 12, fontWeight: 500, color: "#374151", marginBottom: 8 }}>
                调用配额
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 12,
                  marginBottom: 20,
                }}
              >
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: 11,
                      color: "#6B7280",
                      marginBottom: 4,
                    }}
                  >
                    每分钟请求数 (RPM)
                  </label>
                  <input
                    type="number"
                    defaultValue={60}
                    style={{
                      width: "100%",
                      padding: "6px 10px",
                      fontSize: 12,
                      border: "1px solid #D1D5DB",
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
                      color: "#6B7280",
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
                      border: "1px solid #D1D5DB",
                      borderRadius: 4,
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  style={{
                    padding: "8px 24px",
                    borderRadius: 6,
                    fontSize: 13,
                    border: "1px solid #D1D5DB",
                    background: "#fff",
                    color: "#374151",
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
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: 500,
                    background: "#1D4ED8",
                    color: "#fff",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  下一步
                </button>
              </div>
            </div>
          )}

          {/* Step 4: 连通测试 */}
          {step === 4 && (
            <div>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "#111827", margin: "0 0 4px" }}>
                连通性测试
              </h2>
              <p style={{ fontSize: 12, color: "#6B7280", margin: "0 0 16px" }}>
                测试能力端点的连通性和契约一致性
              </p>

              <div style={{ marginBottom: 16 }}>
                <button
                  type="button"
                  onClick={runTests}
                  disabled={testing}
                  style={{
                    padding: "8px 20px",
                    fontSize: 12,
                    fontWeight: 500,
                    border: "none",
                    borderRadius: 6,
                    background: testing ? "#9CA3AF" : "#0F6E56",
                    color: "#fff",
                    cursor: testing ? "default" : "pointer",
                  }}
                >
                  {testing ? "测试中…" : "▶ 运行连通测试"}
                </button>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {TEST_ITEMS.map((item, i) => {
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
                          ? "#D1FAE5"
                          : isPending
                            ? "#FEF3C7"
                            : "#FEE2E2",
                        color: isPass ? "#065F46" : isPending ? "#92400E" : "#991B1B",
                      }}
                    >
                      <span style={{ fontSize: 14 }}>
                        {isPass ? "✓" : isPending ? "○" : "✗"}
                      </span>
                      <span style={{ flex: 1, fontWeight: 500 }}>{item.name}</span>
                      <span style={{ fontSize: 11 }}>{testDone ? item.detail : isPending ? "测试中…" : "等待"}</span>
                    </div>
                  );
                })}
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  style={{
                    padding: "8px 24px",
                    borderRadius: 6,
                    fontSize: 13,
                    border: "1px solid #D1D5DB",
                    background: "#fff",
                    color: "#374151",
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
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: 500,
                    background: testDone ? "#0F6E56" : "#D1D5DB",
                    color: testDone ? "#fff" : "#9CA3AF",
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
