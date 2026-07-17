import { useState } from "react";
import { apiPost, JsonBlock, S2Chrome, useJsonGet } from "./shared";

export function ApolloSpokePage() {
  const list = useJsonGet<{ items: { id: string; kind?: string; channelId?: string; runtime?: string; status?: string }[] }>(
    "/v1/apollo/spokes",
  );
  const { data, err, reload } = useJsonGet<Record<string, unknown>>("/v1/apollo/spokes/local");
  const byId = useJsonGet<Record<string, unknown>>("/v1/apollo/spokes/lite");
  return (
    <S2Chrome title="Spoke 详情" lede="对齐 apollo-spoke · 目录含 lite+full stub（Full 运行时仍延期）">
      <button
        type="button"
        className="btn"
        onClick={() => {
          list.reload();
          reload();
          byId.reload();
        }}
      >
        刷新
      </button>
      {(err || byId.err || list.err) && <p className="error">{err || byId.err || list.err}</p>}
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Catalog
      </h2>
      <ul className="card-list">
        {(list.data?.items || []).map((s) => (
          <li key={s.id} className="card">
            <strong>{s.id}</strong>{" "}
            <span className="muted">
              {s.kind} · channel={s.channelId} · {s.status}
              {s.runtime ? ` · runtime=${s.runtime}` : ""}
            </span>
          </li>
        ))}
      </ul>
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        local
      </h2>
      <JsonBlock value={data} />
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        spokes/lite
      </h2>
      <JsonBlock value={byId.data} />
    </S2Chrome>
  );
}

export function ApolloConfigPage() {
  const { data, err, reload } = useJsonGet<Record<string, unknown>>("/v1/apollo/config");
  return (
    <S2Chrome title="配置与密钥" lede="对齐 apollo-config · 禁密钥明文（Vault ref）">
      <button type="button" className="btn" onClick={() => reload()}>
        刷新
      </button>
      {err && <p className="error">{err}</p>}
      <JsonBlock value={data} />
    </S2Chrome>
  );
}

export function ApolloAssetsPage() {
  const [bundle, setBundle] = useState<unknown>(null);
  const [err, setErr] = useState<string | null>(null);

  async function pack() {
    setErr(null);
    try {
      const b = await apiPost("/v1/apollo/assets", {
        hotfix: false,
        contents: ["WorkOrder"],
      });
      setBundle(b);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title="FDE 资产包" lede="对齐 apollo-assets · Asset Bundle">
      <button type="button" className="btn" onClick={() => void pack()}>
        打包 Asset Bundle
      </button>
      {err && <p className="error">{err}</p>}
      {bundle != null && <JsonBlock value={bundle} />}
    </S2Chrome>
  );
}
