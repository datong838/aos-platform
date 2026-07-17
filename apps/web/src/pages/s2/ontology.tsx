import { ItemsPage, JsonBlock, S2Chrome, useJsonGet } from "./shared";

export function GraphHealthPage() {
  const { data, err, reload } = useJsonGet<Record<string, unknown>>("/v1/ontology/graph-health");
  return (
    <S2Chrome title="图谱健康度" lede="对齐 ontology-graph-health · GH 指标（≠ L1 health）">
      <button type="button" className="btn" onClick={() => reload()}>
        刷新
      </button>
      {err && <p className="error">{err}</p>}
      {data && (
        <p className="aos-text">
          score=<strong>{String(data.score)}</strong>
        </p>
      )}
      <JsonBlock value={data} />
    </S2Chrome>
  );
}

export function FunnelPage() {
  const { data, err, reload } = useJsonGet<Record<string, unknown>>(
    "/v1/funnel/WorkOrder/status",
  );
  return (
    <S2Chrome title="漏斗管道" lede="对齐 ontology-funnel · WorkOrder 四阶段">
      <button type="button" className="btn" onClick={() => reload()}>
        刷新
      </button>
      {err && <p className="error">{err}</p>}
      <JsonBlock value={data} />
    </S2Chrome>
  );
}

export function WikiPage() {
  const { data, err, reload } = useJsonGet<Record<string, unknown>>(
    "/v1/wiki/WorkOrder/wo-1001",
  );
  return (
    <S2Chrome title="活知识 Wiki" lede="对齐 ontology-wiki · seed wo-1001 只读">
      <button type="button" className="btn" onClick={() => reload()}>
        刷新
      </button>
      {err && <p className="error">{err}</p>}
      <JsonBlock value={data} />
    </S2Chrome>
  );
}

export function BranchesPage() {
  return (
    <ItemsPage
      title="分支管理"
      lede="对齐 ontology-branches · meta_branch"
      path="/v1/ontology/branches"
    />
  );
}
