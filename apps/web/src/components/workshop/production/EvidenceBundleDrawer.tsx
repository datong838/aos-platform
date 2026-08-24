import { useEffect, useRef } from "react";
import { ExactRefLink, IntentButton, ProductionFrame, trapModalKey } from "./primitives";
import type { ProductionComponentBase, ProductionExactRef } from "./types";

type Intent = "select" | "request_more";
export type EvidenceBundleDrawerProps = ProductionComponentBase<Intent> & { bundleRef: ProductionExactRef; evidenceRefs: ProductionExactRef[]; open: boolean; onClose: () => void; returnFocusRef?: { current: HTMLElement | null } };

export function EvidenceBundleDrawer(props: EvidenceBundleDrawerProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => { if (props.open) closeRef.current?.focus(); }, [props.open]);
  if (!props.open) return null;
  const close = () => { props.onClose(); props.returnFocusRef?.current?.focus(); };
  return <div className="production-overlay" role="presentation" onKeyDown={(event) => trapModalKey(event, dialogRef.current, close)}><aside ref={dialogRef} className="production-dialog" role="dialog" aria-modal="true" aria-label={props.title}><button ref={closeRef} type="button" className="btn" onClick={close}>关闭证据抽屉</button><ProductionFrame model={props}><ExactRefLink value={props.bundleRef} /><ul aria-label="证据精确引用">{props.evidenceRefs.map((ref) => <li key={`${ref.resourceType}:${ref.resourceId}:${ref.revision}`}><ExactRefLink value={ref} /></li>)}</ul><div className="production-actions"><IntentButton kind="select" subjectRef={props.bundleRef} allowed={props.allowedIntents?.includes("select") ?? false} onIntent={props.onIntent}>选择证据包</IntentButton><IntentButton kind="request_more" subjectRef={props.bundleRef} allowed={props.allowedIntents?.includes("request_more") ?? false} onIntent={props.onIntent}>请求补充</IntentButton></div></ProductionFrame></aside></div>;
}
