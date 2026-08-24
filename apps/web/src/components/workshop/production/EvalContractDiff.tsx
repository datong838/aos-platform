import { ProductionFrame } from "./primitives";
import type { ProductionComponentBase, ProductionDiffRow } from "./types";

export type EvalContractDiffProps = ProductionComponentBase & { rows: ProductionDiffRow[] };
export function EvalContractDiff(props: EvalContractDiffProps) { return <ProductionFrame model={props}><table><caption>评价契约修订差异的文本替代</caption><thead><tr><th>字段</th><th>变更前</th><th>变更后</th></tr></thead><tbody>{props.rows.map((row) => <tr key={row.field}><th scope="row">{row.field}</th><td>{row.before}</td><td>{row.after}</td></tr>)}</tbody></table></ProductionFrame>; }
