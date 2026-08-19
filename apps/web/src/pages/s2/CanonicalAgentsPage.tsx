import { Link } from "react-router-dom";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  aipAgentControl,
  type AgentInstanceListResponse,
  type AgentRuntimeReadinessResponse,
} from "../../api/aipAgentControl";
import { PageChrome } from "../../components/PageChrome";
import { formatBlockers } from "../../lib/aipChineseLabels";

export function CanonicalAgentsPage() {
  const [data, setData] = useState<AgentInstanceListResponse | null>(null);
  const [runtime, setRuntime] = useState<AgentRuntimeReadinessResponse | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const [instances, readiness] = await Promise.all([
        aipAgentControl.listInstances(),
        aipAgentControl.runtimeReadiness(),
      ]);
      setData(instances);
      setRuntime(readiness);
      setError("");
    } catch (e) {
      setData(null);
      setRuntime(null);
      setError(String((e as Error).message || e));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const readinessByTemplate = useMemo(() => {
    const map = new Map<string, { readiness: "blocked" | "runnable"; blockers: string[] }>();
    for (const item of runtime?.catalog.items || []) {
      map.set(item.template.templateId, { readiness: item.runtimeReadiness, blockers: item.blockers });
    }
    return map;
  }, [runtime]);

  return (
    <PageChrome title="智能体列表" lede="当前组织与工作区的 AgentInstance；运行前置门未满足时诚实失败关闭">
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <button className="btn" type="button" onClick={() => void load()}>刷新</button>
        <Link to="/aip/agent-registry">打开智能体目录 →</Link>
        {runtime ? <span>目录可运行 {runtime.catalog.stats.runnableCount}/{runtime.catalog.stats.installedCount}</span> : null}
      </div>
      {error && <div role="alert" className="notice bad">实例读取失败：{error}</div>}
      {!data ? (
        <div className="card">正在读取组织实例…</div>
      ) : data.count === 0 ? (
        <div className="card">
          <h3>尚未安装智能体</h3>
          <p>请先在「智能体目录」安装电商六数字同事。本页不显示本地样例。</p>
          <Link to="/aip/agent-registry">前往安装 →</Link>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {data.items.map((item) => {
            const gate = readinessByTemplate.get(item.template.assetId);
            const runnable = gate?.readiness === "runnable";
            const statusLabel = item.status === "provisioning" ? "待配置" : item.status;
            const note = !gate
              ? "运行就绪尚未对账；请打开智能体目录刷新"
              : runnable
                ? "受限 Pilot 可运行（目录已就绪；本页不直接外呼）"
                : gate.blockers.length
                  ? formatBlockers(gate.blockers)
                  : "缺少完整能力/技能绑定与依赖快照，不能试运行";
            return (
              <article
                className="card"
                key={item.instanceId}
                style={{ padding: 18, display: "grid", gridTemplateColumns: "1fr auto", gap: 12 }}
              >
                <div>
                  <h3 style={{ margin: 0 }}>{item.overlay.displayName || item.instanceId}</h3>
                  <p>
                    <code>{item.instanceId}</code> · 模板{" "}
                    <code>
                      {item.template.assetId}@{item.template.revision}
                    </code>
                  </p>
                  <small>
                    组织 {item.tenant.orgId} · 工作区 {item.tenant.projectId} · revision {item.version}
                  </small>
                </div>
                <div>
                  <strong>{statusLabel}</strong>
                  <p style={{ color: runnable ? "var(--aos-green-700)" : "var(--aos-amber-700)" }}>{note}</p>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </PageChrome>
  );
}
