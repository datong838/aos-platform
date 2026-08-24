import { ExactRefLink, IntentButton, ProductionFrame } from "./primitives";
import type { ProductionComponentBase, ProductionDiffRow, ProductionExactRef } from "./types";

type Intent = "revise" | "freeze";
export type BriefInspectorProps = ProductionComponentBase<Intent> & { briefRef: ProductionExactRef; summary: string; diff: ProductionDiffRow[] };

export function BriefInspector(props: BriefInspectorProps) {
  return <ProductionFrame model={props}><ExactRefLink value={props.briefRef} /><p>{props.summary}</p><dl className="production-diff-text">{props.diff.map((row) => <div key={row.field}><dt>{row.field}</dt><dd>{row.before} → {row.after}</dd></div>)}</dl><div className="production-actions"><IntentButton kind="revise" subjectRef={props.briefRef} allowed={props.allowedIntents?.includes("revise") ?? false} onIntent={props.onIntent}>修订</IntentButton><IntentButton kind="freeze" subjectRef={props.briefRef} allowed={props.allowedIntents?.includes("freeze") ?? false} onIntent={props.onIntent}>冻结</IntentButton></div></ProductionFrame>;
}
