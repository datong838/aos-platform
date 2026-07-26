/**
 * E2.5 — AIP 可观测性页面视觉对齐
 *
 * 4 Tabs: 函数代码 / 测试运行函数 / 运行历史 / 删除代码函数
 * 运行历史 Tab: 三栏画布布局 + 底部执行追踪时间线
 */
import { useState } from "react";
import { PageChrome } from "../../components/PageChrome";

type Tab = "code" | "test" | "history" | "delete";

export function ObservabilityPage() {
  const [tab, setTab] = useState<Tab>("history");
  const [selectedNode, setSelectedNode] = useState<string | null>("sendEmailWithTaskPriority");

  const tabs: { key: Tab; label: string }[] = [
    { key: "code", label: "函数代码" },
    { key: "test", label: "测试运行函数" },
    { key: "history", label: "运行历史" },
    { key: "delete", label: "删除代码函数" },
  ];

  const nodeTypes = [
    { name: "动作", count: 5 },
    { name: "AIP 逻辑函数", count: 1 },
    { name: "函数", count: 4 },
    { name: "语言模型", count: 2, highlight: true },
    { name: "Webhook", count: 1 },
  ];

  const traceBars = [
    { name: "sendEmailWith...", label: "请求", left: 0, width: 100, level: 0, type: "parent", duration: "12.261s" },
    { name: "用户代码", left: 4, width: 95, level: 1, type: "nested", duration: "11.65s" },
    { name: "加载中", left: 4, width: 12, level: 1, type: "nested", duration: "1.47s" },
    { name: "关联对象", left: 4, width: 15, level: 1, type: "blue", duration: "1.84s" },
    { name: "函数调用", left: 16, width: 55, level: 1, type: "nested", duration: "6.75s" },
    { name: "Claude 3.5", left: 16, width: 50, level: 2, type: "ai", duration: "6.0s · 998 tokens" },
    { name: "sendEmail", left: 75, width: 20, level: 1, type: "nested", duration: "2.45s" },
  ];

  return (
    <PageChrome title="AIP 可观测性" lede="运行历史 · 函数代码 · 测试运行 · 依赖检查">
      {/* Tab bar */}
      <div style={{ display: "flex", gap: 24, borderBottom: "1px solid var(--aos-border)", marginBottom: 0, paddingLeft: 4 }}>
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: "10px 0",
              fontSize: 13,
              fontWeight: tab === t.key ? 500 : 400,
              border: "none",
              borderBottom: tab === t.key ? "2px solid var(--aos-indigo)" : "2px solid transparent",
              background: "none",
              color: tab === t.key ? "var(--aos-indigo)" : "var(--aos-muted)",
              cursor: "pointer",
              marginBottom: "-1px",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 函数代码 Tab */}
      {tab === "code" && (
        <div style={{ padding: 24, background: "var(--aos-bg-secondary)", minHeight: 500 }}>
          <div style={{ maxWidth: 768, margin: "0 auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>函数源代码</h3>
                <p style={{ fontSize: 12, color: "var(--aos-muted)", margin: "4px 0 0 0" }}>Python · 后端引擎：PythonBuilder + FunctionsRuntime</p>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, background: "#DBEAFE", color: "#1D4ED8" }}>Python</span>
                <button style={{ fontSize: 12, padding: "6px 12px", border: "1px solid var(--aos-border)", borderRadius: 6, background: "#fff", cursor: "pointer", color: "var(--aos-text)" }}>校验</button>
                <button style={{ fontSize: 12, padding: "6px 12px", border: "none", borderRadius: 6, background: "var(--aos-indigo)", color: "#fff", cursor: "pointer", fontWeight: 500 }}>保存</button>
              </div>
            </div>
            <div style={{ background: "#0D1117", borderRadius: 8, padding: 16, overflowX: "auto", marginBottom: 16 }}>
              <pre style={{ fontSize: 12, color: "#C9D1D9", fontFamily: "monospace", lineHeight: 1.6, margin: 0 }}>
{`def sendEmailWithTaskPriority(to_email, subject, body, task_urgency):
    # 根据 urgency 选择模板和发送通道
    if task_urgency == "high":
        template = load_template("urgent_notification")
        channel = "priority_queue"
    else:
        template = load_template("standard_notification")
        channel = "default_queue"

    # 调用 LLM 生成个性化摘要
    summary = llm_summarize(body, model="claude-3.5-haiku")

    return send_email(
        to=to_email,
        subject=subject,
        body=template.render(summary=summary),
        channel=channel
    )`}
              </pre>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              <div style={{ background: "#fff", border: "1px solid var(--aos-border)", borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 11, color: "var(--aos-muted)", marginBottom: 6 }}>安全约束</div>
                <div style={{ fontSize: 12, color: "var(--aos-text)", lineHeight: 1.6 }}>
                  MAX_CODE_SIZE: 5000字符<br/>
                  MAX_AST_NODES: 1000<br/>
                  TIMEOUT: 5.0s
                </div>
              </div>
              <div style={{ background: "#fff", border: "1px solid var(--aos-border)", borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 11, color: "var(--aos-muted)", marginBottom: 6 }}>黑名单</div>
                <div style={{ fontSize: 12, color: "var(--aos-text)", lineHeight: 1.6 }}>
                  import os / subprocess<br/>
                  __import__ / eval / exec<br/>
                  __dunder__ 方法
                </div>
              </div>
              <div style={{ background: "#fff", border: "1px solid var(--aos-border)", borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 11, color: "var(--aos-muted)", marginBottom: 6 }}>TS 签名预览</div>
                <div style={{ fontSize: 11, color: "var(--aos-text)", fontFamily: "monospace", lineHeight: 1.5 }}>
                  sendEmailWithTaskPriority(<br/>
                  &nbsp;&nbsp;to_email: string,<br/>
                  &nbsp;&nbsp;subject: string<br/>
                  ): SendResult
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 测试运行函数 Tab */}
      {tab === "test" && (
        <div style={{ padding: 24, background: "var(--aos-bg-secondary)", minHeight: 500 }}>
          <div style={{ maxWidth: 768, margin: "0 auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>测试用例</h3>
                <p style={{ fontSize: 12, color: "var(--aos-muted)", margin: "4px 0 0 0" }}>后端引擎：FunctionsTestDebugEngine</p>
              </div>
              <button style={{ fontSize: 12, padding: "6px 12px", border: "none", borderRadius: 6, background: "var(--aos-indigo)", color: "#fff", cursor: "pointer", fontWeight: 500 }}>+ 新建测试</button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { name: "test_high_urgency_uses_priority_queue", status: "passed", assertions: 3, duration: "45ms" },
                { name: "test_low_urgency_uses_default_queue", status: "passed", assertions: 2, duration: "32ms" },
                { name: "test_llm_summary_not_empty", status: "failed", assertions: 1, duration: "6012ms", error: "AssertionError: summary 为空字符串" },
                { name: "test_template_rendering", status: "pending", assertions: 2, duration: "未运行" },
              ].map((tc) => (
                <div key={tc.name} style={{ background: "#fff", border: `1px solid ${tc.status === "failed" ? "#FECACA" : tc.status === "passed" ? "#BBF7D0" : "var(--aos-border)"}`, borderRadius: 8, padding: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                    <span style={{ width: 20, height: 20, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", background: tc.status === "passed" ? "#DCFCE7" : tc.status === "failed" ? "#FEE2E2" : "#F3F4F6", color: tc.status === "passed" ? "#16A34A" : tc.status === "failed" ? "#DC2626" : "#9CA3AF", fontSize: 12 }}>
                      {tc.status === "passed" ? "✓" : tc.status === "failed" ? "✕" : "○"}
                    </span>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)" }}>{tc.name}</div>
                      <div style={{ fontSize: 11, color: "var(--aos-muted)", marginTop: 2 }}>
                        Python · {tc.assertions} assertions · {tc.duration}
                      </div>
                      {tc.error && (
                        <div style={{ fontSize: 11, color: "#EF4444", marginTop: 4 }}>{tc.error}</div>
                      )}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                    <span style={{ fontSize: 11, fontWeight: 500, color: tc.status === "passed" ? "#16A34A" : tc.status === "failed" ? "#DC2626" : "#9CA3AF" }}>
                      {tc.status === "passed" ? "PASSED" : tc.status === "failed" ? "FAILED" : "PENDING"}
                    </span>
                    <button style={{ fontSize: 11, color: "var(--aos-indigo)", background: "none", border: "none", cursor: "pointer", padding: 0 }}>运行</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 运行历史 Tab */}
      {tab === "history" && (
        <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 280px)", minHeight: 500 }}>
          {/* 三栏布局：节点类型 + 画布 + 节点详情 */}
          <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
            {/* 左侧：节点类型面板 */}
            <aside style={{ width: 160, borderRight: "1px solid var(--aos-border)", background: "#fff", overflow: "auto", flexShrink: 0 }}>
              <div style={{ padding: 12 }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: "var(--aos-muted)", letterSpacing: "0.05em", marginBottom: 10 }}>节点类型</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {nodeTypes.map((nt) => (
                    <div key={nt.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 8px", borderRadius: 4, cursor: "pointer" }}>
                      <span style={{ fontSize: 12, color: "var(--aos-text)" }}>{nt.name}</span>
                      <span style={{ fontSize: 12, color: nt.highlight ? "#0891B2" : "var(--aos-muted)", fontWeight: nt.highlight ? 500 : 400 }}>{nt.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </aside>

            {/* 中间：画布区域 */}
            <div style={{ flex: 1, position: "relative", overflow: "auto", background: "linear-gradient(rgba(200,200,200,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(200,200,200,0.3) 1px, transparent 1px)", backgroundSize: "20px 20px", minHeight: 0 }}>
              {/* 工具栏 */}
              <div style={{ position: "absolute", top: 16, left: 16, display: "flex", alignItems: "center", gap: 2, background: "#fff", borderRadius: 8, boxShadow: "0 1px 3px rgba(0,0,0,0.1)", border: "1px solid var(--aos-border)", padding: 4, zIndex: 10 }}>
                <button style={{ padding: 6, background: "none", border: "none", borderRadius: 4, cursor: "pointer", color: "var(--aos-muted)" }} title="撤销">↶</button>
                <button style={{ padding: 6, background: "none", border: "none", borderRadius: 4, cursor: "pointer", color: "var(--aos-muted)" }} title="重做">↷</button>
                <span style={{ width: 1, height: 16, background: "var(--aos-border)" }}></span>
                <button style={{ padding: 6, background: "none", border: "none", borderRadius: 4, cursor: "pointer", color: "var(--aos-muted)" }} title="缩小">−</button>
                <button style={{ padding: 6, background: "none", border: "none", borderRadius: 4, cursor: "pointer", color: "var(--aos-muted)" }} title="放大">+</button>
                <button style={{ padding: 6, background: "none", border: "none", borderRadius: 4, cursor: "pointer", color: "var(--aos-muted)" }} title="布局">⊞</button>
              </div>

              {/* 节点 - Claude */}
              <div style={{ position: "absolute", left: 80, top: 60, minWidth: 180, borderRadius: 8, background: "linear-gradient(135deg, #06b6d4, #0891b2)", border: "2px solid #22d3ee", boxShadow: "0 2px 8px rgba(0,0,0,0.1)" }}>
                <div style={{ display: "flex", alignItems: "center", padding: "8px 12px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>
                  <span style={{ fontSize: 14 }}>⬢</span>
                  <span style={{ marginLeft: 8, fontSize: 12, fontWeight: 500, color: "#fff" }}>Claude 3.5 Haiku</span>
                </div>
                <div style={{ padding: "8px 12px", fontSize: 12, color: "rgba(255,255,255,0.8)" }}>Anthropic 模型</div>
              </div>

              {/* 节点 - sendEmail */}
              <div style={{ position: "absolute", left: 300, top: 40, minWidth: 180, borderRadius: 8, background: "#fff", border: "1px solid var(--aos-border)", boxShadow: "0 2px 8px rgba(0,0,0,0.1)" }}>
                <div style={{ display: "flex", alignItems: "center", padding: "8px 12px", borderBottom: "1px solid #F3F4F6" }}>
                  <span style={{ width: 20, height: 20, borderRadius: 4, background: "#F3F4F6", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "var(--aos-muted)", fontFamily: "monospace" }}>fx</span>
                  <span style={{ marginLeft: 8, fontSize: 12, fontWeight: 500, color: "var(--aos-text)" }}>sendEmail</span>
                </div>
                <div style={{ padding: "8px 12px", fontSize: 12, color: "var(--aos-muted)" }}>2 输入 → 2+ 输出</div>
              </div>

              {/* 节点 - sendEmailWithTaskPriority (选中) */}
              <div style={{ position: "absolute", left: 300, top: 160, minWidth: 200, borderRadius: 8, background: "#fff", border: "2px solid #F59E0B", boxShadow: "0 0 0 2px rgba(245,158,11,0.3), 0 4px 12px rgba(245,158,11,0.3)" }} onClick={() => setSelectedNode("sendEmailWithTaskPriority")}>
                <div style={{ display: "flex", alignItems: "center", padding: "8px 12px", borderBottom: "1px solid #F3F4F6" }}>
                  <span style={{ width: 20, height: 20, borderRadius: 4, background: "#F3F4F6", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "var(--aos-muted)", fontFamily: "monospace" }}>fx</span>
                  <span style={{ marginLeft: 8, fontSize: 12, fontWeight: 500, color: "var(--aos-text)" }}>sendEmailWithTaskPriority</span>
                </div>
                <div style={{ padding: "8px 12px", fontSize: 12, color: "var(--aos-muted)" }}>2 输入 → 2+ 输出</div>
                {/* 悬浮工具栏 */}
                <div style={{ position: "absolute", bottom: -12, left: "50%", transform: "translateX(-50%)", display: "flex", gap: 4 }}>
                  <button style={{ padding: "2px 8px", fontSize: 10, background: "#fff", border: "1px solid var(--aos-border)", borderRadius: 4, color: "var(--aos-text)", boxShadow: "0 1px 2px rgba(0,0,0,0.1)", cursor: "pointer" }}>详情</button>
                  <button style={{ padding: "2px 8px", fontSize: 10, background: "#fff", border: "1px solid var(--aos-border)", borderRadius: 4, color: "var(--aos-text)", boxShadow: "0 1px 2px rgba(0,0,0,0.1)", cursor: "pointer" }}>固定</button>
                </div>
              </div>

              {/* 连线 SVG */}
              <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none", zIndex: 0 }}>
                <path d="M 180 100 C 240 100, 240 80, 300 80" stroke="#F59E0B" strokeWidth="2" fill="none" strokeLinecap="round" />
                <path d="M 180 100 C 240 100, 240 180, 300 180" stroke="#F59E0B" strokeWidth="2" fill="none" strokeLinecap="round" />
              </svg>
            </div>

            {/* 右侧：节点详情面板 */}
            <aside style={{ width: 256, borderLeft: "1px solid var(--aos-border)", background: "#fff", overflow: "auto", flexShrink: 0 }}>
              <div style={{ padding: 16 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>节点详情</h3>
                <p style={{ fontSize: 12, color: "var(--aos-muted)", margin: "4px 0 0 0" }}>{selectedNode || "未选中节点"}</p>
                <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12 }}>
                    <span style={{ color: "var(--aos-muted)" }}>节点类型</span>
                    <span style={{ color: "var(--aos-text)", fontWeight: 500 }}>函数</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12 }}>
                    <span style={{ color: "var(--aos-muted)" }}>输入数量</span>
                    <span style={{ color: "var(--aos-text)" }}>2</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12 }}>
                    <span style={{ color: "var(--aos-muted)" }}>输出数量</span>
                    <span style={{ color: "var(--aos-text)" }}>2+</span>
                  </div>
                </div>
                <div style={{ marginTop: 24 }}>
                  <button style={{ width: "100%", padding: "8px 12px", fontSize: 12, fontWeight: 500, color: "var(--aos-indigo)", background: "#EEF2FF", borderRadius: 8, border: "none", cursor: "pointer" }}>
                    查看代码
                  </button>
                </div>
              </div>
            </aside>
          </div>

          {/* 底部：执行追踪时间线 */}
          <div style={{ borderTop: "1px solid var(--aos-border)", background: "#fff", flexShrink: 0, height: 200, minHeight: 200, overflowY: "auto" }}>
            <div style={{ padding: "12px 16px", borderBottom: "1px solid #F3F4F6", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h4 style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)", margin: 0 }}>执行追踪</h4>
              <div style={{ display: "flex", gap: 12, fontSize: 12, color: "var(--aos-muted)" }}>
                <span>总耗时: 12.261s</span>
                <span style={{ color: "var(--aos-border)" }}>|</span>
                <span style={{ color: "#0891B2" }}>2 个 LLM 调用</span>
                <span style={{ color: "var(--aos-border)" }}>|</span>
                <span>13 个 Span</span>
              </div>
            </div>
            <div style={{ padding: 16, overflowX: "auto" }}>
              {/* 时间刻度 */}
              <div style={{ display: "flex", alignItems: "center", fontSize: 10, color: "var(--aos-muted)", marginBottom: 8, paddingLeft: 80 }}>
                <span style={{ width: 64 }}>0s</span>
                <span style={{ width: 64 }}>3s</span>
                <span style={{ width: 64 }}>6s</span>
                <span style={{ width: 64 }}>9s</span>
                <span style={{ width: 64 }}>12s</span>
              </div>
              {/* Trace Bars */}
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                {traceBars.map((bar, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", cursor: "pointer", padding: "2px 0" }}>
                    <span style={{ width: 80 - bar.level * 16, fontSize: 12, color: bar.type === "ai" ? "#0891B2" : "var(--aos-text)", paddingRight: 8, textAlign: "right", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {bar.name}
                    </span>
                    <div style={{ flex: 1, height: bar.type === "parent" ? 24 : 20, position: "relative" }}>
                      <div
                        style={{
                          position: "absolute",
                          left: `${bar.left}%`,
                          width: `${bar.width}%`,
                          height: "100%",
                          borderRadius: 4,
                          background: bar.type === "ai"
                            ? "linear-gradient(90deg, #06b6d4, #0891b2)"
                            : bar.type === "blue"
                              ? "#93c5fd"
                              : bar.type === "parent"
                                ? "#E5E7EB"
                                : "#D1D5DB",
                          display: "flex",
                          alignItems: "center",
                          paddingLeft: 8,
                          fontSize: 10,
                          color: bar.type === "ai" ? "#fff" : "#4B5563",
                          fontWeight: bar.type === "ai" ? 500 : 400,
                        }}
                      >
                        {bar.label && bar.type === "parent" && bar.label}
                        {bar.type === "ai" && bar.duration}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 删除代码函数 Tab */}
      {tab === "delete" && (
        <div style={{ padding: 24, background: "var(--aos-bg-secondary)", minHeight: 500 }}>
          <div style={{ maxWidth: 576, margin: "0 auto" }}>
            <div>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>删除函数</h3>
              <p style={{ fontSize: 12, color: "var(--aos-muted)", margin: "4px 0 0 0" }}>后端：FunctionsRuntime.delete() + 依赖检查 + 级联清理</p>
            </div>

            {/* 依赖检查 */}
            <div style={{ background: "#fff", border: "1px solid var(--aos-border)", borderRadius: 8, padding: 16, marginTop: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h4 style={{ fontSize: 12, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>依赖检查结果</h4>
                <span style={{ fontSize: 11, color: "#D97706", fontWeight: 500 }}>2 个活跃引用</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 10px", background: "#F9FAFB", borderRadius: 6, fontSize: 12 }}>
                  <div>
                    <span style={{ color: "var(--aos-text)", fontWeight: 500 }}>AIP Logic: 订单审批流程</span>
                    <span style={{ color: "var(--aos-muted)", marginLeft: 8, fontSize: 11 }}>block_id: blk_005 · use_llm</span>
                  </div>
                  <a style={{ color: "var(--aos-indigo)", fontSize: 11, textDecoration: "none" }}>查看</a>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 10px", background: "#F9FAFB", borderRadius: 6, fontSize: 12 }}>
                  <div>
                    <span style={{ color: "var(--aos-text)", fontWeight: 500 }}>Pipeline: 邮件通知转换</span>
                    <span style={{ color: "var(--aos-muted)", marginLeft: 8, fontSize: 11 }}>stage: transform · function_ref</span>
                  </div>
                  <a style={{ color: "var(--aos-indigo)", fontSize: 11, textDecoration: "none" }}>查看</a>
                </div>
              </div>
            </div>

            {/* 级联清理范围 */}
            <div style={{ background: "#fff", border: "1px solid var(--aos-border)", borderRadius: 8, padding: 16, marginTop: 16 }}>
              <h4 style={{ fontSize: 12, fontWeight: 600, color: "var(--aos-text)", margin: "0 0 12px 0" }}>级联清理范围</h4>
              <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12, color: "var(--aos-text)" }}>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <span style={{ marginRight: 8, color: "#EF4444" }}>✕</span>
                  函数本体：RuntimeFunction(fn_id=fn_001)
                </div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <span style={{ marginRight: 8, color: "#EF4444" }}>✕</span>
                  代码位置记录：CodeLocation(repo, path, line)
                </div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <span style={{ marginRight: 8, color: "#EF4444" }}>✕</span>
                  测试用例：4 条 FunctionTestCase
                </div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <span style={{ marginRight: 8, color: "#EF4444" }}>✕</span>
                  性能 Profile：2 条 ProfileResult
                </div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <span style={{ marginRight: 8, color: "#10B981" }}>✓</span>
                  审计记录保留：写入 DecisionRecord
                </div>
              </div>
            </div>

            {/* 确认按钮 */}
            <div style={{ background: "#FEF2F2", border: "1px solid #FCA5A5", borderRadius: 8, padding: 16, marginTop: 16 }}>
              <div style={{ display: "flex", gap: 12 }}>
                <span style={{ fontSize: 20, color: "#DC2626", flexShrink: 0 }}>⚠</span>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 12, color: "#7F1D1D", fontWeight: 500, margin: 0 }}>此操作不可逆！</p>
                  <p style={{ fontSize: 11, color: "#B91C1C", margin: "4px 0 0 0" }}>当前函数有 <strong>2 个活跃引用</strong>。删除后引用方将出现 broken reference。建议先解除依赖再删除。</p>
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    <button style={{ padding: "6px 12px", fontSize: 12, fontWeight: 500, color: "#B91C1C", background: "#fff", border: "1px solid #FCA5A5", borderRadius: 6, cursor: "pointer" }}>强制删除</button>
                    <button style={{ padding: "6px 12px", fontSize: 12, fontWeight: 500, color: "var(--aos-muted)", background: "#fff", border: "1px solid var(--aos-border)", borderRadius: 6, cursor: "pointer" }}>取消</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageChrome>
  );
}
