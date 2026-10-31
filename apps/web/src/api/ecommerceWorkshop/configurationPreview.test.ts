import { describe, expect, it } from "vitest";
import { parseBackgroundProcessingConfigurationPreview } from "./parser";

const preview = (open: boolean) => ({
  tenant: { orgId: "org-org", projectId: "dev-project" },
  preview: {
    schemaVersion: "aos.route-worker-configuration-preview/v1",
    status: open ? "reviewable" : "needs_input",
    title: open ? "后台处理配置可以确认" : "后台处理配置条件未齐",
    summary: "只保存配置，当前不会自动处理业务。",
    approvalAllowed: open,
    checks: [
      ["current_customer_installation", "当前客户安装"],
      ["background_identity", "后台业务身份"],
      ["protected_storage", "受保护保存位置"],
      ["identity_credential", "身份凭据"],
      ["configuration_submission", "配置保存通道"],
    ].map(([key, label], index) => ({ key, label, passed: index < 4 || open, detail: "当前配置条件已核对。" })),
    nextActions: ["核对配置保存通道。"],
    sideEffects: { databaseWrite: false, configurationWrite: false, tokenRequest: false, businessProcessing: false, externalEffect: false },
    canProcessBusinessTasks: false,
    evaluatedAt: "2026-10-31T03:40:00Z",
  },
});

describe("后台配置预览五项正式合同", () => {
  it("接受正式五项已就绪响应", () => {
    expect(parseBackgroundProcessingConfigurationPreview(preview(true)).preview.approvalAllowed).toBe(true);
  });
  it("保存通道关闭时保持不可保存", () => {
    expect(parseBackgroundProcessingConfigurationPreview(preview(false)).preview.approvalAllowed).toBe(false);
  });
  it("拒绝缺少保存通道的旧四项响应", () => {
    const value = preview(true);
    value.preview.checks.pop();
    expect(() => parseBackgroundProcessingConfigurationPreview(value)).toThrow();
  });
});
