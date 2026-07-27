import { useState } from "react";
import { PageChrome } from "../../components/PageChrome";
import { apiPost } from "../../api/client";

export type SourceType = "github" | "local" | "market";
export type AdapterType = "http" | "process" | "mcp" | "docker" | "session";

const STEPS = [
  { num: 1, label: "选择来源" },
  { num: 2, label: "仓库扫描" },
  { num: 3, label: "映射配置" },
  { num: 4, label: "安全与网络" },
  { num: 5, label: "连通测试与安全扫描" },
];

export const ADAPTER_TYPES = [
  { key: "http", label: "HTTP API", desc: "外部服务 URL", tag: "REST/GraphQL", color: "blue" },
  { key: "process", label: "Process Wrapper", desc: "沙箱子进程", tag: "Python/Node 脚本", color: "green", recommended: true },
  { key: "mcp", label: "MCP Bridge", desc: "协议桥接", tag: "MCP Server", color: "purple" },
  { key: "docker", label: "Docker Container", desc: "K8s Pod", tag: "独立运行环境", color: "amber" },
  { key: "session", label: "Session Gateway", desc: "长连接", tag: "音视频/数字人", color: "pink" },
];

/** Adapter 详细配置 schema（用于 Adapter 联动右侧面板展示） */
export const ADAPTER_DETAILS: Record<
  AdapterType,
  {
    schema: { field: string; type: string; required: boolean; desc: string }[];
    example: string;
    compatibility: { item: string; status: "pass" | "warn" | "fail" }[];
    latency: string;
    isolation: string;
  }
> = {
  http: {
    schema: [
      { field: "endpoint", type: "string (URL)", required: true, desc: "外部服务基础 URL" },
      { field: "method", type: "GET|POST|PUT", required: true, desc: "调用方法" },
      { field: "headers", type: "object", required: false, desc: "自定义请求头" },
      { field: "auth", type: "Bearer|Basic|APIKey", required: true, desc: "鉴权方式" },
      { field: "timeout", type: "int (ms)", required: false, desc: "超时时间" },
    ],
    example: `POST https://api.example.com/v1/agent
Authorization: Bearer \${VAULT_TOKEN}
Content-Type: application/json

{ "input": "${'${INPUT}'}" }`,
    compatibility: [
      { item: "REST/GraphQL 端点", status: "pass" },
      { item: "无状态调用", status: "pass" },
      { item: "需要长期持久进程", status: "fail" },
    ],
    latency: "毫秒级",
    isolation: "网络隔离",
  },
  process: {
    schema: [
      { field: "entrypoint", type: "string", required: true, desc: "入口文件 (agent.py:main)" },
      { field: "runtime", type: "python3.11|node20", required: true, desc: "运行时版本" },
      { field: "args", type: "string[]", required: false, desc: "启动参数" },
      { field: "env", type: "object", required: false, desc: "环境变量（vault 引用）" },
      { field: "workdir", type: "string", required: false, desc: "工作目录" },
    ],
    example: `$ python3 agent.py --input '\${INPUT_JSON}'
# stdin/stdout JSON-RPC 通信
# 沙箱内 cgroups + seccomp 隔离`,
    compatibility: [
      { item: "Python/Node 脚本", status: "pass" },
      { item: "main() 入口函数", status: "pass" },
      { item: "Streamlit/Flask 单文件", status: "pass" },
      { item: "需要 GPU 支持", status: "warn" },
    ],
    latency: "秒级",
    isolation: "cgroups + seccomp",
  },
  mcp: {
    schema: [
      { field: "serverUrl", type: "string", required: true, desc: "MCP Server URL" },
      { field: "protocolVersion", type: "string", required: true, desc: "MCP 协议版本" },
      { field: "tools", type: "string[]", required: false, desc: "注册的工具列表" },
      { field: "resources", type: "string[]", required: false, desc: "资源列表" },
    ],
    example: `MCP Server: ws://localhost:8080
Protocol: 2025-06-18
Tools: [search, fetch, compute]`,
    compatibility: [
      { item: "MCP 标准实现", status: "pass" },
      { item: "工具自动注册", status: "pass" },
      { item: "需要流式响应", status: "warn" },
    ],
    latency: "毫秒级",
    isolation: "协议沙箱",
  },
  docker: {
    schema: [
      { field: "image", type: "string", required: true, desc: "Docker 镜像地址" },
      { field: "command", type: "string", required: false, desc: "启动命令" },
      { field: "ports", type: "object", required: false, desc: "端口映射" },
      { field: "volumes", type: "object", required: false, desc: "卷挂载" },
      { field: "gpu", type: "boolean", required: false, desc: "是否启用 GPU" },
      { field: "memory", type: "string", required: false, desc: "内存限制" },
    ],
    example: `docker run -d \\
  --gpus all \\
  -p 8080:8080 \\
  -v /data:/data \\
  my-agent:latest`,
    compatibility: [
      { item: "已有 Dockerfile", status: "pass" },
      { item: "需要特殊系统依赖", status: "pass" },
      { item: "GPU 推理任务", status: "pass" },
      { item: "启动速度要求高", status: "warn" },
    ],
    latency: "冷启动慢",
    isolation: "容器隔离",
  },
  session: {
    schema: [
      { field: "gateway", type: "string", required: true, desc: "Session Gateway URL" },
      { field: "protocol", type: "ws|wss", required: true, desc: "WebSocket 协议" },
      { field: "avStream", type: "object", required: false, desc: "音视频流配置" },
      { field: "heartbeat", type: "int (s)", required: false, desc: "心跳间隔" },
    ],
    example: `WebSocket: wss://gateway.aos/v2/session
Events: [open, push, close, error]
AV Stream: SFU → Janus`,
    compatibility: [
      { item: "实时音视频交互", status: "pass" },
      { item: "WebSocket 长连接", status: "pass" },
      { item: "数字人/虚拟形象", status: "pass" },
      { item: "短时无状态调用", status: "fail" },
    ],
    latency: "长连接",
    isolation: "会话网关",
  },
};

/** 工具映射 — 源 Agent 工具 → 平台工具 ID */
export const DEFAULT_TOOL_MAPPINGS = [
  { sourceTool: "search_web", targetToolId: "web_search_v1", autoMapped: true, status: "pass" },
  { sourceTool: "read_file", targetToolId: "filesystem_read", autoMapped: true, status: "pass" },
  { sourceTool: "write_file", targetToolId: "filesystem_write", autoMapped: false, status: "warn" },
  { sourceTool: "execute_sql", targetToolId: "", autoMapped: false, status: "fail" },
  { sourceTool: "send_email", targetToolId: "notification_email", autoMapped: true, status: "pass" },
];

/** 权限映射 — 源 Agent 权限 → 平台权限 */
export const DEFAULT_PERMISSION_MAPPINGS = [
  { sourcePermission: "read:products", targetPermission: "object:read:Product", granted: true },
  { sourcePermission: "write:orders", targetPermission: "object:write:Order", granted: false },
  { sourcePermission: "call:llm", targetPermission: "model:invoke", granted: true },
  { sourcePermission: "access:network", targetPermission: "net:egress", granted: false },
];

/** 计算映射统计（纯函数） */
export function computeMappingStats(mappings: typeof DEFAULT_TOOL_MAPPINGS) {
  return {
    total: mappings.length,
    autoMapped: mappings.filter((m) => m.autoMapped).length,
    pass: mappings.filter((m) => m.status === "pass").length,
    warn: mappings.filter((m) => m.status === "warn").length,
    fail: mappings.filter((m) => m.status === "fail").length,
  };
}

/** 获取 Adapter 详情（纯函数） */
export function getAdapterDetail(adapterType: AdapterType) {
  return ADAPTER_DETAILS[adapterType];
}

const SCAN_RESULTS = [
  { label: "框架检测", value: "Streamlit + LangChain", status: "pass", statusText: "已识别" },
  { label: "入口文件", value: "agent.py · main()", status: "pass", statusText: "已识别", mono: true },
  { label: "依赖清单", value: "langchain, openai, pydantic", status: "pass", statusText: "兼容" },
  { label: "模型依赖", value: "OpenAI GPT-4", status: "info", statusText: "→ 路由 gpt-5.2" },
  { label: "运行模式", value: "sync（单次调用 <15s）", status: "info", statusText: "C0" },
  { label: "外部服务", value: "无（纯 LLM 调用）", status: "pass", statusText: "安全" },
  { label: "代码量", value: "~450 行 Python", status: "muted", statusText: "轻量" },
];

const CONNECT_TESTS = [
  { label: "代码拉取", detail: "git clone · 2.3MB · 完成", status: "pass" },
  { label: "依赖安装", detail: "pip install · 8 packages · 完成", status: "pass" },
  { label: "沙箱启动", detail: "cgroups + seccomp · 就绪", status: "pass" },
  { label: "LLM 路由", detail: "gpt-5.2-prod · 可达 (23ms)", status: "pass" },
  { label: "冒烟测试", detail: "发送测试请求 → 等待响应…", status: "pending" },
];

const SECURITY_SCANS = [
  { category: "命令注入", content: "os.system() · subprocess 无沙箱调用", result: "pass", resultText: "通过" },
  { category: "代码执行", content: "eval() · __import__() · compile()", result: "fail", resultText: "P1 · 2 处", highlight: true },
  { category: "数据泄露", content: "硬编码密钥 · 明文 Token · 日志敏感信息", result: "pass", resultText: "通过" },
  { category: "Prompt 注入", content: "用户输入拼入系统提示词 · 模板变量未转义", result: "warn", resultText: "P2 · 1 处", highlight: true },
  { category: "依赖供应链", content: "requirements.txt 已知恶意包 · 版本漏洞", result: "pass", resultText: "通过" },
  { category: "权限提升", content: "文件系统越权 · 网络端口越权 · cgroups 逃逸", result: "pass", resultText: "通过" },
];

export function AgentImportPage() {
  const [step, setStep] = useState(1);
  const [sourceType, setSourceType] = useState<SourceType>("github");
  const [adapterType, setAdapterType] = useState<AdapterType>("process");
  const [securityApproved, setSecurityApproved] = useState(false);
  const [importing, setImporting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [githubUrl, setGithubUrl] = useState("github.com/Shubhamsaboo/awesome-llm-apps");
  const [agentPath, setAgentPath] = useState("advanced_ai_agents/single_agent_apps/ai_fraud_investigation_agent");
  const [branch, setBranch] = useState("main");

  const [capName, setCapName] = useState("fraud-investigation");
  const [capDisplayName, setCapDisplayName] = useState("欺诈调查分析 Agent");
  const [capDesc, setCapDesc] = useState("分析交易记录，识别欺诈模式，生成调查报告");
  const [capLevel, setCapLevel] = useState("C0 sync");
  const [timeout, setTimeout] = useState("60");
  const [memory, setMemory] = useState("512Mi");

  const [sandboxLevel, setSandboxLevel] = useState("strict");
  const [cpuLimit, setCpuLimit] = useState("1 core");
  const [rateLimit, setRateLimit] = useState("30");
  const [guardrails, setGuardrails] = useState({
    noFsWrite: true,
    noFork: true,
    tokenLimit: true,
    autoDraft: true,
  });
  const [showGuide, setShowGuide] = useState(true);

  // 工具映射 + 权限映射（Step 3）
  const [toolMappings, setToolMappings] = useState(DEFAULT_TOOL_MAPPINGS);
  const [permissionMappings, setPermissionMappings] = useState(DEFAULT_PERMISSION_MAPPINGS);

  const goStep = (n: number) => {
    if (n < 1 || n > 5) return;
    setStep(n);
    setError(null);
  };

  const handleFinish = async () => {
    if (!securityApproved) {
      setError("请管理员确认接受安全风险后再继续");
      return;
    }
    setError(null);
    setImporting(true);
    try {
      await apiPost("/v1/aip/agent-import", {
        source_type: sourceType,
        adapter_type: adapterType,
        name: capName,
        security_approved: securityApproved,
      });
      setImporting(false);
      setSuccess(true);
    } catch (e) {
      setError(String((e as Error).message || e));
      setImporting(false);
    }
  };

  const adapterInfo = ADAPTER_TYPES.find((a) => a.key === adapterType);

  const yamlContent = `# Capability Manifest — auto-filled
apiVersion: v1
kind: Capability
metadata:
  name: ${capName}
  displayName: ${capDisplayName}
  version: 1.0.0
  source:
    repo: awesome-llm-apps
    path: advanced_ai_agents/.../ai_fraud
    license: Apache-2.0
spec:
  adapter: ${adapterInfo?.label || "Process Wrapper"}
  capabilityLevel: ${capLevel.split(" ")[0]}
  runtime:
    entrypoint: agent.py:main()
    timeout: ${timeout}
    memory: ${memory}
  model:
    provider: openai
    routing: gpt-5.2-prod
  interface:
    input: "{transactions: []}"
    output: "{report: string}"
    writeBack: false`;

  if (success) {
    return (
      <PageChrome title="智能体导入" lede="从外部来源导入智能体 · 支持 Adapter 桥接">
        <div style={{ textAlign: "center", padding: "64px 24px" }}>
          <div style={{ fontSize: 56, marginBottom: 16, color: "var(--aos-green-600)" }}>✓</div>
          <div style={{ fontSize: 22, fontWeight: 600, color: "var(--aos-text)", marginBottom: 8 }}>导入成功</div>
          <p style={{ fontSize: 14, color: "var(--aos-text-secondary)", marginBottom: 4 }}>
            <strong style={{ color: "var(--aos-text)" }}>{capDisplayName}</strong> 已成功导入并注册为 Capability
          </p>
          <p style={{ fontSize: 12, color: "var(--aos-text-tertiary)", marginBottom: 20 }}>
            Adapter: {adapterInfo?.label} · 能力等级: {capLevel}
          </p>
          <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
            <button
              onClick={() => {
                setSuccess(false);
                setStep(1);
              }}
              style={{
                padding: "8px 20px",
                fontSize: 13,
                borderRadius: 6,
                border: "1px solid var(--aos-border-strong)",
                background: "var(--aos-surface)",
                color: "var(--aos-text)",
                cursor: "pointer",
              }}
            >
              继续导入
            </button>
            <button
              style={{
                padding: "8px 20px",
                fontSize: 13,
                fontWeight: 500,
                borderRadius: 6,
                border: "none",
                background: "var(--aos-amber-700)",
                color: "var(--text-on-brand)",
                cursor: "pointer",
              }}
            >
              去智能体目录
            </button>
          </div>
        </div>
      </PageChrome>
    );
  }

  return (
    <PageChrome title="导入外部 Agent（Adapter 桥接）" lede="从开源社区或自有代码导入 Agent，通过 Adapter 桥接为平台 Capability。">
      {/* Adapter 路径说明 */}
      <div
        style={{
          borderRadius: 12,
          border: "1px solid rgba(59, 130, 246, 0.2)",
          background: "rgba(239, 246, 255, 0.6)",
          padding: "14px 16px",
          marginBottom: "1.25rem",
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--aos-blue-600)", marginBottom: 8 }}>Adapter 路径说明</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
          {ADAPTER_TYPES.map((a) => (
            <div
              key={a.key}
              style={{
                textAlign: "center",
                padding: "10px 6px",
                borderRadius: 6,
                background: "rgba(255,255,255,0.7)",
                border: adapterType === a.key ? "1px solid var(--aos-amber-700)" : "1px solid transparent",
                cursor: "pointer",
                transition: "all 0.15s",
              }}
              onClick={() => setAdapterType(a.key as AdapterType)}
            >
              <div style={{ fontWeight: 600, color: "var(--aos-text)", fontSize: 12 }}>{a.label}</div>
              <div style={{ fontSize: 9, color: "var(--aos-text-tertiary)", marginTop: 2 }}>{a.desc}</div>
              <div
                style={{
                  fontSize: 9,
                  marginTop: 3,
                  color:
                    a.color === "blue"
                      ? "var(--aos-blue)"
                      : a.color === "green"
                        ? "var(--aos-green)"
                        : a.color === "purple"
                          ? "var(--aos-purple-600)"
                          : a.color === "amber"
                            ? "var(--aos-amber)"
                            : "var(--aos-purple-600)",
                }}
              >
                {a.tag}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: "flex", gap: 24 }}>
        {/* 左侧步骤导航 */}
        <aside style={{ width: 224, flexShrink: 0 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {STEPS.map((s) => {
              const isActive = step === s.num;
              const isDone = step > s.num;
              return (
                <div
                  key={s.num}
                  onClick={() => goStep(s.num)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 12px",
                    borderRadius: 6,
                    cursor: "pointer",
                    fontSize: 13,
                    color: isActive ? "var(--aos-amber-700)" : isDone ? "var(--aos-amber-700)" : "var(--aos-text-secondary)",
                    fontWeight: isActive ? 500 : 400,
                    background: isActive ? "var(--aos-amber-bg)" : "transparent",
                    border: isActive ? "0.5px solid var(--aos-amber)" : "0.5px solid transparent",
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
                      background: isDone ? "var(--aos-amber-700)" : isActive ? "var(--aos-amber-700)" : "var(--aos-faint)",
                      color: isDone || isActive ? "var(--aos-surface)" : "var(--aos-text-secondary)",
                      flexShrink: 0,
                    }}
                  >
                    {isDone ? "✓" : s.num}
                  </div>
                  <span>{s.label}</span>
                </div>
              );
            })}
          </div>
        </aside>

        {/* 右侧内容区 */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {error && (
            <div
              style={{
                background: "var(--aos-red-bg)",
                color: "var(--aos-red)",
                padding: "8px 12px",
                borderRadius: 6,
                marginBottom: 12,
                fontSize: 13,
              }}
            >
              {error}
            </div>
          )}

          {/* Step 1: 选择来源 */}
          {step === 1 && (
            <div>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 4px 0" }}>选择 Agent 来源</h2>
              <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "0 0 16px 0" }}>
                支持从 GitHub 仓库、本地代码库或市场导入
              </p>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
                {[
                  { key: "github", label: "GitHub 仓库", desc: "从 awesome-llm-apps 或任意 GitHub 仓库导入", icon: "⌨" },
                  { key: "local", label: "本地代码库", desc: "从 AOS 代码库中已有的 Agent 代码导入", icon: "📁" },
                  { key: "market", label: "市场安装", desc: "从 AOS Capability Marketplace 搜索安装", icon: "🛒" },
                ].map((src) => (
                  <div
                    key={src.key}
                    onClick={() => setSourceType(src.key as SourceType)}
                    style={{
                      border: sourceType === src.key ? "1.5px solid var(--aos-amber-700)" : "0.5px solid var(--aos-faint)",
                      borderRadius: 8,
                      padding: 14,
                      cursor: "pointer",
                      transition: "all 0.15s",
                      background: sourceType === src.key ? "var(--aos-amber-bg)" : "var(--aos-surface)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: 18 }}>{src.icon}</span>
                      <span style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)" }}>{src.label}</span>
                    </div>
                    <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", lineHeight: 1.5 }}>{src.desc}</div>
                  </div>
                ))}
              </div>

              {sourceType === "github" && (
                <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>
                      仓库地址（GitHub URL）
                    </label>
                    <input
                      value={githubUrl}
                      onChange={(e) => setGithubUrl(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        border: "0.5px solid var(--aos-faint)",
                        borderRadius: 4,
                        fontSize: 12,
                        background: "var(--aos-surface)",
                        color: "var(--aos-text)",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div>
                      <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>
                        Agent 路径（仓库内子目录）
                      </label>
                      <input
                        value={agentPath}
                        onChange={(e) => setAgentPath(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "6px 10px",
                          border: "0.5px solid var(--aos-faint)",
                          borderRadius: 4,
                          fontSize: 12,
                          background: "var(--aos-surface)",
                          color: "var(--aos-text)",
                          outline: "none",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>分支</label>
                      <input
                        value={branch}
                        onChange={(e) => setBranch(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "6px 10px",
                          border: "0.5px solid var(--aos-faint)",
                          borderRadius: 4,
                          fontSize: 12,
                          background: "var(--aos-surface)",
                          color: "var(--aos-text)",
                          outline: "none",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                  </div>
                  <div
                    style={{
                      padding: "10px 12px",
                      borderRadius: 8,
                      background: "rgba(240, 253, 244, 0.7)",
                      border: "1px solid var(--aos-green-border)",
                      fontSize: 11,
                      color: "var(--aos-text)",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <span style={{ color: "var(--aos-green-600)", fontSize: 14 }}>✓</span>
                    <span>仓库可达 · Apache-2.0 许可证 · 包含 requirements.txt + agent.py</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 2: 仓库扫描 */}
          {step === 2 && (
            <div>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 4px 0" }}>仓库自动扫描</h2>
              <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "0 0 16px 0" }}>
                平台分析 Agent 代码结构，自动推荐 Adapter 类型和运行模式
              </p>

              {/* 扫描结果 */}
              <div
                style={{
                  borderRadius: 8,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  overflow: "hidden",
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
                    padding: "8px 14px",
                    borderBottom: "1px solid var(--aos-border)",
                    background: "var(--aos-surface-hover)",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--aos-text)",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <span style={{ color: "var(--aos-amber)" }}>⌕</span>
                  扫描结果
                </div>
                <div>
                  {SCAN_RESULTS.map((r, i) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "6px 14px",
                        fontSize: 12,
                        borderBottom: i < SCAN_RESULTS.length - 1 ? "0.5px solid var(--aos-divider)" : "none",
                      }}
                    >
                      <span style={{ width: 100, color: "var(--aos-text-secondary)", flexShrink: 0 }}>{r.label}</span>
                      <span
                        style={{
                          fontWeight: 500,
                          color: "var(--aos-text)",
                          fontFamily: r.mono ? "Menlo, Monaco, monospace" : "inherit",
                          fontSize: r.mono ? 11 : 12,
                        }}
                      >
                        {r.value}
                      </span>
                      <span
                        style={{
                          marginLeft: "auto",
                          padding: "2px 8px",
                          borderRadius: 3,
                          fontSize: 10,
                          background:
                            r.status === "pass"
                              ? "var(--aos-green-bg)"
                              : r.status === "info"
                                ? "var(--aos-accent-light)"
                                : "transparent",
                          color:
                            r.status === "pass"
                              ? "var(--aos-green-700)"
                              : r.status === "info"
                                ? "var(--aos-blue-600)"
                                : "var(--aos-text-tertiary)",
                        }}
                      >
                        {r.statusText}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Adapter 类型选择 */}
              <div>
                <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 8, display: "block" }}>
                  推荐 Adapter 类型（可修改）
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
                  {ADAPTER_TYPES.map((a) => (
                    <div
                      key={a.key}
                      onClick={() => setAdapterType(a.key as AdapterType)}
                      style={{
                        border:
                          adapterType === a.key
                            ? "1.5px solid var(--aos-amber-700)"
                            : a.recommended
                              ? "1px solid var(--aos-green-border)"
                              : "0.5px solid var(--aos-faint)",
                        borderRadius: 8,
                        padding: 10,
                        cursor: "pointer",
                        transition: "all 0.15s",
                        background:
                          adapterType === a.key
                            ? "var(--aos-amber-bg)"
                            : a.recommended
                              ? "var(--aos-green-bg)"
                              : "var(--aos-surface)",
                      }}
                    >
                      <div style={{ fontSize: 13, fontWeight: 700, color: "var(--aos-text)" }}>{a.label}</div>
                      {a.recommended && (
                        <span
                          style={{
                            display: "inline-block",
                            padding: "1px 6px",
                            borderRadius: 3,
                            fontSize: 9,
                            background: "var(--aos-green-border)",
                            color: "var(--aos-green-700)",
                            fontWeight: 500,
                            marginTop: 4,
                          }}
                        >
                          推荐
                        </span>
                      )}
                      <div style={{ fontSize: 9, color: "var(--aos-text-tertiary)", marginTop: 4 }}>{a.desc}</div>
                      <div
                        style={{
                          fontSize: 9,
                          marginTop: 4,
                          fontWeight: 500,
                          color:
                            a.color === "blue"
                              ? "var(--aos-blue-600)"
                              : a.color === "green"
                                ? "var(--aos-green-600)"
                                : a.color === "purple"
                                  ? "var(--aos-purple-600)"
                                  : a.color === "amber"
                                    ? "var(--aos-amber-600)"
                                    : "var(--aos-red)",
                        }}
                      >
                        ⏱ {a.color === "blue" ? "毫秒级" : a.color === "amber" ? "冷启动慢" : a.color === "pink" ? "长连接" : "秒级"}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Adapter 选用决策指南 */}
                <details
                  open={showGuide}
                  onToggle={(e) => setShowGuide((e.target as HTMLDetailsElement).open)}
                  style={{
                    marginTop: 12,
                    borderRadius: 8,
                    border: "1px solid var(--aos-border)",
                    background: "var(--aos-surface)",
                    overflow: "hidden",
                  }}
                >
                  <summary
                    style={{
                      padding: "10px 14px",
                      fontSize: 12,
                      fontWeight: 500,
                      color: "var(--aos-text)",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      listStyle: "none",
                    }}
                  >
                    <span style={{ color: "var(--aos-blue)", fontSize: 14 }}>ⓘ</span>
                    如何选用 Adapter 类型？
                    <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--aos-text-tertiary)" }}>
                      {showGuide ? "点击收起" : "点击展开"}
                    </span>
                  </summary>
                  <div style={{ borderTop: "1px solid var(--aos-border)", padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                    {/* HTTP API */}
                    <div
                      style={{
                        display: "flex",
                        gap: 10,
                        padding: 8,
                        borderRadius: 6,
                        background: adapterType === "http" ? "var(--aos-amber-bg)" : "transparent",
                        border: adapterType === "http" ? "1px solid var(--aos-amber)" : "1px solid transparent",
                      }}
                    >
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: 6,
                          background: "var(--aos-accent-light)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          fontSize: 14,
                        }}
                      >
                        🌐
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ fontWeight: 700, color: "var(--aos-text)", fontSize: 12 }}>HTTP API</span>
                          <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 3, background: "var(--aos-accent-light)", color: "var(--aos-blue-600)" }}>
                            最轻量
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginTop: 2 }}>
                          <strong style={{ color: "var(--aos-text)" }}>什么时候选：</strong>
                          Agent 已经部署成 Web 服务，有现成的 REST/GraphQL 端点可以调用
                        </div>
                        <div style={{ fontSize: 11, color: "var(--aos-text-tertiary)", marginTop: 2 }}>
                          <strong style={{ color: "var(--aos-text-secondary)" }}>典型场景：</strong>
                          接入第三方 SaaS API、企业内部已有的微服务
                        </div>
                      </div>
                    </div>

                    {/* Process Wrapper */}
                    <div
                      style={{
                        display: "flex",
                        gap: 10,
                        padding: 8,
                        borderRadius: 6,
                        background: adapterType === "process" ? "var(--aos-amber-bg)" : "rgba(240,253,244,0.5)",
                        border: adapterType === "process" ? "1px solid var(--aos-amber)" : "1px solid var(--aos-green-border)",
                      }}
                    >
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: 6,
                          background: "var(--aos-green-bg)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          fontSize: 14,
                        }}
                      >
                        ⚙
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ fontWeight: 700, color: "var(--aos-text)", fontSize: 12 }}>Process Wrapper</span>
                          <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 3, background: "var(--aos-green-bg)", color: "var(--aos-green-700)" }}>
                            最常用
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginTop: 2 }}>
                          <strong style={{ color: "var(--aos-text)" }}>什么时候选：</strong>
                          Agent 是 Python/Node 脚本，有 main() 入口，可以在沙箱里 fork 子进程跑起来
                        </div>
                        <div style={{ fontSize: 11, color: "var(--aos-text-tertiary)", marginTop: 2 }}>
                          <strong style={{ color: "var(--aos-text-secondary)" }}>典型场景：</strong>
                          awesome-llm-apps 的 Streamlit/Flask 单文件 Agent、内部快速原型
                        </div>
                      </div>
                    </div>

                    {/* MCP Bridge */}
                    <div
                      style={{
                        display: "flex",
                        gap: 10,
                        padding: 8,
                        borderRadius: 6,
                        background: adapterType === "mcp" ? "var(--aos-amber-bg)" : "transparent",
                        border: adapterType === "mcp" ? "1px solid var(--aos-amber)" : "1px solid transparent",
                      }}
                    >
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: 6,
                          background: "var(--aos-indigo-bg)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          fontSize: 14,
                        }}
                      >
                        ✦
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ fontWeight: 700, color: "var(--aos-text)", fontSize: 12 }}>MCP Bridge</span>
                          <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 3, background: "var(--aos-indigo-bg)", color: "var(--aos-purple-600)" }}>
                            标准化协议
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginTop: 2 }}>
                          <strong style={{ color: "var(--aos-text)" }}>什么时候选：</strong>
                          Agent 已经按 MCP（Model Context Protocol）标准实现了 Server
                        </div>
                        <div style={{ fontSize: 11, color: "var(--aos-text-tertiary)", marginTop: 2 }}>
                          <strong style={{ color: "var(--aos-text-secondary)" }}>典型场景：</strong>
                          awesome-llm-apps 的 MCP AI Agents 分支、标准化的工具服务
                        </div>
                      </div>
                    </div>

                    {/* Docker Container */}
                    <div
                      style={{
                        display: "flex",
                        gap: 10,
                        padding: 8,
                        borderRadius: 6,
                        background: adapterType === "docker" ? "var(--aos-amber-bg)" : "transparent",
                        border: adapterType === "docker" ? "1px solid var(--aos-amber)" : "1px solid transparent",
                      }}
                    >
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: 6,
                          background: "var(--aos-amber-bg)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          fontSize: 14,
                        }}
                      >
                        ▦
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ fontWeight: 700, color: "var(--aos-text)", fontSize: 12 }}>Docker Container</span>
                          <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 3, background: "var(--aos-amber-bg)", color: "var(--aos-amber-700)" }}>
                            重量级
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginTop: 2 }}>
                          <strong style={{ color: "var(--aos-text)" }}>什么时候选：</strong>
                          Agent 需要特殊系统依赖（如 GPU 驱动、C++ 库），或者已经有 Dockerfile
                        </div>
                        <div style={{ fontSize: 11, color: "var(--aos-text-tertiary)", marginTop: 2 }}>
                          <strong style={{ color: "var(--aos-text-secondary)" }}>典型场景：</strong>
                          需 GPU 推理的 Agent、含复杂数据处理 pipeline 的 Agent
                        </div>
                      </div>
                    </div>

                    {/* Session Gateway */}
                    <div
                      style={{
                        display: "flex",
                        gap: 10,
                        padding: 8,
                        borderRadius: 6,
                        background: adapterType === "session" ? "var(--aos-amber-bg)" : "transparent",
                        border: adapterType === "session" ? "1px solid var(--aos-amber)" : "1px solid transparent",
                      }}
                    >
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: 6,
                          background: "var(--aos-indigo-bg)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          fontSize: 14,
                        }}
                      >
                        ◎
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ fontWeight: 700, color: "var(--aos-text)", fontSize: 12 }}>Session Gateway</span>
                          <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 3, background: "var(--aos-indigo-bg)", color: "var(--aos-red)" }}>
                            实时会话
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginTop: 2 }}>
                          <strong style={{ color: "var(--aos-text)" }}>什么时候选：</strong>
                          Agent 涉及语音对话、视频通话、数字人/虚拟形象等实时流式交互
                        </div>
                        <div style={{ fontSize: 11, color: "var(--aos-text-tertiary)", marginTop: 2 }}>
                          <strong style={{ color: "var(--aos-text-secondary)" }}>典型场景：</strong>
                          Voice AI Agent、直播数字人、视频客服 Bot
                        </div>
                      </div>
                    </div>

                    {/* 快速决策路径 */}
                    <div style={{ marginTop: 4, paddingTop: 10, borderTop: "1px solid var(--aos-gray-100)" }}>
                      <div style={{ fontSize: 10, color: "var(--aos-text-secondary)", fontWeight: 500, marginBottom: 6 }}>⚡ 快速决策路径：</div>
                      <div style={{ fontSize: 10, color: "var(--aos-text-tertiary)", lineHeight: 1.8 }}>
                        <div>
                          <span style={{ color: "var(--aos-text-secondary)" }}>①</span> Agent 已有 HTTP 接口？→{" "}
                          <strong style={{ color: "var(--aos-blue-600)" }}>HTTP API</strong>
                        </div>
                        <div>
                          <span style={{ color: "var(--aos-text-secondary)" }}>②</span> 是 Python/Node 脚本？→{" "}
                          <strong style={{ color: "var(--aos-green-600)" }}>Process Wrapper</strong>（默认推荐）
                        </div>
                        <div>
                          <span style={{ color: "var(--aos-text-secondary)" }}>③</span> 实现了 MCP 协议？→{" "}
                          <strong style={{ color: "var(--aos-purple-600)" }}>MCP Bridge</strong>
                        </div>
                        <div>
                          <span style={{ color: "var(--aos-text-secondary)" }}>④</span> 需要 Docker 环境？→{" "}
                          <strong style={{ color: "var(--aos-amber-600)" }}>Docker Container</strong>
                        </div>
                        <div>
                          <span style={{ color: "var(--aos-text-secondary)" }}>⑤</span> 有音视频流？→{" "}
                          <strong style={{ color: "var(--aos-red)" }}>Session Gateway</strong>
                        </div>
                      </div>
                    </div>
                  </div>
                </details>

                {/* 推荐理由 */}
                <div
                  style={{
                    marginTop: 12,
                    padding: "10px 12px",
                    borderRadius: 8,
                    background: "rgba(255, 251, 235, 0.8)",
                    border: "1px solid var(--aos-amber-border)",
                    fontSize: 11,
                    color: "var(--aos-text)",
                  }}
                >
                  <strong style={{ color: "var(--aos-amber-700)" }}>推荐理由：</strong>
                  {adapterType === "process"
                    ? "检测到 Streamlit 框架 + Python 单进程运行，适合 Process Wrapper（沙箱内 fork 子进程 + stdin/stdout JSON-RPC 通信）。"
                    : `已选择 ${adapterInfo?.label} — 请确认该 Adapter 类型适合您的 Agent 运行模式。`}
                </div>

                {/* Adapter 联动详情面板 */}
                {(() => {
                  const detail = getAdapterDetail(adapterType);
                  const mappingStats = computeMappingStats(toolMappings);
                  return (
                    <div
                      style={{
                        marginTop: 12,
                        borderRadius: 10,
                        border: "1px solid var(--aos-accent-border)",
                        background: "rgba(239, 246, 255, 0.5)",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          padding: "10px 14px",
                          background: "rgba(219, 234, 254, 0.6)",
                          borderBottom: "1px solid var(--aos-accent-border)",
                          fontSize: 12,
                          fontWeight: 600,
                          color: "var(--aos-blue-600)",
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                        }}
                      >
                        <span>⚡</span>
                        {adapterInfo?.label} · 配置预览
                        <span style={{ marginLeft: "auto", fontSize: 10, fontWeight: 400, color: "var(--aos-blue)" }}>
                          延迟：{detail.latency} · 隔离：{detail.isolation}
                        </span>
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0 }}>
                        {/* 左：配置 Schema */}
                        <div style={{ padding: 12, borderRight: "1px solid var(--aos-accent-border)" }}>
                          <div style={{ fontSize: 11, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                            配置 Schema
                          </div>
                          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                            {detail.schema.map((f, i) => (
                              <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 6, fontSize: 10 }}>
                                <code
                                  style={{
                                    color: "var(--aos-blue-600)",
                                    fontFamily: "Menlo, Monaco, monospace",
                                    minWidth: 80,
                                    flexShrink: 0,
                                  }}
                                >
                                  {f.field}
                                  {f.required && <span style={{ color: "var(--aos-red)" }}>*</span>}
                                </code>
                                <span style={{ color: "var(--aos-text-secondary)" }}>{f.desc}</span>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* 右：示例 + 兼容性 */}
                        <div style={{ padding: 12 }}>
                          <div style={{ fontSize: 11, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                            调用示例
                          </div>
                          <pre
                            style={{
                              background: "var(--aos-text)",
                              color: "var(--aos-border-strong)",
                              padding: 8,
                              borderRadius: 4,
                              fontSize: 9,
                              lineHeight: 1.6,
                              fontFamily: "Menlo, Monaco, monospace",
                              margin: 0,
                              overflowX: "auto",
                              whiteSpace: "pre-wrap",
                            }}
                          >
                            {detail.example}
                          </pre>
                        </div>
                      </div>

                      {/* 兼容性报告 */}
                      <div style={{ padding: "8px 12px", borderTop: "1px solid var(--aos-accent-border)" }}>
                        <div style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", marginBottom: 6 }}>
                          兼容性检查
                        </div>
                        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                          {detail.compatibility.map((c, i) => (
                            <span
                              key={i}
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 3,
                                fontSize: 10,
                                color:
                                  c.status === "pass" ? "var(--aos-green-600)" : c.status === "warn" ? "var(--aos-amber-600)" : "var(--aos-red)",
                              }}
                            >
                              {c.status === "pass" ? "✓" : c.status === "warn" ? "⚡" : "✗"} {c.item}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* 工具映射统计 */}
                      <div
                        style={{
                          padding: "8px 12px",
                          borderTop: "1px solid var(--aos-accent-border)",
                          display: "flex",
                          gap: 16,
                          fontSize: 10,
                          color: "var(--aos-text-secondary)",
                        }}
                      >
                        <span>
                          工具映射：<strong style={{ color: "var(--aos-green-600)" }}>{mappingStats.pass}</strong>/
                          {mappingStats.total}
                        </span>
                        <span>
                          自动匹配：<strong style={{ color: "var(--aos-blue-600)" }}>{mappingStats.autoMapped}</strong>
                        </span>
                        {mappingStats.fail > 0 && (
                          <span style={{ color: "var(--aos-red)" }}>⚠ {mappingStats.fail} 个未映射</span>
                        )}
                      </div>
                    </div>
                  );
                })()}
              </div>
            </div>
          )}

          {/* Step 3: 映射配置 */}
          {step === 3 && (
            <div>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 4px 0" }}>
                映射配置
              </h2>
              <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "0 0 16px 0" }}>
                Agent 名称映射、工具映射（源工具 → 目标工具 ID）、权限映射
              </p>

              {/* Agent 名称映射 */}
              <div
                style={{
                  borderRadius: 8,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  padding: 14,
                  marginBottom: 16,
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 10 }}>
                  Agent 名称映射
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>
                      源 Agent 名称（仓库检测）
                    </label>
                    <input
                      defaultValue="ai_fraud_investigation_agent"
                      readOnly
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        border: "0.5px solid var(--aos-border)",
                        borderRadius: 4,
                        fontSize: 12,
                        background: "var(--aos-surface-hover)",
                        color: "var(--aos-text-secondary)",
                        fontFamily: "Menlo, Monaco, monospace",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>
                      目标 Agent 名称（平台注册）
                    </label>
                    <input
                      value={capName}
                      onChange={(e) => setCapName(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        border: "0.5px solid var(--aos-faint)",
                        borderRadius: 4,
                        fontSize: 12,
                        background: "var(--aos-surface)",
                        color: "var(--aos-text)",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* 工具映射表 */}
              <div
                style={{
                  borderRadius: 8,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  overflow: "hidden",
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
                    padding: "8px 14px",
                    borderBottom: "1px solid var(--aos-border)",
                    background: "var(--aos-surface-hover)",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--aos-text)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <span>工具映射（源工具 → 目标工具 ID）</span>
                  <span style={{ fontSize: 10, color: "var(--aos-text-secondary)" }}>
                    自动匹配 {computeMappingStats(toolMappings).autoMapped} / {computeMappingStats(toolMappings).total}
                  </span>
                </div>
                <div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr 80px 60px",
                      padding: "6px 14px",
                      background: "var(--aos-surface-hover)",
                      fontSize: 10,
                      fontWeight: 500,
                      color: "var(--aos-text-secondary)",
                      borderBottom: "0.5px solid var(--aos-border)",
                    }}
                  >
                    <span>源工具</span>
                    <span>目标工具 ID</span>
                    <span>匹配方式</span>
                    <span style={{ textAlign: "right" }}>状态</span>
                  </div>
                  {toolMappings.map((m, i) => (
                    <div
                      key={i}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr 80px 60px",
                        padding: "6px 14px",
                        fontSize: 11,
                        borderBottom: i < toolMappings.length - 1 ? "0.5px solid var(--aos-gray-100)" : "none",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <code style={{ color: "var(--aos-text)", fontFamily: "Menlo, Monaco, monospace", fontSize: 10 }}>
                        {m.sourceTool}
                      </code>
                      <input
                        value={m.targetToolId}
                        onChange={(e) => {
                          const next = [...toolMappings];
                          next[i] = { ...m, targetToolId: e.target.value };
                          setToolMappings(next);
                        }}
                        placeholder="未映射"
                        style={{
                          padding: "3px 6px",
                          border: "0.5px solid var(--aos-border)",
                          borderRadius: 3,
                          fontSize: 10,
                          fontFamily: "Menlo, Monaco, monospace",
                          background: m.status === "fail" ? "var(--aos-red-bg)" : "var(--aos-surface)",
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
                          background: m.autoMapped ? "var(--aos-accent-light)" : "var(--aos-amber-bg)",
                          color: m.autoMapped ? "var(--aos-blue-600)" : "var(--aos-amber-700)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {m.autoMapped ? "自动" : "手动"}
                      </span>
                      <span style={{ textAlign: "right", fontSize: 11 }}>
                        {m.status === "pass" && <span style={{ color: "var(--aos-green-600)" }}>✓</span>}
                        {m.status === "warn" && <span style={{ color: "var(--aos-amber-600)" }}>⚡</span>}
                        {m.status === "fail" && <span style={{ color: "var(--aos-red)" }}>✗</span>}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 权限映射表 */}
              <div
                style={{
                  borderRadius: 8,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  overflow: "hidden",
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
                    padding: "8px 14px",
                    borderBottom: "1px solid var(--aos-border)",
                    background: "var(--aos-surface-hover)",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--aos-text)",
                  }}
                >
                  权限映射
                </div>
                <div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr 60px",
                      padding: "6px 14px",
                      background: "var(--aos-surface-hover)",
                      fontSize: 10,
                      fontWeight: 500,
                      color: "var(--aos-text-secondary)",
                      borderBottom: "0.5px solid var(--aos-border)",
                    }}
                  >
                    <span>源权限</span>
                    <span>目标平台权限</span>
                    <span style={{ textAlign: "right" }}>授权</span>
                  </div>
                  {permissionMappings.map((p, i) => (
                    <div
                      key={i}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr 60px",
                        padding: "6px 14px",
                        fontSize: 11,
                        borderBottom: i < permissionMappings.length - 1 ? "0.5px solid var(--aos-gray-100)" : "none",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <code style={{ color: "var(--aos-text-secondary)", fontFamily: "Menlo, Monaco, monospace", fontSize: 10 }}>
                        {p.sourcePermission}
                      </code>
                      <code style={{ color: "var(--aos-text)", fontFamily: "Menlo, Monaco, monospace", fontSize: 10 }}>
                        {p.targetPermission}
                      </code>
                      <label style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 4, cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          checked={p.granted}
                          onChange={(e) => {
                            const next = [...permissionMappings];
                            next[i] = { ...p, granted: e.target.checked };
                            setPermissionMappings(next);
                          }}
                        />
                        <span style={{ fontSize: 10, color: p.granted ? "var(--aos-green-600)" : "var(--aos-text-tertiary)" }}>
                          {p.granted ? "允许" : "拒绝"}
                        </span>
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Manifest 表单 + YAML 预览 */}
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                Capability Manifest（基于映射生成）
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                {/* 左栏：表单 */}
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>能力名称</label>
                    <input
                      value={capName}
                      onChange={(e) => setCapName(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        border: "0.5px solid var(--aos-faint)",
                        borderRadius: 4,
                        fontSize: 12,
                        background: "var(--aos-surface)",
                        color: "var(--aos-text)",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>显示名称</label>
                    <input
                      value={capDisplayName}
                      onChange={(e) => setCapDisplayName(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        border: "0.5px solid var(--aos-faint)",
                        borderRadius: 4,
                        fontSize: 12,
                        background: "var(--aos-surface)",
                        color: "var(--aos-text)",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>角色描述</label>
                    <textarea
                      value={capDesc}
                      onChange={(e) => setCapDesc(e.target.value)}
                      rows={2}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        border: "0.5px solid var(--aos-faint)",
                        borderRadius: 4,
                        fontSize: 12,
                        background: "var(--aos-surface)",
                        color: "var(--aos-text)",
                        outline: "none",
                        boxSizing: "border-box",
                        resize: "vertical",
                        fontFamily: "inherit",
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>能力标签</label>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {["交易分析", "风险识别", "报告生成"].map((tag, i) => (
                        <span
                          key={i}
                          style={{
                            padding: "2px 8px",
                            borderRadius: 3,
                            fontSize: 10,
                            background: i === 0 ? "var(--aos-accent-light)" : i === 1 ? "var(--aos-indigo-bg)" : "var(--aos-green-bg)",
                            color: i === 0 ? "var(--aos-blue-600)" : i === 1 ? "var(--aos-purple-600)" : "var(--aos-green-700)",
                          }}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>
                      Capability Level
                    </label>
                    <select
                      value={capLevel}
                      onChange={(e) => setCapLevel(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        border: "0.5px solid var(--aos-faint)",
                        borderRadius: 4,
                        fontSize: 12,
                        background: "var(--aos-surface)",
                        color: "var(--aos-text)",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    >
                      <option>C0 sync</option>
                      <option>C1 Job</option>
                      <option>C2 Session</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>超时（秒）</label>
                    <input
                      type="number"
                      value={timeout}
                      onChange={(e) => setTimeout(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        border: "0.5px solid var(--aos-faint)",
                        borderRadius: 4,
                        fontSize: 12,
                        background: "var(--aos-surface)",
                        color: "var(--aos-text)",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>内存限制</label>
                    <input
                      value={memory}
                      onChange={(e) => setMemory(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        border: "0.5px solid var(--aos-faint)",
                        borderRadius: 4,
                        fontSize: 12,
                        background: "var(--aos-surface)",
                        color: "var(--aos-text)",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                </div>

                {/* 右栏：YAML 预览 */}
                <div>
                  <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>
                    Manifest YAML 预览
                  </label>
                  <div
                    style={{
                      background: "var(--aos-text)",
                      color: "var(--aos-border-strong)",
                      padding: 16,
                      borderRadius: 6,
                      fontFamily: "Menlo, Monaco, monospace",
                      fontSize: 11,
                      lineHeight: 1.7,
                      overflowX: "auto",
                      whiteSpace: "pre",
                      height: 400,
                    }}
                  >
                    {yamlContent.split("\n").map((line, i) => {
                      if (line.startsWith("#")) {
                        return (
                          <div key={i} style={{ color: "var(--aos-text-secondary)" }}>
                            {line}
                          </div>
                        );
                      }
                      const colonIdx = line.indexOf(":");
                      if (colonIdx > 0 && !line.trim().startsWith("-")) {
                        const key = line.slice(0, colonIdx);
                        const rest = line.slice(colonIdx);
                        let restColor = "var(--aos-border-strong)";
                        if (rest.match(/: ["']/)) {
                          restColor = "var(--aos-amber-border)";
                        }
                        return (
                          <div key={i}>
                            <span style={{ color: "var(--aos-accent-border)" }}>{key}</span>
                            <span style={{ color: restColor }}>{rest}</span>
                          </div>
                        );
                      }
                      return (
                        <div key={i} style={{ color: "var(--aos-border-strong)" }}>
                          {line}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 4: 安全与网络 */}
          {step === 4 && (
            <div>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 4px 0" }}>
                安全等级与网络白名单
              </h2>
              <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "0 0 16px 0" }}>外部代码运行需配置安全护栏</p>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                {/* 左栏 */}
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 6, display: "block" }}>
                      沙箱隔离级别
                    </label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      {[
                        { key: "strict", label: "严格隔离", desc: "cgroups + seccomp" },
                        { key: "standard", label: "标准隔离", desc: "进程级" },
                        { key: "none", label: "无隔离", desc: "不推荐", warn: true },
                      ].map((opt) => (
                        <label
                          key={opt.key}
                          style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, cursor: "pointer" }}
                        >
                          <input
                            type="radio"
                            name="sandbox"
                            checked={sandboxLevel === opt.key}
                            onChange={() => setSandboxLevel(opt.key)}
                          />
                          <span style={{ color: "var(--aos-text)", fontWeight: opt.key === "strict" ? 500 : 400 }}>
                            {opt.label}
                          </span>
                          <span style={{ fontSize: 10, color: opt.warn ? "var(--aos-red)" : "var(--aos-text-tertiary)" }}>{opt.desc}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div>
                      <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>CPU 上限</label>
                      <input
                        value={cpuLimit}
                        onChange={(e) => setCpuLimit(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "6px 10px",
                          border: "0.5px solid var(--aos-faint)",
                          borderRadius: 4,
                          fontSize: 12,
                          background: "var(--aos-surface)",
                          color: "var(--aos-text)",
                          outline: "none",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4, display: "block" }}>
                        速率限制（次/分）
                      </label>
                      <input
                        type="number"
                        value={rateLimit}
                        onChange={(e) => setRateLimit(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "6px 10px",
                          border: "0.5px solid var(--aos-faint)",
                          borderRadius: 4,
                          fontSize: 12,
                          background: "var(--aos-surface)",
                          color: "var(--aos-text)",
                          outline: "none",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 6, display: "block" }}>护栏配置</label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      {[
                        { key: "noFsWrite", label: "禁止文件系统写入" },
                        { key: "noFork", label: "禁止子进程派生" },
                        { key: "tokenLimit", label: "Token 上限（4096）" },
                        { key: "autoDraft", label: "自动入 Draft" },
                      ].map((opt) => (
                        <label
                          key={opt.key}
                          style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, cursor: "pointer" }}
                        >
                          <input
                            type="checkbox"
                            checked={guardrails[opt.key as keyof typeof guardrails]}
                            onChange={(e) =>
                              setGuardrails({ ...guardrails, [opt.key]: e.target.checked })
                            }
                          />
                          <span style={{ color: "var(--aos-text)" }}>{opt.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 右栏 */}
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 6, display: "block" }}>
                      网络白名单
                    </label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, cursor: "pointer" }}>
                        <input type="checkbox" defaultChecked />
                        <span style={{ color: "var(--aos-text)" }}>api.openai.com</span>
                        <span style={{ fontSize: 10, color: "var(--aos-text-tertiary)" }}>LLM</span>
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, cursor: "pointer" }}>
                        <input type="checkbox" />
                        <span style={{ color: "var(--aos-text-tertiary)" }}>自定义域名…</span>
                      </label>
                    </div>
                    <p style={{ fontSize: 10, color: "var(--aos-text-tertiary)", marginTop: 6 }}>
                      默认仅允许 LLM API 域名。添加其他域名需 L2+ 审批。
                    </p>
                  </div>

                  <div>
                    <label style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 6, display: "block" }}>
                      环境变量注入
                    </label>
                    <div
                      style={{
                        fontFamily: "Menlo, Monaco, monospace",
                        fontSize: 10,
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <span style={{ color: "var(--aos-text-secondary)" }}>OPENAI_API_KEY</span>
                      <span
                        style={{
                          fontSize: 10,
                          padding: "2px 6px",
                          borderRadius: 3,
                          background: "var(--aos-green-bg)",
                          color: "var(--aos-green-700)",
                        }}
                      >
                        → vault://aip/models/openai
                      </span>
                    </div>
                  </div>

                  <div
                    style={{
                      padding: "10px 12px",
                      borderRadius: 8,
                      background: "rgba(254, 242, 242, 0.7)",
                      border: "1px solid var(--aos-red-border)",
                      fontSize: 11,
                      color: "var(--aos-text)",
                    }}
                  >
                    <strong style={{ color: "var(--aos-red)" }}>安全提示：</strong>
                    外部代码在沙箱内运行。平台已自动配置 cgroups（CPU/内存限制）+ seccomp（系统调用过滤），防止恶意操作。
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 5: 连通测试与安全扫描 */}
          {step === 5 && (
            <div>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 4px 0" }}>
                连通测试与安全扫描
              </h2>
              <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "0 0 16px 0" }}>
                验证沙箱启动、子进程通信、LLM 路由，并执行 6 类安全风险扫描
              </p>

              {/* 连通测试 */}
              <div style={{ display: "flex", flexDirection: "column", gap: 2, marginBottom: 16 }}>
                {CONNECT_TESTS.map((t, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 12px",
                      borderRadius: 4,
                      fontSize: 12,
                      background: t.status === "pass" ? "var(--aos-green-bg)" : t.status === "pending" ? "var(--aos-amber-bg)" : "var(--aos-surface)",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 14,
                        color:
                          t.status === "pass"
                            ? "var(--aos-green-600)"
                            : t.status === "pending"
                              ? "var(--aos-amber-600)"
                              : "var(--aos-text-secondary)",
                      }}
                    >
                      {t.status === "pass" ? "✓" : t.status === "pending" ? "⏱" : "…"}
                    </span>
                    <span style={{ fontWeight: 500, color: "var(--aos-text)" }}>{t.label}</span>
                    <span style={{ fontSize: 10, color: "var(--aos-text-secondary)", marginLeft: "auto" }}>{t.detail}</span>
                  </div>
                ))}
              </div>

              {/* 安全扫描 */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                  <h3 style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: 0 }}>安全扫描</h3>
                  <span style={{ fontSize: 10, color: "var(--aos-text-tertiary)" }}>基于 skill-security-auditor · 零依赖静态分析</span>
                </div>
                <p style={{ fontSize: 11, color: "var(--aos-text-secondary)", margin: "0 0 10px 0" }}>
                  扫描已导入的 Agent 源码，检测 6 类安全风险。高风险项需管理员审批方可继续导入。
                </p>

                <div style={{ borderRadius: 8, border: "1px solid var(--aos-border)", overflow: "hidden" }}>
                  {/* 表头 */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      padding: "8px 12px",
                      background: "var(--aos-surface-hover)",
                      borderBottom: "1px solid var(--aos-border)",
                      fontSize: 10,
                      fontWeight: 500,
                      color: "var(--aos-text-secondary)",
                    }}
                  >
                    <span style={{ width: 100 }}>风险类别</span>
                    <span style={{ flex: 1 }}>扫描内容</span>
                    <span style={{ width: 80, textAlign: "right" }}>结果</span>
                  </div>
                  {SECURITY_SCANS.map((s, i) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        padding: "10px 12px",
                        borderBottom: i < SECURITY_SCANS.length - 1 ? "1px solid var(--aos-gray-100)" : "none",
                        fontSize: 12,
                        background: s.highlight
                          ? s.result === "fail"
                            ? "rgba(254,242,242,0.4)"
                            : "rgba(255,251,235,0.4)"
                          : "transparent",
                      }}
                    >
                      <span style={{ width: 100, color: "var(--aos-text)", fontWeight: 500, flexShrink: 0 }}>
                        {s.category}
                      </span>
                      <span style={{ flex: 1, color: "var(--aos-text-secondary)" }}>
                        {s.result === "fail" && (
                          <span style={{ color: "var(--aos-red)", fontWeight: 500 }}>eval()</span>
                        )}
                        {s.result !== "fail" && s.content}
                        {s.result === "fail" && " · __import__() · compile()"}
                      </span>
                      <span style={{ width: 80, textAlign: "right" }}>
                        {s.result === "pass" && (
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "var(--aos-green-600)" }}>
                            <span>✓</span>通过
                          </span>
                        )}
                        {s.result === "fail" && (
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              color: "var(--aos-red)",
                              fontWeight: 500,
                            }}
                          >
                            <span>⚠</span>
                            {s.resultText}
                          </span>
                        )}
                        {s.result === "warn" && (
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              color: "var(--aos-amber-600)",
                              fontWeight: 500,
                            }}
                          >
                            <span>⚡</span>
                            {s.resultText}
                          </span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>

                {/* 扫描结论 */}
                <div
                  style={{
                    marginTop: 8,
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    padding: "8px 12px",
                    borderRadius: 8,
                    background: "rgba(254, 242, 242, 0.7)",
                    border: "1px solid var(--aos-red-border)",
                  }}
                >
                  <span style={{ color: "var(--aos-red)", fontSize: 16, flexShrink: 0 }}>⚠</span>
                  <div style={{ fontSize: 11, color: "var(--aos-text)" }}>
                    <strong style={{ color: "var(--aos-red)" }}>检测到 P1 风险：</strong>
                    代码执行模块发现 2 处{" "}
                    <code
                      style={{
                        color: "var(--aos-red)",
                        background: "var(--aos-red-bg)",
                        padding: "1px 4px",
                        borderRadius: 3,
                        fontSize: 10,
                      }}
                    >
                      eval()
                    </code>{" "}
                    调用（llm_eval.py:34, agent_chain.py:71）。
                    <div style={{ marginTop: 2, color: "var(--aos-text-secondary)" }}>
                      建议：将 eval() 替换为 ast.literal_eval()，或在沙箱中限制执行权限。需管理员审批方可继续导入。
                    </div>
                  </div>
                </div>

                {/* 管理员审批 */}
                <div
                  style={{
                    marginTop: 8,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 12px",
                    borderRadius: 8,
                    background: "rgba(255, 251, 235, 0.8)",
                    border: "1px solid var(--aos-amber-border)",
                  }}
                >
                  <input
                    type="checkbox"
                    id="sec-approve"
                    checked={securityApproved}
                    onChange={(e) => setSecurityApproved(e.target.checked)}
                    style={{ accentColor: "var(--aos-amber-600)" }}
                  />
                  <label htmlFor="sec-approve" style={{ fontSize: 11, color: "var(--aos-text)", cursor: "pointer" }}>
                    <strong style={{ color: "var(--aos-amber-700)" }}>管理员确认接受风险</strong> — 勾选后允许跳过 P1 门控继续导入，风险记录将写入审计日志
                  </label>
                </div>
              </div>

              {/* 导入汇总 */}
              <div
                style={{
                  borderRadius: 8,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface-hover)",
                  padding: 16,
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 12,
                }}
              >
                <div style={{ color: "var(--aos-text)", fontWeight: 500, marginBottom: 4 }}>导入汇总</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 24px", color: "var(--aos-text-secondary)" }}>
                  <div>
                    Agent 名称：<span style={{ color: "var(--aos-text)", fontWeight: 500 }}>{capDisplayName}</span>
                  </div>
                  <div>
                    来源：<span style={{ color: "var(--aos-text)" }}>awesome-llm-apps</span>
                  </div>
                  <div>
                    Adapter：<span style={{ color: "var(--aos-amber-600)", fontWeight: 500 }}>{adapterInfo?.label}</span>
                  </div>
                  <div>
                    能力类型：<span style={{ color: "var(--aos-blue-600)", fontWeight: 500 }}>{capLevel}</span>
                  </div>
                  <div>
                    沙箱：<span style={{ color: "var(--aos-text)" }}>严格隔离</span>
                  </div>
                  <div>
                    速率限制：<span style={{ color: "var(--aos-text)" }}>{rateLimit} 次/分</span>
                  </div>
                  <div>
                    模型路由：<span style={{ color: "var(--aos-text)" }}>gpt-5.2-prod</span>
                  </div>
                  <div>
                    许可证：<span style={{ color: "var(--aos-text)" }}>Apache-2.0</span>
                  </div>
                </div>
              </div>

              {/* 导入后说明 */}
              <div
                style={{
                  marginTop: 16,
                  padding: "10px 12px",
                  borderRadius: 8,
                  background: "rgba(240, 253, 244, 0.7)",
                  border: "1px solid var(--aos-green-border)",
                  fontSize: 11,
                  color: "var(--aos-text)",
                }}
              >
                <strong style={{ color: "var(--aos-green-600)" }}>导入后：</strong>
                该 Agent 将出现在「智能体目录」和「智能体插件」列表中。可在「智能体工具面板」挂载为 Function Tool，供平台内 Agent 调用。
                <a style={{ color: "var(--aos-blue-600)", marginLeft: 4 }}>去挂载 →</a>
              </div>
            </div>
          )}

          {/* 底部操作栏 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginTop: 24,
              paddingTop: 16,
              borderTop: "1px solid var(--aos-border)",
            }}
          >
            <button
              onClick={() => goStep(step - 1)}
              disabled={step === 1}
              style={{
                padding: "8px 20px",
                fontSize: 13,
                borderRadius: 6,
                border: step === 1 ? "1px solid var(--aos-border)" : "0.5px solid var(--aos-faint)",
                background: "var(--aos-surface)",
                color: step === 1 ? "var(--aos-text-tertiary)" : "var(--aos-text-secondary)",
                cursor: step === 1 ? "default" : "pointer",
                visibility: step === 1 ? "hidden" : "visible",
              }}
            >
              上一步
            </button>
            <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
              <button
                onClick={() => {
                  setSuccess(false);
                  setStep(1);
                }}
                style={{
                  padding: "8px 20px",
                  fontSize: 13,
                  borderRadius: 6,
                  border: "0.5px solid var(--aos-faint)",
                  background: "var(--aos-surface)",
                  color: "var(--aos-text-secondary)",
                  cursor: "pointer",
                }}
              >
                取消
              </button>
              {step < 5 && (
                <button
                  onClick={() => goStep(step + 1)}
                  style={{
                    padding: "8px 20px",
                    fontSize: 13,
                    fontWeight: 500,
                    borderRadius: 6,
                    border: "none",
                    background: "var(--aos-amber-700)",
                    color: "var(--text-on-brand)",
                    cursor: "pointer",
                  }}
                >
                  {step === 4 ? "运行测试" : "下一步"}
                </button>
              )}
              {step === 5 && (
                <button
                  onClick={handleFinish}
                  disabled={importing}
                  style={{
                    padding: "8px 20px",
                    fontSize: 13,
                    fontWeight: 500,
                    borderRadius: 6,
                    border: "none",
                    background: "var(--aos-accent)",
                    color: "var(--text-on-brand)",
                    cursor: importing ? "default" : "pointer",
                    opacity: importing ? 0.7 : 1,
                  }}
                >
                  {importing ? "导入中..." : "确认导入"}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </PageChrome>
  );
}
