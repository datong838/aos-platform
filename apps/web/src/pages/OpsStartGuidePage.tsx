/** 167 — 启停说明端面（按 20a / 72 四版 · 运维交付） */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../components/PageChrome";
import { LOCAL_PLATFORM_NAME, OPS_NAV_SECTION } from "../lib/productCopy";
import {
  OPS_GUIDE_TIERS,
  type OpsGuideTierId,
} from "../lib/opsStartGuideContent";
import { BpBanner } from "./s2/blueprintUi";

export function OpsStartGuidePage() {
  const [tierId, setTierId] = useState<OpsGuideTierId>("local");
  const tier = useMemo(
    () => OPS_GUIDE_TIERS.find((t) => t.id === tierId) || OPS_GUIDE_TIERS[0],
    [tierId],
  );

  return (
    <PageChrome
      title="启停说明"
      lede="按部署形态分档 · 与 20a / 72 对齐 · 无需翻仓库文档"
    >
      <BpBanner tone="info">
        属侧栏「{OPS_NAV_SECTION}」。工程细则真源仍为手册 72；本页为可操作摘要。依赖探活见「
        {LOCAL_PLATFORM_NAME}」。
      </BpBanner>

      <div className="aos-ops-guide-tabs" role="tablist" aria-label="部署分档">
        {OPS_GUIDE_TIERS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={t.id === tierId}
            className={
              t.id === tierId ? "btn-nav is-selected" : "btn-nav"
            }
            data-testid={`ops-guide-tab-${t.id}`}
            onClick={() => setTierId(t.id)}
          >
            {t.title}
          </button>
        ))}
      </div>

      <article className="aos-ops-guide-panel" data-testid="ops-guide-panel">
        <h3 className="aos-h3">{tier.title}</h3>
        <p>
          <strong>对齐 20a：</strong>
          {tier.align20a}
        </p>
        <p>
          <strong>谁用：</strong>
          {tier.who}
        </p>
        <p>
          <strong>拓扑：</strong>
          {tier.topology}
        </p>
        <p>
          <strong>适用：</strong>
          {tier.apply}
        </p>
        {tier.honest ? (
          <p className="aos-muted">
            <strong>诚实边界：</strong>
            {tier.honest}
          </p>
        ) : null}

        <h4 className="aos-h3">启动</h4>
        <ul>
          {tier.start.map((line) => (
            <li key={line}>
              <code>{line}</code>
            </li>
          ))}
        </ul>

        <h4 className="aos-h3">停止</h4>
        <ul>
          {tier.stop.map((line) => (
            <li key={line}>
              <code>{line}</code>
            </li>
          ))}
        </ul>

        <h4 className="aos-h3">健康</h4>
        <ul>
          {tier.health.map((line) => (
            <li key={line}>
              <code>{line}</code>
            </li>
          ))}
        </ul>

        {tier.ports?.length ? (
          <>
            <h4 className="aos-h3">默认端口（单机）</h4>
            <table className="aos-table">
              <thead>
                <tr>
                  <th>组件</th>
                  <th>地址</th>
                </tr>
              </thead>
              <tbody>
                {tier.ports.map((p) => (
                  <tr key={p.name}>
                    <td>{p.name}</td>
                    <td>
                      <code>{p.addr}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : null}
      </article>

      <p className="aos-muted" style={{ marginTop: "1rem" }}>
        <Link to="/settings/local-platform">{LOCAL_PLATFORM_NAME}</Link>
        {" · "}
        <Link to="/apollo">Hub 舰队</Link>
      </p>
    </PageChrome>
  );
}
