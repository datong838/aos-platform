/** TWB.1 — 顶栏可改 aos-api Base */
import { useState } from "react";
import { getApiBase, setApiBase, clearApiBaseOverride } from "../api/apiBase";
import { NavIcon } from "../shell/icons";

export function PlatformBaseSwitcher() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(() => getApiBase());
  const [saved, setSaved] = useState(getApiBase());

  function onSave() {
    const next = setApiBase(value);
    setSaved(next);
    setValue(next);
    setOpen(false);
    window.dispatchEvent(
      new CustomEvent("aos-api-base-changed", { detail: { base: next } }),
    );
  }

  function onReset() {
    clearApiBaseOverride();
    const next = getApiBase();
    setSaved(next);
    setValue(next);
    setOpen(false);
    window.dispatchEvent(
      new CustomEvent("aos-api-base-changed", { detail: { base: next } }),
    );
  }

  return (
    <div className="aos-platform-base">
      <button
        type="button"
        className="aos-platform-base-btn"
        aria-label="平台连接"
        aria-expanded={open}
        title={saved}
        onClick={() => {
          setValue(getApiBase());
          setOpen((v) => !v);
        }}
      >
        <NavIcon name="server" />
        <span className="aos-platform-base-label">平台</span>
      </button>
      {open ? (
        <div className="aos-platform-base-menu" role="dialog">
          <div className="aos-workspace-menu-title">aos-api 地址</div>
          <input
            className="aos-platform-base-input"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="https://aos.example.com"
            aria-label="API Base"
          />
          <div className="aos-platform-base-actions">
            <button type="button" className="aos-workspace-item" onClick={onReset}>
              恢复默认
            </button>
            <button
              type="button"
              className="aos-workspace-item is-selected"
              onClick={onSave}
            >
              保存
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
