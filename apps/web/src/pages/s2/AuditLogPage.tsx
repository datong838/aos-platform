/**
 * Phase 7 · 系统管理 - 审计日志页
 * 对齐 HTML 蓝图：时间线 + 过滤 + 详情展开
 */
import { useMemo, useState } from "react";
import { BpBanner, BpToolbar, BpTable } from "./blueprintUi";
import { S2Chrome } from "./shared";

type AuditAction = "create" | "update" | "delete" | "login" | "logout" | "deploy" | "config";
type AuditResource = "pipeline" | "dataset" | "ontology" | "model" | "user" | "spoke" | "schedule";
type AuditSeverity = "info" | "warn" | "critical";

interface AuditEntry {
  id: string;
  timestamp: string;
  user: string;
  action: AuditAction;
  resource: AuditResource;
  resourceId: string;
  severity: AuditSeverity;
  message: string;
  ip: string;
}

const SEED_AUDIT: AuditEntry[] = [
  { id: "log-001", timestamp: "2026-07-27 19:45:23", user: "datong", action: "deploy", resource: "pipeline", resourceId: "P05-栖月汇-订单", severity: "info", message: "管道「栖月汇-订单清洗」部署成功（搭建 #185）", ip: "192.168.1.100" },
  { id: "log-002", timestamp: "2026-07-27 19:30:12", user: "datong", action: "update", resource: "model", resourceId: "智能路由模型", severity: "info", message: "更新模型路由配置：新增 fallback 链", ip: "192.168.1.100" },
  { id: "log-003", timestamp: "2026-07-27 18:55:01", user: "system", action: "config", resource: "spoke", resourceId: "运行节点-美东-生产", severity: "warn", message: "运行节点配置已修改（日志级别 → DEBUG）", ip: "10.0.0.1" },
  { id: "log-004", timestamp: "2026-07-27 17:20:45", user: "admin", action: "delete", resource: "schedule", resourceId: "栖月汇 旧版批量同步计划", severity: "critical", message: "删除计划任务「旧版批量同步」", ip: "172.16.0.5" },
  { id: "log-005", timestamp: "2026-07-27 16:10:33", user: "datong", action: "create", resource: "ontology", resourceId: "对象类型-会员", severity: "info", message: "创建对象类型「CustomerLite 会员」", ip: "192.168.1.100" },
  { id: "log-006", timestamp: "2026-07-27 15:30:00", user: "datong", action: "login", resource: "user", resourceId: "datong", severity: "info", message: "用户登录", ip: "192.168.1.100" },
  { id: "log-007", timestamp: "2026-07-27 14:15:22", user: "analyst1", action: "update", resource: "dataset", resourceId: "栖月汇-订单 数据集", severity: "warn", message: "数据集 schema 变更（新增列 region 地域）", ip: "10.0.0.20" },
  { id: "log-008", timestamp: "2026-07-27 12:00:00", user: "system", action: "deploy", resource: "spoke", resourceId: "运行节点-西欧-生产", severity: "critical", message: "运行节点部署失败：健康检查超时", ip: "10.0.0.1" },
  { id: "log-009", timestamp: "2026-07-27 10:30:15", user: "admin", action: "config", resource: "user", resourceId: "analyst1", severity: "info", message: "用户角色变更 只读 → 分析员", ip: "172.16.0.5" },
  { id: "log-010", timestamp: "2026-07-27 09:00:00", user: "system", action: "login", resource: "user", resourceId: "scheduler", severity: "info", message: "系统调度器启动", ip: "127.0.0.1" },
];

const ACTION_LABEL: Record<AuditAction, string> = {
  create: "创建", update: "更新", delete: "删除", login: "登录", logout: "登出", deploy: "部署", config: "配置",
};
const SEVERITY_TONE: Record<AuditSeverity, string> = {
  info: "ok", warn: "warn", critical: "error",
};

export function AuditLogPage() {
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    let items = SEED_AUDIT;
    if (actionFilter) items = items.filter((e) => e.action === actionFilter);
    if (severityFilter) items = items.filter((e) => e.severity === severityFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      items = items.filter((e) =>
        e.user.toLowerCase().includes(q) ||
        e.message.toLowerCase().includes(q) ||
        e.resourceId.toLowerCase().includes(q)
      );
    }
    return items;
  }, [search, actionFilter, severityFilter]);

  const selected = filtered.find((e) => e.id === selectedId) || null;

  return (
    <S2Chrome title="审计日志" lede={`${filtered.length} / ${SEED_AUDIT.length} 条记录`}>
      <BpToolbar>
        <input
          type="search"
          placeholder="搜索用户/操作/资源…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ fontSize: "0.8rem", padding: "2px 8px", minWidth: 200 }}
        />
        <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)} style={{ fontSize: "0.8rem" }}>
          <option value="">全部操作</option>
          <option value="create">创建</option>
          <option value="update">更新</option>
          <option value="delete">删除</option>
          <option value="login">登录</option>
          <option value="deploy">部署</option>
          <option value="config">配置</option>
        </select>
        <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} style={{ fontSize: "0.8rem" }}>
          <option value="">全部级别</option>
          <option value="info">信息</option>
          <option value="warn">警告</option>
          <option value="critical">严重</option>
        </select>
      </BpToolbar>

      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ flex: 1 }}>
          <BpTable
            columns={["时间", "用户", "操作", "资源", "级别", "消息"]}
            rows={filtered.map((e) => [
              <span key="ts" className="mono" style={{ fontSize: "0.75rem" }}>{e.timestamp}</span>,
              e.user,
              <span key="act" className={`bp-discover-badge bp-discover-badge-${SEVERITY_TONE[e.severity]}`}>
                {ACTION_LABEL[e.action]}
              </span>,
              <span key="res" className="mono" style={{ fontSize: "0.75rem" }}>{e.resource}:{e.resourceId}</span>,
              <span key="sev" className={`bp-discover-badge bp-discover-badge-${SEVERITY_TONE[e.severity]}`}>
                {e.severity === "critical" ? "严重" : e.severity === "warn" ? "警告" : "信息"}
              </span>,
              <span key="msg" style={{ fontSize: "0.8rem", cursor: "pointer" }} onClick={() => setSelectedId(e.id)}>
                {e.message}
              </span>,
            ])}
          />
          {filtered.length === 0 && <p className="muted">无匹配记录</p>}
        </div>

        {selected && (
          <aside style={{ width: 300, padding: 12, background: "var(--aos-surface, #f7fafc)", borderRadius: 4, border: "1px solid var(--aos-border, #e2e8f0)" }}>
            <h4 className="aos-text" style={{ fontSize: "0.85rem" }}>审计详情</h4>
            <div style={{ marginTop: 8 }}>
              <div style={{ marginBottom: 6 }}><span className="muted" style={{ fontSize: "0.7rem" }}>ID</span><br /><span className="mono" style={{ fontSize: "0.75rem" }}>{selected.id}</span></div>
              <div style={{ marginBottom: 6 }}><span className="muted" style={{ fontSize: "0.7rem" }}>时间</span><br />{selected.timestamp}</div>
              <div style={{ marginBottom: 6 }}><span className="muted" style={{ fontSize: "0.7rem" }}>用户</span><br />{selected.user}</div>
              <div style={{ marginBottom: 6 }}><span className="muted" style={{ fontSize: "0.7rem" }}>操作</span><br />{ACTION_LABEL[selected.action]}</div>
              <div style={{ marginBottom: 6 }}><span className="muted" style={{ fontSize: "0.7rem" }}>资源</span><br /><span className="mono">{selected.resource}:{selected.resourceId}</span></div>
              <div style={{ marginBottom: 6 }}><span className="muted" style={{ fontSize: "0.7rem" }}>IP</span><br /><span className="mono">{selected.ip}</span></div>
              <div style={{ marginBottom: 6 }}><span className="muted" style={{ fontSize: "0.7rem" }}>消息</span><br />{selected.message}</div>
            </div>
            <button type="button" className="nav-link" onClick={() => setSelectedId(null)}>关闭</button>
          </aside>
        )}
      </div>

      <BpBanner tone="info">
        审计日志保留 90 天 · 当前展示最近 {SEED_AUDIT.length} 条
      </BpBanner>
    </S2Chrome>
  );
}
