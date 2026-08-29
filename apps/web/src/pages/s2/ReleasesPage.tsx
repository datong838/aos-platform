import { Link } from "react-router-dom";
import { S2Chrome, useJsonGet } from "./shared";
import { BpLinkRow, BpToolbar } from "./blueprintUi";

export type ChannelStage = "rc" | "beta" | "stable";

export type ReleaseEntry = {
  id: string;
  channel: ChannelStage;
  version: string;
  released_at: number;
  status: string;
};

export type HotfixEntry = {
  id: string;
  version: string;
  base_version: string;
  description: string;
  status: string;
  target_spokes: string[];
};

export type RecallEntry = {
  id: string;
  from_version: string;
  to_version: string;
  reason: string;
  executed_at: number;
  status: string;
};

export function stageBadge(ch: ChannelStage) {
  switch (ch) {
    case "rc":
      return { label: "候选", cls: "bp-discover-badge bp-discover-badge-warn" };
    case "beta":
      return { label: "灰度", cls: "bp-discover-badge bp-discover-badge-warn" };
    case "stable":
      return { label: "稳定", cls: "bp-discover-badge bp-discover-badge-ok" };
  }
}

function releaseTime(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "时间未知";
  return new Date(value * 1000).toLocaleString("zh-CN", { hour12: false });
}

/** Release 通道：只消费当前控制面事实，不在客户端制造发布记录。 */
export function ReleasesPage() {
  const releasesResp = useJsonGet<{ items: ReleaseEntry[]; total: number }>("/api/v1/ops/releases");
  const hotfixResp = useJsonGet<{ hotfix: HotfixEntry | null }>("/api/v1/ops/releases/hotfix");
  const recallResp = useJsonGet<{ items: RecallEntry[]; total: number }>("/api/v1/ops/releases/recall");

  const releases = releasesResp.data?.items || [];
  const hotfixCandidate = hotfixResp.data?.hotfix;
  const hotfix = hotfixCandidate && !Array.isArray(hotfixCandidate) && hotfixCandidate.id
    ? hotfixCandidate
    : null;
  const recalls = recallResp.data?.items || [];
  const err = releasesResp.err || hotfixResp.err || recallResp.err;

  return (
    <S2Chrome
      title="Release 通道"
      lede="查看候选、灰度与稳定通道的当前发布事实；紧急变更必须先完成审批。"
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
        <Link to="/apollo" className="btn-nav">← Hub 舰队</Link>
        <Link to="/apollo/assets" className="btn-nav">资产包列表 →</Link>
      </BpToolbar>

      {err && <p className="error">当前发布控制面读取失败：{err}</p>}

      <section className="bp-domain bp-domain-apollo">
        <h2 className="bp-domain-heading">发布管道</h2>
        {releases.length === 0 ? (
          <p className="muted">当前没有可核验的发布记录</p>
        ) : (
          <div className="bp-kv-list">
            {releases.map((release) => {
              const badge = stageBadge(release.channel);
              return (
                <div key={release.id} className="bp-kv-row">
                  <div>
                    <div className="bp-kv-key">
                      <span className={badge.cls}>{badge.label}</span>{" "}
                      {release.version}
                    </div>
                    <div className="bp-kv-desc">发布时间：{releaseTime(release.released_at)}</div>
                  </div>
                  <span className="bp-kv-value">{release.status}</span>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="bp-domain bp-domain-apollo">
        <h2 className="bp-domain-heading">紧急发布</h2>
        {!hotfix ? (
          <p className="muted">当前没有已登记的紧急补丁</p>
        ) : (
          <div className="bp-banner bp-banner-warn">
            <strong>{hotfix.version}</strong> · 基于 {hotfix.base_version} · {hotfix.status}
            {hotfix.description && <p>{hotfix.description}</p>}
          </div>
        )}
        <p className="hint">紧急发布必须绑定已批准的变更单；本页不直接推送。</p>
        <Link to="/apollo/change" className="btn-nav">查看或创建变更审批</Link>
      </section>

      <section className="bp-domain bp-domain-apollo">
        <h2 className="bp-domain-heading">回滚记录</h2>
        {recalls.length === 0 ? (
          <p className="muted">当前没有可核验的回滚记录</p>
        ) : (
          <div className="bp-kv-list">
            {recalls.map((recall) => (
              <div key={recall.id} className="bp-kv-row">
                <div>
                  <div className="bp-kv-key">{recall.from_version} → {recall.to_version}</div>
                  <div className="bp-kv-desc">
                    {recall.reason || "未填写原因"} · {releaseTime(recall.executed_at)}
                  </div>
                </div>
                <span className="bp-kv-value">{recall.status}</span>
              </div>
            ))}
          </div>
        )}
        <p className="hint">回滚需从已批准的变更单进入，不在历史列表直接执行。</p>
      </section>

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
