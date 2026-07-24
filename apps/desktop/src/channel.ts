/**
 * TWC.12 — 渠道包 SKU（同一内核，仅预置配置）
 */
export type ChannelSku = "private" | "saas" | "local";

export type ChannelConfig = {
  channel: ChannelSku;
  defaultApiBase: string;
  /** 已有预置 Base 时可跳过欢迎强制配置 */
  skipWelcomeWhenBasePreset: boolean;
  productLabel?: string;
};

export const CHANNEL_STORAGE_KEY = "aos-channel-v1";

const PRESETS: Record<ChannelSku, ChannelConfig> = {
  private: {
    channel: "private",
    defaultApiBase: "",
    skipWelcomeWhenBasePreset: false,
    productLabel: "AOS 桌面（私有化）",
  },
  saas: {
    channel: "saas",
    defaultApiBase: "https://aos.example.com",
    skipWelcomeWhenBasePreset: true,
    productLabel: "AOS 桌面（SaaS）",
  },
  local: {
    channel: "local",
    defaultApiBase: "http://127.0.0.1:8080",
    skipWelcomeWhenBasePreset: true,
    productLabel: "AOS 桌面（本机）",
  },
};

export function parseChannelSku(raw: string | null | undefined): ChannelSku {
  const v = (raw || "").trim().toLowerCase();
  if (v === "saas" || v === "private" || v === "local") return v;
  return "local";
}

export function getChannelConfig(sku?: ChannelSku): ChannelConfig {
  const fromEnv = parseChannelSku(
    typeof import.meta !== "undefined"
      ? (import.meta as ImportMeta & { env?: { VITE_AOS_CHANNEL?: string } }).env
          ?.VITE_AOS_CHANNEL
      : undefined,
  );
  let stored: ChannelSku | null = null;
  try {
    stored = parseChannelSku(localStorage.getItem(CHANNEL_STORAGE_KEY));
  } catch {
    stored = null;
  }
  const key = sku || stored || fromEnv;
  return { ...PRESETS[key] };
}

export function setChannelSku(sku: ChannelSku): ChannelConfig {
  try {
    localStorage.setItem(CHANNEL_STORAGE_KEY, sku);
  } catch {
    /* ignore */
  }
  console.info("[aos-channel]", { event: "set", channel: sku });
  return getChannelConfig(sku);
}

/** 若用户尚未覆盖 API Base 且渠道有默认 → 写入 */
export function applyChannelApiBase(
  setApiBase: (b: string) => string,
  hasStoredBase: () => boolean,
): ChannelConfig {
  const cfg = getChannelConfig();
  if (cfg.defaultApiBase && !hasStoredBase()) {
    setApiBase(cfg.defaultApiBase);
    console.info("[aos-channel]", {
      event: "applied_default_base",
      channel: cfg.channel,
      base: cfg.defaultApiBase,
    });
  }
  return cfg;
}

export function shouldSkipWelcomeForce(
  cfg: ChannelConfig = getChannelConfig(),
): boolean {
  return Boolean(cfg.skipWelcomeWhenBasePreset && cfg.defaultApiBase);
}

export { PRESETS as CHANNEL_PRESETS };
