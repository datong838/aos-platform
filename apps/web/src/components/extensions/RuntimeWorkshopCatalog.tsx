import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { listRuntimeWorkshops, type RuntimeWorkshopCatalog, type RuntimeWorkshopEntry } from '../../api/runtimeWorkshop';
import { getTenant, getAuthRevision } from '../../api/tenant';

type State = { phase: 'loading' | 'ready' | 'empty' | 'failed'; items: RuntimeWorkshopEntry[] };
type Value = State & { reload: () => void };
const Context = createContext<Value | null>(null);
const tenantKey = () => { const t = getTenant(); return JSON.stringify([t.orgId,t.projectId,t.subject,t.roles,getAuthRevision()]); };

export function RuntimeWorkshopCatalogProvider({ children, client = listRuntimeWorkshops }: {
  children: ReactNode; client?: (signal?: AbortSignal) => Promise<RuntimeWorkshopCatalog>;
}) {
  const [state,setState] = useState<State>({phase:'loading',items:[]});
  const revision = useRef(0);
  const pending = useRef<AbortController | null>(null);
  const expires = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reload = useCallback(() => {
    const id = ++revision.current;
    const key = tenantKey();
    const {orgId,projectId} = getTenant();
    pending.current?.abort();
    if (expires.current !== null) clearTimeout(expires.current);
    const controller = new AbortController();
    pending.current = controller;
    // A resource projection is never retained while its validity is unknown.
    setState({phase:'loading',items:[]});
    void Promise.resolve().then(() => client(controller.signal)).then(response => {
      if (revision.current !== id || controller.signal.aborted) return;
      if (key !== tenantKey() || response.tenant.orgId !== orgId || response.tenant.projectId !== projectId) {
        setState({phase:'failed',items:[]}); return;
      }
      setState({phase:response.items.length ? 'ready' : 'empty',items:response.items});
      expires.current = setTimeout(reload,60_000);
    }, () => {
      if (revision.current === id && !controller.signal.aborted) setState({phase:'failed',items:[]});
    });
  }, [client]);
  useEffect(() => {
    reload();
    window.addEventListener('aos-auth-updated',reload);
    window.addEventListener('aos-tenant-updated',reload);
    window.addEventListener('aos-workspace-changed',reload);
    return () => {
      ++revision.current;
      pending.current?.abort();
      if (expires.current !== null) clearTimeout(expires.current);
      window.removeEventListener('aos-auth-updated',reload);
      window.removeEventListener('aos-tenant-updated',reload);
      window.removeEventListener('aos-workspace-changed',reload);
    };
  },[reload]);
  return <Context.Provider value={{...state,reload}}>{children}</Context.Provider>;
}

export function useRuntimeWorkshopCatalog(): Value {
  const value = useContext(Context);
  if (value === null) throw new Error('RuntimeWorkshopCatalogProvider is required');
  return value;
}

export function useOptionalRuntimeWorkshopCatalog(): Value | null {
  return useContext(Context);
}
