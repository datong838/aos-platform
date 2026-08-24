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
  type SourceReadinessEnvelope,
} from "../../api/ecommerceWorkshop";
import { getTenant } from "../../api/tenant";

export type SourceReadinessPhase = "loading" | "ready" | "forbidden" | "failed";
export type SourceReadinessClient = Pick<typeof ecommerceWorkshopClient, "getSourceReadiness">;
export type SourceReadinessSnapshot = {
  phase: SourceReadinessPhase;
  response: SourceReadinessEnvelope | null;
  reload: () => void;
};

const SourceReadinessContext = createContext<SourceReadinessSnapshot | null>(null);

function tenantKey(): string {
  const tenant = getTenant();
  return `${tenant.orgId}:${tenant.projectId}`;
}

function asError(cause: unknown): EcommerceWorkshopClientError {
  if (cause instanceof EcommerceWorkshopClientError) return cause;
  const message = cause instanceof Error ? cause.message : String(cause);
  return new EcommerceWorkshopClientError(message, {
    status: 0,
    operationId: "ecommerceWorkshopSourceReadinessGet",
    body: { code: "SOURCE_READINESS_READ_FAILED", message, details: null, traceId: "" },
  });
}

export function SourceReadinessProvider({
  client = ecommerceWorkshopClient,
  children,
}: {
  client?: SourceReadinessClient;
  children: ReactNode;
}) {
  const [phase, setPhase] = useState<SourceReadinessPhase>("loading");
  const [response, setResponse] = useState<SourceReadinessEnvelope | null>(null);
  const revision = useRef(0);

  const reload = useCallback(() => {
    const requestId = ++revision.current;
    const expectedTenant = tenantKey();
    setResponse(null);
    setPhase("loading");
    void client.getSourceReadiness().then(
      (next) => {
        if (requestId !== revision.current) return;
        if (`${next.tenant.orgId}:${next.tenant.projectId}` !== expectedTenant || tenantKey() !== expectedTenant) {
          setPhase("failed");
          return;
        }
        setResponse(next);
        setPhase("ready");
      },
      (cause: unknown) => {
        if (requestId !== revision.current) return;
        const error = asError(cause);
        setPhase(error.status === 401 || error.status === 403 ? "forbidden" : "failed");
      },
    );
  }, [client]);

  useEffect(() => {
    reload();
    return () => { revision.current += 1; };
  }, [reload]);

  const value = useMemo(() => ({ phase, response, reload }), [phase, response, reload]);
  return <SourceReadinessContext.Provider value={value}>{children}</SourceReadinessContext.Provider>;
}

export function useSourceReadinessSnapshot(): SourceReadinessSnapshot | null {
  return useContext(SourceReadinessContext);
}
