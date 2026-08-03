import type {
  ContributionBinding,
  ContributionClaim,
  MigrationStep,
  PermissionSet,
  StoredCompositionLock,
} from "../../../api/assetControl/types";

export interface CompositionDiffPanelProps {
  lock: StoredCompositionLock;
}

const GROUPS = ["baseline", "target", "added", "removed", "unchanged"] as const;
const MIGRATION_GROUPS = ["baseline", "target", "added", "removed"] as const;

function PermissionFacts({ value }: { value: PermissionSet }) {
  return <span>roles={value.roles.join(", ") || "无"}; markings={value.markings.join(", ") || "无"}; dataScopes={value.dataScopes.join(", ") || "无"}; actionTypes={value.actionTypes.join(", ") || "无"}</span>;
}

function MigrationFacts({ value }: { value: MigrationStep }) {
  return <span><code>{value.publisher}/{value.id}@{value.version}</code> · <code>{value.planRef}</code> · {value.downgradePolicy}</span>;
}

function claimText(claim: ContributionClaim): string {
  if (claim.kind === "api") return `api · ${claim.method} ${claim.path} · ${claim.operationId} · ${claim.mode}`;
  if (claim.kind === "navigation") return `navigation · ${claim.route} · ${claim.mode}`;
  return `ui · ${claim.slot}/${claim.id} · ${claim.mode}`;
}

function ContributionFacts({ value }: { value: ContributionBinding }) {
  return <span><code>{value.publisher}/{value.id}@{value.version}</code> · {claimText(value.claim)}</span>;
}

export function CompositionDiffPanel({ lock }: CompositionDiffPanelProps) {
  const { permissionDiff, migrationPlan, contributionDiff } = lock.payload;
  return (
    <section aria-label="Composition 服务端 Diff" style={{ border: "1px solid var(--aos-border)", borderRadius: 3, padding: 12 }}>
      <header>
        <h3 style={{ margin: 0 }}>服务端 Diff（只读）</h3>
        <p>以下集合和 hash 均直接来自不可变 Lock；浏览器不重新计算差异。</p>
      </header>
      <dl>
        <div><dt>Permission diff hash</dt><dd><code>{lock.permissionDiffHash}</code></dd></div>
        <div><dt>Migration plan hash</dt><dd><code>{lock.migrationPlanHash}</code></dd></div>
        <div><dt>Contribution diff hash</dt><dd><code>{lock.contributionDiffHash}</code></dd></div>
      </dl>

      <section aria-label="Permission Diff">
        <h4>Permission Diff</h4>
        <dl>{GROUPS.map((group) => <div key={group}><dt>{group}</dt><dd><PermissionFacts value={permissionDiff[group]} /></dd></div>)}</dl>
      </section>

      <section aria-label="Migration Plan Diff">
        <h4>Migration Plan Diff</h4>
        {MIGRATION_GROUPS.map((group) => <div key={group}><h5>{group}</h5>{migrationPlan[group].length === 0 ? <p>无</p> : <ul>{migrationPlan[group].map((step) => <li key={`${step.publisher}/${step.id}@${step.version}`}><MigrationFacts value={step} /></li>)}</ul>}</div>)}
        <div><h5>changed</h5>{migrationPlan.changed.length === 0 ? <p>无</p> : <ul>{migrationPlan.changed.map((change) => <li key={`${change.publisher}/${change.id}`}><strong><code>{change.publisher}/{change.id}</code></strong><br />before: <MigrationFacts value={change.before} /><br />after: <MigrationFacts value={change.after} /></li>)}</ul>}</div>
      </section>

      <section aria-label="Contribution Diff">
        <h4>Contribution Diff</h4>
        {GROUPS.map((group) => <div key={group}><h5>{group}</h5>{contributionDiff[group].length === 0 ? <p>无</p> : <ul>{contributionDiff[group].map((binding, index) => <li key={`${binding.publisher}/${binding.id}@${binding.version}-${binding.claim.kind}-${index}`}><ContributionFacts value={binding} /></li>)}</ul>}</div>)}
      </section>
    </section>
  );
}
