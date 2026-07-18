import { useEffect, useState } from "react";
import { probeApiHealth } from "../api/client";

const POLL_MS = 12_000;

/** 76 / 38 §8 · 顶栏仅宕机告警；可达时静默（不与页内状态条重复） */
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
  if (ok) return null;
  return (
    <div className="api-status api-status-down" role="alert">
      aos-api 不可达 · {detail} · 浏览器控制台见 [aos-api] 日志
    </div>
  );
}
