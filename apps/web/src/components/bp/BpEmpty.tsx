import type { ReactNode } from "react";

export function BpEmpty({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="bp-empty" role="status">
      {icon ? <div className="bp-empty-icon">{icon}</div> : null}
      <p className="bp-empty-title">{title}</p>
      {description ? <p className="bp-empty-desc">{description}</p> : null}
      {action ? <div className="bp-empty-action">{action}</div> : null}
    </div>
  );
}
