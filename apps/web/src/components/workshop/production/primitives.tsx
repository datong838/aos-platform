import type { KeyboardEvent, MouseEvent, ReactNode } from "react";
import type { ProductionBlocker, ProductionComponentBase, ProductionContributionLineage, ProductionExactRef, ProductionIntent, ProductionReceipt, ProductionUiState } from "./types";

const STATE_LABELS: Record<ProductionUiState, string> = {
  loading: "读取中", empty: "可信空", partial: "部分可用", stale: "已过期", blocked: "等待条件",
  forbidden: "无权访问", unknown: "待核对", ready: "可用", failed: "读取失败",
};

export function ReadinessBadge({ state }: { state: ProductionUiState }) {
  return <span className={`production-readiness is-${state}`} role="status">{STATE_LABELS[state]}</span>;
}

export function ExactRefLink({ value, href }: { value: ProductionExactRef; href?: string }) {
  const label = `${value.resourceType} · ${value.resourceId} · r${value.revision}`;
  const content = <><span>{label}</span><code title={value.contentHash}>{value.contentHash.slice(0, 12)}…</code></>;
  return href ? <a className="production-exact-ref" href={href}>{content}</a> : <span className="production-exact-ref">{content}</span>;
}

export function ReceiptLink({ value }: { value: ProductionReceipt }) {
  return value.href ? <a href={value.href}>{value.label} · {value.receiptId}</a> : <span>{value.label} · {value.receiptId}</span>;
}

export function BlockerList({ items }: { items: ProductionBlocker[] }) {
  if (!items.length) return <p className="production-clear">当前数据截止面没有待补条件；仍以正式来源回读为准。</p>;
  return <ul className="production-blockers" aria-label="阻断原因">{items.map((item) => <li key={`${item.code}:${item.message}`}>
    <strong>{item.message}</strong><span>责任方：{item.owner || "待确认"} · {item.cutoffAt ?? "截止时间未提供"}</span><p>{item.href ? <a href={item.href}>{item.requiredAction} →</a> : item.requiredAction}</p><details><summary>技术状态码（审计用）</summary><code>{item.code}</code></details>
  </li>)}</ul>;
}

export function ContributionLineage({ value }: { value: ProductionContributionLineage }) {
  return <ol className="production-lineage" aria-label="专业贡献归因路径">
    <li><span>原子技能</span>{value.atomicSkillRef ? <ExactRefLink value={value.atomicSkillRef} /> : <strong>待核对</strong>}</li>
    <li><span>逻辑编排</span>{value.logicRef ? <ExactRefLink value={value.logicRef} /> : <strong>待核对</strong>}</li>
    <li><span>数字同事</span><strong>{value.coworker ? `${value.coworker.roleName} · ${value.coworker.assigneeId}` : "待核对"}</strong></li>
    <li><span>工作台贡献</span><strong>{value.workshopContribution}</strong></li>
  </ol>;
}

export function AuthorityStateBoundary({ state, title, children }: { state: ProductionUiState; title: string; children: ReactNode }) {
  const terminal = state === "failed" || state === "forbidden";
  return <section className={`production-authority-state is-${state}`} aria-label={`${title} · ${STATE_LABELS[state]}`} aria-live={terminal ? "assertive" : "polite"}>
    {state === "loading" ? <p>正在读取正式业务数据…</p> : null}
    {state === "empty" ? <p>当前是可信空集合，没有用样例或本地缓存补齐。</p> : null}
    {state === "failed" ? <p role="alert">正式业务数据读取失败，当前不推断业务结论。</p> : null}
    {state === "forbidden" ? <p role="alert">当前操作者无权读取该业务数据。</p> : null}
    {!terminal && state !== "loading" && state !== "empty" ? children : null}
  </section>;
}

export function IntentButton<Kind extends string>({ kind, subjectRef, allowed, onIntent, children }: { kind: Kind; subjectRef: ProductionExactRef; allowed: boolean; onIntent?: (intent: ProductionIntent<Kind>) => void; children: ReactNode }) {
  const click = (event: MouseEvent<HTMLButtonElement>) => {
    if (!allowed) { event.preventDefault(); return; }
    onIntent?.({ kind, subjectRef });
  };
  return <button type="button" className="btn" aria-disabled={!allowed} title={allowed ? undefined : "服务端 command readiness 未允许"} onClick={click}>{children}</button>;
}

export function ProductionFrame<Kind extends string>({ model, children }: { model: ProductionComponentBase<Kind>; children: ReactNode }) {
  return <article className="production-frame"><header><h2>{model.title}</h2><ReadinessBadge state={model.state} /></header><ContributionLineage value={model.lineage} /><AuthorityStateBoundary state={model.state} title={model.title}>{children}</AuthorityStateBoundary>{model.blockers.length || model.state === "blocked" || model.state === "partial" || model.state === "stale" || model.state === "unknown" ? <BlockerList items={model.blockers} /> : null}{model.receipts?.length ? <footer aria-label="回读凭证">{model.receipts.map((item) => <ReceiptLink key={item.receiptId} value={item} />)}</footer> : null}</article>;
}

export function trapModalKey(event: KeyboardEvent<HTMLElement>, root: HTMLElement | null, close: () => void) {
  if (event.key === "Escape") { event.preventDefault(); close(); return; }
  if (event.key !== "Tab" || !root) return;
  const focusable = [...root.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],[tabindex]:not([tabindex="-1"])')];
  if (!focusable.length) return;
  const first = focusable[0]; const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
