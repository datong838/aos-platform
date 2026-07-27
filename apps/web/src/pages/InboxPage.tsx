import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import {
  addFilter,
  canAddFilter,
  SELECTION_LIMIT,
  type SelectionFilter,
} from "../selection";
import { PaginationGuardBanner } from "../paginationGuard";

type Row = Record<string, string>;

type ExecuteOut = {
  draftId?: string;
  id?: string;
  status?: string;
  productionWritten?: boolean;
  route?: string;
  idempotentReplay?: boolean;
};

type ActivityLog = {
  id: string;
  text: string;
  actor: string;
  time: string;
  color: string;
};

const PRESET_FILTERS: { id: string; label: string; field: string; value: string; group: string }[] = [
  { id: "status-open", label: "异常", field: "status", value: "open", group: "状态" },
  { id: "status-handled", label: "已处理", field: "status", value: "handled", group: "状态" },
  { id: "status-closed", label: "已关闭", field: "status", value: "closed", group: "状态" },
  { id: "prio-high", label: "高", field: "priority", value: "high", group: "优先级" },
  { id: "prio-mid", label: "中", field: "priority", value: "mid", group: "优先级" },
  { id: "prio-low", label: "低", field: "priority", value: "low", group: "优先级" },
];

function priorityBadge(v: string) {
  const p = (v || "").toLowerCase();
  if (p === "high") return { bg: "#FEE2E2", color: "#DC2626", label: "高" };
  if (p === "mid") return { bg: "#FEF3C7", color: "#D97706", label: "中" };
  return { bg: "#F3F4F6", color: "#6B7280", label: p === "low" ? "低" : "—" };
}

/** 80 · 对齐 workshop-module.html · 三栏 + Filter + Object Table + Object View + 活动日志 */
export function InboxPage() {
  const [filters, setFilters] = useState<SelectionFilter[]>([]);
  const [presetOn, setPresetOn] = useState<Record<string, boolean>>({});
  const [field, setField] = useState("site");
  const [value, setValue] = useState("DC-East");
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [gateMsg, setGateMsg] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [wikiText, setWikiText] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const displayTotal = total;

  const selectedRows = useMemo(
    () => rows.filter((r) => selected.has(String(r.id))),
    [rows, selected],
  );

  const activeRow = useMemo(() => {
    if (activeId) {
      const hit = rows.find((r) => String(r.id) === activeId);
      if (hit) return hit;
    }
    return selectedRows[0] || rows[0] || null;
  }, [activeId, rows, selectedRows]);

  const activityLog: ActivityLog[] = useMemo(() => {
    if (!activeRow) return [];
    return [
      { id: "a1", text: "风控告警触发", actor: "系统", time: "18:32", color: "#DC2626" },
      { id: "a2", text: "Wiki 规则匹配", actor: "Agent", time: "18:33", color: "#F59E0B" },
      { id: "a3", text: "等待人工审核", actor: "系统", time: "18:34", color: "#3B82F6" },
    ];
  }, [activeRow]);

  async function runQuery(nextFilters: SelectionFilter[]) {
    setError(null);
    try {
      const res = await apiPost<{
        items: Row[];
        total: number;
      }>("/v1/object-sets/query", {
        filters: nextFilters,
        page: 1,
        pageSize: 50,
      });
      setRows(res.items);
      setTotal(res.total);
      setSelected(new Set());
      if (res.items.length > 0) setActiveId(String(res.items[0].id));
      else setActiveId(null);
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  }

  useEffect(() => {
    void runQuery([]);
  }, []);

  useEffect(() => {
    if (!activeRow?.id) {
      setWikiText(null);
      return;
    }
    const oid = String(activeRow.id);
    apiGet<{ body?: { summary?: string; text?: string } | string }>(
      `/v1/wiki/WorkOrder/${encodeURIComponent(oid)}`,
    )
      .then((w) => {
        const body = w.body;
        if (typeof body === "string") setWikiText(body);
        else if (body && typeof body === "object") {
          setWikiText(String(body.summary || body.text || JSON.stringify(body)));
        } else setWikiText(null);
      })
      .catch(() => setWikiText(null));
  }, [activeRow?.id]);

  function syncPresets(nextPreset: Record<string, boolean>) {
    const fromPresets = PRESET_FILTERS.filter((p) => nextPreset[p.id]).map((p) => ({
      field: p.field,
      value: p.value,
    }));
    const custom = filters.filter(
      (f) => !PRESET_FILTERS.some((p) => p.field === f.field && p.value === f.value),
    );
    const merged = [...fromPresets, ...custom];
    setFilters(merged);
    void runQuery(merged);
  }

  function togglePreset(id: string) {
    const next = { ...presetOn, [id]: !presetOn[id] };
    setPresetOn(next);
    syncPresets(next);
  }

  function onAdd(e: FormEvent) {
    e.preventDefault();
    const next = { field, value };
    const gate = canAddFilter(filters, next);
    if (!gate.ok) {
      setGateMsg(gate.reason);
      return;
    }
    setGateMsg(null);
    try {
      const updated = addFilter(filters, next);
      setFilters(updated);
      void runQuery(updated);
    } catch (err) {
      setGateMsg(String((err as Error).message));
    }
  }

  function toggleRow(id: string) {
    setActiveId(id);
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else {
        if (n.size >= 10) {
          setGateMsg("Selection≤10（对齐蓝图运营台）");
          return prev;
        }
        n.add(id);
      }
      setGateMsg(null);
      return n;
    });
  }

  async function proposeClose(targetRows?: Row[]) {
    const targets = targetRows || selectedRows;
    if (targets.length === 0) {
      setGateMsg("请先选中工单");
      return;
    }
    setBusy(true);
    setError(null);
    setActionMsg(null);
    try {
      const results: string[] = [];
      for (const row of targets) {
        const oid = String(row.id);
        const key = `inbox-close-${oid}-${Date.now()}`;
        const out = await apiPost<ExecuteOut>(
          "/v1/actions/execute",
          {
            actionTypeId: "CloseWorkOrder",
            objectType: "WorkOrder",
            objectId: oid,
            payload: {
              reason: "ops-inbox-appeal",
              status: "pending_close",
              title: row.title,
              site: row.site,
            },
            autoApprove: false,
          },
          { "Idempotency-Key": key },
        );
        const draftId = out.draftId || out.id || "?";
        results.push(
          out.idempotentReplay
            ? `${oid}·幂等回放 draft=${draftId}`
            : `${oid}→Draft ${draftId}（未写生产）`,
        );
      }
      setActionMsg(results.join(" · "));
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  const buddyHref = activeRow
    ? `/workshop/buddy?order=${encodeURIComponent(String(activeRow.id))}&assist=1`
    : "/workshop/buddy";

  const filterGroups = ["状态", "优先级"];
  const customFilters = filters.filter(
    (f) => !PRESET_FILTERS.some((p) => p.field === f.field && p.value === f.value),
  );

  return (
    <PageChrome
      title="风险告警管理"
      lede="Filter · Object Table · Object View · Action→Draft HITL"
    >
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        {/* Top bar */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 20px",
          borderBottom: "1px solid #E5E7EB",
          background: "white",
          borderRadius: 2,
          marginBottom: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6B7280" strokeWidth="1.5">
              <path d="M4 4h6l2 3h8v13H4V4z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span style={{ fontSize: 14, fontWeight: 500, color: "#111827" }}>风险告警管理 · Risk Alert Manager</span>
            <span style={{ fontSize: 11, color: "#6B7280", padding: "2px 8px", background: "#F3F4F6", borderRadius: 4 }}>v2 · 已发布</span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Link to="/workshop/canvas" style={{ padding: "5px 12px", fontSize: 12, border: "1px solid var(--aos-border)", borderRadius: 2, background: "var(--aos-surface)", color: "var(--aos-text-secondary)", textDecoration: "none" }}>
              编辑模块
            </Link>
            <Link to="/workshop" style={{ padding: "5px 12px", fontSize: 12, border: "1px solid var(--aos-border)", borderRadius: 2, background: "var(--aos-surface)", color: "var(--aos-text-secondary)", textDecoration: "none" }}>
              ← 返回列表
            </Link>
          </div>
        </div>

        <PaginationGuardBanner total={displayTotal} />
        {gateMsg && <p className="error" style={{ fontSize: 12 }}>{gateMsg}</p>}
        {error && <p className="error" style={{ fontSize: 12 }}>{error}</p>}
        {actionMsg && <p className="aos-text" style={{ fontSize: 12 }}>{actionMsg}</p>}

        {/* 3-pane layout */}
        <div style={{ flex: 1, display: "grid", gridTemplateColumns: "200px 1fr 1fr", minHeight: 500, gap: 0, borderRadius: 2, overflow: "hidden", border: "1px solid var(--aos-border)" }}>
          {/* Left: Filter List */}
          <div style={{ padding: 16, borderRight: "1px solid #E5E7EB", overflowY: "auto", background: "#F9FAFB" }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#111827", marginBottom: 12 }}>筛选列表</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {filterGroups.map((group) => (
                <div key={group}>
                  <div style={{ fontSize: 11, fontWeight: 500, color: "#6B7280", marginTop: group === "状态" ? 0 : 12 }}>{group}</div>
                  {PRESET_FILTERS.filter((p) => p.group === group).map((p) => (
                    <label key={p.id} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#374151", cursor: "pointer", marginTop: 4 }}>
                      <input
                        type="checkbox"
                        checked={!!presetOn[p.id]}
                        onChange={() => togglePreset(p.id)}
                      />
                      {p.label}
                    </label>
                  ))}
                </div>
              ))}
              <div>
                <div style={{ fontSize: 11, fontWeight: 500, color: "#6B7280", marginTop: 12 }}>自定义</div>
                <form onSubmit={onAdd} style={{ marginTop: 6 }}>
                  <input
                    value={field}
                    onChange={(e) => setField(e.target.value)}
                    placeholder="field"
                    style={{ width: "100%", padding: "4px 6px", fontSize: 11, border: "1px solid #D1D5DB", borderRadius: 4, marginBottom: 4 }}
                  />
                  <input
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    placeholder="value"
                    style={{ width: "100%", padding: "4px 6px", fontSize: 11, border: "1px solid #D1D5DB", borderRadius: 4, marginBottom: 6 }}
                  />
                  <button type="submit" style={{ width: "100%", padding: "4px 8px", fontSize: 11, border: "none", borderRadius: 4, background: "#3B82F6", color: "#fff", cursor: "pointer" }}>
                    添加筛选
                  </button>
                </form>
              </div>
            </div>
            <div style={{ marginTop: 16, padding: 8, background: "var(--aos-accent-light)", borderRadius: 2, fontSize: 11, color: "var(--aos-blue-600)" }}>
              输出 → Object Set Filter
              <br />
              维数 {filters.length}/{SELECTION_LIMIT}
            </div>
            {customFilters.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 10, color: "#9CA3AF" }}>
                自定义: {customFilters.map((f) => `${f.field}=${f.value}`).join(", ")}
              </div>
            )}
          </div>

          {/* Middle: Object Table */}
          <div style={{ padding: 16, borderRight: "1px solid #E5E7EB", overflowY: "auto", background: "#fff" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>风控告警列表</div>
              <span style={{ fontSize: 12, color: "#6B7280" }}>{rows.length} 条结果</span>
            </div>
            <div style={{ border: "1px solid var(--aos-border)", borderRadius: 2, overflow: "hidden", background: "var(--aos-surface)" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "10px 12px", background: "#F3F4F6", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 11 }}>订单号</th>
                    <th style={{ textAlign: "left", padding: "10px 12px", background: "#F3F4F6", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 11 }}>问题</th>
                    <th style={{ textAlign: "left", padding: "10px 12px", background: "#F3F4F6", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 11 }}>站点</th>
                    <th style={{ textAlign: "left", padding: "10px 12px", background: "#F3F4F6", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 11 }}>等级</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const id = String(r.id);
                    const isActive = activeRow && String(activeRow.id) === id;
                    const badge = priorityBadge(String(r.priority || ""));
                    return (
                      <tr
                        key={id}
                        onClick={() => toggleRow(id)}
                        style={{
                          cursor: "pointer",
                          background: isActive ? "#EFF6FF" : undefined,
                          borderLeft: isActive ? "3px solid #2563EB" : undefined,
                          borderBottom: "1px solid #E5E7EB",
                        }}
                      >
                        <td style={{ padding: "10px 12px", fontFamily: "monospace", fontSize: 12 }}>{id}</td>
                        <td style={{ padding: "10px 12px", fontSize: 12 }}>{r.title || "—"}</td>
                        <td style={{ padding: "10px 12px", fontSize: 12 }}>{r.site || "—"}</td>
                        <td style={{ padding: "10px 12px" }}>
                          <span style={{ padding: "2px 6px", borderRadius: 3, fontSize: 10, background: badge.bg, color: badge.color }}>
                            {badge.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                  {rows.length === 0 && !error && (
                    <tr>
                      <td colSpan={4} style={{ padding: "24px 12px", textAlign: "center", color: "#9CA3AF", fontSize: 12 }}>
                        无行 · 改 Filter 或到数据连接接入源后刷新
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div style={{ marginTop: 8, fontSize: 11, color: "#9CA3AF" }}>
              Active / Selected → 右栏 Object View · 已选 {selected.size}
            </div>
          </div>

          {/* Right: Object View + Actions + Activity Log */}
          <div style={{ padding: 16, overflowY: "auto", background: "#fff" }}>
            {activeRow ? (
              <>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>订单详情</div>
                  <span style={{ fontSize: 11, color: "#EA580C" }}>Wiki 侧栏</span>
                </div>
                <div style={{ border: "1px solid var(--aos-border)", borderRadius: 2, background: "var(--aos-surface)", padding: 16 }}>
                  <div style={{ fontSize: 18, fontWeight: 600, color: "#111827", marginBottom: 4 }}>
                    {String(activeRow.id)}
                  </div>
                  <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 16 }}>
                    类型：WorkOrder · 状态：{activeRow.status || "—"}
                  </div>

                  {/* Detail grid */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
                    <div style={{ padding: 10, background: "var(--aos-surface-hover)", borderRadius: 2 }}>
                      <div style={{ fontSize: 10, color: "#6B7280" }}>标题</div>
                      <div style={{ fontSize: 14, fontWeight: 500, color: "#111827", marginTop: 2 }}>
                        {String(activeRow.title || "—")}
                      </div>
                    </div>
                    <div style={{ padding: 10, background: "var(--aos-surface-hover)", borderRadius: 2 }}>
                      <div style={{ fontSize: 10, color: "#6B7280" }}>站点</div>
                      <div style={{ fontSize: 14, fontWeight: 500, color: "#111827", marginTop: 2 }}>
                        {String(activeRow.site || "—")}
                      </div>
                    </div>
                    <div style={{ padding: 10, background: "var(--aos-surface-hover)", borderRadius: 2 }}>
                      <div style={{ fontSize: 10, color: "#6B7280" }}>状态</div>
                      <div style={{ fontSize: 14, fontWeight: 500, marginTop: 2, color: activeRow.status === "open" ? "#DC2626" : "#059669" }}>
                        {activeRow.status || "—"}
                      </div>
                    </div>
                    <div style={{ padding: 10, background: "var(--aos-surface-hover)", borderRadius: 2 }}>
                      <div style={{ fontSize: 10, color: "#6B7280" }}>内部成本</div>
                      <div style={{ fontSize: 14, fontWeight: 500, color: "#111827", marginTop: 2 }}>
                        {activeRow.internalCost != null ? String(activeRow.internalCost) : "—"}
                      </div>
                    </div>
                  </div>

                  {/* Wiki section */}
                  {wikiText && (
                    <div style={{ border: "1px solid var(--aos-amber-border)", background: "var(--aos-amber-bg)", borderRadius: 2, padding: 12, marginBottom: 16 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "#EA580C", marginBottom: 4 }}>Wiki · 工单说明</div>
                      <p style={{ fontSize: 12, color: "#9A3412", margin: 0, lineHeight: 1.5 }}>{wikiText}</p>
                    </div>
                  )}

                  {/* Actions */}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    <button
                      type="button"
                      onClick={() => void proposeClose([activeRow])}
                      disabled={busy}
                      style={{
                        padding: "8px 14px",
                        borderRadius: 2,
                        background: "#FEF3C7",
                        border: "1px solid #FCD34D",
                        fontSize: 12,
                        color: "#92400E",
                        cursor: busy ? "not-allowed" : "pointer",
                      }}
                    >
                      发起申诉 · HITL
                    </button>
                    <button
                      type="button"
                      onClick={() => void proposeClose()}
                      disabled={busy || selected.size === 0}
                      style={{
                        padding: "8px 14px",
                        borderRadius: 2,
                        border: "1px solid #D1D5DB",
                        background: "white",
                        fontSize: 12,
                        color: "#374151",
                        cursor: busy || selected.size === 0 ? "not-allowed" : "pointer",
                      }}
                    >
                      批量关闭（{selected.size}）
                    </button>
                    <Link
                      to={buddyHref}
                      style={{
                        padding: "8px 14px",
                        borderRadius: 2,
                        border: "1px solid #BFDBFE",
                        background: "#EFF6FF",
                        fontSize: 12,
                        color: "#2563EB",
                        textDecoration: "none",
                      }}
                    >
                      Assist
                    </Link>
                  </div>
                </div>

                {/* Activity log */}
                <div style={{ marginTop: 16, border: "1px solid var(--aos-border)", borderRadius: 2, background: "var(--aos-surface)", padding: 16 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#111827", marginBottom: 12 }}>活动日志</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {activityLog.map((log) => (
                      <div key={log.id} style={{ display: "flex", gap: 8, fontSize: 12 }}>
                        <div style={{ width: 6, height: 6, borderRadius: "50%", background: log.color, marginTop: 5, flexShrink: 0 }} />
                        <div>
                          <span style={{ color: "#111827" }}>{log.text}</span>
                          <span style={{ color: "#6B7280" }}> · {log.actor} · {log.time}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <p style={{ color: "#9CA3AF", fontSize: 12, textAlign: "center", paddingTop: 40 }}>选择左侧行查看 Object View</p>
            )}
          </div>
        </div>
      </div>
    </PageChrome>
  );
}
