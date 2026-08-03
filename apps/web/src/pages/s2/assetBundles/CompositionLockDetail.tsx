import type { StoredCompositionLock } from "../../../api/assetControl/types";
import type { AssetReadState } from "./model";

export interface CompositionLockDetailProps {
  state: AssetReadState<StoredCompositionLock>;
}

const panelStyle = {
  border: "1px solid var(--aos-border)",
  borderRadius: 3,
  padding: 12,
} as const;

function Retry({ reload }: { reload: () => void }) {
  return <button type="button" className="btn" onClick={reload}>重试读取</button>;
}

function mayShow(state: AssetReadState<StoredCompositionLock>): boolean {
  return state.status === "ready" || (state.status === "error" && state.stale);
}

export function CompositionLockDetail({ state }: CompositionLockDetailProps) {
  const lock = state.data;
  const show = Boolean(lock && mayShow(state));

  return (
    <section aria-label="Composition Lock 详情" style={panelStyle}>
      <header>
        <h3 style={{ margin: 0 }}>不可变 Composition Lock</h3>
        <p>所有 lock payload、diff 与 hash 均来自服务端，只读且不在浏览器重算。</p>
      </header>
      {state.status === "idle" && <p role="status">尚未选择或生成 Composition Lock。</p>}
      {state.status === "loading" && <p role="status">正在读取 Composition Lock…</p>}
      {state.status === "empty" && <div role="status"><p>服务端未返回 Composition Lock。</p><Retry reload={state.reload} /></div>}
      {state.status === "forbidden" && <div role="alert"><strong>无权查看 Composition Lock</strong><p>请申请资产读取权限。</p><Retry reload={state.reload} /></div>}
      {state.status === "not_visible_or_missing" && <div role="alert"><strong>Composition Lock 不可见或不存在</strong><p>为避免泄漏，不区分不存在与标记不可见。</p><Retry reload={state.reload} /></div>}
      {state.status === "error" && <div role="alert"><strong>Composition Lock 读取失败</strong><p>{state.error?.message ?? "未知错误"}</p><Retry reload={state.reload} /></div>}
      {state.stale && mayShow(state) && <div role="status">当前 Lock 是旧数据，刷新失败。<Retry reload={state.reload} /></div>}
      {state.refreshing && <p role="status">正在刷新 Composition Lock…</p>}

      {show && lock && (
        <div data-composition-id={lock.compositionId}>
          <dl>
            <div><dt>Composition ID</dt><dd><code>{lock.compositionId}</code></dd></div>
            <div><dt>Revision</dt><dd>{lock.revision}</dd></div>
            <div><dt>Lock schema</dt><dd>{lock.payload.lockSchemaVersion}</dd></div>
            <div><dt>Resolver</dt><dd>{lock.payload.resolverVersion}</dd></div>
            <div><dt>Registry snapshot hash</dt><dd><code>{lock.payload.registrySnapshotHash}</code>（服务端只读）</dd></div>
            <div><dt>Lock hash</dt><dd><code>{lock.lockHash}</code>（服务端只读）</dd></div>
            <div><dt>Permission diff hash</dt><dd><code>{lock.permissionDiffHash}</code>（服务端只读）</dd></div>
            <div><dt>Migration plan hash</dt><dd><code>{lock.migrationPlanHash}</code>（服务端只读）</dd></div>
            <div><dt>Contribution diff hash</dt><dd><code>{lock.contributionDiffHash}</code>（服务端只读）</dd></div>
            <div><dt>创建时间</dt><dd><time dateTime={lock.createdAt}>{lock.createdAt}</time></dd></div>
          </dl>

          <h4>Canonical request</h4>
          <p>{lock.payload.request.platformApiVersion} · {lock.payload.request.platformRelease} · {lock.payload.request.environment}</p>
          <ul>{lock.payload.request.requested.map((item) => <li key={`${item.publisher}/${item.id}`}><code>{item.publisher}/{item.id}@{item.version}</code></li>)}</ul>

          <h4>Current installation reference</h4>
          {lock.payload.currentInstallationRef ? (
            <dl>
              <div><dt>Installation ID</dt><dd><code>{lock.payload.currentInstallationRef.installationId}</code></dd></div>
              <div><dt>Revision</dt><dd>{lock.payload.currentInstallationRef.revision}</dd></div>
              <div><dt>Lock hash</dt><dd><code>{lock.payload.currentInstallationRef.lockHash}</code>（只读）</dd></div>
              <div><dt>Overlay revision</dt><dd><code>{lock.payload.currentInstallationRef.overlayRevision}</code></dd></div>
            </dl>
          ) : <p>无当前安装基线。</p>}
        </div>
      )}
    </section>
  );
}
