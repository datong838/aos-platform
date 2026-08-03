import type {
  ContributionClaim,
  StoredCompositionLock,
} from "../../../api/assetControl/types";

export interface CompositionDependencyPanelProps {
  lock: StoredCompositionLock;
}

const panelStyle = {
  border: "1px solid var(--aos-border)",
  borderRadius: 3,
  padding: 12,
} as const;

function claimText(claim: ContributionClaim): string {
  if (claim.kind === "api") return `api · ${claim.method} ${claim.path} · ${claim.operationId} · ${claim.mode}`;
  if (claim.kind === "navigation") return `navigation · ${claim.route} · ${claim.mode}`;
  return `ui · ${claim.slot}/${claim.id} · ${claim.mode}`;
}

export function CompositionDependencyPanel({ lock }: CompositionDependencyPanelProps) {
  const { resolved, edges, capabilityProviders } = lock.payload;
  return (
    <section aria-label="Composition 依赖事实" style={panelStyle}>
      <header>
        <h3 style={{ margin: 0 }}>解析结果与依赖事实</h3>
        <p>仅呈现服务端 Lock 内已解析事实；不在客户端推断图层级或冲突路径。</p>
      </header>

      <h4>Resolved bundles（{resolved.length}）</h4>
      {resolved.length === 0 ? <p>服务端未解析出 Bundle。</p> : resolved.map((bundle) => (
        <article key={`${bundle.publisher}/${bundle.id}@${bundle.version}`} style={{ ...panelStyle, marginTop: 8 }}>
          <h5><code>{bundle.publisher}/{bundle.id}@{bundle.version}</code></h5>
          <dl>
            <div><dt>类型 / 选择原因</dt><dd>{bundle.kind} / {bundle.selectionReason}</dd></div>
            <div><dt>Content hash</dt><dd><code>{bundle.contentHash}</code></dd></div>
            <div><dt>Signature fingerprint</dt><dd><code>{bundle.signatureFingerprint}</code></dd></div>
            <div><dt>Release evidence revision</dt><dd><code>{bundle.releaseEvidenceRevision}</code></dd></div>
            <div><dt>Capabilities provides</dt><dd>{bundle.capabilities.provides.join(", ") || "无"}</dd></div>
            <div><dt>Capabilities requires</dt><dd>{bundle.capabilities.requires.join(", ") || "无"}</dd></div>
            <div><dt>权限</dt><dd>roles={bundle.permissions.roles.join(", ") || "无"}; markings={bundle.permissions.markings.join(", ") || "无"}; dataScopes={bundle.permissions.dataScopes.join(", ") || "无"}; actionTypes={bundle.permissions.actionTypes.join(", ") || "无"}</dd></div>
            <div><dt>Migration</dt><dd>{bundle.migration.planRef ?? "无 plan"} · {bundle.migration.downgradePolicy}</dd></div>
          </dl>
          <p>必需依赖：{bundle.dependencies.map((item) => `${item.publisher}/${item.id} ${item.version}`).join("；") || "无"}</p>
          <p>可选依赖：{bundle.optionalDependencies.map((item) => `${item.publisher}/${item.id} ${item.version}`).join("；") || "无"}</p>
          <p>冲突声明：{bundle.conflicts.map((item) => `${item.publisher}/${item.id} ${item.version ?? "任意版本"}`).join("；") || "无"}</p>
          <p>Contributions：{bundle.contributions.map(claimText).join("；") || "无"}</p>
        </article>
      ))}

      <h4>Dependency edges（{edges.length}）</h4>
      {edges.length === 0 ? <p>无依赖边。</p> : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><th>From</th><th>To</th><th>Constraint</th><th>类型</th></tr></thead>
          <tbody>{edges.map((edge, index) => <tr key={`${edge.fromPublisher}/${edge.fromId}-${edge.toPublisher}/${edge.toId}-${index}`}><td><code>{edge.fromPublisher}/{edge.fromId}@{edge.fromVersion}</code></td><td><code>{edge.toPublisher}/{edge.toId}@{edge.toVersion}</code></td><td><code>{edge.constraint}</code></td><td>{edge.optional ? "可选" : "必需"}</td></tr>)}</tbody>
        </table>
      )}

      <h4>Capability providers（{capabilityProviders.length}）</h4>
      {capabilityProviders.length === 0 ? <p>无 capability provider。</p> : <ul>{capabilityProviders.map((provider) => <li key={`${provider.capability}-${provider.publisher}/${provider.id}@${provider.version}`}><code>{provider.capability}</code> → <code>{provider.publisher}/{provider.id}@{provider.version}</code></li>)}</ul>}
    </section>
  );
}
