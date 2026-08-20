import { useCallback, useEffect, useState } from "react";
import { aipOperationalProjection, type AipOperationalProjection } from "../../api/aipOperationalProjection";

const labels = [
  ["roles", "数字同事"],
  ["capabilities", "专业能力"],
  ["tools", "工具"],
  ["evalGates", "Eval 门"],
  ["routes", "模型路由"],
] as const;

export function AipOperationalProjectionStrip() {
  const [data, setData] = useState<AipOperationalProjection | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setState("loading");
    try {
      setData(await aipOperationalProjection.read());
      setError("");
      setState("ready");
    } catch (cause) {
      setData(null);
      setError(String((cause as Error).message || cause));
      setState("error");
    }
  }, []);
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
        <strong>AIP 跨页运行真相</strong>
        <span style={{ color: data.overallReadiness === "ready" ? "var(--aos-green-700)" : "var(--aos-amber-700)" }}>
          {data.overallReadiness === "ready" ? "全链就绪" : "存在阻断"} · <code>{data.snapshotHash.slice(0, 12)}…</code>
        </span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(130px,1fr))", gap: 8 }}>
        {labels.map(([key, label]) => {
          const item = data[key];
          return <div key={key} className="notice" style={{ padding: "8px 10px" }}><div style={{ fontSize: 12 }}>{label}</div><strong>{item.runnable}/{item.definition} 可派发</strong><div style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>绑定 {item.bound} · 启用 {item.enabled}</div></div>;
        })}
      </div>
      {data.blockerCodes.length ? <div style={{ marginTop: 8, fontSize: 12, color: "var(--aos-amber-700)" }}>阻断：{data.blockerCodes.join(" / ")}</div> : null}
    </section>
  );
}
