import type {
  WorkshopReadiness,
  WorkshopReadinessBlocker,
} from "../../api/ecommerceWorkshop";

export function CapabilityBlocker({
  readiness,
  blockers,
}: {
  readiness: WorkshopReadiness;
  blockers: readonly WorkshopReadinessBlocker[];
}) {
  if (readiness === "available") return null;
  const stateLabel = (state: WorkshopReadinessBlocker["state"]) => ({
    ready: "已满足",
    available: "已满足",
    degraded: "部分可用",
    disabled: "当前不可用",
    blocked: "等待业务条件",
    unknown: "待核对",
    failed: "读取失败",
  } as Record<string, string>)[state] ?? "待核对";
  return (
    <section className="ecommerce-workshop-blockers" aria-labelledby="workshop-blocker-title">
      <h2 id="workshop-blocker-title">所需业务条件</h2>
      <p>以下条件尚未取得可验证的正式业务数据，页面保持只读并允许重新读取。</p>
      <details>
        <summary>查看 {blockers.length} 项数据审计信息</summary>
        <ul>
          {blockers.map((blocker) => (
            <li key={`${blocker.dependencyType}:${blocker.dependencyId}`}>
            <div>
              <strong>正式业务数据尚未就绪</strong>
              <span className={`ecommerce-workshop-blocker-state is-${blocker.state}`}>
                {stateLabel(blocker.state)}
              </span>
            </div>
            <p>请补充当前租户可回链的数据来源后重新读取；系统不会用演示数据填补业务结论。</p>
            <details>
              <summary>查看数据审计信息</summary>
              <code>{blocker.reasonCode}</code>
              <p>{blocker.requiredAction}</p>
              <small>依赖：{blocker.dependencyId}</small>
              {blocker.ref ? (
                <small>
                  依据：{blocker.ref.authority} / {blocker.ref.resourceType} / {blocker.ref.resourceId}
                  {blocker.ref.revision ? ` @ ${blocker.ref.revision}` : ""}
                </small>
              ) : (
                <small>当前没有可验证的数据依据</small>
              )}
            </details>
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
