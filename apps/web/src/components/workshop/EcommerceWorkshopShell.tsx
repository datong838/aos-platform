import { useEffect, useRef, useState, type ReactNode } from "react";

import type { EcommerceWorkshopModule } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { CapabilityBlocker } from "./CapabilityBlocker";
import { SourceReadinessProvider } from "./SourceReadinessContext";
import { SourceReadinessPanel } from "./SourceReadinessPanel";

export const WORKSHOP_FOCUS_EVENT = "aos-workshop-focus-mode";

function readinessState(module: EcommerceWorkshopModule): AsyncState {
  if (module.readiness === "available") return "ready";
  if (module.readiness === "degraded") return "partial";
  if (module.readiness === "unknown") return "unknown";
  return "blocked";
}

export function EcommerceWorkshopShell({
  module,
  dataCutoff,
  catalogStale = false,
  exposeReadOnlyWhenUnverified = false,
  children,
}: {
  module: EcommerceWorkshopModule;
  dataCutoff: string | null;
  catalogStale?: boolean;
  exposeReadOnlyWhenUnverified?: boolean;
  children?: ReactNode;
}) {
  const [focusMode, setFocusMode] = useState(false);
  const focusButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    return () => {
      window.dispatchEvent(
        new CustomEvent(WORKSHOP_FOCUS_EVENT, { detail: { active: false } }),
      );
    };
  }, []);

  const toggleFocus = () => {
    const next = !focusMode;
    setFocusMode(next);
    window.dispatchEvent(
      new CustomEvent(WORKSHOP_FOCUS_EVENT, { detail: { active: next } }),
    );
    if (!next) window.requestAnimationFrame(() => focusButton.current?.focus());
  };
  const state = readinessState(module);
  const pendingView = children ?? (
    <section className="ecommerce-workshop-view-pending" role="status">
      <h2>模块目录与外壳已就绪</h2>
      <p>业务视图将在 W2 接入；当前不使用视觉稿或示例数据代替正式读模型。</p>
    </section>
  );

  return (
    <SourceReadinessProvider>
    <div className={`ecommerce-workshop-shell${focusMode ? " is-focus" : ""}`}>
      <a className="ecommerce-workshop-skip-link" href="#ecommerce-workshop-main">
        跳到模块主内容
      </a>
      <header className="ecommerce-workshop-context-header">
        <div>
          <p className="ecommerce-workshop-eyebrow">已安装电商工作台</p>
          <h1>{module.displayName}</h1>
          {module.menuLabel !== module.displayName ? (
            <p className="ecommerce-workshop-alias">菜单名：{module.menuLabel}</p>
          ) : null}
        </div>
        <div className="ecommerce-workshop-context-actions">
          <span className={`ecommerce-workshop-readiness-badge is-${module.readiness}`}>
            {module.readiness}
          </span>
          <button
            ref={focusButton}
            type="button"
            className="ecommerce-workshop-focus-button"
            aria-pressed={focusMode}
            onClick={toggleFocus}
          >
            {focusMode ? "退出专注" : "专注模式"}
          </button>
        </div>
      </header>

      <dl className="ecommerce-workshop-context-refs" aria-label="模块版本上下文">
        <div><dt>Module</dt><dd>{module.moduleId}</dd></div>
        <div><dt>Bundle</dt><dd>{module.moduleRef.bundleId}@{module.moduleRef.version}</dd></div>
        <div><dt>Installation</dt><dd>r{module.installationRef.revision} / lock r{module.installationRef.lockRevision}</dd></div>
        <div><dt>数据截止</dt><dd>{dataCutoff ?? "尚无可验证时间"}</dd></div>
      </dl>

      <SourceReadinessPanel />

      <section
        id="ecommerce-workshop-main"
        tabIndex={-1}
        aria-label="模块主内容"
      >
        {catalogStale ? (
          <AsyncStateBoundary state="stale" dataCutoff={dataCutoff}>
            {pendingView}
          </AsyncStateBoundary>
        ) : state === "ready" ? (
          pendingView
        ) : state === "partial" ? (
          <AsyncStateBoundary state="partial" dataCutoff={dataCutoff}>
            {pendingView}
          </AsyncStateBoundary>
        ) : (
          <>
            <AsyncStateBoundary state={state} dataCutoff={dataCutoff} />
            {exposeReadOnlyWhenUnverified && children ? (
              <div className="ecommerce-workshop-unverified-read-view">
                {children}
              </div>
            ) : null}
          </>
        )}
        <CapabilityBlocker readiness={module.readiness} blockers={module.blockers} />
      </section>
    </div>
    </SourceReadinessProvider>
  );
}
