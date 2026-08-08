import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, apiPut, apiDelete } from "../../api/client";
import { PageChrome } from "../../components/PageChrome";
import { BpDebugPanel } from "./blueprintUi";

export function JsonBlock({ value }: { value: unknown }) {
  return <BpDebugPanel value={value} title="完整 JSON" />;
}

export function useJsonGet<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(path));

  function reload() {
    if (!path) return;
    setLoading(true);
    setErr(null);
    apiGet<T>(path)
      .then(setData)
      .catch((e) => setErr(String((e as Error).message || e)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- path-keyed
  }, [path]);

  return { data, err, loading, reload, setData, setErr };
}

export function S2Chrome({
  title,
  lede,
  children,
}: {
  title: string;
  lede: string;
  children: ReactNode;
}) {
  return (
    <PageChrome title={title} lede={lede}>
      {children}
    </PageChrome>
  );
}

const PIPELINE_WORKFLOW_STEPS = [
  { key: "build", title: "管道构建", to: "/data/pipelines" },
  { key: "proposal", title: "管道提案", to: "/data/pipeline-proposals" },
  { key: "schedule", title: "计划编辑器", to: "/data/schedules" },
  { key: "builds", title: "搭建", to: "/data/builds" },
  { key: "dataset", title: "数据集预览", to: "/data/datasets" },
] as const;

export function PipelineWorkflowStepper({ current }: { current: number }) {
  const clamped = Math.max(0, Math.min(current, PIPELINE_WORKFLOW_STEPS.length - 1));
  return (
    <nav className="pw-stepper" aria-label="管道工作流">
      {PIPELINE_WORKFLOW_STEPS.map((step, i) => {
        const state = i < clamped ? "done" : i === clamped ? "current" : "pending";
        return (
          <Link
            key={step.key}
            to={step.to}
            className={`pw-step pw-step-${state}`}
            aria-current={state === "current" ? "step" : undefined}
          >
            <span className="pw-step-dot">
              {state === "done" ? (
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
                  <path
                    d="M3.5 8.5L6.5 11.5L12.5 5"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                i + 1
              )}
            </span>
            <span className="pw-step-label">{step.title}</span>
            {i < PIPELINE_WORKFLOW_STEPS.length - 1 && <span className="pw-step-sep" />}
          </Link>
        );
      })}
    </nav>
  );
}

export { apiGet, apiPost, apiPut, apiDelete };
