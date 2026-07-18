import type { ReactNode } from "react";

export function PageChrome({
  title,
  lede,
  titleTone,
  children,
}: {
  title: string;
  lede?: string;
  /** brand · 与侧栏「AI操作系统」同级字号（概览定位句） */
  titleTone?: "default" | "brand";
  children?: ReactNode;
}) {
  return (
    <div className="content-inner">
      <header className="page-chrome">
        <h1 className={titleTone === "brand" ? "page-chrome-title-brand" : undefined}>{title}</h1>
        {lede ? <p className="lede">{lede}</p> : null}
      </header>
      {children}
    </div>
  );
}
