/**
 * Phase 7 · 系统管理 - 权限管理页
 * 对齐 HTML 蓝图：角色列表 + 权限矩阵 + 用户分配
 */
import { useState } from "react";
import { BpBanner, BpToolbar, BpTable, BpTabs } from "./blueprintUi";
import { S2Chrome } from "./shared";

type Tab = "roles" | "matrix" | "users";

interface Role {
  id: string;
  name: string;
  description: string;
  userCount: number;
  permissions: string[];
}

interface UserPerm {
  id: string;
  name: string;
  email: string;
  role: string;
  lastActive: string;
  status: "active" | "suspended" | "invited";
}

const ROLES: Role[] = [
  { id: "admin", name: "管理员", description: "完全访问权限，包括系统配置和用户管理", userCount: 2, permissions: ["*"] },
  { id: "developer", name: "开发者", description: "管道/数据集/本体开发，可部署和测试", userCount: 5, permissions: ["pipeline:*", "dataset:*", "ontology:*", "workshop:*"] },
  { id: "analyst", name: "分析师", description: "数据查询和可视化，只读访问", userCount: 8, permissions: ["dataset:read", "workshop:read", "aip:read"] },
  { id: "viewer", name: "访客", description: "仅查看仪表盘和报告", userCount: 12, permissions: ["workshop:read"] },
];

const USERS: UserPerm[] = [
  { id: "u-001", name: "大同", email: "datong@aos.dev", role: "admin", lastActive: "当前在线", status: "active" },
  { id: "u-002", name: "管理员", email: "admin@aos.dev", role: "admin", lastActive: "1 小时前", status: "active" },
  { id: "u-003", name: "开发者A", email: "dev1@aos.dev", role: "developer", lastActive: "30 分钟前", status: "active" },
  { id: "u-004", name: "开发者B", email: "dev2@aos.dev", role: "developer", lastActive: "2 小时前", status: "active" },
  { id: "u-005", name: "分析师A", email: "analyst1@aos.dev", role: "analyst", lastActive: "今天", status: "active" },
  { id: "u-006", name: "访客A", email: "viewer1@aos.dev", role: "viewer", lastActive: "昨天", status: "active" },
  { id: "u-007", name: "待激活用户", email: "new@aos.dev", role: "viewer", lastActive: "—", status: "invited" },
  { id: "u-008", name: "已暂停", email: "suspended@aos.dev", role: "viewer", lastActive: "7 天前", status: "suspended" },
];

const PERMISSION_MATRIX = [
  { resource: "管道", actions: { create: ["admin", "developer"], read: ["admin", "developer", "analyst", "viewer"], update: ["admin", "developer"], delete: ["admin", "developer"], deploy: ["admin", "developer"] } },
  { resource: "数据集", actions: { create: ["admin", "developer"], read: ["admin", "developer", "analyst", "viewer"], update: ["admin", "developer"], delete: ["admin"], deploy: [] } },
  { resource: "本体", actions: { create: ["admin", "developer"], read: ["admin", "developer", "analyst"], update: ["admin", "developer"], delete: ["admin"], deploy: [] } },
  { resource: "工作台", actions: { create: ["admin", "developer"], read: ["admin", "developer", "analyst", "viewer"], update: ["admin", "developer"], delete: ["admin"], deploy: ["admin"] } },
  { resource: "AIP", actions: { create: ["admin", "developer"], read: ["admin", "developer", "analyst"], update: ["admin", "developer"], delete: ["admin"], deploy: ["admin"] } },
  { resource: "运维", actions: { create: ["admin"], read: ["admin", "developer"], update: ["admin"], delete: ["admin"], deploy: ["admin"] } },
  { resource: "用户管理", actions: { create: ["admin"], read: ["admin"], update: ["admin"], delete: ["admin"], deploy: [] } },
];

const STATUS_TONE: Record<string, string> = { active: "ok", suspended: "warn", invited: "muted" };
const STATUS_LABEL: Record<string, string> = { active: "活跃", suspended: "已暂停", invited: "已邀请" };

export function PermissionManagerPage() {
  const [tab, setTab] = useState<Tab>("roles");
  const [selectedRole, setSelectedRole] = useState<string>("developer");

  return (
    <S2Chrome title="权限管理" lede="角色 · 权限矩阵 · 用户分配">
      <BpToolbar>
        <button type="button" className="btn-primary">+ 新建角色</button>
        <button type="button" className="btn">+ 邀请用户</button>
      </BpToolbar>

      <BpTabs
        tabs={[
          { id: "roles", label: "角色" },
          { id: "matrix", label: "权限矩阵" },
          { id: "users", label: "用户" },
        ]}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
      />

      {tab === "roles" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
            {ROLES.map((r) => (
              <div
                key={r.id}
                style={{
                  padding: 12,
                  border: `2px solid ${selectedRole === r.id ? "var(--aos-accent, #3182ce)" : "var(--aos-border, #e2e8f0)"}`,
                  borderRadius: 4,
                  cursor: "pointer",
                }}
                onClick={() => setSelectedRole(r.id)}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h4 className="aos-text" style={{ fontSize: "0.9rem", margin: 0 }}>{r.name}</h4>
                  <span className="muted" style={{ fontSize: "0.75rem" }}>{r.userCount} 用户</span>
                </div>
                <p className="muted" style={{ fontSize: "0.75rem", marginTop: 4 }}>{r.description}</p>
                <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {r.permissions.map((p) => (
                    <span key={p} className="mono" style={{ fontSize: "0.65rem", padding: "2px 6px", background: "var(--aos-surface-hover, #edf2f7)", borderRadius: 3 }}>
                      {p}
                    </span>
                  ))}
                </div>
                <div style={{ marginTop: 8 }}>
                  <button type="button" className="nav-link">编辑权限</button>
                  <button type="button" className="nav-link">查看用户</button>
                </div>
              </div>
            ))}
          </div>
          <BpBanner tone="info">
            当前选中角色：<strong>{ROLES.find((r) => r.id === selectedRole)?.name}</strong>
          </BpBanner>
        </div>
      )}

      {tab === "matrix" && (
        <div style={{ overflowX: "auto" }}>
          <BpTable
            columns={["资源", "创建", "读取", "更新", "删除", "部署"]}
            rows={PERMISSION_MATRIX.map((row) => [
              <strong key="res">{row.resource}</strong>,
              ...(["create", "read", "update", "delete", "deploy"] as const).map((act) => {
                const roles = row.actions[act];
                if (roles.length === 0) return <span key={act} className="muted">—</span>;
                return (
                  <span key={act}>
                    {roles.map((r) => (
                      <span key={r} className="bp-discover-badge bp-discover-badge-ok" style={{ marginRight: 4, fontSize: "0.65rem" }}>
                        {ROLES.find((x) => x.id === r)?.name || r}
                      </span>
                    ))}
                  </span>
                );
              }),
            ])}
          />
          <BpBanner tone="info">
            权限矩阵以「资源 × 操作」为粒度 · 共 {PERMISSION_MATRIX.length} 类资源 × 5 种操作
          </BpBanner>
        </div>
      )}

      {tab === "users" && (
        <div>
          <BpTable
            columns={["用户", "邮箱", "角色", "最后活跃", "状态", ""]}
            rows={USERS.map((u) => [
              u.name,
              <span key="email" className="mono" style={{ fontSize: "0.75rem" }}>{u.email}</span>,
              <span key="role" className="bp-discover-badge bp-discover-badge-ok">
                {ROLES.find((r) => r.id === u.role)?.name || u.role}
              </span>,
              u.lastActive,
              <span key="status" className={`bp-discover-badge bp-discover-badge-${STATUS_TONE[u.status]}`}>
                {STATUS_LABEL[u.status]}
              </span>,
              <div key="actions">
                <button type="button" className="nav-link">编辑</button>
                <button type="button" className="nav-link" style={{ color: "#e53e3e" }}>{u.status === "suspended" ? "恢复" : "暂停"}</button>
              </div>,
            ])}
          />
          <BpBanner tone="info">
            共 {USERS.length} 用户 · 活跃 {USERS.filter((u) => u.status === "active").length} · 已邀请 {USERS.filter((u) => u.status === "invited").length} · 已暂停 {USERS.filter((u) => u.status === "suspended").length}
          </BpBanner>
        </div>
      )}
    </S2Chrome>
  );
}
