import { ExactRefLink, IntentButton, ProductionFrame } from "./primitives";
import type { ProductionComponentBase, ProductionExactRef } from "./types";

type Intent = "select" | "rerun" | "open_lineage";
export type EvalContractBadgeProps = ProductionComponentBase<Intent> & { contractRef: ProductionExactRef; decision: string };
export function EvalContractBadge(props: EvalContractBadgeProps) { return <ProductionFrame model={props}><ExactRefLink value={props.contractRef} /><p>评价决定：{props.decision}</p><div className="production-actions"><IntentButton kind="select" subjectRef={props.contractRef} allowed={props.allowedIntents?.includes("select") ?? false} onIntent={props.onIntent}>选择契约</IntentButton><IntentButton kind="rerun" subjectRef={props.contractRef} allowed={props.allowedIntents?.includes("rerun") ?? false} onIntent={props.onIntent}>重新评价</IntentButton><IntentButton kind="open_lineage" subjectRef={props.contractRef} allowed={props.allowedIntents?.includes("open_lineage") ?? false} onIntent={props.onIntent}>查看归因</IntentButton></div></ProductionFrame>; }
