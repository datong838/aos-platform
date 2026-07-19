/** TWB.2 — 业务侧环境只读徽章（无 Promote） */
import { useEffect, useState } from "react";
import { probeApiHealth } from "../api/client";
import { getApiBase } from "../api/apiBase";
import { ENV_READONLY_HINT } from "../lib/productCopy";

export function EnvReadonlyBadge() {
  const [label, setLabel] = useState("探测中…");

  useEffect(() => {
    let cancelled = false;
    void probeApiHealth().then((r) => {
      if (cancelled) return;
      setLabel(r.ok ? "已连接" : "不可达");
    });
    function onBase() {
      setLabel("探测中…");
      void probeApiHealth().then((r) => setLabel(r.ok ? "已连接" : "不可达"));
    }
    window.addEventListener("aos-api-base-changed", onBase);
    return () => {
      cancelled = true;
      window.removeEventListener("aos-api-base-changed", onBase);
    };
  }, []);

  return (
    <span
      className="aos-env-badge"
      title={`${ENV_READONLY_HINT} · ${getApiBase()}`}
      data-env-readonly="1"
    >
      环境 · {label}
    </span>
  );
}
