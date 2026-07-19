/** TWA.9 — 顶栏组织切换器（UI 称「组织」） */
import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { getTenant, setTenant } from "../api/tenant";
import { clearWorkspaceLocalCache } from "../lib/workspaceCache";
import { NavIcon } from "../shell/icons";

export type OrgItem = {
  id: string;
  name: string;
  kind?: string;
};

type ListResp = { items: OrgItem[]; currentOrgId?: string };
type EnterResp = {
  orgId: string;
  orgName: string;
  projectId: string;
  workspaceName: string;
};

export function OrgSwitcher() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<OrgItem[]>([]);
  const [tenant, setTenantState] = useState(() => getTenant());
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<ListResp>("/v1/orgs");
        if (!cancelled) setItems(res.items || []);
      } catch (e) {
        console.warn("[aos-org]", {
          event: "list_failed",
          error: e instanceof Error ? e.message : String(e),
        });
        if (!cancelled) {
          setItems([{ id: tenant.orgId, name: tenant.orgId }]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenant.orgId]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  async function onSelect(o: OrgItem) {
    if (o.id === getTenant().orgId) {
      setOpen(false);
      return;
    }
    try {
      const entered = await apiPost<EnterResp>(
        `/v1/orgs/${encodeURIComponent(o.id)}/enter`,
        {},
      );
      clearWorkspaceLocalCache("org-switch");
      setTenant({
        orgId: entered.orgId,
        projectId: entered.projectId,
        workspaceName: entered.workspaceName,
      });
      setTenantState(getTenant());
      setOpen(false);
      console.info("[aos-org]", {
        event: "switched",
        orgId: entered.orgId,
        projectId: entered.projectId,
      });
      window.dispatchEvent(
        new CustomEvent("aos-workspace-changed", {
          detail: {
            orgId: entered.orgId,
            projectId: entered.projectId,
          },
        }),
      );
    } catch (e) {
      console.warn("[aos-org]", {
        event: "enter_failed",
        error: e instanceof Error ? e.message : String(e),
      });
    }
  }

  const label =
    items.find((i) => i.id === tenant.orgId)?.name || tenant.orgId;

  return (
    <div className="aos-workspace aos-org-switcher" ref={ref} data-ui="TWA-9">
      <button
        type="button"
        className="aos-workspace-btn"
        aria-label="组织"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((v) => !v)}
        title="组织（多 Org；与 Marking 无关）"
      >
        <NavIcon name="apps" />
        <span className="aos-workspace-label">组织 · {label}</span>
        <NavIcon name="chevron" className="aos-workspace-chevron" />
      </button>
      {open ? (
        <div className="aos-workspace-menu" role="listbox">
          <div className="aos-workspace-menu-title">组织</div>
          {items.map((o) => (
            <button
              key={o.id}
              type="button"
              role="option"
              aria-selected={o.id === tenant.orgId}
              className={
                o.id === tenant.orgId
                  ? "aos-workspace-item is-selected"
                  : "aos-workspace-item"
              }
              onClick={() => void onSelect(o)}
            >
              {o.name}
              <span className="aos-muted"> · {o.id}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
