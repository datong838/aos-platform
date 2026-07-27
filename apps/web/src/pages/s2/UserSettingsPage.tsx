/**
 * Phase 7 · 系统管理 - 用户设置页
 * 对齐 HTML 蓝图风格：个人资料 + 安全设置 + 通知偏好 + API Token
 */
import { useState } from "react";
import { BpBanner, BpToolbar, BpTabs, BpTable } from "./blueprintUi";
import { S2Chrome } from "./shared";

type Tab = "profile" | "security" | "notifications" | "tokens";

export function UserSettingsPage() {
  const [tab, setTab] = useState<Tab>("profile");
  const [theme, setTheme] = useState("light");
  const [notifEmail, setNotifEmail] = useState(true);
  const [notifSlack, setNotifSlack] = useState(false);
  const [notifWebhook, setNotifWebhook] = useState(false);
  const [saved, setSaved] = useState(false);

  const tokens = [
    { id: "tok-001", name: "CI/CD Pipeline Token", created: "2026-07-01", lastUsed: "2026-07-27", scope: "read:pipelines" },
    { id: "tok-002", name: "Dev Debug Token", created: "2026-06-15", lastUsed: "2026-07-26", scope: "read:*,write:*" },
    { id: "tok-003", name: "Monitoring Token", created: "2026-05-20", lastUsed: "2026-07-27", scope: "read:ops" },
  ];

  return (
    <S2Chrome title="用户设置" lede="个人资料 · 安全 · 通知 · API Token">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => setSaved(false)}>重置</button>
        <button type="button" className="btn-primary" onClick={() => setSaved(true)}>保存设置</button>
        {saved && <span style={{ color: "#38a169", fontSize: "0.8rem" }}>✓ 已保存</span>}
      </BpToolbar>

      <BpTabs
        tabs={[
          { id: "profile", label: "个人资料" },
          { id: "security", label: "安全" },
          { id: "notifications", label: "通知" },
          { id: "tokens", label: "API Token" },
        ]}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
      />

      {tab === "profile" && (
        <div style={{ maxWidth: 600, padding: "16px 0" }}>
          <h3 className="aos-text" style={{ fontSize: "0.9rem" }}>基本信息</h3>
          <label className="bp-field" style={{ display: "block", marginBottom: 12 }}>
            <span className="muted" style={{ fontSize: "0.75rem" }}>用户名</span>
            <input type="text" defaultValue="datong" disabled style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }} />
          </label>
          <label className="bp-field" style={{ display: "block", marginBottom: 12 }}>
            <span className="muted" style={{ fontSize: "0.75rem" }}>显示名称</span>
            <input type="text" defaultValue="大同" style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }} />
          </label>
          <label className="bp-field" style={{ display: "block", marginBottom: 12 }}>
            <span className="muted" style={{ fontSize: "0.75rem" }}>邮箱</span>
            <input type="email" defaultValue="datong@aos.dev" style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }} />
          </label>
          <label className="bp-field" style={{ display: "block", marginBottom: 12 }}>
            <span className="muted" style={{ fontSize: "0.75rem" }}>部门</span>
            <input type="text" defaultValue="数据平台部" style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }} />
          </label>
          <label className="bp-field" style={{ display: "block", marginBottom: 12 }}>
            <span className="muted" style={{ fontSize: "0.75rem" }}>角色</span>
            <select style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }}>
              <option value="admin">管理员</option>
              <option value="developer">开发者</option>
              <option value="analyst">分析师</option>
              <option value="viewer">访客</option>
            </select>
          </label>

          <h3 className="aos-text" style={{ fontSize: "0.9rem", marginTop: 24 }}>界面偏好</h3>
          <label className="bp-field" style={{ display: "block", marginBottom: 12 }}>
            <span className="muted" style={{ fontSize: "0.75rem" }}>主题</span>
            <select value={theme} onChange={(e) => setTheme(e.target.value)} style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }}>
              <option value="light">浅色</option>
              <option value="dark">深色</option>
              <option value="auto">跟随系统</option>
            </select>
          </label>
          <label className="bp-field" style={{ display: "block", marginBottom: 12 }}>
            <span className="muted" style={{ fontSize: "0.75rem" }}>语言</span>
            <select style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }}>
              <option value="zh-CN">简体中文</option>
              <option value="en-US">English</option>
            </select>
          </label>
        </div>
      )}

      {tab === "security" && (
        <div style={{ maxWidth: 600, padding: "16px 0" }}>
          <h3 className="aos-text" style={{ fontSize: "0.9rem" }}>修改密码</h3>
          <label className="bp-field" style={{ display: "block", marginBottom: 12 }}>
            <span className="muted" style={{ fontSize: "0.75rem" }}>当前密码</span>
            <input type="password" placeholder="••••••••" style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }} />
          </label>
          <label className="bp-field" style={{ display: "block", marginBottom: 12 }}>
            <span className="muted" style={{ fontSize: "0.75rem" }}>新密码</span>
            <input type="password" placeholder="至少 8 位，含大小写+数字" style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }} />
          </label>
          <label className="bp-field" style={{ display: "block", marginBottom: 12 }}>
            <span className="muted" style={{ fontSize: "0.75rem" }}>确认新密码</span>
            <input type="password" placeholder="再次输入" style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }} />
          </label>
          <button type="button" className="btn-primary">更新密码</button>

          <h3 className="aos-text" style={{ fontSize: "0.9rem", marginTop: 24 }}>双因素认证 (2FA)</h3>
          <BpBanner tone="warn">
            ⚠️ 2FA 尚未启用。建议启用以增强账户安全。
          </BpBanner>
          <button type="button" className="btn" style={{ marginTop: 8 }}>启用 2FA</button>

          <h3 className="aos-text" style={{ fontSize: "0.9rem", marginTop: 24 }}>活跃会话</h3>
          <BpTable
            columns={["设备", "IP 地址", "最后活跃", ""]}
            rows={[
              ["MacBook Pro · Chrome", "192.168.1.100", "当前会话", <span key="1" className="muted">活跃</span>],
              ["iPhone · Safari", "10.0.0.50", "2 小时前", <button key="2" type="button" className="nav-link">注销</button>],
              ["Windows · Edge", "172.16.0.20", "昨天", <button key="3" type="button" className="nav-link">注销</button>],
            ]}
          />
        </div>
      )}

      {tab === "notifications" && (
        <div style={{ maxWidth: 600, padding: "16px 0" }}>
          <h3 className="aos-text" style={{ fontSize: "0.9rem" }}>通知渠道</h3>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <input type="checkbox" checked={notifEmail} onChange={(e) => setNotifEmail(e.target.checked)} />
            <span style={{ fontSize: "0.85rem" }}>邮件通知 (datong@aos.dev)</span>
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <input type="checkbox" checked={notifSlack} onChange={(e) => setNotifSlack(e.target.checked)} />
            <span style={{ fontSize: "0.85rem" }}>Slack 通知 (#aos-alerts)</span>
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <input type="checkbox" checked={notifWebhook} onChange={(e) => setNotifWebhook(e.target.checked)} />
            <span style={{ fontSize: "0.85rem" }}>Webhook 通知</span>
          </label>

          <h3 className="aos-text" style={{ fontSize: "0.9rem", marginTop: 24 }}>通知事件</h3>
          <BpTable
            columns={["事件", "邮件", "Slack", "Webhook"]}
            rows={[
              ["管道构建完成", "✓", "✓", "—"],
              ["管道构建失败", "✓", "✓", "✓"],
              ["数据同步异常", "✓", "—", "✓"],
              ["AIP Agent 上线", "—", "✓", "—"],
              ["安全告警", "✓", "✓", "✓"],
              ["系统维护通知", "✓", "—", "—"],
            ]}
          />
        </div>
      )}

      {tab === "tokens" && (
        <div style={{ padding: "16px 0" }}>
          <BpToolbar>
            <button type="button" className="btn-primary">+ 生成新 Token</button>
          </BpToolbar>
          <BpBanner tone="info">
            Token 仅在创建时显示一次，请妥善保存。已创建 {tokens.length} 个 Token。
          </BpBanner>
          <BpTable
            columns={["名称", "创建时间", "最后使用", "权限范围", ""]}
            rows={tokens.map((t) => [
              <span key="name" className="mono">{t.name}</span>,
              t.created,
              t.lastUsed,
              <span key="scope" className="mono" style={{ fontSize: "0.75rem" }}>{t.scope}</span>,
              <button key="del" type="button" className="nav-link" style={{ color: "#e53e3e" }}>吊销</button>,
            ])}
          />
        </div>
      )}
    </S2Chrome>
  );
}
