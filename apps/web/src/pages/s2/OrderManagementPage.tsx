/**
 * Phase C+ — Order Management Page
 * Aligns with foundry/html/workshop-app-order.html
 *
 * Layout:
 *   - Stats card row (4 cards: total / pending / delivered / revenue)
 *   - Status filter tabs (all / pending / paid / shipped / delivered / cancelled / refunded)
 *   - Search input
 *   - Order table with status badges
 *   - Order detail sidebar with action buttons
 *   - 7-day trend chart (SVG inline)
 */
import { useEffect, useMemo, useState } from "react";
import { PageChrome } from "../../components/PageChrome";
import { apiGet, apiPost } from "../../api/client";

// ── Types ─────────────────────────────────────────────────────────────────────

interface OrderObject {
  id: string;
  type?: string;
  order_no?: string;
  customer_id?: string;
  customer_name?: string;
  order_date?: string;
  total_amount?: number;
  status?: string;
  shipping_address?: string;
  items?: Array<{ product: string; qty: number; price: number }>;
  tracking_no?: string;
  remark?: string;
  [key: string]: unknown;
}

interface OrderListResponse {
  items?: OrderObject[];
  total?: number;
  objects?: OrderObject[];
}

type StatusTab = "all" | "pending" | "paid" | "shipped" | "delivered" | "cancelled" | "refunded";

const STATUS_TABS: { key: StatusTab; label: string; color: string }[] = [
  { key: "all", label: "全部", color: "#374151" },
  { key: "pending", label: "待付款", color: "#6B7280" },
  { key: "paid", label: "已付款", color: "#3B82F6" },
  { key: "shipped", label: "已发货", color: "#F59E0B" },
  { key: "delivered", label: "已签收", color: "#10B981" },
  { key: "cancelled", label: "已取消", color: "#EF4444" },
  { key: "refunded", label: "已退款", color: "#8B5CF6" },
];

const STATUS_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  pending: { bg: "#F3F4F6", text: "#6B7280", label: "待付款" },
  paid: { bg: "#DBEAFE", text: "#2563EB", label: "已付款" },
  shipped: { bg: "#FEF3C7", text: "#D97706", label: "已发货" },
  delivered: { bg: "#D1FAE5", text: "#059669", label: "已签收" },
  cancelled: { bg: "#FEE2E2", text: "#DC2626", label: "已取消" },
  refunded: { bg: "#EDE9FE", text: "#7C3AED", label: "已退款" },
};

// ── Component ─────────────────────────────────────────────────────────────────

export function OrderManagementPage() {
  const [orders, setOrders] = useState<OrderObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<StatusTab>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedOrder, setSelectedOrder] = useState<OrderObject | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    loadOrders();
  }, []);

  function loadOrders() {
    setLoading(true);
    setError(null);
    apiGet<OrderListResponse>("/v1/objects/Order")
      .then((data) => {
        const items = data.items || data.objects || [];
        setOrders(items);
      })
      .catch((e) => setError(String((e as Error).message || e)))
      .finally(() => setLoading(false));
  }

  // Filter + search
  const filteredOrders = useMemo(() => {
    let result = orders;
    if (activeTab !== "all") {
      result = result.filter((o) => o.status === activeTab);
    }
    if (searchTerm.trim()) {
      const term = searchTerm.trim().toLowerCase();
      result = result.filter(
        (o) =>
          (o.order_no || "").toLowerCase().includes(term) ||
          (o.customer_name || "").toLowerCase().includes(term) ||
          (o.customer_id || "").toLowerCase().includes(term),
      );
    }
    return result;
  }, [orders, activeTab, searchTerm]);

  // Stats
  const stats = useMemo(() => {
    const total = orders.length;
    const pending = orders.filter((o) => o.status === "pending" || o.status === "paid").length;
    const delivered = orders.filter((o) => o.status === "delivered").length;
    const revenue = orders
      .filter((o) => o.status === "delivered" || o.status === "shipped")
      .reduce((sum, o) => sum + (o.total_amount || 0), 0);
    return { total, pending, delivered, revenue };
  }, [orders]);

  // 7-day trend (mock from order dates)
  const trendData = useMemo(() => {
    const days: { date: string; count: number }[] = [];
    const now = new Date("2026-07-22");
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().slice(0, 10);
      const count = orders.filter((o) => o.order_date === dateStr).length;
      days.push({ date: dateStr.slice(5), count });
    }
    return days;
  }, [orders]);

  function executeAction(actionTypeId: string, objectId: string, proposed: Record<string, unknown>) {
    setActionLoading(true);
    setActionMessage(null);
    apiPost("/v1/actions/execute", {
      actionTypeId,
      objectType: "Order",
      objectId,
      proposed,
      autoApprove: true,
    })
      .then(() => {
        setActionMessage(`✓ ${actionTypeId} 执行成功`);
        loadOrders();
        setTimeout(() => setActionMessage(null), 3000);
      })
      .catch((e) => {
        setActionMessage(`✗ 执行失败: ${(e as Error).message || e}`);
      })
      .finally(() => setActionLoading(false));
  }

  function handleConfirmShipment(order: OrderObject) {
    const trackingNo = window.prompt("请输入物流单号:", "SF");
    if (!trackingNo) return;
    executeAction("ConfirmShipment", order.id, {
      order_no: order.order_no,
      status: "shipped",
      tracking_no: trackingNo,
    });
  }

  function handleCancelOrder(order: OrderObject) {
    const reason = window.prompt("请输入取消原因:", "用户取消");
    if (!reason) return;
    executeAction("CancelOrder", order.id, {
      order_no: order.order_no,
      status: "cancelled",
      remark: reason,
    });
  }

  function handleRefundOrder(order: OrderObject) {
    const reason = window.prompt("请输入退款原因:", "商品退款");
    if (!reason) return;
    executeAction("RefundOrder", order.id, {
      order_no: order.order_no,
      status: "refunded",
      remark: reason,
      refund_amount: order.total_amount,
    });
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <PageChrome title="订单管理系统" lede="电商订单全生命周期管理 — 列表 · 详情 · 发货 · 取消 · 退款">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Stats Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          <StatCard title="总订单" value={stats.total.toLocaleString()} sublabel="全部订单" color="#3B82F6" />
          <StatCard title="待处理" value={String(stats.pending)} sublabel="待付款+已付款" color="#F59E0B" />
          <StatCard title="已签收" value={stats.delivered.toLocaleString()} sublabel="完成订单" color="#10B981" />
          <StatCard title="总收入" value={`¥${(stats.revenue / 1000).toFixed(1)}K`} sublabel="已签收+已发货" color="#34D399" />
        </div>

        {/* Trend Chart + Detail Panel */}
        <div style={{ display: "grid", gridTemplateColumns: selectedOrder ? "1fr 320px" : "1fr", gap: 12 }}>
          {/* Main Panel */}
          <div style={{
            background: "#fff",
            borderRadius: 2,
            border: "1px solid #E5E7EB",
            overflow: "hidden",
          }}>
            {/* Status Tabs */}
            <div style={{
              display: "flex",
              gap: 4,
              padding: "8px 12px",
              borderBottom: "1px solid #E5E7EB",
              background: "#F9FAFB",
              flexWrap: "wrap",
            }}>
              {STATUS_TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: "4px 12px",
                    fontSize: 12,
                    fontWeight: activeTab === tab.key ? 600 : 400,
                    border: activeTab === tab.key ? `1px solid ${tab.color}` : "1px solid #E5E7EB",
                    borderRadius: 4,
                    background: activeTab === tab.key ? tab.color : "#fff",
                    color: activeTab === tab.key ? "#fff" : "#6B7280",
                    cursor: "pointer",
                    transition: "all 0.15s",
                  }}
                >
                  {tab.label}
                  {tab.key === "all"
                    ? ` (${orders.length})`
                    : ` (${orders.filter((o) => o.status === tab.key).length})`}
                </button>
              ))}
            </div>

            {/* Search Bar */}
            <div style={{ padding: "8px 12px", borderBottom: "1px solid #E5E7EB" }}>
              <input
                type="search"
                placeholder="搜索订单号 / 客户名 / 客户ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{
                  width: "100%",
                  padding: "6px 12px",
                  border: "1px solid #D1D5DB",
                  borderRadius: 2,
                  fontSize: 13,
                  outline: "none",
                }}
              />
            </div>

            {/* Table */}
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "#F9FAFB" }}>
                  <th style={{ textAlign: "left", padding: "8px 12px", fontWeight: 600, color: "#374151" }}>订单号</th>
                  <th style={{ textAlign: "left", padding: "8px 12px", fontWeight: 600, color: "#374151" }}>客户</th>
                  <th style={{ textAlign: "left", padding: "8px 12px", fontWeight: 600, color: "#374151" }}>日期</th>
                  <th style={{ textAlign: "right", padding: "8px 12px", fontWeight: 600, color: "#374151" }}>金额</th>
                  <th style={{ textAlign: "center", padding: "8px 12px", fontWeight: 600, color: "#374151" }}>状态</th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: "center", padding: 24, color: "#9CA3AF" }}>加载中...</td>
                  </tr>
                )}
                {error && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: "center", padding: 24, color: "#EF4444" }}>加载失败: {error}</td>
                  </tr>
                )}
                {!loading && !error && filteredOrders.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: "center", padding: 24, color: "#9CA3AF" }}>无匹配订单</td>
                  </tr>
                )}
                {filteredOrders.map((order) => {
                  const badge = STATUS_BADGE[order.status || ""] || STATUS_BADGE.pending;
                  const isSelected = selectedOrder?.id === order.id;
                  return (
                    <tr
                      key={order.id}
                      onClick={() => setSelectedOrder(order)}
                      style={{
                        cursor: "pointer",
                        background: isSelected ? "#EFF6FF" : undefined,
                        borderBottom: "1px solid #F3F4F6",
                      }}
                    >
                      <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: 12, color: "#1F2937" }}>
                        {order.order_no}
                      </td>
                      <td style={{ padding: "8px 12px", color: "#374151" }}>
                        {order.customer_name || "—"}
                        <span style={{ fontSize: 10, color: "#9CA3AF", marginLeft: 4 }}>{order.customer_id}</span>
                      </td>
                      <td style={{ padding: "8px 12px", color: "#6B7280", fontSize: 12 }}>{order.order_date}</td>
                      <td style={{ padding: "8px 12px", textAlign: "right", fontWeight: 600, color: "#059669" }}>
                        ¥{(order.total_amount || 0).toLocaleString()}
                      </td>
                      <td style={{ padding: "8px 12px", textAlign: "center" }}>
                        <span style={{
                          display: "inline-block",
                          padding: "2px 8px",
                          borderRadius: 4,
                          fontSize: 11,
                          fontWeight: 500,
                          background: badge.bg,
                          color: badge.text,
                        }}>
                          {badge.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Detail Sidebar */}
          {selectedOrder && (
            <div style={{
              background: "#fff",
              borderRadius: 2,
              border: "1px solid #E5E7EB",
              padding: 16,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#1F2937", marginBottom: 4 }}>
                订单详情
              </div>
              <DetailRow label="订单号" value={selectedOrder.order_no || "—"} mono />
              <DetailRow label="客户" value={`${selectedOrder.customer_name || "—"} (${selectedOrder.customer_id || ""})`} />
              <DetailRow label="金额" value={`¥${(selectedOrder.total_amount || 0).toLocaleString()}`} green />
              <DetailRow label="状态" value={STATUS_BADGE[selectedOrder.status || ""]?.label || selectedOrder.status || "—"} />
              <DetailRow label="下单日期" value={selectedOrder.order_date || "—"} />
              <DetailRow label="收货地址" value={selectedOrder.shipping_address || "—"} />
              <DetailRow label="物流单号" value={selectedOrder.tracking_no || "—"} mono />

              {/* Items */}
              {selectedOrder.items && selectedOrder.items.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 4 }}>商品明细</div>
                  {selectedOrder.items.map((item, idx) => (
                    <div key={idx} style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "4px 0",
                      fontSize: 12,
                      color: "#6B7280",
                      borderBottom: "1px solid #F3F4F6",
                    }}>
                      <span>{item.product} × {item.qty}</span>
                      <span style={{ color: "#059669" }}>¥{(item.price * item.qty).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              )}

              {selectedOrder.remark && (
                <DetailRow label="备注" value={selectedOrder.remark} />
              )}

              {/* Action buttons */}
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 12 }}>
                {actionMessage && (
                  <div style={{
                    padding: "6px 10px",
                    fontSize: 12,
                    borderRadius: 4,
                    background: actionMessage.startsWith("✓") ? "#D1FAE5" : "#FEE2E2",
                    color: actionMessage.startsWith("✓") ? "#059669" : "#DC2626",
                  }}>
                    {actionMessage}
                  </div>
                )}
                {(selectedOrder.status === "paid") && (
                  <button
                    onClick={() => handleConfirmShipment(selectedOrder)}
                    disabled={actionLoading}
                    style={actionBtnStyle("#3B82F6")}
                  >
                    {actionLoading ? "处理中..." : "确认发货"}
                  </button>
                )}
                {(selectedOrder.status === "pending" || selectedOrder.status === "paid") && (
                  <button
                    onClick={() => handleCancelOrder(selectedOrder)}
                    disabled={actionLoading}
                    style={actionBtnStyle("#EF4444")}
                  >
                    取消订单
                  </button>
                )}
                {(selectedOrder.status === "shipped" || selectedOrder.status === "delivered") && (
                  <button
                    onClick={() => handleRefundOrder(selectedOrder)}
                    disabled={actionLoading}
                    style={actionBtnStyle("#8B5CF6")}
                  >
                    申请退款
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Trend Chart */}
        <div style={{
          background: "#fff",
          borderRadius: 2,
          border: "1px solid #E5E7EB",
          padding: 16,
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#1F2937", marginBottom: 12 }}>
            近 7 天订单趋势
          </div>
          <TrendChart data={trendData} />
        </div>
      </div>
    </PageChrome>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ title, value, sublabel, color }: { title: string; value: string; sublabel: string; color: string }) {
  return (
    <div style={{
      background: "#fff",
      borderRadius: 2,
      border: "1px solid #E5E7EB",
      padding: 16,
      display: "flex",
      flexDirection: "column",
      gap: 4,
    }}>
      <div style={{ fontSize: 11, color: "#9CA3AF", fontWeight: 500 }}>{title}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 11, color: "#9CA3AF" }}>{sublabel}</div>
    </div>
  );
}

function DetailRow({ label, value, mono, green }: { label: string; value: string; mono?: boolean; green?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
      <span style={{ fontSize: 11, color: "#9CA3AF" }}>{label}</span>
      <span style={{
        fontSize: 12,
        color: green ? "#059669" : "#374151",
        fontFamily: mono ? "monospace" : undefined,
        fontWeight: green ? 600 : 400,
        textAlign: "right",
        maxWidth: 200,
        wordBreak: "break-all",
      }}>
        {value}
      </span>
    </div>
  );
}

function TrendChart({ data }: { data: { date: string; count: number }[] }) {
  const maxCount = Math.max(...data.map((d) => d.count), 1);
  const chartW = 600;
  const chartH = 120;
  const padding = 30;
  const stepX = (chartW - padding * 2) / Math.max(data.length - 1, 1);

  const points = data.map((d, i) => {
    const x = padding + i * stepX;
    const y = chartH - padding - (d.count / maxCount) * (chartH - padding * 2);
    return { x, y, ...d };
  });

  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x},${p.y}`).join(" ");
  const areaD = `${pathD} L ${points[points.length - 1]?.x || padding},${chartH - padding} L ${padding},${chartH - padding} Z`;

  return (
    <svg viewBox={`0 0 ${chartW} ${chartH}`} style={{ width: "100%", height: 120 }}>
      {/* Grid lines */}
      {[0, 0.5, 1].map((ratio) => {
        const y = chartH - padding - ratio * (chartH - padding * 2);
        return (
          <line
            key={ratio}
            x1={padding}
            y1={y}
            x2={chartW - padding}
            y2={y}
            stroke="#F3F4F6"
            strokeWidth={1}
          />
        );
      })}
      {/* Area fill */}
      <path d={areaD} fill="rgba(59,130,246,0.1)" />
      {/* Line */}
      <path d={pathD} fill="none" stroke="#3B82F6" strokeWidth={2} />
      {/* Points */}
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r={3} fill="#3B82F6" />
          <text x={p.x} y={p.y - 8} textAnchor="middle" fontSize={10} fill="#3B82F6" fontWeight={600}>
            {p.count}
          </text>
          <text x={p.x} y={chartH - padding + 14} textAnchor="middle" fontSize={10} fill="#9CA3AF">
            {p.date}
          </text>
        </g>
      ))}
    </svg>
  );
}

function actionBtnStyle(bg: string): React.CSSProperties {
  return {
    padding: "8px 16px",
    fontSize: 13,
    fontWeight: 500,
    border: "none",
    borderRadius: 2,
    background: bg,
    color: "#fff",
    cursor: "pointer",
    transition: "opacity 0.15s",
  };
}
