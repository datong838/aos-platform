export type BpStep = {
  key: string;
  title: string;
  description?: string;
};

export function BpStepper({
  steps,
  current,
  status = "default",
  info,
}: {
  steps: BpStep[];
  /** 0-based 当前步索引；越界则钳制到 [0, steps.length-1] */
  current: number;
  status?: "default" | "info";
  info?: string;
}) {
  if (steps.length === 0) return null;
  const clamped = Math.max(0, Math.min(current, steps.length - 1));
  return (
    <div className="bp-steps">
      {steps.map((step, i) => {
        const state = i < clamped ? "done" : i === clamped ? "current" : "pending";
        const numCls = `bp-step-num is-${state}`;
        const titleCls = state === "pending" ? "bp-step-title is-pending" : "bp-step-title";
        return (
          <div className="bp-step" key={step.key}>
            <div className={numCls} aria-current={state === "current" ? "step" : undefined}>
              {state === "done" ? <CheckIcon /> : i + 1}
            </div>
            <div className="bp-step-content">
              <p className={titleCls}>{step.title}</p>
              {step.description ? <p className="bp-step-desc">{step.description}</p> : null}
              {state === "current" && status === "info" && info ? (
                <div className="bp-step-info" role="note">
                  {info}
                </div>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M3.5 8.5L6.5 11.5L12.5 5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
