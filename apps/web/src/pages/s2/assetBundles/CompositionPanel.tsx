import type { CompositionRequest } from "../../../api/assetControl/types";

export interface CompositionPanelProps {
  request: CompositionRequest;
  resolving: boolean;
  disabledReason?: string | null;
  onRequestChange: (request: CompositionRequest) => void;
  onResolve: () => void;
}

const panelStyle = {
  border: "1px solid var(--aos-border)",
  borderRadius: 3,
  padding: 12,
} as const;

export function CompositionPanel({
  request,
  resolving,
  disabledReason,
  onRequestChange,
  onResolve,
}: CompositionPanelProps) {
  const intrinsicReason = request.requested.length === 0 ? "请先从 Registry 选择至少一个资产版本" : "";
  const reason = disabledReason || intrinsicReason;
  const disabled = resolving || Boolean(reason);

  return (
    <section aria-label="组合预检" style={panelStyle}>
      <header>
        <h3 style={{ margin: 0 }}>组合预检</h3>
        <p style={{ color: "var(--aos-muted)", fontSize: "0.75rem" }}>
          浏览器只提交受控请求；解析、选择、diff 与 hash 全部由服务端生成。
        </p>
      </header>

      <label>
        Platform API version
        <input
          aria-label="Platform API version"
          value={request.platformApiVersion}
          onChange={(event) => onRequestChange({ ...request, platformApiVersion: event.target.value })}
        />
      </label>
      <label>
        Platform release
        <input
          aria-label="Platform release"
          value={request.platformRelease}
          onChange={(event) => onRequestChange({ ...request, platformRelease: event.target.value })}
        />
      </label>
      <label>
        Environment
        <select
          aria-label="Environment"
          value={request.environment}
          onChange={(event) => onRequestChange({ ...request, environment: event.target.value as CompositionRequest["environment"] })}
        >
          <option value="dev">dev</option>
          <option value="staging">staging</option>
          <option value="prod">prod</option>
        </select>
      </label>

      <h4>请求资产（{request.requested.length}）</h4>
      {request.requested.length === 0 ? <p>尚未选择资产版本。</p> : (
        <ul>{request.requested.map((item) => <li key={`${item.publisher}/${item.id}`}><code>{item.publisher}/{item.id}@{item.version}</code></li>)}</ul>
      )}

      {request.registrySnapshotHash && <p>指定 Registry snapshot：<code>{request.registrySnapshotHash}</code>（只读）</p>}
      {request.currentInstallationRef && (
        <dl>
          <div><dt>当前 Installation</dt><dd><code>{request.currentInstallationRef.installationId}</code></dd></div>
          <div><dt>Revision</dt><dd>{request.currentInstallationRef.revision}</dd></div>
          <div><dt>Lock hash</dt><dd><code>{request.currentInstallationRef.lockHash}</code>（只读）</dd></div>
          <div><dt>Overlay revision</dt><dd><code>{request.currentInstallationRef.overlayRevision}</code></dd></div>
        </dl>
      )}

      <button
        type="button"
        className="btn btn-primary"
        disabled={disabled}
        title={resolving ? "服务端正在解析，请勿重复提交" : reason || "提交服务端解析"}
        onClick={() => { if (!disabled) onResolve(); }}
      >
        {resolving ? "解析中…" : "解析并生成不可变 Lock"}
      </button>
      {reason && <p role="status">{reason}</p>}
    </section>
  );
}
