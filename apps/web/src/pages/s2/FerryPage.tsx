import { useState } from "react";
import { S2Chrome, useJsonGet, apiPost } from "./shared";
import {
  BpToolbar,
  BpSplit,
  BpTable,
  BpKvList,
  BpBanner,
  BpStagePipeline,
  BpMetricGrid,
} from "./blueprintUi";

/* ──────────────── Types ──────────────── */

interface FerryBundle {
  id: string;
  name: string;
  size: string;
  signed: boolean;
  signable: boolean;
  contents: { component: string; version: string; type: string }[];
  signature: { algorithm: string; signedBy: string; signedAt: string; fingerprint: string };
  targetSpokes: string[];
}

interface FerrySubmitProgress {
  stage: string;
  message: string;
  progress: number;
}

/* ──────────────── MOCK fallback ──────────────── */

const MOCK_FERRY_BUNDLES: FerryBundle[] = [
  {
    id: "bundle-apollo-core-2.14.1",
    name: "apollo-core-2.14.1",
    size: "248 MB",
    signed: true,
    signable: true,
    contents: [
      { component: "platform-core", version: "2.14.1", type: "runtime" },
      { component: "ontology-engine", version: "2.14.1", type: "runtime" },
      { component: "pipeline-runner", version: "2.14.0", type: "runtime" },
      { component: "aip-gateway", version: "2.14.1", type: "service" },
    ],
    signature: {
      algorithm: "cosign-ed25519",
      signedBy: "release-bot@aos-platform",
      signedAt: "2026-07-20T03:15:00Z",
      fingerprint: "sha256:a1b2c3d4e5f6...",
    },
    targetSpokes: ["spoke-prod-sh", "spoke-prod-bj", "spoke-staging-gz"],
  },
  {
    id: "bundle-fde-repair-1.8.0-rc.2",
    name: "fde-维修派单-1.8.0-rc.2",
    size: "87 MB",
    signed: false,
    signable: true,
    contents: [
      { component: "fde-repair-workshop", version: "1.8.0-rc.2", type: "module" },
      { component: "fde-repair-rules", version: "1.8.0-rc.2", type: "ruleset" },
      { component: "dispatch-widget", version: "1.5.0", type: "widget" },
    ],
    signature: {
      algorithm: "—",
      signedBy: "—",
      signedAt: "—",
      fingerprint: "—",
    },
    targetSpokes: ["spoke-staging-gz", "spoke-prod-sh"],
  },
];

/* ──────────────── Page ──────────────── */

export function FerryPage() {
  const bundlesResp = useJsonGet<{ items: FerryBundle[] } | FerryBundle[]>("/v1/ferry/bundles");
  const rawBundles = bundlesResp.data;
  const bundles =
    rawBundles && Array.isArray(rawBundles)
      ? rawBundles.length > 0
        ? rawBundles
        : MOCK_FERRY_BUNDLES
      : MOCK_FERRY_BUNDLES;

  const [selectedId, setSelectedId] = useState<string>("");
  const [targetSpoke, setTargetSpoke] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState<FerrySubmitProgress | null>(null);

  const selected = bundles.find((b) => b.id === selectedId) || bundles[0] || null;

  function selectBundle(id: string) {
    setSelectedId(id);
    const b = bundles.find((x) => x.id === id);
    if (b && b.targetSpokes.length > 0) setTargetSpoke(b.targetSpokes[0]);
  }

  async function submitFerry() {
    if (!selected || !targetSpoke) return;
    setSubmitting(true);
    setProgress({ stage: "export", message: "正在导出介质…", progress: 0.2 });
    try {
      await apiPost("/v1/ferry/submit", { bundleId: selected.id, targetSpoke });
      setProgress({ stage: "done", message: `已提交到 ${targetSpoke}`, progress: 1 });
    } catch {
      setProgress({ stage: "error", message: "提交失败", progress: 1 });
    } finally {
      setSubmitting(false);
    }
  }

  const ferryStages = selected
    ? [
        {
          step: "①",
          title: "选择 Bundle",
          subtitle: selected.name,
          status: "done",
          tone: "done" as const,
        },
        {
          step: "②",
          title: "校验签名",
          subtitle: selected.signed ? "已签名 ✓" : "未签名",
          status: selected.signed ? "已校验" : "待签名",
          tone: selected.signed ? ("done" as const) : ("active" as const),
        },
        {
          step: "③",
          title: "导出介质",
          subtitle: selected.size,
          status: submitting ? "导出中…" : "待导出",
          tone: submitting ? ("active" as const) : ("wait" as const),
        },
        {
          step: "④",
          title: "目标 Spoke 导入",
          subtitle: targetSpoke || "未选择",
          status: progress?.stage === "done" ? "已完成" : "待执行",
          tone: progress?.stage === "done" ? ("done" as const) : ("wait" as const),
        },
      ]
    : [];

  return (
    <S2Chrome title="Ferry 摆渡" lede="管理 Bundle 从 Hub 到 Spoke 的跨网 Ferry 导出与导入流程">
      {/* Step indicator */}
      <BpStagePipeline stages={ferryStages} />

      {selected && !selected.signed && (
        <div style={{ marginTop: "0.75rem" }}>
          <BpBanner tone="warn">
            该 Bundle 尚未签名。建议在 Ferry 前通过 cosign 完成签名，确保目标 Spoke 可验证完整性。
          </BpBanner>
        </div>
      )}

      <div style={{ marginTop: "0.75rem" }}>
        <BpSplit
          left={
            <div>
              <BpToolbar>
                <span className="muted" style={{ fontSize: "0.75rem" }}>
                  可 Ferry 的 Bundle（{bundles.length}）
                </span>
              </BpToolbar>
              <BpTable
                columns={["", "Bundle 名称", "大小", "签名", "可签名"]}
                rows={bundles.map((b) => {
                  const isSel = (selected?.id || "") === b.id;
                  return [
                    <input
                      key="radio"
                      type="radio"
                      checked={isSel}
                      onChange={() => selectBundle(b.id)}
                    />,
                    <span key="name" style={{ fontWeight: isSel ? 600 : 400 }}>
                      {b.name}
                    </span>,
                    <span key="size" className="mono">
                      {b.size}
                    </span>,
                    <span
                      key="signed"
                      className={b.signed ? "status-ok" : "status-warn"}
                    >
                      {b.signed ? "✓ 已签名" : "未签名"}
                    </span>,
                    <span key="signable" className="muted">
                      {b.signable ? "是" : "—"}
                    </span>,
                  ];
                })}
              />
            </div>
          }
          right={
            selected ? (
              <div>
                <h3 style={{ marginBottom: "0.5rem" }}>Bundle 详情</h3>
                <BpKvList
                  rows={[
                    { key: "名称", value: selected.name },
                    { key: "大小", value: selected.size, mono: true },
                    {
                      key: "签名状态",
                      value: selected.signed ? "已签名 ✓" : "未签名",
                    },
                    { key: "签名算法", value: selected.signature.algorithm, mono: true },
                    { key: "签名者", value: selected.signature.signedBy, mono: true },
                    { key: "签名时间", value: selected.signature.signedAt, mono: true },
                    {
                      key: "指纹",
                      value: selected.signature.fingerprint,
                      mono: true,
                    },
                  ]}
                />

                <h4 style={{ marginTop: "1rem", marginBottom: "0.5rem" }}>内容清单</h4>
                <BpTable
                  columns={["组件", "版本", "类型"]}
                  rows={selected.contents.map((c) => [
                    <span key="c">{c.component}</span>,
                    <span key="v" className="mono">
                      {c.version}
                    </span>,
                    <span key="t" className="muted">
                      {c.type}
                    </span>,
                  ])}
                />

                <h4 style={{ marginTop: "1rem", marginBottom: "0.5rem" }}>
                  目标 Spoke
                </h4>
                <select
                  value={targetSpoke}
                  onChange={(e) => setTargetSpoke(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "0.4rem 0.6rem",
                    borderRadius: 4,
                    border: "1px solid var(--border-color, #d0d5dd)",
                  }}
                >
                  {selected.targetSpokes.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="muted">请选择左侧的 Bundle</div>
            )
          }
        />
      </div>

      {/* Bottom: Ferry submit + progress */}
      <div
        style={{
          marginTop: "1rem",
          padding: "0.75rem 1rem",
          borderTop: "1px solid var(--border-color, #e0e0e0)",
          display: "flex",
          alignItems: "center",
          gap: "1rem",
          flexWrap: "wrap",
        }}
      >
        <button
          type="button"
          className="btn-primary"
          disabled={!selected || !targetSpoke || submitting}
          onClick={submitFerry}
          style={{
            padding: "0.5rem 1.5rem",
            borderRadius: 4,
            border: "none",
            cursor: !selected || !targetSpoke || submitting ? "not-allowed" : "pointer",
            fontWeight: 600,
          }}
        >
          {submitting ? "Ferry 进行中…" : "Ferry 提交"}
        </button>
        {progress && (
          <div style={{ flex: 1, minWidth: 200 }}>
            <div className="muted" style={{ fontSize: "0.75rem", marginBottom: 4 }}>
              {progress.message}
            </div>
            <div
              style={{
                height: 6,
                borderRadius: 3,
                background: "#e0e0e0",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${Math.round(progress.progress * 100)}%`,
                  height: "100%",
                  background: progress.stage === "error" ? "#e74c3c" : "#3b82f6",
                  transition: "width 0.3s",
                }}
              />
            </div>
          </div>
        )}
      </div>

      <div style={{ marginTop: "1rem" }}>
        <BpMetricGrid
          items={[
            {
              label: "可用 Bundle",
              value: String(bundles.length),
              tone: "ok",
            },
            {
              label: "已签名",
              value: String(bundles.filter((b) => b.signed).length),
              tone: "ok",
            },
            {
              label: "待签名",
              value: String(bundles.filter((b) => !b.signed && b.signable).length),
              tone: "warn",
            },
            {
              label: "目标 Spoke 总数",
              value: String(
                new Set(bundles.flatMap((b) => b.targetSpokes)).size,
              ),
              tone: "muted",
            },
          ]}
        />
      </div>
    </S2Chrome>
  );
}
