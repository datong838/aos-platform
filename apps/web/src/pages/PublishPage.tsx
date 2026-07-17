import { useState } from "react";
import { PageChrome } from "../components/PageChrome";

const API_BASE = import.meta.env.VITE_AOS_API_BASE ?? "http://127.0.0.1:8080";

/** T1.7 — publish via POST /v1/modules/{id}/publish + Idempotency-Key. */
export function PublishPage() {
  const [msg, setMsg] = useState<string>("尚未点击");
  const [busy, setBusy] = useState(false);

  async function onPublish() {
    if (busy) return;
    setBusy(true);
    const key = `publish-${Date.now()}`;
    const headers = {
      Authorization: "Bearer dev",
      "X-Org-Id": "dev-org",
      "X-Project-Id": "dev-project",
      "Content-Type": "application/json",
      "Idempotency-Key": key,
    };
    try {
      const created = await fetch(`${API_BASE}/v1/modules`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          name: `Publish Shell ${key}`,
          entryPath: "/workshop/inbox",
        }),
      });
      const body1 = await created.json();
      const mid = body1.id as string;
      const once = await fetch(`${API_BASE}/v1/modules/${mid}/publish`, {
        method: "POST",
        headers,
        body: "{}",
      });
      const pub1 = await once.json();
      const twice = await fetch(`${API_BASE}/v1/modules/${mid}/publish`, {
        method: "POST",
        headers,
        body: "{}",
      });
      const pub2 = await twice.json();
      setMsg(
        pub2.idempotentReplay
          ? `发布幂等成功 · id=${mid} · ${pub1.publish?.status || "ACCEPTED"}`
          : `已发布 id=${mid} · ${pub1.publish?.status || "ok"}`,
      );
    } catch (e) {
      setMsg(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageChrome title="发布入口" lede="T1.7 · POST /v1/modules/{id}/publish · Apollo Lite Adapter">
      <button type="button" className="btn" disabled={busy} onClick={() => void onPublish()}>
        {busy ? "提交中…" : "发布 Module"}
      </button>
      <p className="aos-text">{msg}</p>
    </PageChrome>
  );
}
