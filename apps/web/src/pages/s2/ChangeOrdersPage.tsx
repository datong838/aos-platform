import { useMemo, useState } from "react";
import { S2Chrome, apiPost, useJsonGet } from "./shared";
import { BpBanner, BpKvList, BpMetricGrid, BpSplit, BpTable, BpTabs, BpToolbar } from "./blueprintUi";

export type ChangeOrder = {
  id: string; title?: string; kind?: string; status?: "pending" | "approved" | "rejected" | "merged";
  channelId?: string | null; summary?: string | null; emergency?: boolean;
  createdAt?: string; createdBy?: string; decidedAt?: string | null; decidedBy?: string | null;
};

export const STATUS_TABS = [
  { id: "all", label: "全部" }, { id: "pending", label: "待审批" },
  { id: "approved", label: "已通过" }, { id: "rejected", label: "已驳回" },
];

const statusLabel = (status?: string) => status === "pending" ? "待审批" : status === "approved" ? "已通过" : status === "rejected" ? "已驳回" : status === "merged" ? "已合并" : "未知";

export function ChangeOrdersPage() {
  const response = useJsonGet<{ items?: ChangeOrder[] }>("/v1/apollo/changes");
  const items = Array.isArray(response.data?.items) ? response.data.items : [];
  const [active, setActive] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const filtered = useMemo(() => active === "all" ? items : items.filter((item) => item.status === active), [active, items]);
  const selected = items.find((item) => item.id === selectedId) || filtered[0] || null;

  async function decide(approve: boolean) {
    if (!selected || selected.status !== "pending") return;
    setMessage("");
    try {
      await apiPost(`/v1/apollo/changes/${encodeURIComponent(selected.id)}/${approve ? "approve" : "reject"}`, { note: approve ? "批准" : "驳回" });
      setMessage(approve ? "审批结果已记录" : "驳回结果已记录");
      response.reload();
    } catch (error) { setMessage(`操作失败：${error instanceof Error ? error.message : String(error)}`); }
  }

  return (
    <S2Chrome title="变更审批" lede="查看当前工作区的运维变更与审批状态">
      <BpMetricGrid items={[
        { label: "变更单总数", value: String(items.length), tone: "muted" },
        { label: "待审批", value: String(items.filter((i) => i.status === "pending").length), tone: "warn" },
        { label: "已通过", value: String(items.filter((i) => i.status === "approved").length), tone: "ok" },
        { label: "已驳回", value: String(items.filter((i) => i.status === "rejected").length), tone: "bad" },
      ]} />
      <BpToolbar><BpTabs tabs={STATUS_TABS} active={active} onChange={(id) => { setActive(id); setSelectedId(null); }} /><button type="button" className="btn" onClick={response.reload}>刷新</button></BpToolbar>
      {response.err && <BpBanner tone="warn">变更权威读取失败：{response.err}</BpBanner>}
      {items.length === 0 ? <BpBanner tone="info">当前工作区没有变更单；页面不会生成示例审批记录。</BpBanner> : (
        <BpSplit left={<BpTable columns={["编号", "标题", "类型", "状态", "创建时间"]} rows={filtered.map((item) => [
          <button key="id" type="button" className="btn-link" onClick={() => setSelectedId(item.id)}>{item.id}</button>,
          <span key="title">{item.title || "未命名变更"}</span>, <span key="kind">{item.kind || "未登记"}</span>,
          <span key="status">{statusLabel(item.status)}</span>, <span key="created">{item.createdAt || "未知"}</span>,
        ])} />} right={selected ? <div><h3>{selected.title || selected.id}</h3><BpKvList rows={[
          { key: "编号", value: selected.id, mono: true }, { key: "状态", value: statusLabel(selected.status) },
          { key: "通道", value: selected.channelId || "未登记" }, { key: "摘要", value: selected.summary || "未填写" },
          { key: "创建人", value: selected.createdBy || "未知" }, { key: "审批人", value: selected.decidedBy || "尚未审批" },
        ]} />{selected.status === "pending" && <div style={{ display: "flex", gap: 8, marginTop: 12 }}><button type="button" className="btn-primary" onClick={() => void decide(true)}>批准</button><button type="button" className="btn" onClick={() => void decide(false)}>驳回</button></div>}</div> : <p className="muted">请选择变更单</p>} />
      )}
      {message && <BpBanner tone={message.startsWith("操作失败") ? "warn" : "info"}>{message}</BpBanner>}
    </S2Chrome>
  );
}
