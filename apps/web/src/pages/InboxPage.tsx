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
import {
  LargeResultSimulator,
  PaginationGuardBanner,
  useDisplayTotal,
} from "../paginationGuard";
import { BpPropGrid, BpToolbar, BpVarBar, BpWsGrid } from "./s2/blueprintUi";

type Row = Record<string, string>;

type ExecuteOut = {
  draftId?: string;
  id?: string;
  status?: string;
  productionWritten?: boolean;
  route?: string;
  idempotentReplay?: boolean;
};

const PRESET_FILTERS: { id: string; label: string; field: string; value: string }[] = [
  { id: "site-east", label: "站点：DC-East", field: "site", value: "DC-East" },
  { id: "site-west", label: "站点：DC-West", field: "site", value: "DC-West" },
];

/** 80 · 对齐 workshop-module.html · 变量条 + 三栏 + Action HITL */
export function InboxPage() {
  const [filters, setFilters] = useState<SelectionFilter[]>([]);
  const [presetOn, setPresetOn] = useState<Record<string, boolean>>({});
  const [field, setField] = useState("site");
  const [value, setValue] = useState("DC-East");
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [totalOverride, setTotalOverride] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gateMsg, setGateMsg] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [wikiText, setWikiText] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const displayTotal = useDisplayTotal(total, totalOverride);

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

  async function runQuery(nextFilters: SelectionFilter[]) {
    setError(null);
    setTotalOverride(null);
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

  const filterSummary =
    filters.length > 0
      ? filters.map((f) => `${f.field}=${f.value}`).join(" · ")
      : "无";

  const buddyHref = activeRow
    ? `/workshop/buddy?order=${encodeURIComponent(String(activeRow.id))}&assist=1`
    : "/workshop/buddy";

  return (
    <PageChrome
      title="运营台"
      lede="91 · Filter · Object Table · Object View · 变量条 · Action→Draft HITL"
    >
      <BpToolbar>
        <Link to={buddyHref} className="bp-buddy-toolbar-btn bp-buddy-toolbar-btn-active" style={{ textDecoration: "none" }}>
          💬 Buddy
        </Link>
        <Link to="/workshop/graph" className="bp-buddy-toolbar-btn" style={{ textDecoration: "none" }}>
          图谱台
        </Link>
        <Link to="/workshop/canvas" className="muted" style={{ fontSize: "0.75rem" }}>
          画布编辑 →
        </Link>
        <Link to="/aip/drafts" className="muted" style={{ fontSize: "0.75rem" }}>
          Draft 审批 →
        </Link>
      </BpToolbar>

      <BpVarBar
        chips={[
          {
            label: `Selection=${activeRow ? String(activeRow.id) : "—"}`,
            tone: "sky",
          },
          {
            label: `Selection 维数 ${selected.size} / 10`,
            tone: "amber",
          },
          { label: `Filter=${filterSummary}`, tone: "muted" },
          { label: "User=当前用户", tone: "muted" },
          {
            label: `Table · 命中 ${displayTotal}`,
            tone: "violet",
          },
          { label: "WorkOrder · HITL Action", tone: "emerald" },
        ]}
        trailing="不做 SQL · 只认变量"
      />

      <LargeResultSimulator onSimulate={(n) => setTotalOverride(n)} />
      <PaginationGuardBanner total={displayTotal} />
      {gateMsg && <p className="error">{gateMsg}</p>}
      {error && <p className="error">{error}</p>}
      {actionMsg && <p className="aos-text">{actionMsg}</p>}

      <BpWsGrid
        filter={
          <>
            <div className="bp-ws-section-title">Filter List</div>
            {PRESET_FILTERS.map((p) => (
              <label key={p.id} className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                <input
                  type="checkbox"
                  checked={!!presetOn[p.id]}
                  onChange={() => togglePreset(p.id)}
                  style={{ marginRight: 6 }}
                />
                {p.label}
              </label>
            ))}
            <form onSubmit={onAdd} style={{ marginTop: "0.75rem" }}>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem" }}>
                field{" "}
                <input value={field} onChange={(e) => setField(e.target.value)} style={{ width: "100%" }} />
              </label>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginTop: 4 }}>
                value{" "}
                <input value={value} onChange={(e) => setValue(e.target.value)} style={{ width: "100%" }} />
              </label>
              <button type="submit" className="btn" style={{ marginTop: 6 }}>
                添加维
              </button>
            </form>
            <p className="muted" style={{ fontSize: "0.625rem", marginTop: "0.75rem" }}>
              输出 → Object Set Filter · 维数 {filters.length}/{SELECTION_LIMIT}
            </p>
          </>
        }
        table={
          <>
            <div className="bp-ws-section-title">Object Table · WorkOrder</div>
            <div className="bp-module-frame">
              <div className="bp-module-frame-head">
                <span>工单</span>
                <span>标题</span>
                <span>站点</span>
                <span>状态</span>
              </div>
              {rows.map((r) => {
                const id = String(r.id);
                const isActive = activeRow && String(activeRow.id) === id;
                return (
                  <button
                    key={id}
                    type="button"
                    className={isActive ? "bp-module-row bp-module-row-active" : "bp-module-row"}
                    onClick={() => toggleRow(id)}
                  >
                    <span style={{ color: "var(--aos-text)" }}>{id}</span>
                    <span>{r.title || "—"}</span>
                    <span>{r.site || "—"}</span>
                    <span className={r.status === "open" ? "" : "bp-prop-warn"}>{r.status || "—"}</span>
                  </button>
                );
              })}
              {rows.length === 0 && !error && (
                <p className="muted" style={{ padding: "0.75rem" }}>
                  无行 · 改 Filter 或先在 /data 初始化业务数据
                </p>
              )}
            </div>
            <p className="muted" style={{ fontSize: "0.625rem", marginTop: "0.5rem" }}>
              Active / Selected → 右栏 Object View · 已选 {selected.size}
            </p>
          </>
        }
        objectView={
          activeRow ? (
            <>
              <div className="bp-ws-section-title">
                Object View <span className="muted">· Wiki 侧栏</span>
              </div>
              <div className="bp-object-panel">
                <div className="bp-object-title">{String(activeRow.id)}</div>
                <p className="muted" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                  类型：WorkOrder · 状态：{activeRow.status || "—"}
                </p>
                <BpPropGrid
                  items={[
                    { label: "标题", value: String(activeRow.title || "—") },
                    { label: "站点", value: String(activeRow.site || "—") },
                    {
                      label: "状态",
                      value: String(activeRow.status || "—"),
                      tone: activeRow.status === "open" ? undefined : "warn",
                    },
                    { label: "internalCost", value: activeRow.internalCost != null ? String(activeRow.internalCost) : "—" },
                  ]}
                />
                {wikiText && (
                  <div className="bp-wiki-snippet">
                    <strong>Wiki · 工单说明</strong>
                    {wikiText}
                  </div>
                )}
                <div className="bp-object-actions">
                  <button
                    type="button"
                    className="btn"
                    disabled={busy}
                    onClick={() => void proposeClose([activeRow])}
                  >
                    发起申诉 · HITL
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={busy || selected.size === 0}
                    onClick={() => void proposeClose()}
                  >
                    批量关闭（{selected.size}）
                  </button>
                  <Link to={buddyHref} className="btn" style={{ textDecoration: "none" }}>
                    💡 Assist
                  </Link>
                </div>
              </div>
            </>
          ) : (
            <p className="muted">选择左侧行查看 Object View</p>
          )
        }
      />
    </PageChrome>
  );
}
