import { useMemo, type ChangeEvent } from "react";

export type BpCronPreset = "5min" | "hourly" | "daily" | "weekly" | "monthly";

const PRESETS: Record<BpCronPreset, { expr: string; label: string }> = {
  "5min": { expr: "*/5 * * * *", label: "每 5 分钟" },
  hourly: { expr: "0 * * * *", label: "每小时" },
  daily: { expr: "0 0 * * *", label: "每天 0 点" },
  weekly: { expr: "0 0 * * 0", label: "每周日 0 点" },
  monthly: { expr: "0 0 1 * *", label: "每月 1 日" },
};

const FIELD_RANGES = [
  { name: "minute", min: 0, max: 59 },
  { name: "hour", min: 0, max: 23 },
  { name: "dayOfMonth", min: 1, max: 31 },
  { name: "month", min: 1, max: 12 },
  { name: "dayOfWeek", min: 0, max: 6 },
];

/** 简化版 cron 校验：5 段 + 范围 + 通配/步长/列表 语法 */
export function isValidCron(expr: string): boolean {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return false;
  return parts.every((p, idx) => {
    const range = FIELD_RANGES[idx];
    if (p === "*") return true;
    // 步长 a/b
    if (p.includes("/")) {
      const [base, step] = p.split("/");
      const stepNum = Number(step);
      if (!Number.isInteger(stepNum) || stepNum < 1) return false;
      if (base === "*") return true;
      return validateRange(base, range.min, range.max);
    }
    // 列表 a,b,c
    if (p.includes(",")) {
      return p.split(",").every((s) => validateRange(s, range.min, range.max));
    }
    // 范围 a-b
    return validateRange(p, range.min, range.max);
  });
}

function validateRange(token: string, min: number, max: number): boolean {
  if (token.includes("-")) {
    const [a, b] = token.split("-");
    return validateNum(a, min, max) && validateNum(b, min, max);
  }
  return validateNum(token, min, max);
}

function validateNum(token: string, min: number, max: number): boolean {
  const n = Number(token);
  return Number.isInteger(n) && n >= min && n <= max;
}

/** 简化版人读：覆盖常见模式 */
export function describeCron(expr: string): string {
  if (!isValidCron(expr)) return "无效表达式";
  const [min, hour, dom, month, dow] = expr.trim().split(/\s+/);
  if (min === "*/5" && hour === "*" && dom === "*" && month === "*" && dow === "*") return "每 5 分钟";
  if (min === "0" && hour === "*" && dom === "*" && month === "*" && dow === "*") return "每小时整点";
  if (min === "0" && hour === "0" && dom === "*" && month === "*" && dow === "*") return "每天 00:00";
  if (min === "0" && hour === "0" && dom === "*" && month === "*" && dow === "0") return "每周日 00:00";
  if (min === "0" && hour === "0" && dom === "1" && month === "*" && dow === "*") return "每月 1 日 00:00";
  return `自定义：${expr}`;
}

export function BpCronInput({
  value,
  onChange,
  showPresets = true,
  showHumanReadable = true,
  ariaLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  showPresets?: boolean;
  showHumanReadable?: boolean;
  ariaLabel?: string;
}) {
  const valid = useMemo(() => isValidCron(value), [value]);
  const human = useMemo(() => (valid ? describeCron(value) : "表达式格式不正确"), [value, valid]);
  const activePreset = useMemo(
    () => (Object.keys(PRESETS) as BpCronPreset[]).find((k) => PRESETS[k].expr === value),
    [value],
  );
  return (
    <div className="bp-cron">
      {showPresets ? (
        <div className="bp-cron-presets" role="group" aria-label="cron 预设">
          {(Object.keys(PRESETS) as BpCronPreset[]).map((k) => (
            <button
              key={k}
              type="button"
              className={activePreset === k ? "bp-cron-preset is-active" : "bp-cron-preset"}
              onClick={() => onChange(PRESETS[k].expr)}
              aria-pressed={activePreset === k}
            >
              {PRESETS[k].label}
            </button>
          ))}
        </div>
      ) : null}
      <input
        type="text"
        className={valid ? "bp-cron-input" : "bp-cron-input is-invalid"}
        value={value}
        placeholder="* * * * *  （分 时 日 月 周）"
        spellCheck={false}
        aria-label={ariaLabel ?? "cron 表达式"}
        aria-invalid={!valid}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      />
      {showHumanReadable ? (
        <div className={valid ? "bp-cron-human" : "bp-cron-human is-invalid"} role="status">
          {human}
        </div>
      ) : null}
    </div>
  );
}
