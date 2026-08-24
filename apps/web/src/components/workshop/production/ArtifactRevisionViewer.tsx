import { ExactRefLink, IntentButton, ProductionFrame } from "./primitives";
import type { ProductionComponentBase, ProductionExactRef } from "./types";

type Intent = "compare" | "select";
export type ArtifactRevisionViewerProps = ProductionComponentBase<Intent> & { artifactRef: ProductionExactRef; family: string; relation: string };
export function ArtifactRevisionViewer(props: ArtifactRevisionViewerProps) { return <ProductionFrame model={props}><ExactRefLink value={props.artifactRef} /><dl><div><dt>产物家族</dt><dd>{props.family}</dd></div><div><dt>归因关系</dt><dd>{props.relation}</dd></div></dl><div className="production-actions"><IntentButton kind="compare" subjectRef={props.artifactRef} allowed={props.allowedIntents?.includes("compare") ?? false} onIntent={props.onIntent}>比较修订</IntentButton><IntentButton kind="select" subjectRef={props.artifactRef} allowed={props.allowedIntents?.includes("select") ?? false} onIntent={props.onIntent}>选择修订</IntentButton></div></ProductionFrame>; }
