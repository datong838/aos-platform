import type { ReactNode } from "react";

export function PageChrome({
  title,
  lede,
  titleTone,
  hideHeader,
  children,
}: {
  title?: string;
  /** 支持带色标的 ReactNode（概览页对齐视觉稿） */
  lede?: ReactNode;
  /** brand · 与侧栏「AI操作系统」同级字号（概览定位句） */
  titleTone?: "default" | "brand";
  /** 页面自带顶栏时隐藏 PageChrome header（避免双标题） */
  hideHeader?: boolean;
  children?: ReactNode;
}) {
  const showHeader = !hideHeader && Boolean(title);
  return (
    <div className="content-inner">
      {showHeader ? (
        <header className="page-chrome">
          <h1 className={titleTone === "brand" ? "page-chrome-title-brand" : undefined}>{title}</h1>
          {lede ? <p className="lede">{lede}</p> : null}
        </header>
      ) : null}
      {children}
    </div>
  );
}
