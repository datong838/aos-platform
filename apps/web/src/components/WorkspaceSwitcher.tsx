/** TWA.3 / TWA.10 — 顶栏工作区切换器 · 新建工作区 */
import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { getTenant, setTenant } from "../api/tenant";
import { clearWorkspaceLocalCache } from "../lib/workspaceCache";
import { NavIcon } from "../shell/icons";

export type WorkspaceItem = {
  id: string;
  orgId: string;
  name: string;
  deletable?: boolean;
  kind?: string;
};

type ListResp = { items: WorkspaceItem[]; currentProjectId?: string };

export function WorkspaceSwitcher() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<WorkspaceItem[]>([]);
  const [tenant, setTenantState] = useState(() => getTenant());
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<ListResp>("/v1/workspaces");
        if (!cancelled) setItems(res.items || []);
      } catch (e) {
        console.warn("[aos-workspace]", {
          event: "list_failed",
          error: e instanceof Error ? e.message : String(e),
        });
        if (!cancelled) {
          setItems([
            {
              id: tenant.projectId,
              orgId: tenant.orgId,
              name: tenant.workspaceName,
              deletable: true,
            },
          ]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenant.orgId, tenant.projectId, tenant.workspaceName]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function onSelect(w: WorkspaceItem) {
    const prev = getTenant();
    if (prev.projectId !== w.id || prev.orgId !== w.orgId) {
      clearWorkspaceLocalCache("switcher");
    }
    setTenant({
      orgId: w.orgId,
      projectId: w.id,
      workspaceName: w.name,
    });
    setTenantState(getTenant());
    setOpen(false);
    console.info("[aos-workspace]", {
      event: "switched",
      orgId: w.orgId,
      projectId: w.id,
      name: w.name,
    });
    void apiPost(`/v1/workspaces/${encodeURIComponent(w.id)}/enter`, {}).catch((e) => {
      console.warn("[aos-workspace]", {
        event: "enter_failed",
        error: e instanceof Error ? e.message : String(e),
      });
    });
    window.dispatchEvent(
      new CustomEvent("aos-workspace-changed", {
        detail: { orgId: w.orgId, projectId: w.id, name: w.name },
      }),
    );
  }

  async function onCreate() {
    const name = window.prompt("新工作区名称");
    if (!name?.trim()) return;
    try {
      const ws = await apiPost<WorkspaceItem>("/v1/workspaces", {
        name: name.trim(),
      });
      setItems((prev) => (prev.some((i) => i.id === ws.id) ? prev : [...prev, ws]));
      onSelect(ws);
    } catch (e) {
      console.warn("[aos-workspace]", {
        event: "create_failed",
        error: e instanceof Error ? e.message : String(e),
      });
      window.alert(e instanceof Error ? e.message : String(e));
    }
  }

  const label = tenant.workspaceName || tenant.projectId;

  return (
    <div className="aos-workspace" ref={ref}>
      <button
        type="button"
        className="aos-workspace-btn"
        aria-label="工作区"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <NavIcon name="layers" />
        <span className="aos-workspace-label">{label}</span>
        <NavIcon name="chevron" className="aos-workspace-chevron" />
      </button>
      {open ? (
        <div className="aos-workspace-menu" role="menu">
          <div className="aos-workspace-menu-title">工作区</div>
          {items.map((w) => (
            <button
              key={w.id}
              type="button"
              role="menuitem"
              className={
                w.id === tenant.projectId
                  ? "aos-workspace-item is-selected"
                  : "aos-workspace-item"
              }
              onClick={() => onSelect(w)}
            >
              <span>{w.name}</span>
              {w.deletable ? (
                <span className="aos-workspace-tag" title="可删除的测试工作区">
                  可删
                </span>
              ) : null}
              <span className="aos-check">✓</span>
            </button>
          ))}
          <button
            type="button"
            role="menuitem"
            className="aos-workspace-item"
            onClick={() => void onCreate()}
          >
            新建工作区…
          </button>
        </div>
      ) : null}
    </div>
  );
}
