import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";

/** Wave-5 Apollo Hub — fleet + spoke + asset. */
export function ApolloPage() {
  const [fleet, setFleet] = useState("");
  const [spoke, setSpoke] = useState("");
  const [cfg, setCfg] = useState("");
  const [bundle, setBundle] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const f = await apiGet<Record<string, unknown>>("/v1/apollo/fleet");
      const s = await apiGet<Record<string, unknown>>("/v1/apollo/spokes/local");
      const c = await apiGet<Record<string, unknown>>("/v1/apollo/config");
      setFleet(JSON.stringify(f, null, 2));
      setSpoke(JSON.stringify(s));
      setCfg(JSON.stringify(c));
    })().catch((e) => setErr(String(e.message || e)));
  }, []);

  async function pack() {
    const b = await apiPost<Record<string, unknown>>("/v1/apollo/assets", {
      hotfix: false,
      contents: ["WorkOrder"],
    });
    setBundle(JSON.stringify(b));
  }

  return (
    <PageChrome title="Hub 舰队" lede="对齐 apollo-hub · GET /v1/apollo/fleet · Spoke · Lite">
      <p className="muted">
        Spoke · <Link to="/apollo/spoke">/apollo/spoke</Link> · Release{" "}
        <Link to="/apollo/release">promote/recall</Link> · Full 运行时仍延期
      </p>
      {err && <p className="error">{err}</p>}
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Fleet
      </h2>
      <pre className="card">{fleet}</pre>
      <div className="card">Spoke local: {spoke}</div>
      <div className="card">Config: {cfg}</div>
      <button type="button" className="btn" onClick={() => void pack().catch((e) => setErr(String(e)))}>
        打包 Asset Bundle
      </button>
      {bundle && <pre className="card">{bundle}</pre>}
    </PageChrome>
  );
}
