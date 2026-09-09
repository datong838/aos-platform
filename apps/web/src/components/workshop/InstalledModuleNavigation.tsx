import { NavLink } from "react-router-dom";

import { useEcommerceWorkshopCatalog } from "./EcommerceWorkshopCatalogContext";

export function InstalledModuleNavigation() {
  const catalog = useEcommerceWorkshopCatalog();

  return (
    <div
      className="ecommerce-workshop-installed-navigation"
      aria-label="电商工作台"
    >
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
    </div>
  );
}
