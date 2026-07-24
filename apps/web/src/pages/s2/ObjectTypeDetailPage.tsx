import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet } from "../../api/client";
import { getOntologyClient } from "../../api/ontologyClient";
import {
  loadBranchPref,
  pushRecent,
  saveBranchPref,
} from "../../lib/ontologyRecent";
import { S2Chrome } from "./shared";
import { ObjectTypeDetailPanel } from "./objectTypeDetail";
import { BpToolbar } from "./blueprintUi";

type ObjectTypeRow = {
  id: string;
  name: string;
  description?: string;
  published?: boolean;
  properties?: { name: string; type?: string }[];
};

type Branch = { id: string; name: string; baseRef: string; readonly: boolean };

/** 89/92 · OT 深页：七 Tab + 分支切换（?branch=） */
export function ObjectTypeDetailPage() {
  const { typeId = "" } = useParams();
  const [meta, setMeta] = useState<ObjectTypeRow | null>(null);
  const [objects, setObjects] = useState<Record<string, unknown>[]>([]);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [neighbors, setNeighbors] = useState<{ id?: string; type?: string; rel?: string }[]>([]);
  const [funnelStage, setFunnelStage] = useState<string | undefined>();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchId, setBranchId] = useState(() => loadBranchPref("main"));
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!typeId) return;
    let cancelled = false;
    (async () => {
      try {
        const [types, list, funnel, br] = await Promise.all([
          apiGet<{ items: ObjectTypeRow[] }>("/v1/ontology/object-types"),
          getOntologyClient().listObjects(typeId, { branch: branchId }),
          apiGet<{ stage?: string }>(`/v1/funnel/${encodeURIComponent(typeId)}/status`).catch(() => ({})),
          apiGet<{ items: Branch[] }>("/v1/ontology/branches").catch(() => ({ items: [] })),
        ]);
        if (cancelled) return;
        const hit = types.items.find((t) => t.id === typeId) || null;
        setMeta(hit);
        setObjects((list.items || []) as Record<string, unknown>[]);
        setFunnelStage((funnel as { stage?: string }).stage);
        setBranches(br.items || []);
        if (hit) {
          pushRecent({ kind: "objectType", id: typeId, label: hit.name || typeId });
        }
        if (br.items?.length && !br.items.some((b) => b.id === branchId)) {
          const next = br.items[0].id;
          setBranchId(next);
          saveBranchPref(next);
        }
      } catch (e) {
        if (!cancelled) setErr(String((e as Error).message || e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [typeId, branchId]);

  const instanceCount = useMemo(() => objects.length, [objects]);

  const branchReadonly = useMemo(() => {
    const hit = branches.find((b) => b.id === branchId);
    if (hit) return !!hit.readonly;
    return branchId === "main" || branchId === "master";
  }, [branches, branchId]);

  async function openInstance(id: string) {
    setErr(null);
    const ont = getOntologyClient();
    const d = await ont.getObject(typeId, id, { branch: branchId });
    setDetail(d as Record<string, unknown>);
    const n = (await ont.neighbors(typeId, id)) as {
      items?: { id?: string; type?: string; rel?: string }[];
    };
    setNeighbors(n.items || []);
  }

  async function reloadObjects() {
    if (!typeId) return;
    const ont = getOntologyClient();
    const list = await ont.listObjects(typeId, { branch: branchId });
    setObjects((list.items || []) as Record<string, unknown>[]);
    if (detail?.id) {
      const d = await ont.getObject(typeId, String(detail.id), { branch: branchId });
      setDetail(d as Record<string, unknown>);
    }
  }

  async function reloadMeta() {
    if (!typeId) return;
    const types = await apiGet<{ items: ObjectTypeRow[] }>("/v1/ontology/object-types");
    const hit = types.items.find((t) => t.id === typeId) || null;
    setMeta(hit);
  }

  function onBranchChange(next: string) {
    setBranchId(next);
    saveBranchPref(next);
    setDetail(null);
    setNeighbors([]);
  }

  return (
    <S2Chrome
      title={meta ? `${meta.name}（${typeId}）` : `Object Type · ${typeId}`}
      lede="七 Tab 详情 · 与发现页内嵌同一面板 · 可切换本体分支"
    >
      <div className="ont-page">
      <BpToolbar>
        <Link to="/ontology" className="btn-nav">
          ← 发现
        </Link>
        <label className="mp-field ont-toolbar-field">
          <span className="mp-field-label">分支</span>
          <select
            className="aos-input"
            aria-label="branch"
            value={branchId}
            onChange={(e) => onBranchChange(e.target.value)}
          >
            {(branches.length ? branches : [{ id: branchId, name: branchId, baseRef: "main", readonly: true }]).map(
              (b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                  {b.readonly ? " (只读)" : ""}
                </option>
              ),
            )}
          </select>
        </label>
        <Link to={`/ontology/wiki?type=${encodeURIComponent(typeId)}`} className="btn-nav">
          LLM Wiki
        </Link>
        <Link to={`/ontology/funnel?type=${encodeURIComponent(typeId)}`} className="btn-nav">
          Funnel →
        </Link>
      </BpToolbar>
      {err && <p className="error">{err}</p>}
      {!meta && !err && <p className="muted">加载中…</p>}
      {meta && (
        <ObjectTypeDetailPanel
          typeId={typeId}
          typeName={meta.name}
          description={meta.description}
          published={meta.published}
          properties={meta.properties}
          branchId={branchId}
          branchReadonly={branchReadonly}
          instanceCount={instanceCount}
          funnelStage={funnelStage}
          objects={objects}
          onOpenInstance={(id) => void openInstance(id).catch((e) => setErr(String(e.message || e)))}
          detail={detail}
          neighbors={neighbors}
          onBranchSaved={() => void reloadObjects().catch((e) => setErr(String((e as Error).message || e)))}
          onMetaSaved={() => void reloadMeta().catch((e) => setErr(String((e as Error).message || e)))}
        />
      )}
      {typeId && !meta && !err && (
        <p className="error">未找到 Object Type：{typeId}</p>
      )}
      </div>
    </S2Chrome>
  );
}
