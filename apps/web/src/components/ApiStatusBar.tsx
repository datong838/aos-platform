import { useEffect, useState } from "react";
import { API_BASE, probeApiHealth } from "../api/client";

const POLL_MS = 12_000;

/** 76 · 顶栏 API 可达性；宕机时指向日志与 ensure-api */
export function ApiStatusBar() {
  const [ok, setOk] = useState<boolean | null>(null);
  const [detail, setDetail] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      const r = await probeApiHealth();
      if (!cancelled) {
        setOk(r.ok);
        setDetail(r.detail);
      }
    }
    void tick();
    const id = window.setInterval(() => void tick(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (ok === null) return null;
  if (ok) {
    return (
      <div className="api-status api-status-ok" role="status">
        API {API_BASE.replace(/^https?:\/\//, "")} · 可达
      </div>
    );
  }
  return (
    <div className="api-status api-status-down" role="alert">
      aos-api 不可达 · {detail} · 浏览器控制台见 [aos-api] 日志
    </div>
  );
}
