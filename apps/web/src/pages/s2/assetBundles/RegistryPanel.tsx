import type { RegistryBundleSummary } from "../../../api/assetControl/registry";
import type { AssetReadState, RegistryBundleSelection } from "./model";

export interface RegistryPanelProps {
  state: AssetReadState<RegistryBundleSummary[]>;
  selected: RegistryBundleSelection | null;
  onSelect: (selection: RegistryBundleSelection) => void;
}

const panelStyle = {
  border: "1px solid var(--aos-border)",
  borderRadius: 3,
  padding: 12,
} as const;

function Retry({ reload }: { reload: () => void }) {
  return <button type="button" className="btn" onClick={reload}>重试读取</button>;
}

function StateNotice({ state }: { state: RegistryPanelProps["state"] }) {
  if (state.status === "loading") return <p role="status">正在读取资产 Registry…</p>;
  if (state.status === "empty") {
    return <div role="status"><p>Registry 暂无资产包。</p><Retry reload={state.reload} /></div>;
  }
  if (state.status === "forbidden") {
    return <div role="alert"><strong>无权查看资产 Registry</strong><p>请申请资产读取权限后重试。</p><Retry reload={state.reload} /></div>;
  }
  if (state.status === "not_visible_or_missing") {
    return <div role="alert"><strong>资源不可见或不存在</strong><p>为避免泄漏，不区分资源不存在与标记不可见。</p><Retry reload={state.reload} /></div>;
  }
  if (state.status === "error") {
    return <div role="alert"><strong>资产 Registry 读取失败</strong><p>{state.error?.message ?? "未知错误"}</p><Retry reload={state.reload} /></div>;
  }
  if (state.status === "idle") return <p role="status">尚未开始读取资产 Registry。</p>;
  return null;
}

export function RegistryPanel({ state, selected, onSelect }: RegistryPanelProps) {
  const bundles = state.data ?? [];
  const mayShowData = state.status === "ready" || (state.status === "error" && state.stale);
  const showRows = mayShowData && bundles.length > 0;

  return (
    <section aria-label="资产 Registry" style={panelStyle}>
      <header>
        <h3 style={{ margin: 0 }}>资产 Registry</h3>
        <p style={{ color: "var(--aos-muted)", fontSize: "0.75rem" }}>
          下列内容来自 Canonical Registry，不使用演示数据兜底。
        </p>
      </header>

      {state.stale && mayShowData && (
        <div role="status" style={{ padding: 8, background: "var(--aos-amber-bg)" }}>
          当前展示的是上次成功读取的数据；刷新失败，数据可能已过期。
          <Retry reload={state.reload} />
        </div>
      )}
      {state.refreshing && <p role="status">正在刷新 Registry，当前数据保留并标记为旧数据…</p>}
      <StateNotice state={state} />

      {showRows && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><th>发布方</th><th>Bundle ID</th><th>名称</th><th>类型</th><th>选择</th></tr></thead>
          <tbody>
            {bundles.map((bundle) => {
              const active = selected?.publisher === bundle.publisher && selected.bundleId === bundle.bundleId;
              return (
                <tr key={`${bundle.publisher}/${bundle.bundleId}`} data-selected={active || undefined}>
                  <td><code>{bundle.publisher}</code></td>
                  <td><code>{bundle.bundleId}</code></td>
                  <td>{bundle.displayName}</td>
                  <td>{bundle.kind}</td>
                  <td>
                    <button
                      type="button"
                      className="btn"
                      aria-pressed={active}
                      onClick={() => onSelect({ publisher: bundle.publisher, bundleId: bundle.bundleId })}
                    >
                      {active ? "已选择" : "查看详情"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
