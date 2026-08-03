import type {
  InstallationListResponse,
  InstallationState,
} from "../../../api/assetControl/types";
import {
  installationPageControls,
  type AssetReadState,
  type InstallationPageRequest,
} from "./model";

export interface InstallationPanelProps {
  state: AssetReadState<InstallationListResponse>;
  request: InstallationPageRequest;
  selectedInstallationId: string | null;
  onStateChange: (state: InstallationState | undefined) => void;
  onPageChange: (offset: number) => void;
  onSelect: (installationId: string) => void;
}

const INSTALLATION_STATES: readonly InstallationState[] = [
  "draft", "submitted", "approved", "rejected", "applied", "active", "rolled_back",
];

const panelStyle = {
  border: "1px solid var(--aos-border)",
  borderRadius: 3,
  padding: 12,
} as const;

function Retry({ reload }: { reload: () => void }) {
  return <button type="button" className="btn" onClick={reload}>重试读取</button>;
}

function StateNotice({ state }: { state: InstallationPanelProps["state"] }) {
  if (state.status === "loading") return <p role="status">正在读取安装列表…</p>;
  if (state.status === "empty") return <div role="status"><p>当前筛选条件下暂无安装记录。</p><Retry reload={state.reload} /></div>;
  if (state.status === "forbidden") return <div role="alert"><strong>无权查看安装记录</strong><p>请申请资产安装读取权限。</p><Retry reload={state.reload} /></div>;
  if (state.status === "not_visible_or_missing") return <div role="alert"><strong>资源不可见或不存在</strong><p>为避免泄漏，不区分不存在与标记不可见。</p><Retry reload={state.reload} /></div>;
  if (state.status === "error") return <div role="alert"><strong>安装列表读取失败</strong><p>{state.error?.message ?? "未知错误"}</p><Retry reload={state.reload} /></div>;
  if (state.status === "idle") return <p role="status">尚未开始读取安装列表。</p>;
  return null;
}

export function InstallationPanel({
  state,
  request,
  selectedInstallationId,
  onStateChange,
  onPageChange,
  onSelect,
}: InstallationPanelProps) {
  const response = state.data;
  const items = response?.items ?? [];
  const mayShowData = state.status === "ready" || (state.status === "error" && state.stale);
  const controls = installationPageControls(
    response?.total ?? 0,
    response?.limit ?? request.limit,
    response?.offset ?? request.offset,
  );
  const start = response && response.total > 0 ? response.offset + 1 : 0;
  const end = response ? Math.min(response.offset + response.items.length, response.total) : 0;

  return (
    <section aria-label="安装列表" style={panelStyle}>
      <header>
        <h3 style={{ margin: 0 }}>安装管理（只读）</h3>
        <p style={{ color: "var(--aos-muted)", fontSize: "0.75rem" }}>列表数量与翻页均采用服务端 total、limit、offset。</p>
      </header>

      <label>
        状态筛选
        <select
          aria-label="安装状态筛选"
          value={request.state ?? ""}
          onChange={(event) => onStateChange(event.target.value ? event.target.value as InstallationState : undefined)}
        >
          <option value="">全部状态</option>
          {INSTALLATION_STATES.map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
      </label>

      {state.stale && mayShowData && <div role="status">当前安装列表是旧数据，刷新失败。<Retry reload={state.reload} /></div>}
      {state.refreshing && <p role="status">正在刷新安装列表…</p>}
      <StateNotice state={state} />

      {mayShowData && items.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><th>名称</th><th>状态</th><th>当前 revision</th><th>活跃指针</th><th>更新时间</th><th>选择</th></tr></thead>
          <tbody>
            {items.map((item) => {
              const active = item.installationId === selectedInstallationId;
              return (
                <tr key={item.installationId} data-selected={active || undefined}>
                  <td>{item.displayName}<br /><code>{item.installationId}</code></td>
                  <td>{item.state}</td>
                  <td>{item.currentRevision}</td>
                  <td>{item.activeRevision ?? "—"} / {item.previousActiveRevision ?? "—"}</td>
                  <td><time dateTime={item.updatedAt}>{item.updatedAt}</time></td>
                  <td><button type="button" className="btn" aria-pressed={active} onClick={() => onSelect(item.installationId)}>{active ? "已选择" : "查看事件"}</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {mayShowData && response && (
        <nav aria-label="安装列表分页" style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10 }}>
          <button type="button" className="btn" disabled={!controls.hasPrevious || state.refreshing} onClick={() => onPageChange(controls.previousOffset)}>上一页</button>
          <span>第 {start}–{end} 条 / 共 {response.total} 条 · limit {response.limit} · offset {response.offset}</span>
          <button type="button" className="btn" disabled={!controls.hasNext || state.refreshing} onClick={() => onPageChange(controls.nextOffset)}>下一页</button>
        </nav>
      )}
    </section>
  );
}
