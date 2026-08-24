import { IntentButton, ProductionFrame } from "./primitives";
import type { ProductionComponentBase, ProductionExactRef, ProductionUiState } from "./types";

type Intent = "resolve" | "reassign" | "takeover";
export type ResponsibilityMatrixProps = ProductionComponentBase<Intent> & { planRef: ProductionExactRef; slots: { slotId: string; responsibility: string; assignee: string; readiness: ProductionUiState }[] };
export function ResponsibilityMatrix(props: ResponsibilityMatrixProps) { return <ProductionFrame model={props}><table><caption>职责覆盖与实际就绪状态</caption><thead><tr><th>职责槽</th><th>责任</th><th>实际 assignee</th><th>当前状态</th></tr></thead><tbody>{props.slots.map((slot) => <tr key={slot.slotId}><th scope="row">{slot.slotId}</th><td>{slot.responsibility}</td><td>{slot.assignee}</td><td>{slot.readiness}</td></tr>)}</tbody></table><div className="production-actions">{(["resolve", "reassign", "takeover"] as const).map((kind) => <IntentButton key={kind} kind={kind} subjectRef={props.planRef} allowed={props.allowedIntents?.includes(kind) ?? false} onIntent={props.onIntent}>{kind === "resolve" ? "刷新就绪" : kind === "reassign" ? "改派" : "人工接管"}</IntentButton>)}</div></ProductionFrame>; }
