import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";

/** Wave-C Capability — Job → MediaSet rid (TC.4 light). */
export function CapabilityPage() {
  const [out, setOut] = useState("");
  const [mediaRid, setMediaRid] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function run() {
    setErr(null);
    try {
      await apiPost("/v1/aip/capabilities", {
        id: "video-job",
        kind: "job",
      });
      const job = await apiPost<{
        jobId: string;
        artifact?: { mediaRid?: string; rid?: string };
      }>("/v1/aip/capabilities/video-job/invoke", {
        kind: "job",
        input: { clip: "demo" },
      });
      const rid = job.artifact?.mediaRid || job.artifact?.rid || null;
      setMediaRid(rid);
      setOut(JSON.stringify(job, null, 2));
      if (rid) {
        const media = await apiGet(`/v1/media-sets/${encodeURIComponent(rid)}`);
        setOut((prev) => `${prev}\n\n--- media ---\n${JSON.stringify(media, null, 2)}`);
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  return (
    <PageChrome title="重能力接入" lede="TC.* · Facade 禁 UI 直连 SDK · Job 产物挂 MediaSet">
      <button type="button" className="btn" onClick={() => void run()}>
        登记并提交 Job
      </button>
      {mediaRid && (
        <p className="aos-text">
          产物 MediaSet：<code>{mediaRid}</code> ·{" "}
          <Link to="/data/media-sets">媒体集</Link>
        </p>
      )}
      {err && <p className="error">{err}</p>}
      {out && <pre className="card">{out}</pre>}
    </PageChrome>
  );
}
