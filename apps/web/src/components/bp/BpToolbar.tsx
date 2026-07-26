import type { ChangeEvent, ReactNode } from "react";

export function BpToolbar({
  search,
  filters,
  actions,
  count,
  children,
}: {
  search?: {
    value: string;
    onChange: (v: string) => void;
    placeholder?: string;
  };
  filters?: ReactNode;
  actions?: ReactNode;
  count?: number;
  children?: ReactNode;
}) {
  return (
    <div className="bp-toolbar" role="toolbar">
      {search ? (
        <div className="bp-toolbar-search">
          <span className="bp-toolbar-search-icon" aria-hidden>
            <SearchIcon />
          </span>
          <input
            type="search"
            value={search.value}
            placeholder={search.placeholder ?? "搜索…"}
            onChange={(e: ChangeEvent<HTMLInputElement>) => search.onChange(e.target.value)}
            aria-label="搜索"
          />
        </div>
      ) : null}
      {filters ? <div className="bp-toolbar-group">{filters}</div> : null}
      {children}
      {actions ? (
        <>
          <span className="bp-toolbar-sep" aria-hidden />
          <div className="bp-toolbar-group">{actions}</div>
        </>
      ) : null}
      {typeof count === "number" ? (
        <span className="bp-toolbar-count">{count} 条</span>
      ) : null}
    </div>
  );
}

function SearchIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M11 11L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
