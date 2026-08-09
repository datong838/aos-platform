import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphSnapshot } from "../../api/ontologyExplorerContracts";
import {
  layoutOntologyGraph,
  stableObjectTypeColor,
  type OntologyGraphLayoutMode,
} from "./ontologyGraphLayout";
import "./OntologyGraphCanvas.css";

type Viewport = { x: number; y: number; scale: number };

export function OntologyGraphCanvas({
  snapshot,
  loading = false,
  error = null,
  onSelectNode,
  onExpandNode,
}: {
  snapshot: GraphSnapshot | null;
  loading?: boolean;
  error?: string | null;
  onSelectNode?: (node: GraphSnapshot["nodes"][number]) => void;
  onExpandNode?: (node: GraphSnapshot["nodes"][number]) => void;
}) {
  const shellRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; y: number; viewport: Viewport } | null>(null);
  const [layoutMode, setLayoutMode] = useState<OntologyGraphLayoutMode>("radial");
  const [displayMode, setDisplayMode] = useState<"graph" | "list">(() =>
    typeof window !== "undefined" && window.matchMedia("(max-width: 560px)").matches ? "list" : "graph",
  );
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, scale: 1 });
  const layout = useMemo(
    () => snapshot ? layoutOntologyGraph(snapshot, layoutMode) : null,
    [snapshot, layoutMode],
  );
  const adjacentKeys = useMemo(() => {
    if (!snapshot || !selectedKey) return new Set<string>();
    const keys = new Set([selectedKey]);
    snapshot.edges.forEach((edge) => {
      if (edge.source === selectedKey) keys.add(edge.target);
      if (edge.target === selectedKey) keys.add(edge.source);
    });
    return keys;
  }, [snapshot, selectedKey]);
  const objectTypes = useMemo(
    () => [...new Set(snapshot?.nodes.map((node) => node.objectType) || [])].sort(),
    [snapshot],
  );

  function fit() {
    if (!layout || !shellRef.current) return;
    const rect = shellRef.current.getBoundingClientRect();
    const scale = Math.min(1, Math.max(0.12, Math.min((rect.width - 48) / layout.width, (rect.height - 48) / layout.height)));
    setViewport({ x: (rect.width - layout.width * scale) / 2, y: (rect.height - layout.height * scale) / 2, scale });
  }

  useEffect(() => {
    const id = window.requestAnimationFrame(fit);
    return () => window.cancelAnimationFrame(id);
  }, [layout]);

  function zoom(multiplier: number) {
    setViewport((current) => ({ ...current, scale: Math.min(2.5, Math.max(0.12, current.scale * multiplier)) }));
  }

  function select(node: GraphSnapshot["nodes"][number]) {
    setSelectedKey(node.key);
    onSelectNode?.(node);
  }

  if (loading) return <div className="o1-graph-state" role="status">正在读取权威图快照…</div>;
  if (error) return <div className="o1-graph-state is-error" role="alert">{error}</div>;
  if (!snapshot || snapshot.nodes.length === 0 || !layout) {
    return <div className="o1-graph-state">暂无权威图实例，请先选择已接入的对象。</div>;
  }

  return (
    <section className="o1-graph" aria-label="知识图谱画布">
      <header className="o1-graph-meta">
        <div>
          <strong>{snapshot.graphDomain === "operational_lineage" ? "运行血缘图" : "领域知识图谱"}</strong>
          <span>{snapshot.nodes.length} 节点 · {snapshot.edges.length} 边</span>
          <span>watermark {snapshot.snapshot.watermark}</span>
        </div>
        {snapshot.page.truncated && <span className="o1-graph-warning">结果已按 {snapshot.limits.maxNodes} 节点截断</span>}
      </header>
      <div className="o1-graph-toolbar" role="toolbar" aria-label="图谱工具">
        <button type="button" onClick={() => zoom(1.2)} aria-label="放大图谱">放大</button>
        <button type="button" onClick={() => zoom(1 / 1.2)} aria-label="缩小图谱">缩小</button>
        <button type="button" onClick={() => setViewport({ x: 0, y: 0, scale: 1 })}>重置</button>
        <button type="button" onClick={fit}>适配</button>
        <button type="button" onClick={() => setLayoutMode((value) => value === "radial" ? "layered" : "radial")}>
          {layoutMode === "radial" ? "切换分层布局" : "切换放射布局"}
        </button>
        <button type="button" onClick={() => setDisplayMode((value) => value === "graph" ? "list" : "graph")}>
          {displayMode === "graph" ? "邻居列表" : "图谱画布"}
        </button>
      </div>
      <div className="o1-graph-legend" aria-label="图例">
        {objectTypes.map((objectType) => (
          <span key={objectType}><i style={{ background: stableObjectTypeColor(objectType) }} />{objectType}</span>
        ))}
        <span><b>实线</b> authoritative</span>
      </div>
      {displayMode === "list" ? (
        <div className="o1-graph-list">
          {layout.nodes.map((node) => (
            <button key={node.key} type="button" onClick={() => select(node)} onDoubleClick={() => onExpandNode?.(node)}>
              <i style={{ background: stableObjectTypeColor(node.objectType) }} />
              <span><strong>{node.label}</strong><small>{node.objectType} · {node.objectId} · depth {node.depth}</small></span>
            </button>
          ))}
        </div>
      ) : (
        <div
          ref={shellRef}
          className="o1-graph-viewport"
          data-testid="ontology-graph-viewport"
          onWheel={(event) => {
            event.preventDefault();
            zoom(event.deltaY > 0 ? 0.9 : 1.1);
          }}
          onPointerDown={(event) => {
            if ((event.target as Element).closest("[data-graph-node]")) return;
            dragRef.current = { x: event.clientX, y: event.clientY, viewport };
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            if (!dragRef.current) return;
            setViewport({
              ...dragRef.current.viewport,
              x: dragRef.current.viewport.x + event.clientX - dragRef.current.x,
              y: dragRef.current.viewport.y + event.clientY - dragRef.current.y,
            });
          }}
          onPointerUp={() => { dragRef.current = null; }}
        >
          <svg width="100%" height="100%" aria-label="权威知识图谱">
            <defs>
              <marker id="o1-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                <path d="M 0 0 L 8 4 L 0 8 z" fill="currentColor" />
              </marker>
            </defs>
            <g transform={`translate(${viewport.x} ${viewport.y}) scale(${viewport.scale})`}>
              {layout.edges.map((edge) => {
                const muted = selectedKey && (!adjacentKeys.has(edge.source) || !adjacentKeys.has(edge.target));
                return (
                  <g key={edge.key} className={muted ? "is-muted" : ""}>
                    <path className="o1-graph-edge" d={edge.path} markerEnd="url(#o1-arrow)" />
                    {(layout.edges.length <= 80 || edge.source === selectedKey || edge.target === selectedKey) && (
                      <text className="o1-graph-edge-label" x={edge.labelX} y={edge.labelY}>{edge.relationType}</text>
                    )}
                  </g>
                );
              })}
              {layout.nodes.map((node) => {
                const selected = selectedKey === node.key;
                const muted = selectedKey && !adjacentKeys.has(node.key);
                return (
                  <g
                    key={node.key}
                    data-graph-node
                    role="button"
                    tabIndex={0}
                    aria-label={`${node.label}，${node.objectType}，深度 ${node.depth}`}
                    className={`o1-graph-node ${selected ? "is-selected" : ""} ${muted ? "is-muted" : ""}`}
                    transform={`translate(${node.x - node.width / 2} ${node.y - node.height / 2})`}
                    onClick={() => select(node)}
                    onDoubleClick={() => onExpandNode?.(node)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        select(node);
                        if (event.key === "Enter") onExpandNode?.(node);
                      }
                    }}
                  >
                    <rect width={node.width} height={node.height} rx="5" />
                    <rect className="o1-graph-node-accent" width="7" height={node.height} rx="5" fill={stableObjectTypeColor(node.objectType)} />
                    <text className="o1-graph-node-title" x="18" y="23">{node.label.slice(0, 23)}</text>
                    <text className="o1-graph-node-meta" x="18" y="42">{node.objectType} · {node.objectId.slice(0, 18)} · d{node.depth}</text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
      )}
    </section>
  );
}
