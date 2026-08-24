import { ExactRefLink, IntentButton, ProductionFrame } from "./primitives";
import type { ProductionComponentBase, ProductionExactRef } from "./types";

type Intent = "resolve" | "return";
export type ReviewIssuePanelProps = ProductionComponentBase<Intent> & { issueRef: ProductionExactRef; severity: string; suggestedFix: string };
export function ReviewIssuePanel(props: ReviewIssuePanelProps) { return <ProductionFrame model={props}><ExactRefLink value={props.issueRef} /><p>严重级别：{props.severity}</p><p>建议修复：{props.suggestedFix}</p><div className="production-actions"><IntentButton kind="resolve" subjectRef={props.issueRef} allowed={props.allowedIntents?.includes("resolve") ?? false} onIntent={props.onIntent}>解决意图</IntentButton><IntentButton kind="return" subjectRef={props.issueRef} allowed={props.allowedIntents?.includes("return") ?? false} onIntent={props.onIntent}>退回意图</IntentButton></div></ProductionFrame>; }
