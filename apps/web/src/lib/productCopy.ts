/** TWB.2 / TWB.3 / 163 / 170 — 端云产品文案真源
 * - 本机探活 ∈ 运维交付（R-OPS-01）；禁止称 Apollo
 * - 禁止演示临时候补页（R-PROD-01 · 续见 75）
 */
export const LOCAL_PLATFORM_NAME = "本机探活";

/** 侧栏运维面分组名（可收；含本机探活 + Apollo 交付页） */
export const OPS_NAV_SECTION = "运维交付";

export const ENV_READONLY_HINT = "业务侧环境状态只读 · 晋升/Promote 在运维面";

export const MODEL_CONFIG_NO_VAULT =
  "已配置大模型仅使用 secretRef；请勿从业务座舱进入 Vault/网关运维台";

export function assertNotCallingLocalPlatformApollo(label: string): boolean {
  const bad =
    /apollo/i.test(label) &&
    (label.includes("本机") || /local.?first/i.test(label));
  return !bad;
}
