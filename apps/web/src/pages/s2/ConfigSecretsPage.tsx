import { useState } from "react";
import { S2Chrome, useJsonGet } from "./shared";
import {
  BpToolbar,
  BpTable,
  BpKvList,
  BpBanner,
  BpMetricGrid,
} from "./blueprintUi";

/* ──────────────── Types ──────────────── */

interface ConfigOverride {
  key: string;
  value: string;
  sensitive: boolean;
  source: "global" | "env" | "spoke";
  desc?: string;
}

interface MaintenanceWindow {
  start: string;
  end: string;
  active: boolean;
  notes: string;
}

/* ──────────────── MOCK fallback ──────────────── */

const MOCK_CONFIG_OVERRIDES: ConfigOverride[] = [
  {
    key: "aip.model.default",
    value: "glm-4-flash",
    sensitive: false,
    source: "global",
    desc: "默认 LLM 模型路由",
  },
  {
    key: "db.connection.poolSize",
    value: "50",
    sensitive: false,
    source: "spoke",
    desc: "上海 Spoke 数据库连接池大小",
  },
  {
    key: "integration.apiKey",
    value: "sk-aip-xxxxxxxxxxxxxxxxxxxx",
    sensitive: true,
    source: "env",
    desc: "外部集成 API 密钥（Vault 引用）",
  },
];

const MOCK_MAINTENANCE_WINDOW: MaintenanceWindow = {
  start: "2026-07-28 02:00",
  end: "2026-07-28 04:00",
  active: false,
  notes: "计划内维护：升级 platform-core 至 2.14.1",
};

/* ──────────────── Page ──────────────── */

export function ConfigSecretsPage() {
  const cfgResp = useJsonGet<{ items: ConfigOverride[] } | ConfigOverride[]>(
    "/v1/spokes/spoke-prod-sh/config",
  );
  const mwResp = useJsonGet<MaintenanceWindow | null>(
    "/v1/spokes/spoke-prod-sh/maintenance-window",
  );

  const rawCfg = cfgResp.data;
  const overrides =
    rawCfg && Array.isArray(rawCfg) && rawCfg.length > 0
      ? rawCfg
      : MOCK_CONFIG_OVERRIDES;

  const mw =
    mwResp.data && (mwResp.data as MaintenanceWindow).start
      ? (mwResp.data as MaintenanceWindow)
      : MOCK_MAINTENANCE_WINDOW;

  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set());
  const [showEditModal, setShowEditModal] = useState(false);
  const [editKey, setEditKey] = useState("");
  const [editValue, setEditValue] = useState("");
  const [editSource, setEditSource] = useState("global");

  function toggleReveal(key: string) {
    const next = new Set(revealedKeys);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setRevealedKeys(next);
  }

  function openNewConfig() {
    setEditKey("");
    setEditValue("");
    setEditSource("global");
    setShowEditModal(true);
  }

  function openEditConfig(cfg: ConfigOverride) {
    setEditKey(cfg.key);
    setEditValue(cfg.value);
    setEditSource(cfg.source);
    setShowEditModal(true);
  }

  function saveConfig() {
    // In real impl, this would call apiPut
    setShowEditModal(false);
  }

  const sourceCounts = {
    global: overrides.filter((o) => o.source === "global").length,
    env: overrides.filter((o) => o.source === "env").length,
    spoke: overrides.filter((o) => o.source === "spoke").length,
    sensitive: overrides.filter((o) => o.sensitive).length,
  };

  return (
    <S2Chrome title="配置与密钥" lede="管理 Spoke 级别的配置覆盖项与敏感凭据，查看维护窗口">
      {/* Metrics */}
      <BpMetricGrid
        items={[
          { label: "配置项总数", value: String(overrides.length), tone: "ok" },
          { label: "全局配置", value: String(sourceCounts.global), tone: "muted" },
          { label: "环境变量", value: String(sourceCounts.env), tone: "muted" },
          { label: "Spoke 级", value: String(sourceCounts.spoke), tone: "muted" },
          { label: "敏感项", value: String(sourceCounts.sensitive), tone: "warn" },
        ]}
      />

      {/* Maintenance window */}
      <div style={{ marginTop: "1rem" }}>
        <h3 style={{ marginBottom: "0.5rem" }}>维护窗口</h3>
        <BpKvList
          rows={[
            { key: "开始时间", value: mw.start, mono: true },
            { key: "结束时间", value: mw.end, mono: true },
            {
              key: "状态",
              value: mw.active ? "进行中" : "未激活",
            },
            { key: "备注", value: mw.notes },
          ]}
        />
      </div>

      {/* Config overrides */}
      <div style={{ marginTop: "1rem" }}>
        <BpToolbar>
          <h3 style={{ margin: 0 }}>配置覆盖项</h3>
          <button
            type="button"
            onClick={openNewConfig}
            style={{
              marginLeft: "auto",
              padding: "0.35rem 1rem",
              borderRadius: 4,
              border: "1px solid #3b82f6",
              background: "#3b82f6",
              color: "#fff",
              cursor: "pointer",
              fontWeight: 600,
              fontSize: "0.8rem",
            }}
          >
            + 新增配置
          </button>
        </BpToolbar>

        <BpTable
          columns={["Key", "Value", "来源", "描述", "操作"]}
          rows={overrides.map((o) => [
            <span key="key" className="mono" style={{ fontWeight: 500 }}>
              {o.key}
            </span>,
            <span key="val" className="mono">
              {o.sensitive && !revealedKeys.has(o.key)
                ? "••••••••••••••••"
                : o.value}
            </span>,
            <span
              key="src"
              className={
                o.source === "global"
                  ? "status-ok"
                  : o.source === "env"
                    ? "status-warn"
                    : "muted"
              }
            >
              {o.source === "global"
                ? "全局"
                : o.source === "env"
                  ? "环境"
                  : "Spoke"}
            </span>,
            <span key="desc" className="muted" style={{ fontSize: "0.75rem" }}>
              {o.desc || "—"}
            </span>,
            <div key="actions" style={{ display: "flex", gap: "0.5rem" }}>
              {o.sensitive && (
                <button
                  type="button"
                  onClick={() => toggleReveal(o.key)}
                  style={{
                    border: "none",
                    background: "none",
                    cursor: "pointer",
                    color: "#3b82f6",
                    fontSize: "0.75rem",
                    padding: 0,
                  }}
                >
                  {revealedKeys.has(o.key) ? "隐藏" : "显示"}
                </button>
              )}
              <button
                type="button"
                onClick={() => openEditConfig(o)}
                style={{
                  border: "none",
                  background: "none",
                  cursor: "pointer",
                  color: "#3b82f6",
                  fontSize: "0.75rem",
                  padding: 0,
                }}
              >
                编辑
              </button>
            </div>,
          ])}
        />
      </div>

      <div style={{ marginTop: "0.75rem" }}>
        <BpBanner tone="warn">
          敏感配置（如 API Key、数据库密码）通过 Vault 引用注入，明文仅在调试模式下可显示。修改生产配置需先提交变更审批。
        </BpBanner>
      </div>

      {/* Edit modal */}
      {showEditModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setShowEditModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "#fff",
              borderRadius: 8,
              padding: "1.5rem",
              minWidth: 400,
              maxWidth: 500,
              boxShadow: "0 4px 20px rgba(0,0,0,0.15)",
            }}
          >
            <h3 style={{ marginBottom: "1rem" }}>
              {editKey ? "编辑配置" : "新增配置"}
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <label>
                <span className="muted" style={{ fontSize: "0.75rem" }}>
                  Key
                </span>
                <input
                  value={editKey}
                  onChange={(e) => setEditKey(e.target.value)}
                  placeholder="如 aip.model.default"
                  style={{
                    display: "block",
                    width: "100%",
                    padding: "0.4rem 0.6rem",
                    marginTop: 4,
                    borderRadius: 4,
                    border: "1px solid #d0d5dd",
                    fontFamily: "monospace",
                  }}
                />
              </label>
              <label>
                <span className="muted" style={{ fontSize: "0.75rem" }}>
                  Value
                </span>
                <input
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  placeholder="配置值"
                  style={{
                    display: "block",
                    width: "100%",
                    padding: "0.4rem 0.6rem",
                    marginTop: 4,
                    borderRadius: 4,
                    border: "1px solid #d0d5dd",
                    fontFamily: "monospace",
                  }}
                />
              </label>
              <label>
                <span className="muted" style={{ fontSize: "0.75rem" }}>
                  来源
                </span>
                <select
                  value={editSource}
                  onChange={(e) => setEditSource(e.target.value)}
                  style={{
                    display: "block",
                    width: "100%",
                    padding: "0.4rem 0.6rem",
                    marginTop: 4,
                    borderRadius: 4,
                    border: "1px solid #d0d5dd",
                  }}
                >
                  <option value="global">全局</option>
                  <option value="env">环境</option>
                  <option value="spoke">Spoke</option>
                </select>
              </label>
            </div>
            <div
              style={{
                marginTop: "1rem",
                display: "flex",
                gap: "0.5rem",
                justifyContent: "flex-end",
              }}
            >
              <button
                type="button"
                onClick={() => setShowEditModal(false)}
                style={{
                  padding: "0.4rem 1rem",
                  borderRadius: 4,
                  border: "1px solid #d0d5dd",
                  background: "#fff",
                  cursor: "pointer",
                }}
              >
                取消
              </button>
              <button
                type="button"
                onClick={saveConfig}
                style={{
                  padding: "0.4rem 1rem",
                  borderRadius: 4,
                  border: "none",
                  background: "#3b82f6",
                  color: "#fff",
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </S2Chrome>
  );
}
