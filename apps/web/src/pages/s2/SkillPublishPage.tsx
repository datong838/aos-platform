import { Link } from "react-router-dom";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../../api/client";
import { aipAgentControl, type AgentRuntimeReadinessResponse } from "../../api/aipAgentControl";
import { getTenant } from "../../api/tenant";
import { PageChrome } from "../../components/PageChrome";
import { logicDisplayName } from "../../lib/aipChineseLabels";

type SkillItem = {
  skillId: string;
  revision: number;
  lifecycle: string;
  contentHash: string;
  canonicalLogicId: string;
  logicRevisionRef?: { assetType: string; assetId: string; revision: number; contentHash: string } | null;
};

type SkillListResponse = {
  tenant: { orgId: string; projectId: string };
  items: SkillItem[];
  count: number;
};

type ExactPublicationForm = {
  publicationId: string; releaseGateDecisionId: string;
  routeId: string; routeRevision: string; routeHash: string;
  policyId: string; policyRevision: string; policyHash: string;
  logicRevision: string; logicHash: string;
};
const EMPTY_PUBLICATION: ExactPublicationForm = { publicationId: "", releaseGateDecisionId: "", routeId: "", routeRevision: "", routeHash: "", policyId: "", policyRevision: "", policyHash: "", logicRevision: "", logicHash: "" };

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
  const [runtime, setRuntime] = useState<AgentRuntimeReadinessResponse | null>(null);
  const [publication, setPublication] = useState<ExactPublicationForm>(EMPTY_PUBLICATION);
  const [receiptId, setReceiptId] = useState("");

  const load = useCallback(async () => {
    try {
      const qs = filter === "all" ? "" : `?lifecycle=${filter}`;
      const [body, all, readiness] = await Promise.all([
        apiGet<SkillListResponse>(`/v1/aip/skills${qs}`),
        apiGet<SkillListResponse>(`/v1/aip/skills?limit=200`),
        aipAgentControl.runtimeReadiness(),
      ]);
      const tenant = getTenant();
      if (body.tenant.orgId !== tenant.orgId || body.tenant.projectId !== tenant.projectId) {
        throw new Error("技能列表租户与当前工作区不一致");
      }
      setData(body);
      setAllItems(all.items);
      setRuntime(readiness);
      setError("");
      setSelectedId((prev) => {
        if (prev && body.items.some((item) => `${item.skillId}@${item.revision}` === prev)) return prev;
        const first = body.items[0];
        return first ? `${first.skillId}@${first.revision}` : null;
      });
    } catch (e) {
      setData(null);
      setAllItems([]);
      setRuntime(null);
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
    setReceiptId("");
    try {
      const revision = (value: string, label: string) => { const parsed = Number(value); if (!Number.isInteger(parsed) || parsed < 1) throw new Error(`${label}必须为正整数`); return parsed; };
      const hash = (value: string, label: string) => { const cleaned = value.trim(); if (!/^[0-9a-f]{64}$/.test(cleaned)) throw new Error(`${label}必须为 64 位 SHA-256`); return cleaned; };
      if (!publication.publicationId.trim() || !publication.releaseGateDecisionId.trim() || !publication.routeId.trim() || !publication.policyId.trim()) throw new Error("发布事件、评测放行、模型路由和运行策略均需精确引用");
      const idempotencyKey = `skill-publish-${selected.skillId}-${selected.revision}-${crypto.randomUUID()}`;
      const response = await apiPost<{ tenant: { orgId: string; projectId: string }; skill: SkillItem; receiptId: string; operation: string }>("/v1/aip/skills/publish-evaluated", {
        sourceSkill: { assetType: "SkillTemplate", assetId: selected.skillId, revision: selected.revision, contentHash: selected.contentHash },
        publicationId: publication.publicationId.trim(), releaseGateDecisionId: publication.releaseGateDecisionId.trim(),
        modelRouteRef: { assetType: "ModelRouteRevision", assetId: publication.routeId.trim(), revision: revision(publication.routeRevision, "路由修订"), contentHash: hash(publication.routeHash, "路由摘要") },
        runtimePolicyRef: { assetType: "RuntimePolicyRevision", assetId: publication.policyId.trim(), revision: revision(publication.policyRevision, "策略修订"), contentHash: hash(publication.policyHash, "策略摘要") },
        logicRevisionRef: { assetType: "LogicRevision", assetId: selected.canonicalLogicId, revision: revision(publication.logicRevision, "逻辑修订"), contentHash: hash(publication.logicHash, "逻辑摘要") },
        idempotencyKey,
      }, { "Idempotency-Key": idempotencyKey });
      const tenant = getTenant();
      if (response.tenant.orgId !== tenant.orgId || response.tenant.projectId !== tenant.projectId || response.skill.skillId !== selected.skillId || !response.receiptId) throw new Error("发布回读与当前租户或精确技能不一致");
      setReceiptId(response.receiptId);
      setNote(`已发布修订 ${response.skill.revision}，并回读发布回执。`);
      setBindStep(1);
      await load();
    } catch (value) {
      setNote(`发布未执行：${String((value as Error).message || value)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageChrome title="技能发布" lede="把已通过评测的技能提交发布，并继续完成智能体绑定；缺少证据时失败关闭。">
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
          需核验业务逻辑权威 <strong>{batchStats.waitingLogic}</strong> 个 ·
          列表共 {batchStats.total} 条修订。发布必须引用当前评测、路由、策略和 Logic 精确版本。
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
                {selected.lifecycle === "evaluated" ? <details open style={{ marginTop: 14 }}><summary><strong>精确发布证据</strong></summary><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10, marginTop: 10 }}>{([
                  ["publicationId", "发布事件 ID"], ["releaseGateDecisionId", "评测放行决定 ID"], ["routeId", "模型路由 ID"], ["routeRevision", "模型路由修订"], ["routeHash", "模型路由 SHA-256"], ["policyId", "运行策略 ID"], ["policyRevision", "运行策略修订"], ["policyHash", "运行策略 SHA-256"], ["logicRevision", "业务逻辑修订"], ["logicHash", "业务逻辑 SHA-256"],
                ] as const).map(([key, label]) => <label key={key} style={{ display: "grid", gap: 5 }}>{label}<input className="input" value={publication[key]} onChange={(event) => setPublication((current) => ({ ...current, [key]: event.target.value }))} /></label>)}</div></details> : null}
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
                  <button
                    className="btn primary"
                    type="button"
                    disabled={busy || selected.lifecycle !== "evaluated"}
                    title={selected.lifecycle !== "evaluated" ? "仅已通过评测的技能可以发布" : "准备发布（须齐备精确权威引用）"}
                    onClick={() => void tryPublish()}
                  >
                    {selected.lifecycle === "published" ? "已发布" : busy ? "处理中…" : "发布此修订"}
                  </button>
                  <Link className="btn" to="/aip/evals">去评测确认门绿</Link>
                </div>
                {note && <div className="notice" style={{ marginTop: 12, padding: 10 }} role="status">{note}</div>}
                {receiptId ? <details><summary>发布回执（审计用）</summary><code>{receiptId}</code></details> : null}

                <div style={{ marginTop: 20, borderTop: "1px solid var(--aos-border,#e5e7eb)", paddingTop: 14 }}>
                  <h3 style={{ marginTop: 0 }}>组织消费与绑定</h3>
                  <ol style={{ color: "var(--aos-text-secondary)", paddingLeft: 18 }}>
                    <li style={{ opacity: bindStep >= 0 ? 1 : 0.5 }}>确认技能修订已经发布</li>
                    <li style={{ opacity: bindStep >= 1 || selected.lifecycle === "published" ? 1 : 0.5 }}>由目录权威命令创建、评估并激活技能绑定</li>
                    <li style={{ opacity: bindStep >= 1 || selected.lifecycle === "published" ? 1 : 0.5 }}>回读绑定 Receipt 与当前运行准备快照</li>
                  </ol>
                  <div className="notice"><strong>当前消费方</strong><p>{runtime?.catalog.items.filter((item) => item.skills.some((skill) => skill.skillId === selected.skillId && skill.revision === selected.revision)).map((item) => item.template.displayName).join("、") || "当前组织没有消费此精确修订的数字同事"}</p></div>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <Link className="btn" to={`/aip/agent-registry?skillId=${encodeURIComponent(selected.skillId)}&revision=${selected.revision}&intent=bind`}>打开权威绑定流程</Link>
                    <Link className="btn" to={`/aip/logic?logicId=${encodeURIComponent(selected.canonicalLogicId)}`}>查看业务逻辑</Link>
                  </div>
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </PageChrome>
  );
}
