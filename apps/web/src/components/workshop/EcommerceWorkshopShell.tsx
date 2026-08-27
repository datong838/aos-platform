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

const READINESS_LABEL = {
  available: "可用",
  degraded: "部分可用",
  disabled: "已停用",
  blocked: "等待条件",
  unknown: "待核对",
} as const;

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
  const analystVisualContext = module.moduleId === "ecommerce.analyst";
  const pendingView = children ?? (
    <section className="ecommerce-workshop-view-pending" role="status">
      <h2>模块目录与外壳已就绪</h2>
      <p>业务视图等待正式读模型接入；当前不使用视觉稿或示例数据代替业务事实。</p>
    </section>
  );

  return (
    <SourceReadinessProvider>
    <div
      className={`ecommerce-workshop-shell${focusMode ? " is-focus" : ""}`}
      data-module-id={module.moduleId}
    >
      <a className="ecommerce-workshop-skip-link" href="#ecommerce-workshop-main">
        跳到模块主内容
      </a>
      <header className="ecommerce-workshop-context-header">
        {analystVisualContext ? <div className="analyst-exact-context-strip">
          <span className="is-blue">渠道未选择 · 数据截止未验证</span>
          <span className="is-purple">经营参谋（负责人未绑定）</span>
          <span className="is-gray">数据截止未验证 · 新鲜度待核对</span>
          <i aria-hidden="true" />
          <span className="is-red">业务操作：只读</span>
          <button ref={focusButton} type="button" className="is-yellow" aria-pressed={focusMode} onClick={toggleFocus}>{focusMode ? "退出专注" : "专注模式"}</button>
        </div> : <><div>
          <p className="ecommerce-workshop-eyebrow">已安装电商工作台</p>
          <h1>{module.displayName}</h1>
          {module.menuLabel !== module.displayName ? (
            <p className="ecommerce-workshop-alias">菜单名：{module.menuLabel}</p>
          ) : null}
        </div>
        <div className="ecommerce-workshop-context-actions">
          <span className={`ecommerce-workshop-readiness-badge is-${module.readiness}`}>
            {READINESS_LABEL[module.readiness]}
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
        </>}
      </header>

      <details className="ecommerce-workshop-technical-context">
        <summary>
          <span>模块与数据上下文</span>
          <small>{module.moduleId} · {READINESS_LABEL[module.readiness]} · 数据截止 {dataCutoff ?? "待验证"}</small>
        </summary>
        <div className="ecommerce-workshop-technical-context-body">
          <dl className="ecommerce-workshop-context-refs" aria-label="模块版本上下文">
            <div><dt>Module</dt><dd>{module.moduleId}</dd></div>
            <div><dt>Bundle</dt><dd>{module.moduleRef.bundleId}@{module.moduleRef.version}</dd></div>
            <div><dt>Installation</dt><dd>r{module.installationRef.revision} / lock r{module.installationRef.lockRevision}</dd></div>
            <div><dt>数据截止</dt><dd>{dataCutoff ?? "尚无可验证时间"}</dd></div>
          </dl>

          <SourceReadinessPanel />
        </div>
      </details>

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
