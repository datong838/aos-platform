import { lazy, Suspense } from "react";
import { useLocation } from "react-router-dom";

import {
  EcommerceWorkshopHost,
  resolveLegacyWorkshopRoute,
  useEcommerceWorkshopCatalog,
} from "../../../components/workshop";

const OrderManagementPage = lazy(() =>
  import("../OrderManagementPage").then((module) => ({
    default: module.OrderManagementPage,
  })),
);
const ProductInventoryPage = lazy(() =>
  import("../ProductInventoryPage").then((module) => ({
    default: module.ProductInventoryPage,
  })),
);

function LegacyFallback() {
  const location = useLocation();
  if (location.pathname === "/workshop/orders") return <OrderManagementPage />;
  if (location.pathname === "/workshop/inventory") return <ProductInventoryPage />;
  return <EcommerceWorkshopHost />;
}

export function EcommerceWorkshopEntryRoute() {
  const location = useLocation();
  const catalog = useEcommerceWorkshopCatalog();
  const isLegacyReadPage =
    location.pathname === "/workshop/orders" ||
    location.pathname === "/workshop/inventory";
  const legacyResolution = resolveLegacyWorkshopRoute(catalog.modules, location.pathname);

  if (
    isLegacyReadPage &&
    catalog.phase !== "loading" &&
    legacyResolution.kind === "preserve"
  ) {
    return (
      <Suspense fallback={<div role="status">正在加载旧只读入口…</div>}>
        <LegacyFallback />
      </Suspense>
    );
  }
  return <EcommerceWorkshopHost />;
}
