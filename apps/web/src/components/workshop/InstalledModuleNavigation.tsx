import { NavLink } from "react-router-dom";

import { useEcommerceWorkshopCatalog } from "./EcommerceWorkshopCatalogContext";

const READINESS_LABEL = {
  available: "可用",
  degraded: "降级",
  disabled: "停用",
  blocked: "阻断",
  unknown: "待验证",
} as const;

export function InstalledModuleNavigation() {
  const catalog = useEcommerceWorkshopCatalog();

  if (catalog.phase === "loading") {
    return (
      <div className="ecommerce-workshop-nav-message" role="status">
        正在读取已安装工作台…
      </div>
    );
  }
  if (catalog.phase === "forbidden") {
    return (
      <div className="ecommerce-workshop-nav-message is-error" role="status">
        无权读取工作台目录
      </div>
    );
  }
  if (catalog.phase === "failed" && catalog.modules.length === 0) {
    return (
      <button
        type="button"
        className="ecommerce-workshop-nav-retry"
        onClick={catalog.reload}
      >
        目录读取失败，重试
      </button>
    );
  }
  if (catalog.modules.length === 0) {
    return (
      <div className="ecommerce-workshop-nav-message" role="status">
        当前工作区未安装电商工作台
      </div>
    );
  }

  return (
    <div
      className="ecommerce-workshop-installed-navigation"
      aria-label="已安装电商工作台"
    >
      {catalog.phase === "stale" ? (
        <div className="ecommerce-workshop-nav-message is-stale" role="status">
          目录刷新未完成，当前显示旧快照
        </div>
      ) : null}
      {catalog.modules.map((module) => (
        <NavLink
          key={`${module.moduleId}:${module.moduleRef.moduleArtifactHash}`}
          to={module.route}
          data-workshop-module-id={module.moduleId}
          className={({ isActive }) =>
            `aos-nav-link ecommerce-workshop-nav-link${isActive ? " is-active" : ""}`
          }
        >
          <span className="ecommerce-workshop-nav-glyph" aria-hidden="true" />
          <span className="aos-nav-label">{module.menuLabel}</span>
          <span
            className={`ecommerce-workshop-readiness-status is-${module.readiness}`}
            title={`就绪状态：${READINESS_LABEL[module.readiness]}`}
          >
            <span className="ecommerce-workshop-readiness-dot" aria-hidden="true" />
            <span>{READINESS_LABEL[module.readiness]}</span>
          </span>
        </NavLink>
      ))}
    </div>
  );
}
