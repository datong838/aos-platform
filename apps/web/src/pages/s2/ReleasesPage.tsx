import { Link } from "react-router-dom";
import { S2Chrome, useJsonGet } from "./shared";
import { BpBanner, BpLinkRow, BpToolbar } from "./blueprintUi";

type ChannelStage = "rc" | "beta" | "stable";

type ReleaseEntry = {
  channel: ChannelStage;
  version: string;
  spokeCount: number;
  releasedAt: string;
  pushPercent: number;
  isCurrent?: boolean;
};

type HotfixEntry = {
  patchVersion: string;
  cveNumber: string;
  description: string;
  baseVersion: string;
};

type RecallEntry = {
  fromVersion: string;
  toVersion: string;
  reason: string;
  appliedAt?: string;
};

type ReleasesData = {
  stages: ReleaseEntry[];
  hotfix: HotfixEntry[];
  recalls: RecallEntry[];
};

const MOCK_RELEASES: ReleasesData = {
  stages: [
    {
      channel: "rc",
      version: "2.15.0-rc.5",
      spokeCount: 2,
      releasedAt: "2026-07-25 14:30",
      pushPercent: 20,
    },
    {
      channel: "beta",
      version: "2.14.2-beta.1",
      spokeCount: 1,
      releasedAt: "2026-07-24 10:00",
      pushPercent: 40,
      isCurrent: true,
    },
    {
      channel: "stable",
      version: "2.14.1",
      spokeCount: 4,
      releasedAt: "2026-07-20 08:00",
      pushPercent: 100,
    },
  ],
  hotfix: [
    {
      patchVersion: "2.14.1-hotfix.2",
      cveNumber: "CVE-2026-1842",
      description: "修复 auth middleware token 校验绕过",
      baseVersion: "2.14.1",
    },
  ],
  recalls: [
    {
      fromVersion: "2.14.1",
      toVersion: "2.13.8",
      reason: "API 兼容性降级 · 下游 Agent 适配未就绪",
    },
  ],
};

function stageBadge(ch: ChannelStage) {
  switch (ch) {
    case "rc":
      return { label: "rc", cls: "bp-discover-badge bp-discover-badge-warn" };
    case "beta":
      return { label: "beta", cls: "bp-discover-badge bp-discover-badge-warn" };
    case "stable":
      return { label: "stable", cls: "bp-discover-badge bp-discover-badge-ok" };
  }
}

function stageCardStyle(ch: ChannelStage, isCurrent?: boolean) {
  const base: React.CSSProperties = {
    borderRadius: "0.5rem",
    padding: "1rem",
    textAlign: "center",
    flex: 1,
    minWidth: 100,
  };
  switch (ch) {
    case "rc":
      return {
        ...base,
        background: "var(--bg-muted, #f0f2f5)",
        border: "1px solid var(--border-muted, #d1d5db)",
      };
    case "beta":
      return {
        ...base,
        background: "var(--bg-yellow, #fef9c3)",
        border: "1px solid var(--border-yellow, #fde047)",
        boxShadow: "0 0 0 1px #fbbf24",
      };
    case "stable":
      return {
        ...base,
        background: "var(--bg-green, #dcfce7)",
        border: "1px solid var(--border-green, #86efac)",
      };
  }
}

/** Release 通道 */
export function ReleasesPage() {
  const releasesResp = useJsonGet<ReleasesData>("/v1/releases");
  const hotfixResp = useJsonGet<{ items: HotfixEntry[] }>("/v1/releases/hotfix");
  const recallResp = useJsonGet<{ items: RecallEntry[] }>("/v1/releases/recall");

  const releases = releasesResp.data?.stages?.length ? releasesResp.data : MOCK_RELEASES;
  const hotfixes = hotfixResp.data?.items?.length ? hotfixResp.data.items : MOCK_RELEASES.hotfix;
  const recalls = recallResp.data?.items?.length ? recallResp.data.items : MOCK_RELEASES.recalls;
  const err = releasesResp.err || hotfixResp.err || recallResp.err;

  return (
    <S2Chrome
      title="Release Channel 管道"
      lede="资产包沿 rc → beta → stable 推进；支持紧急 hotfix 旁路通道。"
    >
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            releasesResp.reload();
            hotfixResp.reload();
            recallResp.reload();
          }}
        >
          刷新
        </button>
        <Link to="/apollo" className="btn-nav">
          ← Hub 舰队
        </Link>
        <Link to="/apollo/assets" className="btn-nav">
          资产包列表 →
        </Link>
      </BpToolbar>

      {err && <p className="error">{err}</p>}

      {/* Pipeline stages */}
      <section className="bp-domain bp-domain-apollo">
        <h2 className="bp-domain-heading">发布管道</h2>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 0,
            flexWrap: "wrap",
          }}
        >
          {releases.stages.map((s, i) => (
            <div key={s.channel} style={{ display: "flex", alignItems: "center", gap: 0 }}>
              <div style={stageCardStyle(s.channel, s.isCurrent)}>
                <div className="uppercase muted" style={{ fontSize: "0.625rem" }}>
                  {s.channel}
                  {s.isCurrent ? " · 当前" : ""}
                </div>
                <div style={{ fontWeight: 500, fontSize: "0.875rem", marginTop: 4 }}>
                  {s.version}
                </div>
                <div className="muted" style={{ fontSize: "0.625rem", marginTop: 4 }}>
                  {s.spokeCount} Spoke
                </div>
              </div>
              {i < releases.stages.length - 1 && (
                <div
                  style={{
                    flexShrink: 0,
                    padding: "0 0.5rem",
                    color: "var(--status-ok, #16a34a)",
                    fontSize: "1.25rem",
                    fontWeight: 600,
                  }}
                >
                  →
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Stage detail table */}
        <div
          className="bp-kv-list"
          style={{ marginTop: "1rem" }}
        >
          {releases.stages.map((s) => {
            const badge = stageBadge(s.channel);
            return (
              <div key={s.channel} className="bp-kv-row">
                <div>
                  <div className="bp-kv-key">
                    <span className={badge.cls}>{badge.label}</span>{" "}
                    {s.version}
                  </div>
                  <div className="bp-kv-desc">
                    发布时间: {s.releasedAt} · 推送 {s.pushPercent}% ·{" "}
                    {s.spokeCount} Spoke
                  </div>
                </div>
                <span
                  className={
                    s.channel === "stable"
                      ? "bp-kv-value"
                      : "bp-kv-value bp-prop-muted"
                  }
                  style={s.isCurrent ? { color: "var(--status-ok, #16a34a)" } : undefined}
                >
                  {s.isCurrent ? "● 当前通道" : s.channel === "stable" ? "● 全量" : "● 灰度中"}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* Hotfix */}
      <section className="bp-domain bp-domain-apollo" style={{ borderColor: "var(--border-red, #fca5a5)" }}>
        <h2 className="bp-domain-heading">Hotfix / 紧急发布</h2>
        <p className="hint">旁路 beta，直达选定 Spoke · 须变更审批</p>

        {hotfixes.length === 0 && (
          <p className="muted">暂无活跃 hotfix</p>
        )}

        {hotfixes.map((hf) => (
          <div key={hf.patchVersion} className="bp-banner bp-banner-warn">
            <div style={{ fontWeight: 500, marginBottom: 4 }}>
              补丁包{" "}
              <code style={{ color: "var(--status-err, #dc2626)" }}>
                {hf.patchVersion}
              </code>{" "}
              · {hf.cveNumber} {hf.description}
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
              <button
                type="button"
                className="btn"
                style={{
                  background: "var(--bg-red, #fecaca)",
                  border: "1px solid var(--border-red, #fca5a5)",
                  color: "var(--status-err, #dc2626)",
                  fontSize: "0.75rem",
                }}
                onClick={() => {
                  alert(`已触发推送 ${hf.patchVersion}`);
                }}
              >
                推送到紧急通道
              </button>
              <Link
                to="/apollo/change"
                className="btn-nav"
                style={{ fontSize: "0.75rem" }}
              >
                查看审批单
              </Link>
            </div>
          </div>
        ))}
      </section>

      {/* Recall */}
      <section className="bp-domain bp-domain-apollo">
        <h2 className="bp-domain-heading">Recall 回滚</h2>
        <p className="hint">将 stable 通道回退至上一已知良好版本。</p>

        {recalls.length === 0 ? (
          <p className="muted">暂无回滚记录</p>
        ) : (
          recalls.map((r, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 8,
                border: "1px solid var(--border-muted, #d1d5db)",
                borderRadius: "0.5rem",
                padding: "0.75rem 1rem",
                marginTop: 8,
              }}
            >
              <div style={{ fontSize: "0.875rem" }}>
                <span className="muted">当前 stable</span>{" "}
                <code>{r.fromVersion}</code>
                <span style={{ margin: "0 0.5rem", color: "var(--fg-muted, #9ca3af)" }}>
                  →
                </span>
                <span style={{ color: "var(--status-ok, #16a34a)" }}>
                  <code>{r.toVersion}</code>
                </span>
              </div>
              <div className="muted" style={{ fontSize: "0.75rem" }}>
                {r.reason}
              </div>
              <button
                type="button"
                className="btn"
                style={{
                  border: "1px solid var(--border-red, #fca5a5)",
                  color: "var(--status-err, #dc2626)",
                  fontSize: "0.75rem",
                }}
                onClick={() => {
                  alert(`Recall 已触发: ${r.fromVersion} → ${r.toVersion}`);
                }}
              >
                执行 Recall
              </button>
            </div>
          ))
        )}
      </section>

      {/* Recall history table */}
      {recalls.length > 0 && (
        <section className="bp-domain bp-domain-apollo">
          <h2 className="bp-domain-heading">回滚历史</h2>
          <div className="bp-kv-list">
            {recalls.map((r, i) => (
              <div key={i} className="bp-kv-row">
                <div>
                  <div className="bp-kv-key">
                    {r.fromVersion} → {r.toVersion}
                  </div>
                  <div className="bp-kv-desc">{r.reason}</div>
                </div>
                <span className="bp-kv-value">
                  {r.appliedAt || "待执行"}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      <BpLinkRow
        links={[
          { to: "/apollo", label: "← Hub 舰队" },
          { to: "/apollo/ferry", label: "Ferry 摆渡 →" },
          { to: "/apollo/assets", label: "资产包列表 →" },
        ]}
      />
    </S2Chrome>
  );
}
