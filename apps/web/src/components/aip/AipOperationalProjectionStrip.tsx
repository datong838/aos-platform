import { useCallback, useEffect, useState } from "react";
import { aipOperationalProjection, type AipOperationalProjection } from "../../api/aipOperationalProjection";
import { formatBlockers } from "../../lib/aipChineseLabels";

const labels = [
  ["roles", "数字同事"],
  ["capabilities", "专业能力"],
  ["tools", "工具"],
  ["evalGates", "评测门"],
  ["routes", "模型路由"],
] as const;

export interface AipOperationalProjectionStripProps {
  onProjection?: (projection: AipOperationalProjection | null) => void;
}

export function AipOperationalProjectionStrip({ onProjection }: AipOperationalProjectionStripProps = {}) {
  const [data, setData] = useState<AipOperationalProjection | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setState("loading");
    try {
      const next = await aipOperationalProjection.read();
      setData(next);
      onProjection?.(next);
      setError("");
      setState("ready");
    } catch (cause) {
      setData(null);
      onProjection?.(null);
      setError(String((cause as Error).message || cause));
      setState("error");
    }
  }, [onProjection]);
  useEffect(() => {
    void load();
    const refresh = () => void load();
    window.addEventListener("aos-tenant-updated", refresh);
    return () => window.removeEventListener("aos-tenant-updated", refresh);
  }, [load]);

  if (state === "loading") {
    return <div className="notice" role="status" data-testid="aip-operational-projection-loading">正在读取 AIP 跨页权威投影…</div>;
  }
  if (state === "error" || !data) {
    return <div className="notice bad" role="alert" data-testid="aip-operational-projection-error">跨页权威投影不可用：{error || "未知错误"} <button className="btn" onClick={() => void load()}>重试</button></div>;
  }
  return (
    <section className="card" data-testid="aip-operational-projection" style={{ padding: 12, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 8 }}>
        <strong>智能体运行总览</strong>
        <span style={{ color: data.overallReadiness === "ready" ? "var(--aos-green-700)" : "var(--aos-amber-700)" }}>
          {data.overallReadiness === "ready" ? "可自动执行" : "需人工确认"}
        </span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(130px,1fr))", gap: 8 }}>
        {labels.map(([key, label]) => {
          const item = data[key];
          return <div key={key} className="notice" style={{ padding: "8px 10px" }}><div style={{ fontSize: 12 }}>{label}</div><strong>{item.runnable}/{item.definition} 可自动执行</strong><div style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>已绑定 {item.bound} · 已启用 {item.enabled}</div></div>;
        })}
      </div>
      {data.blockerCodes.length ? (
        <div style={{ marginTop: 8, fontSize: 12, color: "var(--aos-amber-700)" }}>
          自动执行前需确认：{formatBlockers(data.blockerCodes)}
          <details style={{ marginTop: 4 }}>
            <summary>技术标识（审计用）</summary>
            <code>{data.blockerCodes.join(" / ")}</code> · 快照 <code>{data.snapshotHash.slice(0, 12)}…</code>
          </details>
        </div>
      ) : null}
    </section>
  );
}
