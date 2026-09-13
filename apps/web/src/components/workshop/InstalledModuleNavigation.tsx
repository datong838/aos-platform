import { NavLink } from "react-router-dom";

import { useEcommerceWorkshopCatalog } from "./EcommerceWorkshopCatalogContext";
import { useOptionalRuntimeWorkshopCatalog } from '../extensions/RuntimeWorkshopCatalog';

export function InstalledModuleNavigation() {
  const catalog = useEcommerceWorkshopCatalog();
  const runtime = useOptionalRuntimeWorkshopCatalog();
  const runtimeModules = runtime?.phase === 'ready'
    ? runtime.items.filter(entry => !catalog.modules.some(module => module.route === entry.module.route)) : [];
  const notice = runtimeModules.length && catalog.phase === 'empty' ? null : {
    loading: "正在读取工作台目录",
    empty: "暂无可见工作台入口",
    failed: "工作台目录读取失败",
    forbidden: "没有读取工作台目录的权限",
    stale: "工作台目录待更新",
    ready: null,
  }[catalog.phase];
  const canReload = ["empty", "failed", "stale"].includes(catalog.phase);

  return (
    <div
      className="ecommerce-workshop-installed-navigation"
      aria-label="电商工作台"
    >
      {notice ? (
        <div className="aos-nav-label" role="status">
          <span>{notice}</span>
          {canReload ? <button type="button" onClick={() => { catalog.reload(); runtime?.reload(); }}>重新读取目录</button> : null}
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
        </NavLink>
      ))}
      {runtimeModules.map(entry => <NavLink key={`runtime:${entry.installationId}:${entry.module.moduleId}:${entry.ui.resourceHash}`}
        to={entry.module.route} data-workshop-module-id={entry.module.moduleId}
        className={({ isActive }) => `aos-nav-link ecommerce-workshop-nav-link${isActive ? ' is-active' : ''}`}>
        <span className="ecommerce-workshop-nav-glyph" aria-hidden="true" />
        <span className="aos-nav-label">{entry.module.menuLabel}</span>
      </NavLink>)}
    </div>
  );
}
