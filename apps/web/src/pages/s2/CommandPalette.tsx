/**
 * Phase 7 · 全局搜索命令面板（Command Palette）
 * 快捷键 Cmd+K / Ctrl+K 唤出，支持页面跳转、资源搜索、快捷操作
 */
import { useEffect, useState, useCallback } from "react";

export interface CommandItem {
  id: string;
  label: string;
  hint?: string;
  group: "navigate" | "resource" | "action";
  icon?: string;
  action: () => void;
}

export interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  items: CommandItem[];
}

export function CommandPalette({ open, onClose, items }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const filtered = items.filter((item) =>
    !query ||
    item.label.toLowerCase().includes(query.toLowerCase()) ||
    (item.hint || "").toLowerCase().includes(query.toLowerCase())
  );

  const grouped = filtered.reduce((acc, item) => {
    if (!acc[item.group]) acc[item.group] = [];
    acc[item.group].push(item);
    return acc;
  }, {} as Record<string, CommandItem[]>);

  const flatList = Object.values(grouped).flat();

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      if (open) onClose();
    }
    if (e.key === "Escape" && open) {
      onClose();
    }
  }, [open, onClose]);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  if (!open) return null;

  const GROUP_LABEL: Record<string, string> = {
    navigate: "页面导航",
    resource: "资源",
    action: "快捷操作",
  };

  let runningIndex = 0;

  return (
    <div
      style={{
        position: "fixed",
        top: 0, left: 0, right: 0, bottom: 0,
        zIndex: 9999,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: "15vh",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "min(640px, 90vw)",
          background: "var(--aos-surface, #fff)",
          borderRadius: 2,
          boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 搜索输入 */}
        <div style={{ display: "flex", alignItems: "center", padding: "12px 16px", borderBottom: "1px solid var(--aos-border, #e2e8f0)" }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 8, opacity: 0.5 }}>
            <circle cx="11" cy="11" r="7" /><path d="M20 20l-3-3" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="搜索页面、资源或操作…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            style={{
              flex: 1, border: "none", outline: "none", fontSize: "0.95rem",
              background: "transparent", color: "var(--aos-text, #1a202c)",
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setSelectedIndex((i) => Math.min(i + 1, flatList.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSelectedIndex((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                const item = flatList[selectedIndex];
                if (item) {
                  item.action();
                  onClose();
                }
              }
            }}
          />
          <kbd style={{ fontSize: "0.7rem", padding: "2px 6px", background: "var(--aos-surface-hover, #edf2f7)", borderRadius: 3, color: "var(--aos-text-muted, #718096)" }}>ESC</kbd>
        </div>

        {/* 结果列表 */}
        <div style={{ maxHeight: 400, overflowY: "auto", padding: "4px 0" }}>
          {flatList.length === 0 && (
            <div style={{ padding: "24px 16px", textAlign: "center", color: "var(--aos-text-muted, #718096)", fontSize: "0.85rem" }}>
              无匹配结果
            </div>
          )}
          {Object.entries(grouped).map(([group, groupItems]) => (
            <div key={group}>
              <div style={{ padding: "4px 16px", fontSize: "0.7rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--aos-text-muted, #718096)" }}>
                {GROUP_LABEL[group] || group}
              </div>
              {groupItems.map((item) => {
                const idx = runningIndex++;
                const isSelected = idx === selectedIndex;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onMouseEnter={() => setSelectedIndex(idx)}
                    onClick={() => { item.action(); onClose(); }}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      width: "100%", padding: "8px 16px",
                      background: isSelected ? "var(--aos-surface-hover, #edf2f7)" : "transparent",
                      border: "none", cursor: "pointer", textAlign: "left",
                      fontSize: "0.85rem",
                    }}
                  >
                    <span>
                      {item.icon && <span style={{ marginRight: 8 }}>{item.icon}</span>}
                      {item.label}
                    </span>
                    {item.hint && (
                      <span style={{ fontSize: "0.7rem", color: "var(--aos-text-muted, #718096)" }}>{item.hint}</span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        {/* 底部提示 */}
        <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 16px", borderTop: "1px solid var(--aos-border, #e2e8f0)", fontSize: "0.7rem", color: "var(--aos-text-muted, #718096)" }}>
          <span>↑↓ 导航 · Enter 确认</span>
          <span>{flatList.length} 个结果</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Hook: useCommandPalette
 * 管理命令面板的开关状态和全局快捷键
 */
export function useCommandPalette() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return { open, setOpen };
}
