import type { ThreeModuleClosureContributionViewResponse, ThreeModuleId, WorkshopTenant } from "../../api/ecommerceWorkshop";

const MODULE_LABEL: Record<ThreeModuleId, string> = { creator: "达人", price: "价格", customer: "客户" };
export function unavailableThreeModuleClosure(module: ThreeModuleId, tenant: WorkshopTenant, evaluatedAt: string): ThreeModuleClosureContributionViewResponse {
  const roles = { creator: ["达人运营官", ["内容官", "数据参谋"]], price: ["数据参谋", ["活动策划师", "导购顾问"]], customer: ["私域管家", ["内容官", "客服专员", "导购顾问", "数据参谋"]] } as const;
  const logic = { creator: "ecommerce-creator-growth", price: "ecommerce-price-governance", customer: "ecommerce-customer-relationship" } as const;
  return { schemaVersion: "aos.ecommerce-workshop.three-module-closure/v1", tenant, module, evaluatedAt, atomicSkillIds: ["canonical-outcome-rebuild"], logicId: logic[module], primaryColleague: roles[module][0], collaboratorColleagues: [...roles[module][1]], latestClosure: null, latestUsage: null, latestEffect: null, latestHandoff: null, blockers: ["THREE_MODULE_CLOSURE_AUTHORITY_UNAVAILABLE", "THREE_MODULE_USAGE_NOT_BOUND", "THREE_MODULE_EFFECT_NOT_BOUND", "THREE_MODULE_HANDOFF_NOT_BOUND"], allowedCommands: ["COMPILE_THREE_MODULE_CLOSURE", "BIND_CANONICAL_USAGE", "BIND_CANONICAL_EFFECT_REVIEW", "BIND_CANONICAL_HANDOFF"], handoffConsumeAllowed: false, memoryPromotionAllowed: false, externalEffectsAllowed: false };
}

export function ThreeModuleClosureCard({ value }: { value: ThreeModuleClosureContributionViewResponse }) {
  const ledger = value.latestClosure?.ledger;
  return <section className="three-module-closure-card" aria-label={`${MODULE_LABEL[value.module]}五轴闭环贡献`}>
    <header><div><span>原子 Skill → Logic → 数字同事 → 工作台贡献</span><h2>{MODULE_LABEL[value.module]} Partial / Usage / Effect / Handoff</h2></div><strong>{ledger?.state ?? "失败关闭"}</strong></header>
    <p>{value.primaryColleague}主责，{value.collaboratorColleagues.join("、")}协作；五条 authority 轴独立，任何一轴都不能冒充整体完成。</p>
    <div className="three-module-closure-axes">
      <article><span>Item outcome</span><strong>{ledger?.state ?? "未编译"}</strong><small>{ledger ? `${ledger.succeeded}/${ledger.total} succeeded · ${ledger.unknown} unknown` : "等待 canonical original"}</small></article>
      <article><span>Action outcome</span><strong>{value.latestClosure ? "原状态保留" : "unknown"}</strong><small>不由公共 reducer 覆盖领域真源</small></article>
      <article><span>Usage settlement</span><strong>{value.latestUsage?.settlement ?? "未绑定"}</strong><small>{value.latestUsage?.quantity ?? "unknown 不造 0"} {value.latestUsage?.unit ?? ""}</small></article>
      <article><span>Effect maturity</span><strong>{value.latestEffect?.maturityStatus ?? "未绑定"}</strong><small>{value.latestEffect?.effectCompleted ? "成熟完成" : "不晋升有效经验"}</small></article>
      <article><span>Handoff decision</span><strong>{value.latestHandoff?.businessDecision ?? "未决定"}</strong><small>{value.latestHandoff?.transportStatus ?? "未绑定"} ≠ 业务接受</small></article>
    </div>
    <footer><span>Handoff consume：0</span><span>Memory promotion：0</span><span>外部效果：0</span></footer>
    {value.blockers.length ? <aside>{value.blockers.map((item) => <code key={item}>{item}</code>)}</aside> : null}
  </section>;
}
