/** TWB.3 / TWC.10 / 163 / 165 — 本机平台（Local-First）· 归运维交付 · 依赖自动拉起 · Hub 主动探活 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../components/PageChrome";
import { getApiBase } from "../api/apiBase";
import { apiGet, apiPost, probeApiHealth } from "../api/client";
import { LOCAL_PLATFORM_NAME, OPS_NAV_SECTION } from "../lib/productCopy";
import { BpBanner } from "./s2/blueprintUi";

type Probe = { ok: boolean; detail: string } | null;

type DepItem = {
  id: string;
  name: string;
  endpoint: string;
  ok: boolean;
};

type DepsState = {
  ok: boolean;
  items: DepItem[];
  action?: string;
  message?: string;
} | null;

type HubState = {
  ok: boolean;
  endpoint?: string;
  message?: string;
  hint?: string;
  latencyMs?: number;
} | null;

export function LocalPlatformPage() {
  const base = getApiBase();
  const [probe, setProbe] = useState<Probe>(null);
  const [deps, setDeps] = useState<DepsState>(null);
  const [hub, setHub] = useState<HubState>(null);
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

      let status = await apiGet<{
        ok: boolean;
        items: DepItem[];
        ensureAllowed?: boolean;
      }>("/v1/ops/local/deps");
      setDeps({
        ok: status.ok,
        items: status.items || [],
        action: status.ok ? "already_up" : "probe",
        message: status.ok ? "依赖已就绪" : "依赖未齐，正在自动拉起…",
      });

      if (!status.ok) {
        try {
          const ensured = await apiPost<{
            ok: boolean;
            items: DepItem[];
            action?: string;
            message?: string;
          }>("/v1/ops/local/deps/ensure", {});
          setDeps({
            ok: ensured.ok,
            items: ensured.items || [],
            action: ensured.action,
            message: ensured.message,
          });
          console.info("[aos-local-platform]", {
            event: "deps_ensure",
            ok: ensured.ok,
            action: ensured.action,
          });
        } catch (e) {
          const detail = e instanceof Error ? e.message : String(e);
          setDeps({
            ok: false,
            items: status.items || [],
            action: "failed",
            message: `自动拉起失败：${detail}`,
          });
        }
      }

      try {
        const hubRes = await apiGet<{
          ok: boolean;
          endpoint?: string;
          message?: string;
          hint?: string;
          latencyMs?: number;
        }>("/v1/ops/local/hub");
        setHub({
          ok: hubRes.ok,
          endpoint: hubRes.endpoint,
          message: hubRes.message,
          hint: hubRes.hint,
          latencyMs: hubRes.latencyMs,
        });
        console.info("[aos-local-platform]", {
          event: "hub_probe",
          ok: hubRes.ok,
          latencyMs: hubRes.latencyMs,
        });
      } catch (e) {
        const detail = e instanceof Error ? e.message : String(e);
        const apiOffline = /离线|无法连接|Failed to fetch|NetworkError/i.test(
          detail,
        );
        setHub({
          ok: false,
          message: `探活失败 · ${detail}`,
          hint: apiOffline
            ? "请先恢复 aos-api（顶栏「重试连接」或 bash scripts/demo/ensure-api.sh），再探 Docker Hub"
            : "改用 bash scripts/demo/start-local-native.sh（见启停手册 72 §1.3.1）",
        });
      }
    } catch (e) {
      const detail = e instanceof Error ? e.message : String(e);
      setDeps({
        ok: false,
        items: [],
        action: "failed",
        message: detail,
      });
    } finally {
      setBusy(false);
    }
  }, [base]);

  useEffect(() => {
    void redetect();
  }, [redetect]);

  const depsDotClass =
    deps == null
      ? "aos-local-platform-dot"
      : deps.ok
        ? "aos-local-platform-dot is-up"
        : busy
          ? "aos-local-platform-dot"
          : "aos-local-platform-dot is-down";

  const depsSummary =
    deps == null
      ? "检测中…"
      : deps.ok
        ? deps.message || "已就绪"
        : busy
          ? deps.message || "自动拉起中…"
          : deps.message || "未就绪";

  const hubDotClass =
    hub == null
      ? "aos-local-platform-dot"
      : hub.ok
        ? "aos-local-platform-dot is-up"
        : "aos-local-platform-dot is-down";

  return (
    <PageChrome
      title={LOCAL_PLATFORM_NAME}
      lede="Local-First：在本机探活 aos-api 与依赖 · 业务流量仍只经 aos-api，不直连引擎"
    >
      <BpBanner tone="info">
        「{LOCAL_PLATFORM_NAME}」属侧栏「{OPS_NAV_SECTION}」的正式运维探活能力（单机
        Local-First）。
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
          <span className={depsDotClass} aria-hidden />
          <div>
            <strong>依赖服务（PG / MinIO 等）</strong>
            <div className="aos-muted" data-testid="local-platform-deps-summary">
              {depsSummary}
            </div>
            {deps?.items?.length ? (
              <ul className="aos-local-platform-deps" data-testid="local-platform-deps-list">
                {deps.items.map((i) => (
                  <li key={i.id}>
                    {i.name} · <code>{i.endpoint}</code> ·{" "}
                    {i.ok ? "可达" : "不可达"}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>

        <div className="aos-local-platform-row" data-testid="local-platform-hub-row">
          <span className={hubDotClass} aria-hidden />
          <div>
            <strong>Docker Hub（镜像拉取）</strong>
            <div className="aos-muted" data-testid="local-platform-hub-summary">
              {hub == null
                ? "主动探活中…"
                : hub.ok
                  ? `${hub.message || "可达"}${
                      hub.latencyMs != null ? ` · ${hub.latencyMs}ms` : ""
                    }`
                  : hub.message || "不可达"}
            </div>
            {hub?.hint ? (
              <div className="aos-muted" data-testid="local-platform-hub-hint">
                {hub.hint}
              </div>
            ) : null}
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
          <Link
            className="btn-nav"
            to="/settings/ops-start-guide"
            data-testid="local-platform-ops-guide"
          >
            打开启停说明
          </Link>
        </div>
      </div>

      <dl className="aos-local-platform-dl">
        <dt>业务入口</dt>
        <dd>
          <Link to="/">概览</Link> · <Link to="/workshop">应用列表</Link> ·{" "}
          <Link to="/workspace/members">工作区成员</Link> ·{" "}
          <Link to="/org/membership">组织与加入</Link>
        </dd>
        <dt>{OPS_NAV_SECTION}（同组）</dt>
        <dd>
          <Link to="/settings/ops-start-guide">启停说明</Link>
          {" · "}
          <Link to="/apollo">Hub 舰队</Link>
          <span className="aos-muted"> · 默认可收</span>
        </dd>
      </dl>
    </PageChrome>
  );
}
