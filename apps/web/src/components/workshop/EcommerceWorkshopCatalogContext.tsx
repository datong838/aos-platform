import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  EcommerceWorkshopClientError,
  ecommerceWorkshopClient,
  type EcommerceWorkshopModule,
  type EcommerceWorkshopModuleListResponse,
} from "../../api/ecommerceWorkshop";
import { getTenant } from "../../api/tenant";

export type EcommerceWorkshopCatalogPhase =
  | "loading"
  | "ready"
  | "empty"
  | "stale"
  | "forbidden"
  | "failed";

export type EcommerceWorkshopCatalogState = {
  phase: EcommerceWorkshopCatalogPhase;
  tenantKey: string;
  response: EcommerceWorkshopModuleListResponse | null;
  error: EcommerceWorkshopClientError | null;
};

export type EcommerceWorkshopCatalogClient = Pick<
  typeof ecommerceWorkshopClient,
  "listModules"
>;

export type EcommerceWorkshopCatalogValue = EcommerceWorkshopCatalogState & {
  modules: readonly EcommerceWorkshopModule[];
  reload: () => void;
};

const CatalogContext = createContext<EcommerceWorkshopCatalogValue | null>(null);

function currentTenantKey(): string {
  const tenant = getTenant();
  return `${tenant.orgId}:${tenant.projectId}`;
}

function errorPhase(error: EcommerceWorkshopClientError): EcommerceWorkshopCatalogPhase {
  return error.status === 401 || error.status === 403 ? "forbidden" : "failed";
}

function normalizeError(error: unknown): EcommerceWorkshopClientError {
  if (error instanceof EcommerceWorkshopClientError) return error;
  const message = error instanceof Error ? error.message : String(error);
  return new EcommerceWorkshopClientError(message, {
    status: 0,
    operationId: "ecommerceWorkshopModulesList",
    body: { code: "CATALOG_READ_FAILED", message, details: null, traceId: "" },
  });
}

export function EcommerceWorkshopCatalogProvider({
  children,
  client = ecommerceWorkshopClient,
}: {
  children: ReactNode;
  client?: EcommerceWorkshopCatalogClient;
}) {
  const [state, setState] = useState<EcommerceWorkshopCatalogState>(() => ({
    phase: "loading",
    tenantKey: currentTenantKey(),
    response: null,
    error: null,
  }));
  const stateRef = useRef(state);
  const requestRevision = useRef(0);

  const commitState = useCallback((next: EcommerceWorkshopCatalogState) => {
    stateRef.current = next;
    setState(next);
  }, []);

  const load = useCallback(
    (tenantKey: string, preserveCurrent: boolean) => {
      const requestId = ++requestRevision.current;
      const previous = stateRef.current;
      commitState({
        phase:
          preserveCurrent && previous.response !== null ? "stale" : "loading",
        tenantKey,
        response: preserveCurrent ? previous.response : null,
        error: null,
      });
      void client.listModules().then(
        (response) => {
          if (requestId !== requestRevision.current) return;
          const responseKey = `${response.tenant.orgId}:${response.tenant.projectId}`;
          if (responseKey !== tenantKey || currentTenantKey() !== tenantKey) {
            const mismatch = new EcommerceWorkshopClientError(
              "工作台目录租户与当前会话不一致",
              {
                status: 0,
                operationId: "ecommerceWorkshopModulesList",
                body: {
                  code: "TENANT_MISMATCH",
                  message: "工作台目录租户与当前会话不一致",
                  details: null,
                  traceId: "",
                },
              },
            );
            commitState({
              phase: "failed",
              tenantKey,
              response: null,
              error: mismatch,
            });
            return;
          }
          commitState({
            phase: response.items.length === 0 ? "empty" : "ready",
            tenantKey,
            response,
            error: null,
          });
        },
        (cause: unknown) => {
          if (requestId !== requestRevision.current) return;
          const error = normalizeError(cause);
          const current = stateRef.current;
          commitState({
            phase:
              preserveCurrent && current.response !== null
                ? "stale"
                : errorPhase(error),
            tenantKey,
            response: preserveCurrent ? current.response : null,
            error,
          });
        },
      );
    },
    [client, commitState],
  );

  useEffect(() => {
    const initialKey = currentTenantKey();
    load(initialKey, false);
    const onTenantChanged = () => {
      const nextKey = currentTenantKey();
      if (nextKey === stateRef.current.tenantKey) return;
      load(nextKey, false);
    };
    window.addEventListener("aos-workspace-changed", onTenantChanged);
    window.addEventListener("aos-tenant-updated", onTenantChanged);
    return () => {
      requestRevision.current += 1;
      window.removeEventListener("aos-workspace-changed", onTenantChanged);
      window.removeEventListener("aos-tenant-updated", onTenantChanged);
    };
  }, [load]);

  const reload = useCallback(() => {
    load(currentTenantKey(), true);
  }, [load]);

  const value = useMemo<EcommerceWorkshopCatalogValue>(
    () => ({
      ...state,
      modules: state.response?.items ?? [],
      reload,
    }),
    [reload, state],
  );

  return <CatalogContext.Provider value={value}>{children}</CatalogContext.Provider>;
}

export function useEcommerceWorkshopCatalog(): EcommerceWorkshopCatalogValue {
  const value = useContext(CatalogContext);
  if (value === null) {
    throw new Error("EcommerceWorkshopCatalogProvider is required");
  }
  return value;
}

export type WorkshopRouteMatch = {
  module: EcommerceWorkshopModule;
  kind: "canonical" | "legacy";
};

export function findInstalledWorkshopRoute(
  modules: readonly EcommerceWorkshopModule[],
  pathname: string,
): WorkshopRouteMatch | null {
  const canonical = modules.find(
    (module) =>
      pathname === module.route || pathname.startsWith(`${module.route}/`),
  );
  if (canonical) return { module: canonical, kind: "canonical" };
  const legacy = modules.find((module) => module.legacyRoutes.includes(pathname));
  return legacy ? { module: legacy, kind: "legacy" } : null;
}

export function isReplacedLegacyWorkshopRoute(
  modules: readonly EcommerceWorkshopModule[],
  pathname: string,
): boolean {
  return modules.some((module) => module.legacyRoutes.includes(pathname));
}
