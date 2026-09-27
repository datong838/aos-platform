# W5CB4 当前数据分类策略产品入口 verification（2026-09-27）

## 结论与范围

- 已在 `/aip/model-runtime` 增加数据分类策略草稿表单，安装页当前候选缺口可以导航到该入口。表单不是 Runtime 准入，也不是数据读取授权；本波未提交任何策略行、未激活任何策略。
- 使用正式 `/v1/aip/runtime-guard-policies/data-classifications` Owner。四个可选获准类别默认全未选；七个必须禁止类别和 `denyUnknown=true/allowDirectPii=false/allowCommercialSensitive=false/allowCrossTenant=false` 固定且服务端仍独立校验。policy ID、owner、approvalRef、有效窗均需用户明确填写，lifecycle 固定 `draft`。
- 首次 POST 为唯一幂等键、`If-Match:0`、不进离线队列；随后权威 GET 核对租户、revision、hash、所有策略字段，POST/GET hash 一致，并在两次网络响应后重核身份。未知结果仅可只读对账，不换键重发；已有 ID 只读查询，不覆盖。

## 验证

- 前端专项/相邻 Vitest：`RuntimeDataClassificationPanel.test.tsx` 3、`RuntimeInstallationPanel.test.tsx` 8、`ModelRuntimePage.test.tsx` 6、上波 Budget 3、API client 4，共 24/24 通过。TypeScript `tsc --noEmit` 通过；`git diff --check` 通过。
- 浏览器 `http://127.0.0.1:8434/aip/model-runtime` 实见新面板、四个均未选择的复选框，以及“仅创建 draft”说明；空表单点击“创建 draft 并核对”仅显示“策略 ID、负责人和正式审批引用均须明确填写”。本波没有真实 approvalRef，因此未做真实 POST。
- 同页现有跨页权威投影显示 `ecommerce agent definitions differ from 6-role authority`，这是独立当前阻断；本波没有改写为绿、没有启动受控试聊。

## 复审与下一波

- 方案/代码一致：没有后端合同改动，没有把 draft 计作当前 active 候选；数据类别和禁止集与 `aip_runtime_guard_policy_contracts.py` 对齐。尚未实测已填表单真实提交与服务端持久化，必须待真实 owner/approvalRef/窗口由合法使用者给出，不以测试 fixture 代替。
- 下一波检查同一 GuardPolicy Owner 的 egress 出站策略产品入口；先冻结受控 Host/Region/approvalRef 的产品与技术合同，再做最小草稿入口。BudgetPolicy 仍依赖 active BudgetRevision，Action 正向 producer 仍依赖健康绑定；均保留独立门。
- 原 12 Run、商城源、Runtime Host/worker、Provider 和旧数据卷未触碰；P2g30b RED 工作树保持原状。
