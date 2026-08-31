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
import { ActionBoundaryPanel } from "../components/aip/ActionBoundaryPanel";
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
  withdrawn: "已撤回",
};

export function actionStatusTab(status: ActionProposalStatus): InboxTab {
  if (status === "proposed" || status === "drafted") return "approval";
  if (status === "approved") return "approved";
  if (status === "leased" || status === "executing" || status === "unknown") return "execution";
  return "closed";
}

export function effectiveProposalStatus(
  proposal: ActionDraftBundle["proposal"],
  now = Date.now(),
): ActionProposalStatus {
  if (["proposed", "drafted", "approved"].includes(proposal.status)) {
    const expiry = new Date(proposal.expiresAt).getTime();
    if (Number.isFinite(expiry) && expiry <= now) return "expired";
  }
  return proposal.status;
}

const CHANGE_FIELD_LABELS: Record<string, string> = {
  status: "业务状态", price: "价格", salePrice: "销售价", stock: "库存",
  assignee: "负责人", channel: "渠道", content: "内容", title: "标题",
  schedule: "执行时间", customerGroup: "客户分群", reason: "原因",
};

function readableValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "未设置";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "string") return businessDisplayName(value, value);
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.map(readableValue).join("、");
  return JSON.stringify(value);
}

export function businessChangeRows(diff: Record<string, unknown>): Array<{ field: string; before: string; after: string }> {
  return Object.entries(diff).map(([key, raw]) => {
    const value = raw && typeof raw === "object" && !Array.isArray(raw) ? raw as Record<string, unknown> : { to: raw };
    return {
      field: CHANGE_FIELD_LABELS[key] || businessDisplayName(key, "业务字段"),
      before: readableValue(value.from),
      after: readableValue(value.to),
    };
  });
}

function timelineEventLabel(value: string): string {
  return ({
    proposed: "已创建执行提案", drafted: "已提交审批草稿", approved: "审批通过",
    rejected: "审批拒绝", leased: "已获取单次执行租约", executing: "已提交受控执行",
    applied: "外部结果已应用", failed: "执行失败", unknown: "外部结果待对账",
    reconciled: "已完成结果对账", compensated: "已建立补偿提案", withdrawn: "提案已由发起人撤回",
  } as Record<string, string>)[value] || "权威状态已更新";
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
  if (["rejected", "failed", "expired", "withdrawn"].includes(status)) return "bg-red-50 text-red-700 border-red-200";
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
    if (actionStatusTab(effectiveProposalStatus(proposal)) !== tab) return false;
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
  const [approvalReason, setApprovalReason] = useState("");
  const [withdrawReason, setWithdrawReason] = useState("");
  const [replacementOpen, setReplacementOpen] = useState(false);
  const [replacementPurpose, setReplacementPurpose] = useState("");
  const [replacementDiff, setReplacementDiff] = useState("{}");
  const [replacementExpiry, setReplacementExpiry] = useState("");
  const [compensationPurpose, setCompensationPurpose] = useState("");
  const generation = useRef(0);

  const counts = useMemo(() => items.reduce<Record<InboxTab, number>>((result, item) => {
    result[actionStatusTab(effectiveProposalStatus(item.proposal))] += 1;
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
    setApprovalReason("");
    setWithdrawReason("");
    setReplacementOpen(false);
    setCompensationPurpose("");
    void loadDetail(proposalId);
  };

  const mutate = async (label: string, action: () => Promise<unknown>) => {
    if (!selected || state !== "ready" || detailState !== "ready") return;
    setBusy(true);
    setError("");
    setNotice(`${label}请求提交中…`);
    try {
      const result = await action();
      setNotice(`${label}请求已接受，已从服务端重新读取权威状态。`);
      const preferredId = result && typeof result === "object" && "proposal" in result
        ? (result as { proposal?: { id?: unknown } }).proposal?.id
        : null;
      await load(typeof preferredId === "string" ? preferredId : selected.proposal.id);
    } catch (mutationError) {
      setNotice("");
      setError(`${label}失败：${message(mutationError)}。写操作已停止，请刷新后再判断。`);
      setDetailState("error");
    } finally {
      setBusy(false);
    }
  };

  const unknownReceipt = execution?.receipts.find((receipt) => receipt.receiptKind === "initial" && receipt.status === "unknown");
  const compensableReceipt = execution ? [...execution.receipts].reverse().find((receipt) => ["applied", "reconciled"].includes(receipt.status)) : undefined;
  const selectedStatus = selected ? effectiveProposalStatus(selected.proposal) : null;
  const writable = state === "ready" && detailState === "ready" && !busy && selectedStatus !== "expired";
  const changeRows = selected ? businessChangeRows(selected.proposal.diff || selected.draft.diff) : [];
  const policySnapshot = selected?.proposal.policySnapshot || {};
  const openReplacement = () => {
    if (!selected) return;
    setReplacementPurpose(`修订：${businessDisplayName(selected.proposal.purpose, "受控业务动作申请")}`);
    setReplacementDiff(JSON.stringify(selected.proposal.diff || selected.draft.diff, null, 2));
    const expiry = new Date(Date.now() + 24 * 60 * 60 * 1000);
    setReplacementExpiry(expiry.toISOString().slice(0, 16));
    setReplacementOpen(true);
  };
  const submitReplacement = async () => {
    if (!selected) return;
    let diff: Record<string, unknown>;
    try {
      const parsed = JSON.parse(replacementDiff) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("业务变更必须是 JSON 对象");
      diff = parsed as Record<string, unknown>;
    } catch (parseError) {
      setError(`修改草稿未提交：${message(parseError)}`);
      return;
    }
    await mutate("创建修改草稿并提交新提案", () => sdk.createReplacementProposal(selected, {
      purpose: replacementPurpose,
      diff,
      expiresAt: replacementExpiry,
    }));
    setReplacementOpen(false);
  };

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
          <p className="mt-1 text-xs">原子 Skill → Logic 编排 → 数字同事 → 工作台贡献视图；需要外部副作用时，再进入独立 Action / Effect 边界。</p>
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
                  <div className="flex items-center justify-between gap-2"><ProposalBadge status={effectiveProposalStatus(bundle.proposal)} /><span className="text-xs text-gray-400">{formatTime(bundle.proposal.updatedAt)}</span></div>
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
                    <div className="flex flex-wrap items-center gap-2"><ProposalBadge status={selectedStatus || selected.proposal.status} /><span className="text-xs text-gray-500">{riskDisplayName(selected.proposal.riskLevel)}</span><span className="ml-auto text-xs text-gray-400">版本 {selected.proposal.version}</span></div>
                    <h2 className="mt-2 text-lg font-semibold text-gray-900">{actionDisplayName(selected.proposal.actionType.actionTypeId)}</h2>
                    <p className="mt-1 text-sm text-gray-600">{businessDisplayName(selected.proposal.purpose, "受控业务动作申请")}</p>
                  </header>

                  {detailState === "loading" && <p role="status" className="p-10 text-center text-sm text-gray-500">正在读取执行租约、交付凭证与事件时间线…</p>}
                  {detailState === "ready" && timeline && execution && (
                    <div className="space-y-5 p-4">
                      {selectedStatus === "unknown" && (
                        <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">外部结果未知：禁止重复执行，只允许读取供应商状态并追加对账凭证。</div>
                      )}
                      <ActionBoundaryPanel bundle={selected} execution={execution} />
                      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="draft-business-impact">
                        <div className="rounded border border-gray-200 p-3"><strong className="block text-xs text-gray-500">影响对象</strong><span className="text-sm">{selected.proposal.objectRef ? `${objectTypeDisplayName(selected.proposal.objectRef.resourceType)} · ${businessDisplayName(selected.proposal.objectRef.resourceId, "已选业务对象")}` : "未绑定单一对象"}</span></div>
                        <div className="rounded border border-gray-200 p-3"><strong className="block text-xs text-gray-500">提案责任人</strong><span className="text-sm">{businessDisplayName(selected.proposal.createdBy.actorId, "当前提案发起人")}</span></div>
                        <div className="rounded border border-gray-200 p-3"><strong className="block text-xs text-gray-500">审批权限</strong><span className="text-sm">至少 {Number(policySnapshot.minimumApprovals || 1)} 人审批{policySnapshot.makerChecker ? " · 发起与审批分离" : ""}</span></div>
                        <div className="rounded border border-gray-200 p-3"><strong className="block text-xs text-gray-500">影响预览</strong><span className="text-sm">{selected.proposal.impactPreviewRef ? `已绑定修订 ${selected.proposal.impactPreviewRef.revision}` : "未绑定精确影响预览"}</span></div>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <details><summary>提案标识（审计用）</summary><code className="text-xs">{selected.proposal.id}</code></details>
                        <details><summary>内容摘要（审计用）</summary><code className="text-xs" title={selected.proposal.proposalHash}>{shortHash(selected.proposal.proposalHash)}</code></details>
                        <details><summary>任务与运行标识（审计用）</summary><span className="text-sm">{selected.proposal.taskId ?? "—"} / {selected.proposal.runId ?? "—"}</span></details>
                        <div><strong className="block text-xs text-gray-500">到期时间</strong><span className="text-sm">{formatTime(selected.proposal.expiresAt)}</span></div>
                      </div>

                      <div data-testid="draft-readable-changes">
                        <h3 className="text-sm font-semibold text-gray-800">业务变更前后对比</h3>
                        {changeRows.length === 0 ? <p className="mt-2 text-sm text-gray-500">本提案没有可展示的字段变更。</p> : (
                          <table className="data-table mt-2 w-full"><thead><tr><th>业务字段</th><th>变更前</th><th>变更后</th></tr></thead><tbody>{changeRows.map((row) => <tr key={row.field}><td>{row.field}</td><td>{row.before}</td><td>{row.after}</td></tr>)}</tbody></table>
                        )}
                        <details className="mt-2"><summary className="text-xs text-gray-500">查看审计原始差异</summary><pre className="mt-2 max-h-48 overflow-auto rounded bg-gray-950 p-3 text-xs text-gray-100">{JSON.stringify(selected.draft.diff, null, 2)}</pre></details>
                      </div>

                      <div data-testid="draft-evidence-summary">
                        <h3 className="text-sm font-semibold text-gray-800">业务证据与约束（{selected.draft.evidenceRefs.length}）</h3>
                        {selected.draft.evidenceRefs.length === 0 ? <p className="mt-2 text-sm text-amber-700">当前草稿未引用业务证据；审批人需按风险策略决定是否拒绝。</p> : <ul className="mt-2 space-y-1 text-sm">{selected.draft.evidenceRefs.map((ref) => <li key={`${ref.resourceType}:${ref.resourceId}:${ref.revision}`}>{businessDisplayName(ref.resourceType, "业务证据")} · 修订 {ref.revision || "未标明"} · {businessDisplayName(ref.authority, "权威来源")}</li>)}</ul>}
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
                          {selected.proposal.taskId && <Link to={`/aip/assist?taskId=${encodeURIComponent(selected.proposal.taskId)}${selected.proposal.runId ? `&runId=${encodeURIComponent(selected.proposal.runId)}` : ""}`} className="rounded border border-gray-300 bg-white px-2 py-1 text-gray-700 no-underline">任务协作上下文 →</Link>}
                          {selected.proposal.taskId && <Link to={`/aip/logic?taskId=${encodeURIComponent(selected.proposal.taskId)}${selected.proposal.runId ? `&runId=${encodeURIComponent(selected.proposal.runId)}` : ""}`} className="rounded border border-gray-300 bg-white px-2 py-1 text-gray-700 no-underline">业务逻辑与运行 →</Link>}
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

                      <div data-testid="draft-result-summary">
                        <h3 className="text-sm font-semibold text-gray-800">执行结果、补偿与回滚边界</h3>
                        <p className="mt-2 text-sm">{execution.receipts.length === 0 ? "尚无执行结果；审批通过不代表业务变更已经生效。" : `最新凭证：${statusDisplayName(execution.receipts[execution.receipts.length - 1]?.status || "unknown")}。`}</p>
                        {selected.proposal.compensationOriginalProposalId ? <p className="mt-1 text-sm">本提案由已确认结果生成补偿方案；仍须重新审批、获取租约并取得新交付凭证。</p> : null}
                        {selected.proposal.compensationResidualEffect ? <details><summary>补偿后残余影响（审计用）</summary><pre>{JSON.stringify(selected.proposal.compensationResidualEffect, null, 2)}</pre></details> : null}
                        {compensableReceipt && !selected.proposal.compensationOriginalProposalId ? (
                          <div className="mt-3 flex flex-wrap items-end gap-2 rounded border border-amber-200 bg-amber-50 p-3">
                            <label className="min-w-[260px] flex-1 text-sm">补偿目的
                              <input aria-label="补偿目的" value={compensationPurpose} onChange={(event) => setCompensationPurpose(event.target.value)} className="mt-1 w-full rounded border border-amber-300 bg-white px-2 py-1.5" placeholder="说明需要抵消的已确认业务影响" />
                            </label>
                            <button type="button" disabled={!writable || !compensationPurpose.trim()} className="rounded bg-amber-700 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void mutate("创建独立补偿提案", () => sdk.createCompensation(selected, compensableReceipt.id, compensationPurpose))}>创建补偿提案</button>
                            <p className="w-full text-xs text-amber-900">仅创建需重新审批的补偿提案，不会直接执行反向业务动作。</p>
                          </div>
                        ) : null}
                      </div>

                      <details>
                        <summary className="cursor-pointer text-sm font-semibold text-gray-800">权威事件时间线（{timeline.events.length}）</summary>
                        <ol className="mt-2 space-y-2">{timeline.events.map((event) => <li key={event.id} className="border-l-2 border-blue-200 pl-3 text-sm">{timelineEventLabel(event.type)} · {businessDisplayName(event.actorId, "系统或业务用户")} · {formatTime(event.createdAt)}</li>)}</ol>
                      </details>
                    </div>
                  )}

                  <footer className="flex flex-wrap gap-2 border-t border-gray-100 bg-gray-50 p-3">
                    {selectedStatus === "expired" && <p className="mr-auto text-sm text-red-700">提案已过有效期，写操作关闭；请基于最新业务事实创建新草稿。</p>}
                    {selectedStatus === "withdrawn" && <p className="mr-auto text-sm text-gray-700">提案已撤回，历史版本和审计事件保留；如需继续，请基于最新业务事实创建新草稿。</p>}
                    {selectedStatus === "drafted" && <>
                      <label className="min-w-[260px] flex-1 text-sm">审批意见
                        <input aria-label="审批意见" value={approvalReason} onChange={(event) => setApprovalReason(event.target.value)} className="mt-1 w-full rounded border border-gray-300 bg-white px-2 py-1.5" placeholder="填写基于业务影响和证据的审批意见" />
                      </label>
                      <button type="button" disabled={!writable || !approvalReason.trim()} className="self-end rounded bg-green-600 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void mutate("批准", () => sdk.decide(selected, "approved", approvalReason))}>批准精确版本</button>
                      <button type="button" disabled={!writable || !approvalReason.trim()} className="self-end rounded bg-red-600 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void mutate("拒绝", () => sdk.decide(selected, "rejected", approvalReason))}>拒绝</button>
                    </>}
                    {selectedStatus === "approved" && <button type="button" disabled={!writable} className="rounded bg-purple-600 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void mutate("获取执行租约", () => sdk.acquireLease(selected))}>获取单次执行租约</button>}
                    {selectedStatus === "leased" && execution?.lease && <button type="button" disabled={!writable} className="rounded bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void mutate("执行受控动作", () => sdk.execute(execution))}>执行一次</button>}
                    {selectedStatus === "unknown" && unknownReceipt && <button type="button" disabled={!writable || !unknownReceipt.providerRequestId} title={!unknownReceipt.providerRequestId ? "缺少 provider request id，不能自动对账" : undefined} className="rounded bg-amber-600 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void mutate("只读对账", () => sdk.reconcile(unknownReceipt.id, "草稿审批台人工发起只读对账"))}>只读对账</button>}
                    {(selectedStatus === "drafted" || selectedStatus === "approved") && <>
                      <label className="min-w-[240px] flex-1 text-sm">撤回原因
                        <input aria-label="撤回原因" value={withdrawReason} onChange={(event) => setWithdrawReason(event.target.value)} className="mt-1 w-full rounded border border-gray-300 bg-white px-2 py-1.5" placeholder="仅发起人可撤回，原因将进入审计事件" />
                      </label>
                      <button type="button" disabled={!writable || !withdrawReason.trim()} className="self-end rounded border border-red-300 bg-white px-3 py-2 text-sm text-red-700 disabled:opacity-50" onClick={() => void mutate("撤回提案", () => sdk.withdraw(selected, withdrawReason))}>撤回精确版本</button>
                    </>}
                    <button type="button" className="rounded border border-blue-300 bg-white px-3 py-2 text-sm text-blue-700" disabled={busy} onClick={openReplacement}>基于当前提案修改</button>
                    <button type="button" className="rounded border border-gray-300 bg-white px-3 py-2 text-sm" disabled={busy} onClick={() => void loadDetail(selected.proposal.id)}>重读详情</button>
                  </footer>
                  {replacementOpen && (
                    <section className="space-y-3 border-t border-blue-200 bg-blue-50 p-4" aria-label="修改草稿">
                      <div><h3 className="font-semibold text-blue-950">创建新修订草稿</h3><p className="text-xs text-blue-800">原提案保持不可变；提交后生成新的待审批提案。</p></div>
                      <label className="block text-sm">修改说明<input aria-label="修改说明" className="mt-1 w-full rounded border border-blue-200 bg-white px-3 py-2" value={replacementPurpose} onChange={(event) => setReplacementPurpose(event.target.value)} /></label>
                      <label className="block text-sm">业务变更 JSON<textarea aria-label="业务变更 JSON" rows={6} className="mt-1 w-full rounded border border-blue-200 bg-white px-3 py-2 font-mono text-xs" value={replacementDiff} onChange={(event) => setReplacementDiff(event.target.value)} /></label>
                      <label className="block text-sm">新提案有效期<input aria-label="新提案有效期" type="datetime-local" className="ml-2 rounded border border-blue-200 bg-white px-3 py-2" value={replacementExpiry} onChange={(event) => setReplacementExpiry(event.target.value)} /></label>
                      <div className="flex gap-2"><button type="button" disabled={busy || !replacementPurpose.trim() || !replacementExpiry} className="rounded bg-blue-700 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => void submitReplacement()}>提交为新审批提案</button><button type="button" className="rounded border border-gray-300 bg-white px-3 py-2 text-sm" onClick={() => setReplacementOpen(false)}>取消</button></div>
                    </section>
                  )}
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
