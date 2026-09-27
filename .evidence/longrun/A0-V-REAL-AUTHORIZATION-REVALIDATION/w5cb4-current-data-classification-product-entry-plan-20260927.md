# W5CB4 当前数据分类策略产品入口波（2026-09-27，编码前）

## 上位与权威复习

- 231 BG-00 / 231-9 要求安全安装和产品配置，不允许开发者直接写库或以旧配置复活 Runtime；本波按当前新库八项零候选继续。产品方案中的商品教育与内容任务只需获准商品/知识资料，不需要读取原始订单、客户会话或凭据。
- 正式 Owner 是 `AipRuntimeGuardPolicyStore`，入口 `/v1/aip/runtime-guard-policies/data-classifications`。合同仅允许四个 approved 类别；必须禁止 `direct_pii/raw_order_detail/customer_conversation/credential/commercial_sensitive/cross_tenant/unknown`，且 `denyUnknown=true`、三项越权 allow=false。服务端校验保留原状。
- BudgetPolicy 即使 draft 也要求 exact BudgetRevision active，当前草稿不能替代；P2g30b 正向 Action 仍需健康 Skill/CapabilityBinding。这些阻断作为独立待办，不通过本波“做绿”。

## 文件级与最小交付

1. `apps/web/src/pages/s2/RuntimeDataClassificationPanel.tsx` 新增受控表单，仅允许用户明确选择 approved 类别、填写 policy ID、owner、真实 approvalRef、生效窗口；服务端强制的禁止列表与 fail-closed 字段固定，生命周期仅 draft。已有 ID 可只读查看，不覆盖或激活。
2. `apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.tsx` 将数据分类阻断导航到该入口，避免假链接；在既有 `/aip/model-runtime` 运行就绪页承载表单。调用 `apiPostUnqueued` + `apiGetAuthoritative`，POST 携唯一幂等键与 `If-Match:0`，未知结果只读对账，不排队、不重发；身份前后、tenant/hash/字段精确核验。
3. 新增专项测试覆盖类别边界、禁止项、空值与 readback；相邻累计、TypeScript、浏览器空表单验收、方案/代码复审、verification 后 m1 提交。

## 退出/停止条件

- 不从当前业务数据推断可出站类别，不自动选类别/审批人/approvalRef。无真实审批时不实际提交；draft 不计八项 active 候选。
- 不更改后端合同或绕过审批、Runtime/Provider/商城源；未知结果冻结原命令。旧 12 Run 和 P2g RED 工作树保持原样。
