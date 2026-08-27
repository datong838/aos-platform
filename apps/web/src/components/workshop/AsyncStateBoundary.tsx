import type { ReactNode } from "react";

export type AsyncState =
  | "loading"
  | "empty"
  | "forbidden"
  | "stale"
  | "partial"
  | "failed"
  | "unknown"
  | "blocked"
  | "not-installed"
  | "ready";

const DEFAULT_COPY: Record<AsyncState, { title: string; description: string }> = {
  loading: { title: "正在读取", description: "正在从正式服务读取当前工作区状态。" },
  empty: { title: "暂无数据", description: "服务已返回空集合，没有使用示例数据填充。" },
  forbidden: { title: "没有访问权限", description: "当前主体无权读取此资源。" },
  stale: { title: "数据可能已过期", description: "后台刷新未完成，当前保留上一份已标记快照。" },
  partial: { title: "部分数据可用", description: "仅展示已确认部分，缺失范围不会以零值代替。" },
  failed: { title: "读取失败", description: "正式服务未返回可验证结果。" },
  unknown: { title: "状态待核对", description: "当前数据来源尚未提供可验证结论。" },
  blocked: { title: "等待必要条件", description: "页面保持可浏览；补齐所需数据后可继续处理。" },
  "not-installed": { title: "模块未安装", description: "当前工作区的 active installation 中没有此模块。" },
  ready: { title: "已就绪", description: "资源已通过当前边界检查。" },
};

export function AsyncStateBoundary({
  state,
  children,
  title,
  description,
  dataCutoff,
  action,
}: {
  state: AsyncState;
  children?: ReactNode;
  title?: string;
  description?: string;
  dataCutoff?: string | null;
  action?: ReactNode;
}) {
  if (state === "ready") return <>{children}</>;
  const copy = DEFAULT_COPY[state];
  const preservesContent = state === "stale" || state === "partial";
  const role = state === "failed" || state === "forbidden" || state === "blocked"
    ? "alert"
    : "status";

  return (
    <div className={`ecommerce-workshop-state is-${state}`}>
      <div className="ecommerce-workshop-state-summary" role={role} aria-live="polite">
        <strong>{title ?? copy.title}</strong>
        <span>{description ?? copy.description}</span>
        {dataCutoff ? <small>数据截止：{dataCutoff}</small> : null}
        {action ? <div className="ecommerce-workshop-state-action">{action}</div> : null}
      </div>
      {preservesContent && children ? (
        <div className="ecommerce-workshop-preserved-content">{children}</div>
      ) : null}
    </div>
  );
}
