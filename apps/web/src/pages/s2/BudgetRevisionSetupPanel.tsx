import { useState } from "react";

import { apiGetAuthoritative, apiPostUnqueued } from "../../api/client";
import { getAuthRevision, getTenant } from "../../api/tenant";

export type BudgetDraftInput = {
  budgetId: string;
  dailyYuan: string;
  monthlyYuan: string;
  alertThresholdPct: string;
  effectiveFrom: string;
  effectiveUntil: string;
  owner: string;
  overBudgetApprover: string;
};

export type BudgetDraftBody = {
  budgetId: string; revision: 1; environment: "development"; currency: "CNY";
  dailyLimitMinor: number; monthlyLimitMinor: number; alertThresholdPct: number;
  hardStop: true; unknownUsageBehavior: "block";
  effectiveFrom: string; effectiveUntil: string;
  owner: string; overBudgetApprover: string; lifecycle: "draft";
};

type BudgetReadback = BudgetDraftBody & {
  tenant: { orgId: string; projectId: string };
  contentHash: string;
};

function yuanToMinor(value: string): number {
  if (!/^\d{1,8}(?:\.\d{1,2})?$/.test(value)) throw new Error("金额须为元，最多两位小数");
  const [yuan, fraction = ""] = value.split(".");
  const minor = Number(yuan) * 100 + Number(fraction.padEnd(2, "0"));
  if (!Number.isSafeInteger(minor) || minor <= 0) throw new Error("金额必须大于零");
  return minor;
}

export function buildBudgetDraft(input: BudgetDraftInput): BudgetDraftBody {
  const budgetId = input.budgetId.trim();
  const owner = input.owner.trim();
  const approver = input.overBudgetApprover.trim();
  if (!budgetId || budgetId.length > 160 || !owner || owner.length > 160 || !approver || approver.length > 160) {
    throw new Error("预算 ID、负责人和超预算审批人均须明确填写");
  }
  const dailyLimitMinor = yuanToMinor(input.dailyYuan);
  const monthlyLimitMinor = yuanToMinor(input.monthlyYuan);
  if (monthlyLimitMinor < dailyLimitMinor) throw new Error("月预算不得小于日预算");
  if (!/^(?:[1-9]|[1-9][0-9]|100)$/.test(input.alertThresholdPct)) {
    throw new Error("告警阈值须明确填写 1–100 的整数百分比");
  }
  const from = new Date(input.effectiveFrom);
  const until = new Date(input.effectiveUntil);
  if (!Number.isFinite(from.getTime()) || !Number.isFinite(until.getTime()) || until <= from) {
    throw new Error("须填写有效的预算生效起止时间");
  }
  return {
    budgetId, revision: 1, environment: "development", currency: "CNY",
    dailyLimitMinor, monthlyLimitMinor, alertThresholdPct: Number(input.alertThresholdPct),
    hardStop: true, unknownUsageBehavior: "block",
    effectiveFrom: from.toISOString(), effectiveUntil: until.toISOString(),
    owner, overBudgetApprover: approver, lifecycle: "draft",
  };
}

export function exactBudgetDraftReadback(value: unknown, expected: BudgetDraftBody, tenant: { orgId: string; projectId: string }): boolean {
  if (!value || typeof value !== "object") return false;
  const row = value as Partial<BudgetReadback>;
  return row.budgetId === expected.budgetId && row.revision === 1
    && row.tenant?.orgId === tenant.orgId && row.tenant?.projectId === tenant.projectId
    && /^([0-9a-f]{64})$/.test(row.contentHash ?? "")
    && row.dailyLimitMinor === expected.dailyLimitMinor && row.monthlyLimitMinor === expected.monthlyLimitMinor
    && row.alertThresholdPct === expected.alertThresholdPct && row.environment === expected.environment
    && row.currency === expected.currency
    && typeof row.effectiveFrom === "string" && Date.parse(row.effectiveFrom) === Date.parse(expected.effectiveFrom)
    && typeof row.effectiveUntil === "string" && Date.parse(row.effectiveUntil) === Date.parse(expected.effectiveUntil)
    && row.owner === expected.owner && row.overBudgetApprover === expected.overBudgetApprover
    && row.lifecycle === "draft" && row.hardStop === true && row.unknownUsageBehavior === "block";
}

const EMPTY: BudgetDraftInput = {
  budgetId: "", dailyYuan: "", monthlyYuan: "", alertThresholdPct: "", effectiveFrom: "", effectiveUntil: "",
  owner: "", overBudgetApprover: "",
};

export function BudgetRevisionSetupPanel() {
  const [input, setInput] = useState<BudgetDraftInput>(EMPTY);
  const [attempted, setAttempted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("仅创建 draft；不会激活预算、批准费用或启动模型调用。");
  const [attemptedBody, setAttemptedBody] = useState<BudgetDraftBody | null>(null);
  const [attemptedTenant, setAttemptedTenant] = useState<{ orgId: string; projectId: string; identity: string } | null>(null);

  function setField<K extends keyof BudgetDraftInput>(field: K, value: BudgetDraftInput[K]) {
    setInput(previous => ({ ...previous, [field]: value }));
  }

  async function submit() {
    if (busy || attempted) return;
    let body: BudgetDraftBody;
    try { body = buildBudgetDraft(input); } catch (error) { setMessage((error as Error).message); return; }
    const tenant = getTenant();
    const identity = JSON.stringify([tenant.orgId, tenant.projectId, tenant.subject, getAuthRevision()]);
    const key = `budget-draft-${crypto.randomUUID()}`;
    setAttempted(true);
    setAttemptedBody(body);
    setAttemptedTenant({ orgId: tenant.orgId, projectId: tenant.projectId, identity });
    setBusy(true);
    setMessage("正在提交唯一草稿命令并做权威回读…");
    try {
      const posted = await apiPostUnqueued<unknown>("/v1/aip/budgets", body,
        { "Idempotency-Key": key, "If-Match": "0" });
      const current = getTenant();
      if (identity !== JSON.stringify([current.orgId, current.projectId, current.subject, getAuthRevision()])) {
        throw new Error("提交期间身份或租户已变化");
      }
      const reread = await apiGetAuthoritative<unknown>(`/v1/aip/budgets/${encodeURIComponent(body.budgetId)}?revision=1`);
      const afterRead = getTenant();
      if (identity !== JSON.stringify([afterRead.orgId, afterRead.projectId, afterRead.subject, getAuthRevision()])) {
        throw new Error("权威回读期间身份或租户已变化");
      }
      if (!exactBudgetDraftReadback(posted, body, tenant) || !exactBudgetDraftReadback(reread, body, tenant)
          || (posted as BudgetReadback).contentHash !== (reread as BudgetReadback).contentHash) {
        throw new Error("提交与当前权威回读不一致");
      }
      setMessage(`预算 ${body.budgetId}@1 已以 draft 写入并精确回读；尚未激活或绑定安装。`);
    } catch (error) {
      setMessage(`提交结果未确认：${(error as Error).message}。请只读对账，勿换幂等键重发。`);
    } finally { setBusy(false); }
  }

  async function reconcile() {
    if (!attemptedBody || !attemptedTenant || busy) return;
    const tenant = getTenant();
    if (attemptedTenant.identity !== JSON.stringify([tenant.orgId, tenant.projectId, tenant.subject, getAuthRevision()])) {
      setMessage("身份或租户已变化；请回到原作用域核对，不能重发。");
      return;
    }
    setBusy(true);
    try {
      const reread = await apiGetAuthoritative<unknown>(`/v1/aip/budgets/${encodeURIComponent(attemptedBody.budgetId)}?revision=1`);
      const current = getTenant();
      if (attemptedTenant.identity !== JSON.stringify([current.orgId, current.projectId, current.subject, getAuthRevision()])) {
        throw new Error("权威回读期间身份或租户已变化");
      }
      setMessage(exactBudgetDraftReadback(reread, attemptedBody, tenant)
        ? `只读核对：预算 ${attemptedBody.budgetId}@1 的 draft 已存在；尚未激活。`
        : "只读核对与原请求不一致；冻结此命令，需人工排查。" );
    } catch {
      setMessage("只读核对仍无法确认；冻结此命令，勿重发。");
    } finally { setBusy(false); }
  }

  async function lookupExisting() {
    const budgetId = input.budgetId.trim();
    if (!budgetId || budgetId.length > 160 || busy) {
      setMessage("先填写有效预算 ID，再只读查询当前版本。");
      return;
    }
    const tenant = getTenant();
    const identity = JSON.stringify([tenant.orgId, tenant.projectId, tenant.subject, getAuthRevision()]);
    setBusy(true);
    try {
      const raw = await apiGetAuthoritative<unknown>(`/v1/aip/budgets/${encodeURIComponent(budgetId)}`);
      const current = getTenant();
      const row = raw as Partial<BudgetReadback>;
      if (identity !== JSON.stringify([current.orgId, current.projectId, current.subject, getAuthRevision()])
          || row.budgetId !== budgetId || row.tenant?.orgId !== tenant.orgId
          || row.tenant?.projectId !== tenant.projectId || !Number.isSafeInteger(row.revision)
          || !/^([0-9a-f]{64})$/.test(row.contentHash ?? "")) {
        throw new Error("当前版本身份或内容不一致");
      }
      setMessage(`只读查询：预算 ${budgetId}@${row.revision}，状态 ${row.lifecycle}；本页不会覆盖现有版本。`);
    } catch {
      setMessage("当前预算未能被权威确认；不能据此认定不存在，也不能覆盖或换键重发。");
    } finally { setBusy(false); }
  }

  return <section className="card" aria-label="预算草稿配置" style={{ padding: 18, marginTop: 16 }}>
    <h2>预算修订草稿</h2>
    <p>金额单位为元，服务端存分；日/月上限、告警阈值、负责人、超预算审批人及生效窗口均由您明确填写。此处不会自动激活或调用付费能力。</p>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
      <label>预算 ID<input value={input.budgetId} disabled={attempted} onChange={e => setField("budgetId", e.target.value)} /></label>
      <label>日上限（元）<input inputMode="decimal" value={input.dailyYuan} disabled={attempted} onChange={e => setField("dailyYuan", e.target.value)} /></label>
      <label>月上限（元）<input inputMode="decimal" value={input.monthlyYuan} disabled={attempted} onChange={e => setField("monthlyYuan", e.target.value)} /></label>
      <label>告警阈值（%）<input inputMode="numeric" value={input.alertThresholdPct} disabled={attempted} onChange={e => setField("alertThresholdPct", e.target.value)} /></label>
      <label>生效时间<input type="datetime-local" value={input.effectiveFrom} disabled={attempted} onChange={e => setField("effectiveFrom", e.target.value)} /></label>
      <label>失效时间<input type="datetime-local" value={input.effectiveUntil} disabled={attempted} onChange={e => setField("effectiveUntil", e.target.value)} /></label>
      <label>负责人<input value={input.owner} disabled={attempted} onChange={e => setField("owner", e.target.value)} /></label>
      <label>超预算审批人<input value={input.overBudgetApprover} disabled={attempted} onChange={e => setField("overBudgetApprover", e.target.value)} /></label>
    </div>
    <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
      <button type="button" className="btn" disabled={busy} onClick={() => void lookupExisting()}>按 ID 只读查询</button>
      <button type="button" className="btn btn-primary" disabled={busy || attempted} onClick={() => void submit()}>创建 draft 并核对</button>
      <button type="button" className="btn" disabled={busy || !attempted} onClick={() => void reconcile()}>只读核对原命令</button>
    </div>
    <p role="status">{message}</p>
  </section>;
}
