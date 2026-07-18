import { useState } from "react";
import { Link } from "react-router-dom";
import { apiPost, S2Chrome, useJsonGet } from "./shared";
import {
  BpBanner,
  BpKvList,
  BpLinkRow,
  BpPropGrid,
  BpTable,
  BpToolbar,
} from "./blueprintUi";

type SpokeRow = {
  id: string;
  name?: string;
  kind?: string;
  channelId?: string;
  runtime?: string;
  status?: string;
  version?: string;
  heartbeatOk?: boolean;
  hub?: string;
};

/** 81 · 对齐 apollo-spoke.html */
export function ApolloSpokePage() {
  const list = useJsonGet<{ items: SpokeRow[] }>("/v1/apollo/spokes");
  const local = useJsonGet<SpokeRow>("/v1/apollo/spokes/local");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const detail = useJsonGet<SpokeRow>(
    selectedId ? `/v1/apollo/spokes/${encodeURIComponent(selectedId)}` : null,
  );

  const primary = local.data || list.data?.items?.[0];

  return (
    <S2Chrome title="Spoke 详情" lede="出站轮询 · Lite/FULL 形态 · Full 运行时仍延期">
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            list.reload();
            local.reload();
            if (selectedId) detail.reload();
          }}
        >
          刷新
        </button>
        <Link to="/apollo/release" className="muted">
          Release 通道
        </Link>
      </BpToolbar>
      {(list.err || local.err) && <p className="error">{list.err || local.err}</p>}

      {primary && (
        <>
          <h1 className="bp-object-title">{primary.name || primary.id}</h1>
          <p className="muted" style={{ fontSize: "0.875rem", marginBottom: "0.75rem" }}>
            {primary.kind || "lite"} · channel {primary.channelId || "—"} · {primary.status}
          </p>
        </>
      )}

      <div className="bp-apollo-callout">
        <strong>出站轮询（Outbound Polling）</strong>
        Spoke 主动拉取 Hub 变更队列；气隙环境无入站时仅此路径可用。Lite MVP · Full 运行时延期。
      </div>

      <div className="bp-domain bp-domain-apollo" style={{ marginBottom: "1rem" }}>
        <h2 style={{ fontSize: "0.875rem", margin: "0 0 0.5rem" }}>Spoke 形态</h2>
        <p className="muted" style={{ fontSize: "0.75rem" }}>
          当前：<strong>Lite Spoke</strong> · Full Spoke 目录骨架可用 · 完整运行时规划中
        </p>
        <BpPropGrid
          items={[
            { label: "Lite", value: "轻量代理 · 出站轮询" },
            { label: "Full", value: "完整运行时（延期）" },
          ]}
        />
      </div>

      <h2 className="bp-ws-section-title">Catalog</h2>
      <BpTable
        columns={["Spoke", "形态", "Channel", "Runtime", "状态", ""]}
        rows={(list.data?.items || []).map((s) => [
          s.name || s.id,
          s.kind || "—",
          s.channelId || "—",
          s.runtime || "—",
          s.status || "—",
          <button
            key={s.id}
            type="button"
            className="nav-link"
            onClick={() => setSelectedId(s.id)}
          >
            详情
          </button>,
        ])}
      />

      {(detail.data || primary) && (
        <>
          <h2 className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
            选中 Spoke
          </h2>
          <BpKvList
            rows={[
              { key: "id", value: (detail.data || primary)!.id, mono: true },
              { key: "version", desc: "SemVer", value: String((detail.data || primary)!.version || "—"), mono: true },
              { key: "heartbeat", value: (detail.data || primary)!.heartbeatOk ? "OK" : "—" },
              { key: "hub", value: String((detail.data || primary)!.hub || "dev-hub"), mono: true },
              { key: "runtime", value: String((detail.data || primary)!.runtime || "lite-deferred"), mono: true },
            ]}
          />
        </>
      )}

      <BpLinkRow
        links={[
          { to: "/apollo", label: "Hub 舰队" },
          { to: "/apollo/ferry", label: "Ferry 摆渡" },
        ]}
      />
    </S2Chrome>
  );
}

/** 81 · 对齐 apollo-config.html */
export function ApolloConfigPage() {
  const { data, err, reload } = useJsonGet<{
    vaultRefsOnly?: boolean;
    plaintextRejected?: boolean;
    secrets?: Record<string, string>;
  }>("/v1/apollo/config");

  return (
    <S2Chrome title="Config Override" lede="Spoke 级配置覆盖与维护窗口；密钥仅存 Vault/KMS 引用。">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <span className="muted">spoke-local-dev</span>
      </BpToolbar>
      {err && <p className="error">{err}</p>}

      <BpBanner tone="warn">
        <strong>维护窗口</strong> · 2026-07-20 22:00 — 2026-07-21 02:00 · 维护期内暂停非紧急 Plan
      </BpBanner>

      <h2 className="bp-ws-section-title">覆盖项 / 密钥引用</h2>
      <BpKvList
        rows={[
          {
            key: "vaultRefsOnly",
            desc: "禁明文密钥",
            value: data?.vaultRefsOnly ? "true" : "false",
            mono: true,
          },
          ...Object.entries(data?.secrets || {}).map(([k, v]) => ({
            key: k,
            desc: "Vault ref",
            value: v,
            mono: true,
          })),
        ]}
      />

      {data?.plaintextRejected && (
        <p className="muted" style={{ marginTop: "0.75rem" }}>
          PATCH 拒绝明文 secret · 须 <code>vault:</code> 前缀
        </p>
      )}
    </S2Chrome>
  );
}

type BundleRow = {
  bundleId: string;
  platformVersion?: string;
  contents?: string[];
  hotfix?: boolean;
  validated?: boolean;
};

/** 81 · 对齐 apollo-assets.html */
export function ApolloAssetsPage() {
  const [rows, setRows] = useState<BundleRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function pack() {
    setErr(null);
    try {
      const b = await apiPost<BundleRow>("/v1/apollo/assets", {
        hotfix: false,
        contents: ["WorkOrder"],
      });
      setRows((prev) => [b, ...prev]);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title="FDE Asset Bundle" lede="可交付资产版本化打包；绑定 Release Channel 同步推进。">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void pack()}>
          + 新建资产包
        </button>
        <Link to="/apollo/release" className="muted">
          Release 通道
        </Link>
      </BpToolbar>
      {err && <p className="error">{err}</p>}

      <BpTable
        columns={["资产包", "SemVer", "内容", "状态"]}
        rows={
          rows.length > 0
            ? rows.map((r) => [
                r.bundleId,
                r.platformVersion || "—",
                (r.contents || []).join(" · "),
                r.validated ? "已验证" : r.hotfix ? "hotfix" : "—",
              ])
            : [["—", "—", "点击「新建资产包」", "—"]]
        }
      />

      <BpLinkRow links={[{ to: "/apollo/ferry", label: "Ferry 摆渡" }]} />
    </S2Chrome>
  );
}
