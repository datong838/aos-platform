import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getOntologyClient } from "../api/ontologyClient";
import { PageChrome } from "../components/PageChrome";

type Draft = {
  id: string;
  title: string;
  status: string;
  actionTypeId: string;
  objectType?: string;
  objectId?: string;
  createdBy?: string;
  proposed?: Record<string, unknown>;
};

type TabId = "overview" | "changes" | "comments" | "history";

type ReviewTask = {
  id: string;
  badge: "InsightBackfill" | "Action" | "工具";
  badgeColor: string;
  time: string;
  title: string;
  meta: string;
  done?: boolean;
  approved?: boolean;
};

const REVIEW_TASKS: ReviewTask[] = [
  { id: "t1", badge: "InsightBackfill", badgeColor: "#7C3AED", time: "1h", title: "纯度异常 ↔ 设备振动 · 知识回填", meta: "质控 Agent · AIP Logic · 置信 0.93" },
  { id: "t2", badge: "Action", badgeColor: "#D97706", time: "2h", title: "维修派单 · 更新派单规则", meta: "李工 · AIP Logic" },
  { id: "t3", badge: "工具", badgeColor: "#D97706", time: "1d", title: "库存预警 Agent · 新增工具调用", meta: "王产品 · Chatbot Studio" },
  { id: "t4", badge: "工具", badgeColor: "#16A34A", time: "3d", title: "客户画像 Action · 批量标签更新", meta: "已完成 · 写入生产", done: true, approved: true },
];

const TIMELINE = [
  { dotColor: "#7C3AED", title: "提案已创建", meta: "质控 Agent · 1h ago", desc: "由 AIP Logic 触发，置信度 0.93 超过回填阈值。" },
  { dotColor: "#3B82F6", title: "已请求审查", meta: "系统 · 55m ago", desc: "分派给：李工（Ontology Owner）、王产品（AIP 审查er）。" },
  { dotColor: "#9CA3AF", title: "Comment", meta: "李工 · 30m ago", desc: "振动 32Hz 的阈值需要再核对一次设备手册。" },
  { dotColor: "#9CA3AF", title: "Comment", meta: "王产品 · 12m ago", desc: "同意，Evals 已通过，可以批准。" },
  { dotColor: "#F59E0B", title: "Awaiting approval", meta: "2 / 2 reviewers", desc: "待你做出最终决定。", pending: true },
];

const PREVIOUS_DECISIONS = [
  { approved: true, title: "客户画像 Action · 批量标签更新", meta: "3d ago · 已写入生产" },
  { approved: false, title: "价格策略 · 折扣阈值调整", meta: "5d ago · 已丢弃" },
  { approved: true, title: "库存补货 · 安全库存公式更新", meta: "7d ago · 已写入生产" },
];

function draftStatus(s: string): "proposed" | "approved" | "rejected" {
  if (s === "approved") return "approved";
  if (s === "rejected") return "rejected";
  return "proposed";
}

function proposedProps(proposed?: Record<string, unknown>) {
  if (!proposed || Object.keys(proposed).length === 0) return [];
  return Object.entries(proposed).map(([label, value]) => ({
    label,
    value: typeof value === "object" ? JSON.stringify(value) : String(value),
  }));
}

export function DraftInboxPage() {
  const [items, setItems] = useState<Draft[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeReviewId, setActiveReviewId] = useState<string>("t1");
  const [tab, setTab] = useState<TabId>("overview");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function reload() {
    const res = await getOntologyClient().listDrafts();
    setItems((res.items || []) as Draft[]);
  }

  useEffect(() => {
    reload().catch((e) => setErr(String(e.message || e)));
  }, []);

  useEffect(() => {
    if (items.length === 0) {
      setSelectedId(null);
      return;
    }
    if (selectedId && items.some((d) => d.id === selectedId)) return;
    const next = items.find((d) => d.status === "proposed") ?? items[0];
    setSelectedId(next.id);
  }, [items, selectedId]);

  const selected = useMemo(
    () => items.find((d) => d.id === selectedId) ?? null,
    [items, selectedId],
  );

  const pending = items.filter((d) => d.status === "proposed").length;

  async function createSample() {
    setErr(null);
    try {
      const d = (await getOntologyClient().createDraft({
        actionTypeId: "CloseWorkOrder",
        objectType: "WorkOrder",
        objectId: "wo-1001",
        proposed: { reason: "manual" },
        title: "关闭工单提案",
      })) as Draft;
      setMsg(`已创建 ${d.id}（未写生产）`);
      setSelectedId(d.id);
      await reload();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function approve(id: string) {
    setErr(null);
    try {
      const body = await getOntologyClient().approveDraft(id, {
        idempotencyKey: `ui-approve-${id}`,
        allowConflicts: true,
      });
      setMsg(`已批准并写生产 · object=${body.objectId} · lineage=${body.lineageId}`);
      await reload();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function reject(id: string) {
    setErr(null);
    try {
      await getOntologyClient().rejectDraft(id, {});
      setMsg(`已驳回 ${id}`);
      await reload();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  const props = selected ? proposedProps(selected.proposed) : [];
  const st = selected ? draftStatus(selected.status) : "proposed";

  return (
    <PageChrome
      title="Draft 审批台"
      lede="Agent / Action 写入须经 HITL 批准后方可落生产 Ontology；含 Insight Backfill（知识回填）。"
    >
      {msg && (
        <div style={{ background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: 8, padding: 12, marginBottom: 16, fontSize: 13, color: "#1E40AF" }}>
          {msg}
        </div>
      )}
      {err && (
        <div style={{ background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 8, padding: 12, marginBottom: 16, fontSize: 13, color: "#991B1B" }}>
          {err}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {pending > 0 && (
            <span style={{ background: "#FEF3C7", color: "#92400E", padding: "4px 10px", borderRadius: 12, fontSize: 12, fontWeight: 500 }}>
              {pending} 待审
            </span>
          )}
          <span style={{ background: "#F3F4F6", color: "#374151", padding: "4px 10px", borderRadius: 12, fontSize: 12 }}>
            已审 12
          </span>
        </div>
        <button type="button" className="btn" onClick={() => void createSample()}>
          新建提案
        </button>
      </div>

      {/* Draft Dataset 隔离说明 */}
      <div style={{ background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: 8, padding: 12, marginBottom: 16, fontSize: 12, color: "#1E40AF" }}>
        <strong>Draft Dataset 隔离：</strong>
        所有待审写入暂存于独立 Draft Dataset，与生产数据物理隔离；驳回即丢弃，不污染主库。
      </div>

      {/* 三栏布局 */}
      <div style={{ display: "grid", gridTemplateColumns: "260px 1fr 280px", gap: 16, minHeight: 600 }}>
        {/* 左栏：审查er tasks */}
        <aside
          style={{
            border: "1px solid #E5E7EB",
            borderRadius: 8,
            background: "#fff",
            padding: 12,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 8, borderBottom: "1px solid #F3F4F6" }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#111827" }}>审查er tasks</div>
            <div style={{ fontSize: 11, color: "#6B7280" }}>待审 {REVIEW_TASKS.filter((t) => !t.done).length} · 已审 {REVIEW_TASKS.filter((t) => t.done).length}</div>
          </div>
          <div style={{ position: "relative" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="1.5" style={{ position: "absolute", left: 8, top: 9 }}>
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-3-3" strokeLinecap="round" />
            </svg>
            <input
              type="search"
              placeholder="搜索任务…"
              style={{
                width: "100%",
                padding: "6px 8px 6px 28px",
                fontSize: 12,
                border: "1px solid #E5E7EB",
                borderRadius: 6,
                outline: "none",
              }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }}>
            {REVIEW_TASKS.map((task) => {
              const active = task.id === activeReviewId;
              return (
                <button
                  key={task.id}
                  type="button"
                  onClick={() => setActiveReviewId(task.id)}
                  style={{
                    textAlign: "left",
                    padding: 10,
                    borderRadius: 6,
                    border: active ? "1px solid #4F46E5" : "1px solid transparent",
                    background: active ? "#EEF2FF" : task.done ? "#F9FAFB" : "#fff",
                    cursor: "pointer",
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span
                      style={{
                        fontSize: 10,
                        padding: "1px 6px",
                        borderRadius: 3,
                        background: task.done
                          ? task.approved
                            ? "#DCFCE7"
                            : "#FEE2E2"
                          : `${task.badgeColor}1A`,
                        color: task.done
                          ? task.approved
                            ? "#166534"
                            : "#991B1B"
                          : task.badgeColor,
                        fontWeight: 500,
                      }}
                    >
                      {task.done ? (task.approved ? "已批准" : "Rejected") : task.badge}
                    </span>
                    <span style={{ fontSize: 10, color: "#9CA3AF" }}>{task.time}</span>
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 500, color: "#111827", lineHeight: 1.4 }}>
                    {task.title}
                  </div>
                  <div style={{ fontSize: 10, color: "#6B7280" }}>{task.meta}</div>
                </button>
              );
            })}
          </div>
        </aside>

        {/* 中栏：任务详情 */}
        <section style={{ border: "1px solid #E5E7EB", borderRadius: 8, background: "#fff", padding: 16 }}>
          {selected ? (
            <>
              {/* 详情 header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, paddingBottom: 16, borderBottom: "1px solid #F3F4F6" }}>
                <div>
                  <div style={{ fontSize: 11, color: "#9CA3AF", marginBottom: 4 }}>
                    <Link to="/ontology" style={{ color: "#6B7280" }}>Ontology</Link>
                    <span style={{ margin: "0 4px" }}>/</span>
                    <span style={{ color: "#6B7280" }}>Proposals</span>
                    <span style={{ margin: "0 4px" }}>/</span>
                    <span style={{ color: "#111827" }}>{selected.title || selected.id}</span>
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 600, color: "#111827", marginBottom: 6 }}>
                    {selected.title || selected.id}
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12 }}>
                    <span style={{ padding: "2px 8px", borderRadius: 4, background: "#EEF2FF", color: "#4F46E5", fontWeight: 500 }}>
                      {selected.actionTypeId === "CloseWorkOrder" ? "InsightBackfill" : selected.actionTypeId}
                    </span>
                    <span style={{ padding: "2px 8px", borderRadius: 4, background: "#F3F4F6", color: "#374151" }}>draft</span>
                    <span style={{ color: "#6B7280" }}>
                      提交人 {selected.createdBy || "质控 Agent"} · {selected.objectType && selected.objectId ? `${selected.objectType}/${selected.objectId} · ` : ""}来源 AIP Logic
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <Link to="/aip/lineage" style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #E5E7EB", background: "#fff", fontSize: 12, color: "#374151", textDecoration: "none" }}>
                    查看决策链
                  </Link>
                  {st === "proposed" && (
                    <>
                      <button
                        type="button"
                        onClick={() => void reject(selected.id)}
                        style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #E5E7EB", background: "#fff", fontSize: 12, color: "#374151", cursor: "pointer" }}
                      >
                        驳回
                      </button>
                      <button
                        type="button"
                        onClick={() => void approve(selected.id)}
                        style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #4F46E5", background: "#4F46E5", fontSize: 12, color: "#fff", cursor: "pointer" }}
                      >
                        批准并写入
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Tab 导航 */}
              <div style={{ display: "flex", gap: 4, borderBottom: "1px solid #E5E7EB", marginBottom: 16 }}>
                {([
                  { id: "overview", label: "概览" },
                  { id: "changes", label: "变更" },
                  { id: "comments", label: "评论", count: 2 },
                  { id: "history", label: "审查记录" },
                ] as const).map((t) => {
                  const active = tab === t.id;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setTab(t.id)}
                      style={{
                        padding: "8px 12px",
                        fontSize: 13,
                        fontWeight: active ? 500 : 400,
                        color: active ? "#4F46E5" : "#6B7280",
                        background: "none",
                        border: "none",
                        borderBottom: active ? "2px solid #4F46E5" : "2px solid transparent",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      {t.label}
                      {"count" in t && t.count ? (
                        <span
                          style={{
                            fontSize: 10,
                            padding: "0 4px",
                            borderRadius: 8,
                            background: "#F3F4F6",
                            color: "#6B7280",
                          }}
                        >
                          {t.count}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>

              {/* Tab 内容 */}
              {tab === "overview" && (
                <>
                  <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, marginBottom: 12 }}>
                    <div style={{ padding: "8px 12px", borderBottom: "1px solid #F3F4F6", fontSize: 13, fontWeight: 600, color: "#111827" }}>
                      提案概述
                    </div>
                    <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                        <span style={{ color: "#6B7280" }}>提案类型</span>
                        <span style={{ color: "#374151" }}>Insight Backfill（知识回填）</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                        <span style={{ color: "#6B7280" }}>置信度</span>
                        <span style={{ color: "#2563EB", fontWeight: 600 }}>0.93 / 1.00</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                        <span style={{ color: "#6B7280" }}>提交人</span>
                        <span style={{ color: "#374151" }}>{selected.createdBy || "质控 Agent（AIP Logic）"}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                        <span style={{ color: "#6B7280" }}>来源链</span>
                        <Link to="/aip/lineage" style={{ color: "#4F46E5" }}>决策谱系 →</Link>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                        <span style={{ color: "#6B7280" }}>Draft Dataset</span>
                        <span style={{ color: "#374151" }}>draft/insight_2026_07_22（与生产物理隔离）</span>
                      </div>
                    </div>
                  </div>
                  <div style={{ border: "1px solid #E5E7EB", borderRadius: 8 }}>
                    <div style={{ padding: "8px 12px", borderBottom: "1px solid #F3F4F6", fontSize: 13, fontWeight: 600, color: "#111827" }}>
                      影响面 & 风险
                    </div>
                    <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                        <span style={{ color: "#6B7280" }}>影响对象数</span>
                        <span style={{ color: "#374151" }}>1 新建 + 1 关联 + 1 更新 = <b>3</b></span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                        <span style={{ color: "#6B7280" }}>下游管道</span>
                        <span style={{ color: "#374151" }}>2 条（异常告警、月度质控报表）</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, alignItems: "center" }}>
                        <span style={{ color: "#6B7280" }}>权限校验</span>
                        <span style={{ color: "#374151", display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ padding: "1px 6px", borderRadius: 3, background: "#DCFCE7", color: "#166534", fontSize: 10 }}>通过</span>
                          提交人具备 Batch / Equipment 写权限
                        </span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, alignItems: "center" }}>
                        <span style={{ color: "#6B7280" }}>Evals 门控</span>
                        <span style={{ color: "#374151", display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ padding: "1px 6px", borderRadius: 3, background: "#DCFCE7", color: "#166534", fontSize: 10 }}>通过</span>
                          回填准确率 96% &gt; 阈值 90%
                        </span>
                      </div>
                    </div>
                  </div>
                </>
              )}

              {tab === "changes" && (
                <div style={{ border: "1px solid #E5E7EB", borderRadius: 8 }}>
                  <div style={{ padding: "8px 12px", borderBottom: "1px solid #F3F4F6", fontSize: 13, fontWeight: 600, color: "#111827" }}>
                    变更内容 · 3 项变更 · 预计影响 1 条新建对象 + 1 条 Link + 1 字段更新
                  </div>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: "#F9FAFB" }}>
                        <th style={{ padding: "8px 12px", textAlign: "left", width: 90, fontSize: 11, color: "#6B7280", fontWeight: 500 }}>类型</th>
                        <th style={{ padding: "8px 12px", textAlign: "left", fontSize: 11, color: "#6B7280", fontWeight: 500 }}>对象</th>
                        <th style={{ padding: "8px 12px", textAlign: "left", width: 140, fontSize: 11, color: "#6B7280", fontWeight: 500 }}>字段</th>
                        <th style={{ padding: "8px 12px", textAlign: "left", fontSize: 11, color: "#6B7280", fontWeight: 500 }}>变更</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr style={{ borderTop: "1px solid #F3F4F6" }}>
                        <td style={{ padding: "8px 12px" }}>
                          <span style={{ padding: "1px 6px", borderRadius: 3, background: "#DCFCE7", color: "#166534", fontSize: 10 }}>新建</span>
                        </td>
                        <td style={{ padding: "8px 12px", color: "#4F46E5" }}><a href="#" style={{ color: "#4F46E5" }}>Insight</a></td>
                        <td style={{ padding: "8px 12px", color: "#9CA3AF" }}>—</td>
                        <td style={{ padding: "8px 12px", color: "#374151" }}>新建 Insight: 纯度异常 ↔ 设备振动相关性</td>
                      </tr>
                      <tr style={{ borderTop: "1px solid #F3F4F6" }}>
                        <td style={{ padding: "8px 12px" }}>
                          <span style={{ padding: "1px 6px", borderRadius: 3, background: "#DBEAFE", color: "#1E40AF", fontSize: 10 }}>关联</span>
                        </td>
                        <td style={{ padding: "8px 12px", color: "#4F46E5" }}><a href="#" style={{ color: "#4F46E5" }}>Batch#A</a> ↔ <a href="#" style={{ color: "#4F46E5" }}>Equipment#B</a></td>
                        <td style={{ padding: "8px 12px", color: "#9CA3AF" }}>—</td>
                        <td style={{ padding: "8px 12px", color: "#374151" }}>建立双向关联</td>
                      </tr>
                      <tr style={{ borderTop: "1px solid #F3F4F6" }}>
                        <td style={{ padding: "8px 12px" }}>
                          <span style={{ padding: "1px 6px", borderRadius: 3, background: "#FEF3C7", color: "#92400E", fontSize: 10 }}>更新</span>
                        </td>
                        <td style={{ padding: "8px 12px", color: "#4F46E5" }}><a href="#" style={{ color: "#4F46E5" }}>Batch#A</a></td>
                        <td style={{ padding: "8px 12px", color: "#374151" }}>anomaly_note</td>
                        <td style={{ padding: "8px 12px", color: "#374151" }}>null → "振动频率 32Hz 触发纯度偏差"</td>
                      </tr>
                    </tbody>
                  </table>
                  {props.length > 0 && (
                    <div style={{ borderTop: "1px solid #F3F4F6", padding: 12 }}>
                      <div style={{ fontSize: 12, fontWeight: 500, color: "#374151", marginBottom: 8 }}>拟写入字段</div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 12 }}>
                        {props.map((p) => (
                          <div key={p.label} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                            <span style={{ color: "#6B7280" }}>{p.label}</span>
                            <span style={{ color: "#374151" }}>{p.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {tab === "comments" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, padding: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 500, color: "#111827" }}>李工</span>
                      <span style={{ fontSize: 11, color: "#9CA3AF" }}>30m ago</span>
                    </div>
                    <p style={{ fontSize: 12, color: "#374151", margin: 0, lineHeight: 1.6 }}>振动 32Hz 的阈值需要再核对一次设备手册。</p>
                  </div>
                  <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, padding: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 500, color: "#111827" }}>王产品</span>
                      <span style={{ fontSize: 11, color: "#9CA3AF" }}>12m ago</span>
                    </div>
                    <p style={{ fontSize: 12, color: "#374151", margin: 0, lineHeight: 1.6 }}>同意，Evals 已通过，可以批准。</p>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      type="text"
                      placeholder="写下你的评论…"
                      style={{ flex: 1, padding: "8px 12px", fontSize: 12, border: "1px solid #E5E7EB", borderRadius: 6, outline: "none" }}
                    />
                    <button
                      type="button"
                      style={{ padding: "8px 16px", fontSize: 12, borderRadius: 6, border: "1px solid #4F46E5", background: "#4F46E5", color: "#fff", cursor: "pointer" }}
                    >
                      发表
                    </button>
                  </div>
                </div>
              )}

              {tab === "history" && (
                <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, padding: 12 }}>
                  <div style={{ fontSize: 12, color: "#6B7280", lineHeight: 1.6 }}>
                    <div style={{ marginBottom: 8 }}>
                      <span style={{ color: "#111827", fontWeight: 500 }}>提案已创建</span> · 质控 Agent · 1h ago
                    </div>
                    <div style={{ marginBottom: 8 }}>
                      <span style={{ color: "#111827", fontWeight: 500 }}>已请求审查</span> · 系统 · 55m ago
                    </div>
                    <div>
                      <span style={{ color: "#111827", fontWeight: 500 }}>Awaiting approval</span> · 2 / 2 reviewers
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ padding: 40, textAlign: "center", color: "#9CA3AF", fontSize: 13 }}>
              队列为空 · 可新建提案
            </div>
          )}
        </section>

        {/* 右栏：活动记录 */}
        <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, background: "#fff", padding: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#111827", marginBottom: 12, paddingBottom: 8, borderBottom: "1px solid #F3F4F6" }}>
              活动记录
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {TIMELINE.map((item, idx) => (
                <div key={idx} style={{ display: "flex", gap: 8 }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                    <div
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        background: item.dotColor,
                        flexShrink: 0,
                        boxShadow: item.pending ? `0 0 0 4px ${item.dotColor}33` : "none",
                      }}
                    />
                    {idx < TIMELINE.length - 1 && (
                      <div style={{ width: 2, flex: 1, background: "#F3F4F6", minHeight: 16 }} />
                    )}
                  </div>
                  <div style={{ flex: 1, paddingBottom: 4 }}>
                    <div style={{ fontSize: 12, fontWeight: 500, color: "#111827" }}>{item.title}</div>
                    <div style={{ fontSize: 10, color: "#9CA3AF", margin: "2px 0 4px" }}>{item.meta}</div>
                    <div style={{ fontSize: 11, color: "#6B7280", lineHeight: 1.5 }}>{item.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, background: "#fff", padding: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#111827", marginBottom: 12, paddingBottom: 8, borderBottom: "1px solid #F3F4F6" }}>
              Previous decisions
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {PREVIOUS_DECISIONS.map((d, idx) => (
                <div key={idx}>
                  <span
                    style={{
                      fontSize: 10,
                      padding: "1px 6px",
                      borderRadius: 3,
                      marginRight: 6,
                      background: d.approved ? "#DCFCE7" : "#FEE2E2",
                      color: d.approved ? "#166534" : "#991B1B",
                      fontWeight: 500,
                    }}
                  >
                    {d.approved ? "已批准" : "Rejected"}
                  </span>
                  <div style={{ fontSize: 12, fontWeight: 500, color: "#111827", marginTop: 4 }}>{d.title}</div>
                  <div style={{ fontSize: 10, color: "#9CA3AF", marginTop: 2 }}>{d.meta}</div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>

      {/* 底部链接 */}
      <div
        style={{
          display: "flex",
          gap: 16,
          padding: "12px 0",
          marginTop: 16,
          borderTop: "1px solid #F3F4F6",
          fontSize: 12,
        }}
      >
        <Link to="/aip/lineage" style={{ color: "#4F46E5" }}>决策谱系 →</Link>
        <Link to="/workshop/inbox" style={{ color: "#4F46E5" }}>运营 Inbox →</Link>
      </div>
    </PageChrome>
  );
}
