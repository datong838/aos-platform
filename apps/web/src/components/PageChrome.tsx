import type { ReactNode } from "react";

export function PageChrome({
  title,
  lede,
  children,
}: {
  title: string;
  lede?: string;
  children?: ReactNode;
}) {
  return (
    <div className="content-inner">
      <header className="page-chrome">
        <h1>{title}</h1>
        {lede ? <p className="lede">{lede}</p> : null}
      </header>
      {children}
    </div>
  );
}
