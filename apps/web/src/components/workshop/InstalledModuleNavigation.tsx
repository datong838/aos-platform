import { NavLink } from "react-router-dom";

import { useEcommerceWorkshopCatalog } from "./EcommerceWorkshopCatalogContext";
import { WORKSHOP_ACCEPTANCE_MODULES } from "./workshopAcceptance";

export function InstalledModuleNavigation() {
  const catalog = useEcommerceWorkshopCatalog();
  const primaryIds = new Set<string>(WORKSHOP_ACCEPTANCE_MODULES.map((module) => module.moduleId));
  const primaryRoutes = new Set<string>(WORKSHOP_ACCEPTANCE_MODULES.map((module) => module.route));
  const installedById = new Map(catalog.modules.map((module) => [module.moduleId, module]));
  const navigationItems = [
    ...WORKSHOP_ACCEPTANCE_MODULES.map((module) => {
      const installed = installedById.get(module.moduleId);
      return {
        moduleId: module.moduleId,
        route: module.route,
        menuLabel: module.label,
        key: installed
          ? `${installed.moduleId}:${installed.moduleRef.moduleArtifactHash}`
          : `${module.moduleId}:product-route`,
      };
    }),
    ...catalog.modules
      .filter((module) => !primaryIds.has(module.moduleId) && !primaryRoutes.has(module.route))
      .map((module) => ({
        moduleId: module.moduleId,
        route: module.route,
        menuLabel: module.menuLabel,
        key: `${module.moduleId}:${module.moduleRef.moduleArtifactHash}`,
      })),
  ];

  return (
    <div
      className="ecommerce-workshop-installed-navigation"
      aria-label="电商工作台"
    >
      {navigationItems.map((module) => (
        <NavLink
          key={module.key}
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
    </div>
  );
}
