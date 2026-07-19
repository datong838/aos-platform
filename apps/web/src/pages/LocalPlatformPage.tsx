/** TWB.3 / TWC.10 — 本机平台（Local-First）；禁止称 Apollo · UI-11 探活 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../components/PageChrome";
import { getApiBase } from "../api/apiBase";
import { probeApiHealth } from "../api/client";
import { LOCAL_PLATFORM_NAME } from "../lib/productCopy";
import { BpBanner } from "./s2/blueprintUi";

const DOCS_72 =
  "docs/palantier/20_tech/72-系统启停与健康检查手册.md";

type Probe = { ok: boolean; detail: string } | null;

export function LocalPlatformPage() {
  const base = getApiBase();
  const [probe, setProbe] = useState<Probe>(null);
  const [busy, setBusy] = useState(false);

  const redetect = useCallback(async () => {
    setBusy(true);
    try {
      const r = await probeApiHealth();
      setProbe(r);
      console.info("[aos-local-platform]", {
        event: "redetect",
        ok: r.ok,
        base,
      });
    } finally {
      setBusy(false);
    }
  }, [base]);

  useEffect(() => {
    void redetect();
  }, [redetect]);

  return (
    <PageChrome
      title={LOCAL_PLATFORM_NAME}
      lede="在本机拉起/探活 aos-api 与依赖 · 仍只经 aos-api，不直连引擎"
    >
      <BpBanner tone="info">
        产品名是「{LOCAL_PLATFORM_NAME}」，<strong>不是</strong> Apollo。Apollo
        属于运维交付面（侧栏可收分组）。
      </BpBanner>

      <div className="aos-local-platform-panel" data-ui="UI-11">
        <div className="aos-local-platform-row">
          <span
            className={
              probe?.ok
                ? "aos-local-platform-dot is-up"
                : probe
                  ? "aos-local-platform-dot is-down"
                  : "aos-local-platform-dot"
            }
            aria-hidden
          />
          <div>
            <strong>aos-api</strong>
            <div>
              <code>{base}</code>
              <span className="aos-muted">
                {" "}
                ·{" "}
                {probe == null
                  ? "检测中…"
                  : probe.ok
                    ? "可达"
                    : `不可达 · ${probe.detail}`}
              </span>
            </div>
          </div>
        </div>

        <div className="aos-local-platform-row">
          <span className="aos-local-platform-dot is-muted" aria-hidden />
          <div>
            <strong>依赖服务（PG / MinIO 等）</strong>
            <div className="aos-muted">
              摘要探活不在本页伪造；请按启停手册检查 compose / 端口。
            </div>
          </div>
        </div>

        <div className="aos-local-platform-actions">
          <button
            type="button"
            className="btn-nav"
            data-testid="local-platform-redetect"
            disabled={busy}
            onClick={() => void redetect()}
          >
            {busy ? "检测中…" : "重新检测"}
          </button>
          <a
            className="btn-nav"
            href={`../../${DOCS_72}`}
            data-testid="local-platform-docs72"
            onClick={(e) => {
              e.preventDefault();
              window.alert(
                `请在仓库中打开：\n${DOCS_72}\n\n（浏览器内不执行启停脚本）`,
              );
            }}
          >
            打开启停说明
          </a>
        </div>
      </div>

      <dl className="aos-local-platform-dl">
        <dt>业务入口</dt>
        <dd>
          <Link to="/">概览</Link> · <Link to="/workshop">应用列表</Link> ·{" "}
          <Link to="/workspace/members">工作区成员</Link>
        </dd>
        <dt>运维交付（可选）</dt>
        <dd>
          <Link to="/apollo">Hub 舰队</Link>
          <span className="aos-muted"> · 默认折叠在「运维交付」</span>
        </dd>
      </dl>
    </PageChrome>
  );
}
