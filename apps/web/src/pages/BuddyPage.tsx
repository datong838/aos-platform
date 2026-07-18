import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import type { SelectionFilter } from "../selection";
import { BpLinkRow, BpToolbar, BpVarBar } from "./s2/blueprintUi";

type WoRow = { id: string; title?: string; status?: string; site?: string };

/** 95 · 对齐 workshop-aip-chat · 真实 WorkOrder + Inbox/Graph ?order= 上下文 */
export function BuddyPage({
  initialSelection = [{ field: "site", value: "DC-East" }],
}: {
  initialSelection?: SelectionFilter[];
}) {
  const [selection, setSelection] = useState<SelectionFilter[]>(initialSelection);
  const [rows, setRows] = useState<WoRow[]>([]);
  const [selectedId, setSelectedId] = useState("wo-1001");
  const [query, setQuery] = useState("这单当前风险与建议下一步？");
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([
    {
      role: "Buddy",
      text: "已注入 Selection。表格来自 object-sets/query，与 Inbox 同源。",
    },
  ]);
  const [assistOpen, setAssistOpen] = useState(false);
  const [buddyOpen, setBuddyOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchParams] = useSearchParams();

  const activeRow = useMemo(
    () => rows.find((r) => String(r.id) === selectedId) || rows[0] || null,
    [rows, selectedId],
  );

  async function loadRows(preferId?: string | null) {
    setLoading(true);
    setError(null);
    try {
      const res = await apiPost<{ items: WoRow[] }>("/v1/object-sets/query", {
        filters: [],
        page: 1,
        pageSize: 20,
        objectType: "WorkOrder",
      });
      setRows(res.items);
      const pick =
        (preferId && res.items.some((r) => String(r.id) === preferId) && preferId) ||
        res.items[0]?.id ||
        preferId ||
        "wo-1001";
      if (pick) {
        setSelectedId(String(pick));
        setSelection([{ field: "objectId", value: String(pick) }]);
      }
    } catch (err) {
      setError(String((err as Error).message || err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const order = searchParams.get("order");
    void loadRows(order);
    if (order) {
      setQuery(`请分析工单 ${order} 当前风险与建议下一步。`);
    }
    if (searchParams.get("assist") === "1") setAssistOpen(true);
  }, [searchParams]);

  async function onAsk(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await apiPost<{ answer: string; traceId: string }>("/v1/buddy/ask", {
        query,
        context: {
          selection,
          objectType: "WorkOrder",
          objectId: selectedId,
        },
      });
      setMessages((m) => [
        ...m,
        { role: "你", text: query },
        { role: "Buddy", text: `${res.answer} · trace=${res.traceId}` },
      ]);
      setQuery("");
    } catch (err) {
      setError(String((err as Error).message || err));
    }
  }

  function pickOrder(id: string) {
    setSelectedId(id);
    setSelection([{ field: "objectId", value: id }]);
    setAssistOpen(true);
  }

  const buddyShare = `/workshop/buddy?order=${encodeURIComponent(selectedId)}&assist=1`;

  return (
    <PageChrome
      title="Buddy · Assist"
      lede="流程内提问 · WorkOrder 与 Inbox 同源 · 写回仍须 Action"
    >
      <BpToolbar>
        <button
          type="button"
          className={buddyOpen ? "bp-buddy-toolbar-btn bp-buddy-toolbar-btn-active" : "bp-buddy-toolbar-btn"}
          onClick={() => setBuddyOpen((v) => !v)}
        >
          💬 Buddy
        </button>
        <button
          type="button"
          className={
            assistOpen ? "bp-buddy-toolbar-btn bp-buddy-toolbar-btn-assist-active" : "bp-buddy-toolbar-btn"
          }
          onClick={() => setAssistOpen((v) => !v)}
        >
          💡 Assist
        </button>
        <Link to="/workshop/inbox" className="muted" style={{ fontSize: "0.75rem" }}>
          Inbox →
        </Link>
        <Link
          to={activeRow ? `/workshop/graph` : "/workshop/graph"}
          className="muted"
          style={{ fontSize: "0.75rem" }}
        >
          图谱 →
        </Link>
      </BpToolbar>

      <div className={`bp-buddy-layout${buddyOpen ? "" : " bp-buddy-layout-single"}`}>
        <div className="bp-buddy-main">
          <BpVarBar
            chips={[
              {
                label: activeRow
                  ? `${activeRow.id} · ${activeRow.title || "—"}`
                  : `Selection=${selectedId}`,
                tone: "sky",
              },
              ...selection.map((s) => ({
                label: `${s.field}=${s.value}`,
                tone: "violet" as const,
              })),
            ]}
          />

          <div className="bp-ws-section-title">WorkOrder 表 · 选中行 → Assist / Buddy</div>

          <div className="bp-module-frame">
            <div className="bp-module-frame-head">
              <span>工单</span>
              <span>标题</span>
              <span>状态</span>
              <span>站点</span>
            </div>
            {loading && <p className="muted" style={{ padding: "0.75rem" }}>加载中…</p>}
            {!loading &&
              rows.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className={
                    selectedId === String(r.id) ? "bp-module-row bp-module-row-active" : "bp-module-row"
                  }
                  onClick={() => pickOrder(String(r.id))}
                >
                  <span>{r.id}</span>
                  <span>{r.title || "—"}</span>
                  <span className={r.status === "open" ? "bp-prop-warn" : ""}>{r.status || "—"}</span>
                  <span className="muted">{r.site || "—"}</span>
                </button>
              ))}

            {!loading && rows.length === 0 && (
              <p className="muted" style={{ padding: "0.75rem" }}>
                暂无工单 · 请到 <Link to="/data">数据连接</Link> 新建数据源并完成同步
              </p>
            )}

            {assistOpen && activeRow && (
              <div className="bp-assist-popover">
                <div style={{ color: "#7dd3fc", fontSize: "0.75rem", fontWeight: 500 }}>
                  💡 流程内提问 · {activeRow.id}
                </div>
                <p className="muted" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                  {activeRow.title || "—"} · {activeRow.status || "—"} · {activeRow.site || "—"}
                </p>
                <p className="aos-text" style={{ fontSize: "0.875rem", marginTop: 8 }}>
                  该工单当前需要关注什么？
                </p>
                <Link to={buddyShare} className="nav-link" style={{ fontSize: "0.75rem", marginTop: 8 }}>
                  带 Selection 打开 Buddy 侧栏 →
                </Link>
                <Link to="/workshop/inbox" className="nav-link" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                  回 Inbox 执行 Action →
                </Link>
              </div>
            )}
          </div>

          <BpLinkRow
            links={[
              { to: "/aip/maturity", label: "成熟度 L3" },
              { to: "/ontology/wiki", label: "Wiki 字段" },
              { to: "/workshop", label: "应用列表" },
            ]}
          />
        </div>

        {buddyOpen && (
          <aside className="bp-buddy-panel">
            <div className="bp-ws-section-title">AIP Chat · WorkBuddy</div>
            <span className="bp-tag bp-tag-warn" style={{ marginBottom: "0.5rem" }}>
              WorkOrder Buddy
            </span>
            <BpVarBar
              chips={[
                { label: `objectId: ${selectedId}`, tone: "sky" },
                { label: "Ontology: WorkOrder", tone: "violet" },
              ]}
            />
            <Link to="/aip/lineage" className="nav-link" style={{ fontSize: "0.75rem" }}>
              查看决策谱系 →
            </Link>

            <div className="bp-buddy-log">
              {messages.map((m, i) => (
                <div key={i} style={{ marginBottom: "0.75rem" }}>
                  <div className={m.role === "Buddy" ? "bp-prop-warn" : "muted"} style={{ fontSize: "0.7rem" }}>
                    {m.role}
                  </div>
                  <div className="aos-text" style={{ fontSize: "0.875rem", marginTop: 4 }}>
                    {m.text}
                  </div>
                </div>
              ))}
            </div>

            <form className="filter-bar" onSubmit={onAsk} style={{ marginTop: "auto" }}>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={`@Buddy 分析 ${selectedId}…`}
                aria-label="buddy-query"
                style={{ flex: 1, minWidth: 0 }}
              />
              <button type="submit" className="btn">
                发送
              </button>
            </form>
            {error && <p className="error">{error}</p>}
          </aside>
        )}
      </div>
    </PageChrome>
  );
}
