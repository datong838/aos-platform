import { describe, expect, it } from "vitest";

import {
  buildPipelineProposalPreview,
  pipelineProposalStatusLabel,
  type PipelineProposalItem,
} from "./remainder";

const proposal: PipelineProposalItem = {
  id: "proposal-1",
  pipeline_id: "P05-order-qyh",
  title: "补充订单状态说明",
  description: "明确取消订单的识别条件。",
  proposed_by: "当前用户",
  status: "pending",
  diff_summary: "增加取消状态的中文映射。",
};

describe("pipeline proposal business preview", () => {
  it("uses only proposal facts and keeps technical identity in the audit section", () => {
    const preview = buildPipelineProposalPreview(proposal, "栖月汇-订单");

    expect(preview).toContain("所属业务管道：栖月汇-订单");
    expect(preview).toContain("增加取消状态的中文映射。");
    expect(preview).toContain("## 提案审计");
    expect(preview).toContain("提案标识：proposal-1");
    expect(preview).not.toContain("原 5 列");
    expect(preview).not.toContain("password");
  });

  it("does not invent a summary when the service did not return one", () => {
    const preview = buildPipelineProposalPreview({ ...proposal, diff_summary: "", description: "" }, "栖月汇-订单");

    expect(preview).not.toContain("变更摘要");
    expect(preview).not.toContain("变更说明");
  });

  it("translates every service status into Chinese", () => {
    expect(pipelineProposalStatusLabel("pending")).toBe("待审");
    expect(pipelineProposalStatusLabel("approved")).toBe("已审批");
    expect(pipelineProposalStatusLabel("merged")).toBe("已合并");
    expect(pipelineProposalStatusLabel("discarded")).toBe("已作废");
    expect(pipelineProposalStatusLabel("rejected")).toBe("已驳回");
  });
});
