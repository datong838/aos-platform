import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { getAuthRevision, getTenant } from "../../api/tenant";

export type AnalystSelection = {
  tenant: { orgId: string; projectId: string };
  channelId: string;
  entityId: string;
  channelLabel: string;
  sourceCutoffAt: string | null;
};
type Publication = { publish: (value: AnalystSelection | null) => void; release: () => void };
type Context = {
  scopeKey: string;
  selection: AnalystSelection | null;
  register: (owner: symbol, scopeKey: string) => Publication;
};
const SelectionContext = createContext<Context | null>(null);
const NO_PUBLICATION: Publication = { publish: () => {}, release: () => {} };
const EVENTS = ["aos-tenant-updated", "aos-auth-updated", "aos-workspace-changed"];
function subscribe(notify: () => void) {
  for (const event of EVENTS) window.addEventListener(event, notify);
  return () => { for (const event of EVENTS) window.removeEventListener(event, notify); };
}
function scopeKey(active: boolean) {
  const tenant = getTenant();
  return JSON.stringify([tenant.orgId, tenant.projectId, getAuthRevision(), active]);
}

/** Presentation only: values cannot grant data access, readiness, or execution permission. */
export function AnalystSelectionProvider({ active, children }: { active: boolean; children: ReactNode }) {
  const activeRef = useRef(active); activeRef.current = active;
  const getSnapshot = useCallback(() => scopeKey(active), [active]);
  const currentScope = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const [snapshot, setSnapshot] = useState<{ scopeKey: string; value: AnalystSelection } | null>(null);
  const nextTicket = useRef(0);
  const latest = useRef<{ ticket: number; owner: symbol } | null>(null);
  const register = useCallback((owner: symbol, capturedScope: string): Publication => {
    if (!activeRef.current || capturedScope !== scopeKey(activeRef.current)) return NO_PUBLICATION;
    const ticket = ++nextTicket.current;
    latest.current = { ticket, owner }; setSnapshot(null);
    const owns = () => latest.current?.ticket === ticket && latest.current.owner === owner;
    return {
      publish(value) {
        if (!owns() || !activeRef.current || capturedScope !== scopeKey(activeRef.current)) return;
        const tenant = getTenant();
        if (!value || value.tenant.orgId !== tenant.orgId || value.tenant.projectId !== tenant.projectId
          || !value.channelId || !value.entityId) { setSnapshot(null); return; }
        setSnapshot({ scopeKey: capturedScope, value });
      },
      release() {
        if (owns()) { latest.current = null; setSnapshot(null); }
      },
    };
  }, []);
  const selection = active && snapshot?.scopeKey === currentScope ? snapshot.value : null;
  const context = useMemo(() => ({ scopeKey: currentScope, selection, register }), [currentScope, selection, register]);
  return <SelectionContext.Provider value={context}>{children}</SelectionContext.Provider>;
}

export function useAnalystSelection(): AnalystSelection | null {
  return useContext(SelectionContext)?.selection ?? null;
}

/** A scope change renews the lease but never automatically republishes cached data. */
export function usePublishAnalystSelection(value: AnalystSelection | null, sourceClient: object) {
  const context = useContext(SelectionContext);
  const owner = useMemo(() => Symbol("analyst-selection"), [sourceClient]);
  const publication = useRef<Publication | null>(null);
  const register = context?.register, currentScope = context?.scopeKey;
  useLayoutEffect(() => {
    const lease = register && currentScope ? register(owner, currentScope) : NO_PUBLICATION;
    publication.current = lease;
    return () => { lease.release(); if (publication.current === lease) publication.current = null; };
  }, [register, currentScope, owner]);
  useLayoutEffect(() => { publication.current?.publish(value); }, [value, owner]);
}
