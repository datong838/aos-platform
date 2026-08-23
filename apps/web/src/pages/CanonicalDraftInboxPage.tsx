import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  aipActionsSdk,
  type ActionDraftBundle,
  type ActionExecutionView,
  type ActionProposalStatus,
  type ActionProposalTimeline,
  type AipActionsSdk,
} from "../api/aipActions";
import { PageChrome } from "../components/PageChrome";
import { actionDisplayName, businessDisplayName, objectTypeDisplayName, riskDisplayName, statusDisplayName } from "../lib/aipChineseLabels";

type InboxTab = "approval" | "approved" | "execution" | "closed";
type LoadState = "loading" | "ready" | "error";

export interface CanonicalDraftInboxPageProps { sdk?: AipActionsSdk }

const TAB_LABELS: Array<{ id: InboxTab; label: string }> = [
  { id: "approval", label: "待审批" },
  { id: "approved", label: "已批准" },
  { id: "execution", label: "执行与对账" },
  { id: "closed", label: "已结束" },
];

const STATUS_LABELS: Record<ActionProposalStatus, string> = {
  proposed: "待生成草稿", drafted: "待审批", approved: "已批准", rejected: "已拒绝",
  expired: "已过期", leased: "已获执行租约", executing: "已提交外部系统", applied: "已应用",
  failed: "执行失败", unknown: "结果待对账", reconciled: "已完成对账", compensated: "已建立补偿提案",
};

export function actionStatusTab(status: ActionProposalStatus): InboxTab {
  if (status === "proposed" || status === "drafted") return "approval";
  if (status === "approved") return "approved";
  if (status === "leased" || status === "executing" || status === "unknown") return "execution";
  return "closed";
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function formatTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function shortHash(value: string): string {
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

function statusClass(status: ActionProposalStatus): string {
  if (["applied", "reconciled"].includes(status)) return "bg-green-50 text-green-700 border-green-200";
  if (["rejected", "failed", "expired"].includes(status)) return "bg-red-50 text-red-700 border-red-200";
  if (status === "unknown") return "bg-amber-50 text-amber-800 border-amber-300";
  if (["leased", "executing"].includes(status)) return "bg-purple-50 text-purple-700 border-purple-200";
  return "bg-blue-50 text-blue-700 border-blue-200";
}

function ProposalBadge({ status }: { status: ActionProposalStatus }) {
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${statusClass(status)}`}>{STATUS_LABELS[status]}</span>;
}

export function filterCanonicalProposals(
  items: ActionDraftBundle[],
  tab: InboxTab,
  search: string,
  taskId: string,
  runId: string,
): ActionDraftBundle[] {
  const query = search.trim().toLowerCase();
  return items.filter(({ proposal }) => {
    if (actionStatusTab(proposal.status) !== tab) return false;
    if (taskId && proposal.taskId !== taskId) return false;
    if (runId && proposal.runId !== runId) return false;
    if (query && ![proposal.id, proposal.actionType.actionTypeId, proposal.actionType.objectType, proposal.purpose]
      .some((value) => value.toLowerCase().includes(query))) return false;
    return true;
  });
}

export function CanonicalDraftInboxPage({ sdk = aipActionsSdk }: CanonicalDraftInboxPageProps) {
  const [params] = useSearchParams();
  const taskId = params.get("taskId")?.trim() ?? "";
  const runId = params.get("runId")?.trim() ?? "";
  const proposalParam = params.get("proposal")?.trim() ?? "";
  const [items, setItems] = useState<ActionDraftBundle[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [activeTab, setActiveTab] = useState<InboxTab>("approval");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<ActionProposalTimeline | null>(null);
  const [execution, setExecution] = useState<ActionExecutionView | null>(null);
  const [detailState, setDetailState] = useState<LoadState>("loading");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const generation = useRef(0);

  const counts = useMemo(() => items.reduce<Record<InboxTab, number>>((result, item) => {
    result[actionStatusTab(item.proposal.status)] += 1;
    return result;
  }, { approval: 0, approved: 0, execution: 0, closed: 0 }), [items]);
  const visible = useMemo(
    () => filterCanonicalProposals(items, activeTab, search, taskId, runId),
    [items, activeTab, search, taskId, runId],
  );
  const selected = useMemo(
    () => visible.find(({ proposal }) => proposal.id === selectedId) ?? null,
    [selectedId, visible],
  );

  const loadDetail = useCallback(async (proposalId: string) => {
    const current = ++generation.current;
    setDetailState("loading");
    try {
      const [nextTimeline, nextExecution] = await Promise.all([sdk.timeline(proposalId), sdk.execution(proposalId)]);
      if (current !== generation.current) return;
      if (nextTimeline.bundle.proposal.id !== proposalId || nextExecution.proposal.id !== proposalId) {
        throw new Error("服务端返回的 Action 资源不一致");
      }
      setTimeline(nextTimeline);
      setExecution(nextExecution);
      setDetailState("ready");
    } catch (loadError) {
      if (current !== generation.current) return;
      setTimeline(null);
      setExecution(null);
      setDetailState("error");
      setError(`详情读取失败：${message(loadError)}`);
    }
  }, [sdk]);

  const load = useCallback(async (preferredId?: string) => {
    const current = ++generation.current;
    setState("loading");
    setError("");
    try {
      const response = await sdk.list(500);
      if (current !== generation.current) return;
      const scoped = response.items.filter(({ proposal }) => (!taskId || proposal.taskId === taskId) && (!runId || proposal.runId === runId));
      setItems(response.items);
      const preferredHit = preferredId
        ? response.items.find(({ proposal }) => proposal.id === preferredId)
        : undefined;
      const nextId = preferredHit
        ? preferredHit.proposal.id
        : scoped[0]?.proposal.id ?? null;
      setSelectedId(nextId);
      if (nextId) {
        const nextBundle = preferredHit ?? scoped.find(({ proposal }) => proposal.id === nextId);
        if (nextBundle) setActiveTab(actionStatusTab(nextBundle.proposal.status));
      }
      setState("ready");
      if (nextId) await loadDetail(nextId); else { setTimeline(null); setExecution(null); setDetailState("ready"); }
    } catch (loadError) {
      if (current !== generation.current) return;
      setItems([]);
      setSelectedId(null);
      setTimeline(null);
      setExecution(null);
      setState("error");
      setDetailState("error");
      setError(`Action 服务不可用：${message(loadError)}`);
    }
  }, [loadDetail, runId, sdk, taskId]);

  useEffect(() => {
    void load(proposalParam || undefined);
    return () => { generation.current += 1; };
  }, [load, proposalParam]);

  useEffect(() => {
    if (!proposalParam) return;
    setSearch((prev) => (prev.trim() ? prev : proposalParam));
  }, [proposalParam]);

  const select = (proposalId: string) => {
    setSelectedId(proposalId);
    setNotice("");
    setError("");
    void loadDetail(proposalId);
  };

  const mutate = async (label: string, action: () => Promise<unknown>) => {
    if (!selected || state !== "ready" || detailState !== "ready") return;
    setBusy(true);
    setError("");
    setNotice(`${label}请求提交中…`);
    try {
      await action();
      setNotice(`${label}请求已接受，已从服务端重新读取权威状态。`);
      await load(selected.proposal.id);
    } catch (mutationError) {
      setNotice("");
      setError(`${label}失败：${message(mutationError)}。写操作已停止，请刷新后再判断。`);
      setDetailState("error");
    } finally {
      setBusy(false);
    }
  };

  const unknownReceipt = execution?.receipts.find((receipt) => receipt.receiptKind === "initial" && receipt.status === "unknown");
  const writable = state === "ready" && detailState === "ready" && !busy;

  return (
    <PageChrome
      title="草稿审批台"
      lede="执行提案 → 变更草稿 → 审批 → 执行租约 → 交付凭证；批准不等于已执行，只有交付凭证才能证明外部结果。"
    >
      <div
        data-testid="drafts-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 12 }}
      >
        {[
          { label: "加载态", value: state === "ready" ? "就绪" : state === "loading" ? "读取中" : "失败" },
          { label: "合计", value: String(items.length) },
          { label: "待批", value: String(counts.approval) },
          { label: "已批", value: String(counts.approved) },
          { label: "执行中", value: String(counts.execution) },
          { label: "已关", value: String(counts.closed) },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
          </div>
        ))}
      </div>
      <div className="aip-draft-inbox space-y-4" data-testid="canonical-action-inbox">
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900" data-testid="drafts-chain-banner">
          <strong>真实受控动作权威链</strong> · 页面不注入示例草稿，也不在浏览器维护第二套状态机。
          {(taskId || runId) && <details><summary>当前筛选的技术标识</summary>{taskId ? `任务 ${taskId}` : ""}{taskId && runId ? " · " : ""}{runId ? `运行 ${runId}` : ""}</details>}
          {proposalParam && <details><summary>深链提案标识</summary><code>{proposalParam}</code></details>}
        </div>
        {notice && <p role="status" className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">{notice}</p>}
        {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}

        <div className="flex items-center justify-between gap-3">
          <input
            aria-label="搜索受控业务动作"
            className="min-w-0 flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
            placeholder="搜索执行提案、业务动作、对象类型或目的…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <button type="button" className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm" disabled={busy || state === "loading"} onClick={() => void load(selectedId ?? undefined)}>
            刷新 / 对账
          </button>
        </div>

        <div className="flex gap-1 border-b border-gray-200">
          {TAB_LABELS.map((tab) => (
            <button key={tab.id} type="button" onClick={() => { setActiveTab(tab.id); setSelectedId(null); }} className={`border-b-2 px-4 py-2 text-sm ${activeTab === tab.id ? "border-blue-600 text-blue-700" : "border-transparent text-gray-500"}`}>
              {tab.label} <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">{counts[tab.id]}</span>
            </button>
          ))}
        </div>

        {state === "loading" && <p role="status" className="py-12 text-center text-sm text-gray-500">正在读取受控执行提案…</p>}
        {state === "ready" && items.length === 0 && (
          <div className="rounded-lg border border-dashed border-gray-300 bg-white py-16 text-center" data-testid="drafts-empty">
            <h2 className="font-medium text-gray-800">当前工作区暂无受控动作</h2>
            <p className="mt-2 text-sm text-gray-500">这是有效的真实空状态，不会使用演示提案填充页面。</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Link to="/aip/logic" className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white no-underline" data-testid="drafts-cta-logic">去逻辑画布产生提案</Link>
              <Link to="/aip/evals" className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 no-underline" data-testid="drafts-cta-evals">查看评测门控</Link>
            </div>
          </div>
        )}

        {state === "ready" && items.length > 0 && (
          <div className="grid gap-4 xl:grid-cols-[minmax(320px,0.8fr)_minmax(520px,1.4fr)]">
            <section className="max-h-[720px] space-y-2 overflow-y-auto" aria-label="执行提案列表">
              {visible.length === 0 && <p className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-sm text-gray-500">当前筛选下暂无执行提案。</p>}
              {visible.map((bundle) => (
                <button key={bundle.proposal.id} type="button" onClick={() => select(bundle.proposal.id)} className={`w-full rounded-lg border p-3 text-left ${selectedId === bundle.proposal.id ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white hover:border-gray-300"}`}>
                  <div className="flex items-center justify-between gap-2"><ProposalBadge status={bundle.proposal.status} /><span className="text-xs text-gray-400">{formatTime(bundle.proposal.updatedAt)}</span></div>
                  <h3 className="mt-2 font-medium text-gray-900">{actionDisplayName(bundle.proposal.actionType.actionTypeId)}</h3>
                  <p className="mt-1 line-clamp-2 text-sm text-gray-600">{businessDisplayName(bundle.proposal.purpose, "受控业务动作申请")}</p>
                  <p className="mt-2 text-xs text-gray-500">{objectTypeDisplayName(bundle.proposal.actionType.objectType)} · {riskDisplayName(bundle.proposal.riskLevel)} · 版本 {bundle.proposal.version}</p>
                </button>
              ))}
            </section>

            <section className="rounded-lg border border-gray-200 bg-white" aria-label="执行提案详情">
              {!selected && <p className="p-12 text-center text-sm text-gray-500">请选择执行提案查看权威状态。</p>}
              {selected && (
                <>
                  <header className="border-b border-gray-100 p-4">
                    <div className="flex flex-wrap items-center gap-2"><ProposalBadge status={selected.proposal.status} /><span className="text-xs text-gray-500">{riskDisplayName(selected.proposal.riskLevel)}</span><span className="ml-auto text-xs text-gray-400">版本 {selected.proposal.version}</span></div>
                    <h2 className="mt-2 text-lg font-semibold text-gray-900">{actionDisplayName(selected.proposal.actionType.actionTypeId)}</h2>
                    <p className="mt-1 text-sm text-gray-600">{businessDisplayName(selected.proposal.purpose, "受控业务动作申请")}</p>
                  </header>

                  {detailState === "loading" && <p role="status" className="p-10 text-center text-sm text-gray-500">正在读取执行租约、交付凭证与事件时间线…</p>}
                  {detailState === "ready" && timeline && execution && (
                    <div className="space-y-5 p-4">
                      {selected.proposal.status === "unknown" && (
                        <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">外部结果未知：禁止重复执行，只允许读取供应商状态并追加对账凭证。</div>
                      )}
                      <div className="grid gap-3 sm:grid-cols-2">
                        <details><summary>提案标识（审计用）</summary><code className="text-xs">{selected.proposal.id}</code></details>
                        <details><summary>内容摘要（审计用）</summary><code className="text-xs" title={selected.proposal.proposalHash}>{shortHash(selected.proposal.proposalHash)}</code></details>
                        <details><summary>任务与运行标识（审计用）</summary><span className="text-sm">{selected.proposal.taskId ?? "—"} / {selected.proposal.runId ?? "—"}</span></details>
                        <div><strong className="block text-xs text-gray-500">到期时间</strong><span className="text-sm">{formatTime(selected.proposal.expiresAt)}</span></div>
                      </div>

                      <div>
                        <h3 className="text-sm font-semibold text-gray-800">草稿变更</h3>
                        <pre className="mt-2 max-h-48 overflow-auto rounded bg-gray-950 p-3 text-xs text-gray-100">{JSON.stringify(selected.draft.diff, null, 2)}</pre>
                      </div>

                      <div data-testid="drafts-chain-links">
                        <h3 className="text-sm font-semibold text-gray-800">评测与决策谱系证据链</h3>
                        <div className="mt-2 flex flex-wrap gap-2 text-sm">
                          <Link
                            to={`/aip/lineage?rootType=action&rootId=${encodeURIComponent(selected.proposal.id)}`}
                            className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-amber-900 no-underline"
                            data-testid="drafts-jump-lineage"
                          >
                            决策谱系（action/{selected.proposal.id.slice(0, 12)}…）→
                          </Link>
                          {selected.draft.evidenceRefs
                            .filter((ref) => ref.resourceType === "EvalSuite")
                            .map((ref) => (
                              <Link
                                key={`${ref.resourceType}:${ref.resourceId}`}
                                to={`/aip/evals?suite=${encodeURIComponent(ref.resourceId)}&proposal=${encodeURIComponent(selected.proposal.id)}`}
                                className="rounded border border-blue-300 bg-blue-50 px-2 py-1 text-blue-800 no-underline"
                                data-testid="drafts-jump-evals"
                              >
                                评测套件 →
                              </Link>
                            ))}
                          {selected.draft.evidenceRefs.length === 0 && (
                            <span className="text-gray-500">本草稿没有评测套件证据引用；仍可跳转查看决策谱系。</span>
                          )}
                        </div>
                      </div>

                      <div>
                        <h3 className="text-sm font-semibold text-gray-800">审批事实（{selected.approvals.length}）</h3>
                        {selected.approvals.length === 0 ? <p className="mt-2 text-sm text-gray-500">尚无审批事件。</p> : (
                          <ol className="mt-2 space-y-2">{selected.approvals.map((approval) => <li key={approval.id} className="rounded border border-gray-200 p-2 text-sm">{approval.decision === "approved" ? "批准" : "拒绝"} · {approval.actor.actorId} · {formatTime(approval.createdAt)}{approval.reason ? ` · ${approval.reason}` : ""}</li>)}</ol>
                        )}
                      </div>

                      <div>
                        <h3 className="text-sm font-semibold text-gray-800">执行租约</h3>
                        {execution.lease ? <div className="mt-2 rounded border border-purple-200 bg-purple-50 p-2 text-sm">第 {execution.lease.attempt} 次执行尝试 · 到期 {formatTime(execution.lease.expiresAt)}<details><summary>租约技术标识</summary><code>{execution.lease.id}</code></details></div> : <p className="mt-2 text-sm text-gray-500">尚未获取执行租约。</p>}
                      </div>

                      <div>
                        <h3 className="text-sm font-semibold text-gray-800">不可变交付凭证链（{execution.receipts.length}）</h3>
                        {execution.receipts.length === 0 ? <p className="mt-2 text-sm text-gray-500">尚无交付凭证，不能宣称已执行。</p> : (
                          <ol className="mt-2 space-y-2">{execution.receipts.map((receipt) => <li key={receipt.id} className="rounded border border-gray-200 p-2 text-sm"><strong>{statusDisplayName(receipt.status)}</strong> · {receipt.receiptKind === "initial" ? "首次交付" : "后续对账"}<details><summary>凭证技术详情</summary><code className="text-xs">{receipt.id}</code>{receipt.providerRequestId ? <span> · 供应商请求 {receipt.providerRequestId}</span> : null}{receipt.supersedesReceiptId ? <span className="text-xs text-gray-500"> · 替代凭证 {receipt.supersedesReceiptId}</span> : null}</details></li>)}</ol>
                        )}
                      </div>

                      <details>
                        <summary className="cursor-pointer text-sm font-semibold text-gray-800">权威事件时间线（{timeline.events.length}）</summary>
                        <ol className="mt-2 space-y-2">{timeline.events.map((event) => <li key={event.id} className="border-l-2 border-blue-200 pl-3 text-sm">{event.type} · {event.actorId} · {formatTime(event.createdAt)}</li>)}</ol>
                      </details>
                    </div>
                  )}

                  <footer className="flex flex-wrap gap-2 border-t border-gray-100 bg-gray-50 p-3">
                    {selected.proposal.status === "drafted" && <>
                      <button type="button" disabled={!writable} className="rounded bg-green-600 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void mutate("批准", () => sdk.decide(selected, "approved", "Draft Inbox 审批通过"))}>批准精确版本</button>
                      <button type="button" disabled={!writable} className="rounded bg-red-600 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void mutate("拒绝", () => sdk.decide(selected, "rejected", "Draft Inbox 审批拒绝"))}>拒绝</button>
                    </>}
                    {selected.proposal.status === "approved" && <button type="button" disabled={!writable} className="rounded bg-purple-600 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void mutate("获取执行租约", () => sdk.acquireLease(selected))}>获取单次执行租约</button>}
                    {selected.proposal.status === "leased" && execution?.lease && <button type="button" disabled={!writable} className="rounded bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void mutate("执行受控动作", () => sdk.execute(execution))}>执行一次</button>}
                    {selected.proposal.status === "unknown" && unknownReceipt && <button type="button" disabled={!writable || !unknownReceipt.providerRequestId} title={!unknownReceipt.providerRequestId ? "缺少 provider request id，不能自动对账" : undefined} className="rounded bg-amber-600 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void mutate("只读对账", () => sdk.reconcile(unknownReceipt.id, "Draft Inbox 手动只读对账"))}>只读对账</button>}
                    <button type="button" className="rounded border border-gray-300 bg-white px-3 py-2 text-sm" disabled={busy} onClick={() => void loadDetail(selected.proposal.id)}>重读详情</button>
                  </footer>
                </>
              )}
            </section>
          </div>
        )}

        <div className="flex gap-4 border-t border-gray-100 py-3 text-xs">
          <Link
            to={selectedId ? `/aip/lineage?rootType=action&rootId=${encodeURIComponent(selectedId)}` : "/aip/lineage"}
            className="text-blue-600 hover:underline"
          >
            决策谱系 →
          </Link>
          <Link
            to={selectedId ? `/aip/evals?proposal=${encodeURIComponent(selectedId)}` : "/aip/evals"}
            className="text-blue-600 hover:underline"
          >
            评测门控 →
          </Link>
          <Link to="/aip/logic" className="text-blue-600 hover:underline">业务逻辑编排 →</Link>
        </div>
      </div>
    </PageChrome>
  );
}
