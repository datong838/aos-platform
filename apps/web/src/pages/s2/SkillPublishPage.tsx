import { Link } from "react-router-dom";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "../../api/client";
import { getTenant } from "../../api/tenant";
import { PageChrome } from "../../components/PageChrome";
import { logicDisplayName } from "../../lib/aipChineseLabels";

type SkillItem = {
  skillId: string;
  revision: number;
  lifecycle: string;
  contentHash: string;
  canonicalLogicId: string;
};

type SkillListResponse = {
  tenant: { orgId: string; projectId: string };
  items: SkillItem[];
  count: number;
};

function lifecycleLabel(lifecycle: string): string {
  return (
    {
      draft: "草稿",
      evaluated: "仅已评测",
      published: "已发布",
      deprecated: "已弃用",
      revoked: "已撤销",
    } as Record<string, string>
  )[lifecycle] || lifecycle;
}

export function SkillPublishPage() {
  const [data, setData] = useState<SkillListResponse | null>(null);
  const [allItems, setAllItems] = useState<SkillItem[]>([]);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "evaluated" | "published">("evaluated");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [bindStep, setBindStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    try {
      const qs = filter === "all" ? "" : `?lifecycle=${filter}`;
      const [body, all] = await Promise.all([
        apiGet<SkillListResponse>(`/v1/aip/skills${qs}`),
        apiGet<SkillListResponse>(`/v1/aip/skills?limit=200`),
      ]);
      const tenant = getTenant();
      if (body.tenant.orgId !== tenant.orgId || body.tenant.projectId !== tenant.projectId) {
        throw new Error("技能列表租户与当前工作区不一致");
      }
      setData(body);
      setAllItems(all.items);
      setError("");
      setSelectedId((prev) => {
        if (prev && body.items.some((item) => `${item.skillId}@${item.revision}` === prev)) return prev;
        const first = body.items[0];
        return first ? `${first.skillId}@${first.revision}` : null;
      });
    } catch (e) {
      setData(null);
      setAllItems([]);
      setError(String((e as Error).message || e));
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  const selected = useMemo(() => {
    if (!data || !selectedId) return null;
    return data.items.find((item) => `${item.skillId}@${item.revision}` === selectedId) || null;
  }, [data, selectedId]);

  const batchStats = useMemo(() => {
    const published = new Set(
      allItems.filter((item) => item.lifecycle === "published").map((item) => item.skillId),
    );
    const evaluatedOnly = new Set(
      allItems
        .filter((item) => item.lifecycle === "evaluated" && !published.has(item.skillId))
        .map((item) => item.skillId),
    );
    return { published: published.size, waitingLogic: evaluatedOnly.size, total: allItems.length };
  }, [allItems]);

  async function tryPublish() {
    if (!selected || selected.lifecycle !== "evaluated") return;
    setBusy(true);
    setNote("");
    try {
      // F2：完整 exact refs 须由运维从 Eval/路由权威填入；首波 UI 先 fail-closed 提示，避免半参假发。
      setNote("发布需齐备 Eval 放行决策、模型路由、运行策略与 LogicRevision exact。请在「评测」确认门绿后，用受控脚本或后续表单补齐 refs 再发。当前已接通 POST /v1/aip/skills/publish-evaluated。");
      setBindStep(1);
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageChrome title="技能发布" lede="evaluated → published · Receipt/幂等 · 可内嵌绑定向导">
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14, alignItems: "center" }}>
        <button className="btn" type="button" onClick={() => void load()}>刷新</button>
        <label>
          筛选{" "}
          <select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}>
            <option value="evaluated">仅已评测</option>
            <option value="published">已发布</option>
            <option value="all">全部</option>
          </select>
        </label>
        <Link to="/aip/evals">评测门控</Link>
        <Link to="/aip/agent-registry">智能体目录</Link>
        <Link to="/aip/maturity">成熟度</Link>
        {data ? <span className="notice" style={{ padding: "6px 10px" }}>共 {data.count} 条</span> : null}
      </div>
      {error && <div role="alert" className="notice bad">技能列表读取失败：{error}</div>}
      {allItems.length > 0 ? (
        <div className="notice" style={{ padding: 12, marginBottom: 12 }} role="status" data-testid="skill-publish-batch-stats">
          首批发布对账：已发布技能 <strong>{batchStats.published}</strong> 个 ·
          仍待 Logic 权威进库 <strong>{batchStats.waitingLogic}</strong> 个 ·
          列表共 {batchStats.total} 条修订。缺 Logic 图时保持 fail-closed，不在此页伪造发布。
        </div>
      ) : null}
      {!data ? (
        <div className="card" role="status">正在读取技能模板…</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(280px,360px) minmax(0,1fr)", gap: 14, minHeight: 480 }}>
          <aside className="card" style={{ padding: 0, overflow: "auto" }} aria-label="技能列表">
            {data.items.length === 0 ? (
              <p style={{ padding: 14 }}>当前筛选无技能</p>
            ) : (
              data.items.map((item) => {
                const id = `${item.skillId}@${item.revision}`;
                const active = selectedId === id;
                const title = logicDisplayName(item.canonicalLogicId) || item.skillId;
                return (
                  <button
                    type="button"
                    key={id}
                    onClick={() => { setSelectedId(id); setBindStep(0); setNote(""); }}
                    style={{
                      display: "block",
                      width: "100%",
                      textAlign: "left",
                      padding: "12px 14px",
                      border: "none",
                      borderBottom: "1px solid var(--aos-border,#f3f4f6)",
                      borderLeft: active ? "3px solid var(--aos-indigo-600,#4f46e5)" : "3px solid transparent",
                      background: active ? "var(--aos-indigo-50,#eef2ff)" : "transparent",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>{title}</div>
                    <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4 }}>
                      修订 {item.revision} · {lifecycleLabel(item.lifecycle)}
                    </div>
                  </button>
                );
              })
            )}
          </aside>
          <section className="card" style={{ padding: 18 }}>
            {!selected ? (
              <p>请选择左侧技能</p>
            ) : (
              <>
                <h2 style={{ marginTop: 0 }}>{logicDisplayName(selected.canonicalLogicId) || selected.skillId}</h2>
                <p style={{ color: "var(--aos-text-secondary)" }}>
                  生命周期：{lifecycleLabel(selected.lifecycle)} · 修订 {selected.revision}
                </p>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
                  <button
                    className="btn primary"
                    type="button"
                    disabled={busy || selected.lifecycle !== "evaluated"}
                    title={selected.lifecycle !== "evaluated" ? "仅「仅已评测」可发布" : "准备发布（须齐备 exact refs）"}
                    onClick={() => void tryPublish()}
                  >
                    {selected.lifecycle === "published" ? "已发布" : busy ? "处理中…" : "发布此修订"}
                  </button>
                  <Link className="btn" to="/aip/evals">去评测确认门绿</Link>
                </div>
                {note && <div className="notice" style={{ marginTop: 12, padding: 10 }} role="status">{note}</div>}

                <div style={{ marginTop: 20, borderTop: "1px solid var(--aos-border,#e5e7eb)", paddingTop: 14 }}>
                  <h3 style={{ marginTop: 0 }}>绑定向导（发布后）</h3>
                  <ol style={{ color: "var(--aos-text-secondary)", paddingLeft: 18 }}>
                    <li style={{ opacity: bindStep >= 0 ? 1 : 0.5 }}>确认技能修订已 published</li>
                    <li style={{ opacity: bindStep >= 1 ? 1 : 0.5 }}>在目录为对应同事创建/激活 SkillBinding</li>
                    <li style={{ opacity: bindStep >= 1 ? 1 : 0.5 }}>目录「刷新」重评就绪快照</li>
                  </ol>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <Link className="btn" to="/aip/agent-registry">打开智能体目录绑定</Link>
                    <button className="btn" type="button" disabled={bindStep < 1} onClick={() => setBindStep(2)}>
                      我已完成绑定
                    </button>
                  </div>
                  {bindStep >= 2 && <p style={{ color: "var(--aos-green-700)" }}>请回目录确认可运行态；本页不写入演示 Binding。</p>}
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </PageChrome>
  );
}
