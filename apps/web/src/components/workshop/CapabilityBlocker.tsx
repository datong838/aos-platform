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
  return (
    <section className="ecommerce-workshop-blockers" aria-labelledby="workshop-blocker-title">
      <h2 id="workshop-blocker-title">依赖检查</h2>
      <p>以下结论来自当前 Module readiness；没有通过的依赖不会被当作可用。</p>
      <ul>
        {blockers.map((blocker) => (
          <li key={`${blocker.dependencyType}:${blocker.dependencyId}`}>
            <div>
              <strong>{blocker.dependencyId}</strong>
              <span className={`ecommerce-workshop-blocker-state is-${blocker.state}`}>
                {blocker.state}
              </span>
            </div>
            <code>{blocker.reasonCode}</code>
            <p>{blocker.requiredAction}</p>
            {blocker.ref ? (
              <small>
                依据：{blocker.ref.authority} / {blocker.ref.resourceType} / {blocker.ref.resourceId}
                {blocker.ref.revision ? ` @ ${blocker.ref.revision}` : ""}
              </small>
            ) : (
              <small>当前没有可验证 authority ref</small>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
