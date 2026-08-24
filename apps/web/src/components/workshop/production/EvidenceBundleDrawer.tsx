import { useEffect, useRef, useState } from "react";
import { aipEvidenceSdk, type AipEvidenceSdk } from "../../../api/aipEvidence/client";
import type { EvidenceDisclosureDecision, EvidenceDisclosureLevel, EvidenceDisclosurePurpose } from "../../../api/aipEvidence/contracts";
import { ExactRefLink, IntentButton, ProductionFrame, trapModalKey } from "./primitives";
import type { ProductionComponentBase, ProductionExactRef } from "./types";

type Intent = "select" | "request_more";
export type EvidenceBundleDrawerProps = ProductionComponentBase<Intent> & {
  bundleRef: ProductionExactRef;
  evidenceRefs: ProductionExactRef[];
  open: boolean;
  onClose: () => void;
  returnFocusRef?: { current: HTMLElement | null };
  disclosureSdk?: Pick<AipEvidenceSdk, "resolveDisclosure">;
};

const levelRank: Record<EvidenceDisclosureLevel, number> = { l1: 1, l2: 2, l3: 3 };
const statusLabel = { allowed: "已授权", blocked: "已阻断", stale: "已过期", unknown: "状态未知" } as const;

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "unknown";
  if (Array.isArray(value)) return value.length ? value.join("、") : "unknown";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function EvidenceBundleDrawer(props: EvidenceBundleDrawerProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [decisions, setDecisions] = useState<Record<string, EvidenceDisclosureDecision>>({});
  useEffect(() => { if (props.open) closeRef.current?.focus(); }, [props.open]);
  if (!props.open) return null;
  const close = () => { props.onClose(); props.returnFocusRef?.current?.focus(); };
  const resolve = async (ref: ProductionExactRef, purpose: EvidenceDisclosurePurpose, requestedLevel: EvidenceDisclosureLevel) => {
    if (ref.resourceType !== "Evidence") { setError("证据引用类型无效，已保持失败关闭。"); return; }
    const key = `${ref.resourceId}:${requestedLevel}`;
    setPending(key); setError("");
    try {
      const decision = await (props.disclosureSdk ?? aipEvidenceSdk).resolveDisclosure({ evidenceRef: { resourceType: "Evidence", resourceId: ref.resourceId, revision: ref.revision, contentHash: ref.contentHash }, purpose, requestedLevel }, `workshop-disclosure-${crypto.randomUUID()}`);
      setDecisions((current) => ({ ...current, [ref.resourceId]: decision }));
    } catch (caught) { setError(String((caught as Error).message || caught)); }
    finally { setPending(""); }
  };
  return <div className="production-overlay" role="presentation" onKeyDown={(event) => trapModalKey(event, dialogRef.current, close)}><aside ref={dialogRef} className="production-dialog" role="dialog" aria-modal="true" aria-label={props.title}><button ref={closeRef} type="button" className="btn" onClick={close}>关闭证据抽屉</button><ProductionFrame model={props}><ExactRefLink value={props.bundleRef} />
    {props.evidenceRefs.length === 0 ? <p className="notice">该证据包没有可披露的精确证据引用；不会生成样例内容。</p> : <ul aria-label="证据精确引用">{props.evidenceRefs.map((ref) => {
      const decision = decisions[ref.resourceId];
      const grantedRank = decision?.grantedLevel ? levelRank[decision.grantedLevel] : 0;
      const expired = Boolean(decision?.expiresAt && new Date(decision.expiresAt).getTime() <= Date.now());
      return <li key={`${ref.resourceType}:${ref.resourceId}:${ref.revision}`} style={{ marginBottom: 16 }}><ExactRefLink value={ref} /><div className="production-actions">
        <button className="btn" type="button" disabled={Boolean(pending)} onClick={() => void resolve(ref, "summary", "l1")}>{pending === `${ref.resourceId}:l1` ? "读取安全摘要中…" : "查看安全摘要"}</button>
        <button className="btn" type="button" disabled={Boolean(pending) || grantedRank < 1} title={grantedRank < 1 ? "先取得服务端 L1 决策" : "服务端会重新裁决 marking、许可与时效"} onClick={() => void resolve(ref, "excerpt", "l2")}>{pending === `${ref.resourceId}:l2` ? "读取引用中…" : "查看最小引用片段"}</button>
        <button className="btn" type="button" disabled={Boolean(pending) || grantedRank < 2} title={grantedRank < 2 ? "先取得服务端 L2 决策" : "只申请短期 scoped source ref，不下载正文"} onClick={() => void resolve(ref, "source", "l3")}>{pending === `${ref.resourceId}:l3` ? "申请来源引用中…" : "申请短期来源引用"}</button>
      </div>{decision ? <section className={`notice ${decision.status === "allowed" && !expired ? "" : "bad"}`} aria-label={`证据披露决策 ${statusLabel[decision.status]}`} aria-live="polite"><strong>{expired ? "授权引用已过期" : statusLabel[decision.status]} · {decision.requestedLevel.toUpperCase()}</strong>
        {decision.status === "allowed" && !expired ? <>{decision.requestedLevel === "l1" ? <p>来源：{displayValue(decision.displayPayload.sourceType)} · 采集：{displayValue(decision.displayPayload.capturedAt)} · 时效：{displayValue(decision.displayPayload.freshnessAt)} · 适用性：{displayValue(decision.displayPayload.applicability)} · 标记：{displayValue(decision.displayPayload.marking)} · 许可：{displayValue(decision.displayPayload.licenseStatus)}</p> : null}{decision.requestedLevel === "l2" ? <><p>{displayValue(decision.displayPayload.excerpt)}</p><details><summary>精确定位（审计用）</summary><code>{displayValue(decision.displayPayload.locator)}</code></details></> : null}{decision.requestedLevel === "l3" ? <p>已获得短期来源引用，有效期至 {decision.expiresAt ? new Date(decision.expiresAt).toLocaleString() : "unknown"}；本抽屉不会自动下载或缓存正文。</p> : null}</> : <p>服务端未返回正文。原因：{decision.reasons.length ? decision.reasons.join("、") : "unknown"}</p>}
        <details><summary>披露决策（审计用）</summary><code>{decision.decisionId}</code> · 摘要 <code>{decision.decisionHash.slice(0, 12)}…</code></details></section> : null}</li>;
    })}</ul>}
    {error ? <p role="alert" className="notice bad">证据披露读取失败：{error}</p> : null}
    <div className="production-actions"><IntentButton kind="select" subjectRef={props.bundleRef} allowed={props.allowedIntents?.includes("select") ?? false} onIntent={props.onIntent}>选择证据包</IntentButton><IntentButton kind="request_more" subjectRef={props.bundleRef} allowed={props.allowedIntents?.includes("request_more") ?? false} onIntent={props.onIntent}>请求补充</IntentButton></div></ProductionFrame></aside></div>;
}
