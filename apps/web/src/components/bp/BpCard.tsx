import type { ReactNode } from "react";

export function BpCard({
  title,
  subtitle,
  actions,
  footer,
  padding = "md",
  children,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  padding?: "sm" | "md" | "none";
  children?: ReactNode;
}) {
  const bodyCls =
    padding === "sm" ? "bp-card-body-sm" : padding === "none" ? "bp-card-body-none" : "bp-card-body";
  const hasHeader = title || subtitle || actions;
  return (
    <div className="bp-card">
      {hasHeader ? (
        <div className="bp-card-header">
          <div>
            {title ? <h3 className="bp-card-title">{title}</h3> : null}
            {subtitle ? <p className="bp-card-subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="bp-card-actions">{actions}</div> : null}
        </div>
      ) : null}
      {children ? <div className={bodyCls}>{children}</div> : null}
      {footer ? <div className="bp-card-footer">{footer}</div> : null}
    </div>
  );
}
