import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, API_BASE } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import {
  BpBanner,
  BpDraftCard,
  BpLinkRow,
  BpPropGrid,
  BpSplit,
  BpToolbar,
} from "./s2/blueprintUi";

type Draft = {
  id: string;
  title: string;
  status: string;
  actionTypeId: string;
  objectType?: string;
  objectId?: string;
  createdBy?: string;
  proposed?: Record<string, unknown>;
};

function draftStatus(s: string): "proposed" | "approved" | "rejected" {
  if (s === "approved") return "approved";
  if (s === "rejected") return "rejected";
  return "proposed";
}

function proposedProps(proposed?: Record<string, unknown>) {
  if (!proposed || Object.keys(proposed).length === 0) return [];
  return Object.entries(proposed).map(([label, value]) => ({
    label,
    value: typeof value === "object" ? JSON.stringify(value) : String(value),
  }));
}

/** 86 · 对齐 aip-draft-inbox · 队列 + 详情分栏 · TB.4 写回闭环 */
export function DraftInboxPage() {
  const [items, setItems] = useState<Draft[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function reload() {
    const res = await apiGet<{ items: Draft[] }>("/v1/aip/drafts");
    setItems(res.items);
  }

  useEffect(() => {
    reload().catch((e) => setErr(String(e.message || e)));
  }, []);

  useEffect(() => {
    if (items.length === 0) {
      setSelectedId(null);
      return;
    }
    if (selectedId && items.some((d) => d.id === selectedId)) return;
    const next = items.find((d) => d.status === "proposed") ?? items[0];
    setSelectedId(next.id);
  }, [items, selectedId]);

  const selected = useMemo(
    () => items.find((d) => d.id === selectedId) ?? null,
    [items, selectedId],
  );

  const pending = items.filter((d) => d.status === "proposed").length;

  async function createSample() {
    setErr(null);
    try {
      const d = await apiPost<Draft>("/v1/aip/drafts", {
        actionTypeId: "CloseWorkOrder",
        objectType: "WorkOrder",
        objectId: "wo-1001",
        proposed: { reason: "manual" },
        title: "关闭工单提案",
      });
      setMsg(`已创建 ${d.id}（未写生产）`);
      setSelectedId(d.id);
      await reload();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function approve(id: string) {
    setErr(null);
    try {
      const res = await fetch(`${API_BASE}/v1/aip/drafts/${id}/approve`, {
        method: "POST",
        headers: {
          Authorization: "Bearer dev",
          "X-Org-Id": "dev-org",
          "X-Project-Id": "dev-project",
          "Idempotency-Key": `ui-approve-${id}`,
          "X-Allow-Conflicts": "true",
        },
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || res.statusText);
      setMsg(
        `已批准并写生产 · object=${body.objectId} · lineage=${body.lineageId}`,
      );
      await reload();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function reject(id: string) {
    setErr(null);
    try {
      await apiPost(`/v1/aip/drafts/${id}/reject`, {});
      setMsg(`已驳回 ${id}`);
      await reload();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  function renderDetail(d: Draft) {
    const st = draftStatus(d.status);
    const meta = [
      `来源：${d.actionTypeId}`,
      d.objectType && d.objectId ? `${d.objectType}/${d.objectId}` : null,
      d.createdBy ? `提交人：${d.createdBy}` : null,
      `ID：${d.id}`,
    ]
      .filter(Boolean)
      .join(" · ");

    const props = proposedProps(d.proposed);

    return (
      <div>
        <BpDraftCard
          title={d.title || d.id}
          meta={meta}
          status={st}
          tag={d.actionTypeId === "CloseWorkOrder" ? "WorkOrder" : undefined}
          actions={
            st === "proposed" ? (
              <>
                <button type="button" className="btn" onClick={() => void approve(d.id)}>
                  批准写入
                </button>
                <button type="button" className="btn" onClick={() => void reject(d.id)}>
                  驳回
                </button>
                <Link to="/aip/lineage" className="btn" style={{ textDecoration: "none" }}>
                  查看决策链
                </Link>
              </>
            ) : st === "approved" ? (
              <Link to="/aip/lineage" className="btn-nav">
                查看决策链 →
              </Link>
            ) : null
          }
        />
        {props.length > 0 && (
          <div style={{ marginTop: "1rem" }}>
            <div className="bp-ws-section-title">拟写入字段</div>
            <BpPropGrid items={props} />
          </div>
        )}
      </div>
    );
  }

  return (
    <PageChrome
      title="Draft 审批队列"
      lede="Agent / Action 写入须经 HITL 批准后方可落生产 Ontology；含 Insight Backfill（知识回填）。"
    >
      {pending > 0 && (
        <p className="status-pill" style={{ marginBottom: "0.75rem" }}>
          <span className="status-dot" />
          {pending} 待审
        </p>
      )}

      <BpBanner tone="info">
        <strong>Draft Dataset 隔离：</strong>
        所有待审写入暂存于独立 Draft Dataset，与生产数据物理隔离；驳回即丢弃，不污染主库。
      </BpBanner>

      <BpToolbar>
        <button type="button" className="btn" onClick={() => void createSample()}>
          新建提案
        </button>
      </BpToolbar>

      <BpLinkRow
        links={[
          { to: "/aip/lineage", label: "决策谱系" },
          { to: "/workshop/inbox", label: "运营 Inbox" },
        ]}
      />

      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}

      <div style={{ marginTop: "1rem" }}>
        {items.length === 0 && !err && (
          <p className="muted">队列为空 · 可新建提案</p>
        )}
        {items.length > 0 && (
          <BpSplit
            left={
              <div className="bp-draft-queue">
                <div className="bp-ws-section-title">队列 ({items.length})</div>
                <ul className="card-list" style={{ marginTop: "0.5rem" }}>
                  {items.map((d) => {
                    const st = draftStatus(d.status);
                    const active = d.id === selectedId;
                    return (
                      <li key={d.id}>
                        <button
                          type="button"
                          className={
                            active
                              ? "bp-draft-queue-item bp-draft-queue-active"
                              : "bp-draft-queue-item"
                          }
                          onClick={() => setSelectedId(d.id)}
                        >
                          <span className="bp-draft-queue-title">{d.title || d.id}</span>
                          <span className={`bp-draft-badge bp-draft-badge-${st === "proposed" ? "pending" : st === "approved" ? "done" : "reject"}`}>
                            {st === "proposed" ? "待审" : st === "approved" ? "已通过" : "已驳回"}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            }
            right={
              selected ? (
                <div className="bp-draft-detail">
                  <div className="bp-ws-section-title">详情</div>
                  {renderDetail(selected)}
                </div>
              ) : (
                <p className="muted">选择一条 Draft 查看详情</p>
              )
            }
          />
        )}
      </div>
    </PageChrome>
  );
}
