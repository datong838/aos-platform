import { useEffect, useMemo, useState } from "react";

import { listLogicGraphRevisions } from "./logicGraphApi";
import type { LogicGraphSnapshot } from "./logicCanvasGraph";

function changedNodeCount(left: LogicGraphSnapshot, right: LogicGraphSnapshot): number {
  const byId = new Map(left.nodes.map((node) => [node.id, JSON.stringify(node)]));
  const ids = new Set([...left.nodes.map((node) => node.id), ...right.nodes.map((node) => node.id)]);
  return [...ids].filter((id) => byId.get(id) !== JSON.stringify(right.nodes.find((node) => node.id === id))).length;
}

export function LogicRevisionHistoryPanel({ graphId }: { graphId: string }) {
  const [items, setItems] = useState<LogicGraphSnapshot[]>([]);
  const [leftRevision, setLeftRevision] = useState(0);
  const [rightRevision, setRightRevision] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    void listLogicGraphRevisions(graphId).then((result) => {
      if (cancelled) return;
      setItems(result.items);
      const newest = result.items.at(-1)?.revision || 0;
      const previous = result.items.at(-2)?.revision || newest;
      setLeftRevision(previous);
      setRightRevision(newest);
    }).catch((cause: unknown) => {
      if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
    });
    return () => { cancelled = true; };
  }, [graphId]);

  const comparison = useMemo(() => {
    const left = items.find((item) => item.revision === leftRevision);
    const right = items.find((item) => item.revision === rightRevision);
    if (!left || !right) return null;
    return {
      left,
      right,
      nodeChanges: changedNodeCount(left, right),
      edgeDelta: right.edges.length - left.edges.length,
      nameChanged: left.name !== right.name,
      descriptionChanged: left.description !== right.description,
    };
  }, [items, leftRevision, rightRevision]);

  return (
    <section className="card" style={{ padding: 14 }} aria-label="业务逻辑修订比较">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <div><h3 style={{ margin: 0 }}>修订历史比较</h3><p className="muted" style={{ margin: "4px 0 0" }}>每次保存形成不可变快照；比较不会修改当前画布。</p></div>
        <div style={{ display: "flex", gap: 8 }}>
          <select aria-label="比较起始修订" value={leftRevision} onChange={(event) => setLeftRevision(Number(event.target.value))}>{items.map((item) => <option key={item.revision} value={item.revision}>修订 {item.revision}</option>)}</select>
          <select aria-label="比较目标修订" value={rightRevision} onChange={(event) => setRightRevision(Number(event.target.value))}>{items.map((item) => <option key={item.revision} value={item.revision}>修订 {item.revision}</option>)}</select>
        </div>
      </div>
      {error && <div role="alert" className="notice" style={{ marginTop: 10, color: "var(--aos-red)" }}>{error}</div>}
      {comparison && <dl style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(120px,1fr))", gap: 8, margin: "12px 0 0" }}>
        <div className="notice"><dt>节点变化</dt><dd style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>{comparison.nodeChanges}</dd></div>
        <div className="notice"><dt>连接变化</dt><dd style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>{comparison.edgeDelta > 0 ? "+" : ""}{comparison.edgeDelta}</dd></div>
        <div className="notice"><dt>名称</dt><dd style={{ margin: 0 }}>{comparison.nameChanged ? "有变化" : "未变化"}</dd></div>
        <div className="notice"><dt>描述</dt><dd style={{ margin: 0 }}>{comparison.descriptionChanged ? "有变化" : "未变化"}</dd></div>
      </dl>}
      {!items.length && !error && <p className="muted">正在读取修订历史…</p>}
      {comparison && <details style={{ marginTop: 8 }}><summary>精确修订与摘要</summary><code>{comparison.left.id}@{comparison.left.revision} · {comparison.left.graph_hash}</code><br /><code>{comparison.right.id}@{comparison.right.revision} · {comparison.right.graph_hash}</code></details>}
    </section>
  );
}
