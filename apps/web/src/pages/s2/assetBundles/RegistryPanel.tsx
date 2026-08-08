import type {
  RegistryBundleDetail,
  RegistryBundleSummary,
  RegistryVersionDetail,
} from "../../../api/assetControl/registry";
import { apiPost } from "../../../api/client";
import type {
  AssetReadState,
  RegistryBundleSelection,
  RegistryVersionSelection,
} from "./model";
import { useState } from "react";

export interface RegistryPanelProps {
  state: AssetReadState<RegistryBundleSummary[]>;
  selected: RegistryBundleSelection | null;
  onSelect: (selection: RegistryBundleSelection) => void;
  detailState?: AssetReadState<RegistryBundleDetail>;
  versionState?: AssetReadState<RegistryVersionDetail>;
  selectedVersion?: RegistryVersionSelection | null;
  onSelectVersion?: (selection: RegistryVersionSelection) => void;
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

function DetailStateNotice({
  state,
  label,
}: {
  state: AssetReadState<unknown>;
  label: string;
}) {
  if (state.status === "loading") return <p role="status">正在读取{label}…</p>;
  if (state.status === "empty") return <div role="status"><p>{label}为空。</p><Retry reload={state.reload} /></div>;
  if (state.status === "forbidden") return <div role="alert"><strong>无权查看{label}</strong><p>请申请资产读取权限。</p><Retry reload={state.reload} /></div>;
  if (state.status === "not_visible_or_missing") return <div role="alert"><strong>{label}不可见或不存在</strong><p>为避免泄漏，不区分不存在与标记不可见。</p><Retry reload={state.reload} /></div>;
  if (state.status === "error") return <div role="alert"><strong>{label}读取失败</strong><p>{state.error?.message ?? "未知错误"}</p><Retry reload={state.reload} /></div>;
  if (state.status === "idle") return <p role="status">请选择记录以读取{label}。</p>;
  return null;
}

function mayShow<T>(state: AssetReadState<T>): boolean {
  return state.status === "ready" || (state.status === "error" && state.stale);
}

function StaleNotice({ state, label }: { state: AssetReadState<unknown>; label: string }) {
  if (!state.stale || !mayShow(state)) return null;
  return <div role="status">当前{label}是旧数据，刷新失败。<Retry reload={state.reload} /></div>;
}

function BundleDetail({
  detail,
  selectedVersion,
  onSelectVersion,
  onVersionAction,
}: {
  detail: RegistryBundleDetail;
  selectedVersion: RegistryVersionSelection | null;
  onSelectVersion?: (selection: RegistryVersionSelection) => void;
  onVersionAction?: () => void;
}) {
  const [actionMsg, setActionMsg] = useState("");
  const [actioning, setActioning] = useState<string | null>(null);

  async function versionAction(version: string, action: "publish" | "deprecate" | "revoke") {
    setActionMsg("");
    setActioning(`${version}:${action}`);
    try {
      await apiPost(
        `/v1/bundles/${encodeURIComponent(detail.publisher)}/${encodeURIComponent(detail.bundleId)}/versions/${encodeURIComponent(version)}/${action}`,
        {},
      );
      setActionMsg(`已${action === "publish" ? "发布" : action === "deprecate" ? "废弃" : "撤销"}版本 ${version}`);
      onVersionAction?.();
    } catch (e) {
      setActionMsg(String((e as Error).message || e));
    } finally {
      setActioning(null);
    }
  }

  return (
    <section aria-label="Registry Bundle 详情" style={{ ...panelStyle, marginTop: 10 }}>
      <h4>Bundle 详情</h4>
      <dl>
        <div><dt>发布方</dt><dd><code>{detail.publisher}</code></dd></div>
        <div><dt>Bundle ID</dt><dd><code>{detail.bundleId}</code></dd></div>
        <div><dt>名称</dt><dd>{detail.displayName}</dd></div>
        <div><dt>类型</dt><dd>{detail.kind}</dd></div>
      </dl>
      {actionMsg && <div role="status" style={{ padding: 6, fontSize: "0.8rem", color: "var(--aos-muted)" }}>{actionMsg}</div>}
      <h5>真实版本（{detail.versions.length}）</h5>
      {detail.versions.length === 0 ? <p>该 Bundle 暂无服务端版本。</p> : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><th>版本</th><th>状态</th><th>Content hash</th><th>签名</th><th>创建者</th><th>选择</th><th>生命周期</th></tr></thead>
          <tbody>
            {detail.versions.map((version) => {
              const selection = { publisher: detail.publisher, bundleId: detail.bundleId, version: version.version };
              const active = selectedVersion?.publisher === selection.publisher
                && selectedVersion.bundleId === selection.bundleId
                && selectedVersion.version === selection.version;
              const canPublish = version.status === "draft" || version.status === "validated";
              const canDeprecate = version.status === "published";
              const canRevoke = version.status === "published";
              const actionKey = `${version.version}:`;
              return (
                <tr key={version.version} data-selected={active || undefined}>
                  <td><code>{version.version}</code></td>
                  <td>{version.status}</td>
                  <td><code>{version.contentHash}</code></td>
                  <td>{version.signature ? `${version.signature.algorithm} · ${version.signature.keyId} · ${version.signature.signedAt}` : "未签名"}</td>
                  <td>{version.createdBy}</td>
                  <td><button type="button" className="btn" aria-pressed={active} disabled={!onSelectVersion} onClick={() => onSelectVersion?.(selection)}>{active ? "已选择版本" : "查看版本事实"}</button></td>
                  <td style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {canPublish && (
                      <button
                        type="button"
                        className="btn"
                        disabled={actioning === `${actionKey}publish`}
                        onClick={() => void versionAction(version.version, "publish")}
                      >发布</button>
                    )}
                    {canDeprecate && (
                      <button
                        type="button"
                        className="btn"
                        disabled={actioning === `${actionKey}deprecate`}
                        onClick={() => void versionAction(version.version, "deprecate")}
                      >废弃</button>
                    )}
                    {canRevoke && (
                      <button
                        type="button"
                        className="btn"
                        disabled={actioning === `${actionKey}revoke`}
                        onClick={() => void versionAction(version.version, "revoke")}
                      >撤销</button>
                    )}
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

function VersionDetail({ detail }: { detail: RegistryVersionDetail }) {
  return (
    <section aria-label="Registry 版本详情" style={{ ...panelStyle, marginTop: 10 }}>
      <h4>版本只读事实</h4>
      <dl>
        <div><dt>坐标</dt><dd><code>{detail.publisher}/{detail.bundleId}@{detail.version}</code></dd></div>
        <div><dt>状态</dt><dd>{detail.status}</dd></div>
        <div><dt>Content hash</dt><dd><code>{detail.contentHash}</code></dd></div>
        <div><dt>创建者</dt><dd>{detail.createdBy}</dd></div>
        <div><dt>签名</dt><dd>{detail.signature ? `${detail.signature.algorithm} · ${detail.signature.keyId} · ${detail.signature.signedAt}` : "未签名"}</dd></div>
        <div><dt>Manifest / Platform API</dt><dd>{detail.manifest.apiVersion} · {detail.manifest.spec.platformApi}</dd></div>
      </dl>

      <h5>依赖（{detail.dependencies.length}）</h5>
      {detail.dependencies.length === 0 ? <p>无依赖。</p> : <ul>{detail.dependencies.map((item) => <li key={`${item.optional}-${item.ordinal}-${item.publisher ?? "default"}/${item.id}`}><code>{item.publisher ?? "默认发布方"}/{item.id}</code> · {item.versionRange} · {item.optional ? "可选" : "必需"}</li>)}</ul>}

      <h5>Artifacts（{detail.artifacts.length}）</h5>
      {detail.artifacts.length === 0 ? <p>无 artifacts。</p> : <ul>{detail.artifacts.map((item) => <li key={item.relativePath}><code>{item.relativePath}</code> · {item.mediaType} · {item.size} bytes<br /><code>{item.digest}</code><br /><code>{item.artifactRef}</code></li>)}</ul>}

      <h5>Evidence（{detail.evidence.length}）</h5>
      {detail.evidence.length === 0 ? <p>无公开 evidence。</p> : <ol>{detail.evidence.map((item, index) => <li key={`${item.type}-${item.artifactHash}-${index}`}>{item.type} · {item.status}<br /><code>{item.artifactHash}</code><br /><time dateTime={item.observedAt}>{item.observedAt}</time>{item.expiresAt ? <> · expires <time dateTime={item.expiresAt}>{item.expiresAt}</time></> : null}{item.revokedAt ? <> · revoked <time dateTime={item.revokedAt}>{item.revokedAt}</time></> : null}</li>)}</ol>}

      <h5>生命周期事件（{detail.lifecycleEvents.length}）</h5>
      {detail.lifecycleEvents.length === 0 ? <p>无生命周期事件。</p> : <ol>{detail.lifecycleEvents.map((event) => <li key={event.sequence}>#{event.sequence} · {event.fromStatus} → {event.toStatus}<br /><code>{event.evidenceRevision}</code> · <time dateTime={event.createdAt}>{event.createdAt}</time></li>)}</ol>}
    </section>
  );
}

export function RegistryPanel({
  state,
  selected,
  onSelect,
  detailState,
  versionState,
  selectedVersion = null,
  onSelectVersion,
}: RegistryPanelProps) {
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

      {selected && detailState && (
        <>
          <StaleNotice state={detailState} label="Bundle 详情" />
          {detailState.refreshing && <p role="status">正在刷新 Bundle 详情…</p>}
          <DetailStateNotice state={detailState} label="Bundle 详情" />
          {detailState.data && mayShow(detailState) && (
            <BundleDetail
              detail={detailState.data}
              selectedVersion={selectedVersion}
              onSelectVersion={onSelectVersion}
              onVersionAction={() => detailState.reload()}
            />
          )}
        </>
      )}

      {selectedVersion && versionState && (
        <>
          <StaleNotice state={versionState} label="版本详情" />
          {versionState.refreshing && <p role="status">正在刷新版本详情…</p>}
          <DetailStateNotice state={versionState} label="版本详情" />
          {versionState.data && mayShow(versionState) && <VersionDetail detail={versionState.data} />}
          {versionState.data && mayShow(versionState) && (
            <InstallVersionCta
              selection={selectedVersion}
              onInstalled={() => {
                versionState.reload();
                detailState?.reload();
              }}
            />
          )}
        </>
      )}
    </section>
  );
}

function InstallVersionCta({
  selection,
  onInstalled,
}: {
  selection: RegistryVersionSelection;
  onInstalled?: () => void;
}) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function install() {
    setMsg("");
    setBusy(true);
    try {
      const idem = () => crypto.randomUUID();
      // 1. resolve composition → 拿到 compositionId + lockRevision
      const lock = await apiPost<{
        compositionId: string;
        lockRevision: number;
      }>(
        "/v1/bundle-compositions:resolve",
        {
          requested: [
            { publisher: selection.publisher, id: selection.bundleId, version: selection.version },
          ],
        },
        { "Idempotency-Key": idem() },
      );
      // 2. create installation
      const displayName = `安装 ${selection.bundleId}@${selection.version}`;
      await apiPost(
        "/v1/bundle-installations",
        {
          compositionId: lock.compositionId,
          lockRevision: lock.lockRevision,
          overlayRevision: "v1",
          displayName,
        },
        { "Idempotency-Key": idem() },
      );
      setMsg(`✅ 安装已创建：${displayName}`);
      onInstalled?.();
    } catch (e) {
      setMsg(`❌ ${String((e as Error).message || e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={{ ...panelStyle, marginTop: 10 }}>
      <h5>安装此版本</h5>
      <p style={{ color: "var(--aos-muted)", fontSize: "0.75rem" }}>
        选中版本 <code>{selection.publisher}/{selection.bundleId}@{selection.version}</code> 后，
        点击下方按钮创建安装实例（自动创建组合锁定 + 安装记录）。
      </p>
      <button
        type="button"
        className="btn btn-nav"
        disabled={busy}
        onClick={() => void install()}
      >
        {busy ? "正在创建安装…" : "安装此版本"}
      </button>
      {msg && <div role="status" style={{ marginTop: 8, fontSize: "0.8rem" }}>{msg}</div>}
    </section>
  );
}
