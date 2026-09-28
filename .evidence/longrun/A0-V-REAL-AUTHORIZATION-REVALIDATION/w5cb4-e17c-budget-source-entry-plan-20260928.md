# W5CB4 E17-c｜BG-00 预算来源产品入口最小接线计划（2026-09-28）

## 上位方案和当前证据

- 231-9 BG-00 要求“过期原因→正式更新→影响预览→恢复”进入产品入口；231-3 的正式配置消费仍须同事务核当前责任、数据分类、预算、运行策略四源，不能因页面可点就放行运行。
- 当前 `org-org/dev-project` 的八类有效候选全为 0。`CapacityPage` 已挂 `BudgetRevisionSetupPanel`，支持由用户明确填写金额/Owner/有效期创建 **draft**、幂等提交后 exact 回读和未知结果只读对账。`RuntimeInstallationPanel` 的 `budgets` 却标为“产品配置入口待建”；既有数据/出站入口也仅能建草稿，却统一显示“进入正式配置入口”，容易误读为 active。
- 正式 active 发布涉及 Owner、批准与费用边界；本切片既不伪造金额/审批，也不提交当前真实库。只补可发现的既有草稿入口和准确的动作说明，为下一波正式生产者铺路，不把草稿计入候选。

## 文件级改动

1. `apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.test.tsx`：先加失败断言，要求 `budgets` 行有指向 `/aip/capacity` 的预算草稿入口，文案明确“不生效”；旧 `budgets` 空链接应 RED。数据/出站、配额等既有入口的文案同样不得冒充 active。过期候选不显示任何入口。
2. `apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.tsx`：仅扩展候选静态映射的入口文案和 `budgets` href；保留候选计数、当前安装 ETag 检查、Host 禁入和所有写按钮逻辑。不得在前端新增 budget 请求、默认金额或审批引用。
3. 同目录 verification 记录 RED/GREEN、专项与累计、方案对应、浏览器门状态和风险；D-waves/外部 AOS 上下文按收口规则登记。m1 仅精确提交本波仓库文件，不纳入原有他项未提交改动。

## 验收与边界

- 专项：候选当前时八行仍显示，预算行可去现有 `/aip/capacity` 草稿表单且明确 draft；数据/出站只称草稿，配额只称查看/修订；候选 stale 时不渲染行和链接；运行准备按钮继续受服务端准入门控制。
- 累计：受影响 Web 测试与类型/构建通过；浏览器 `browser-pilot` 可用时补真实页面截图，不可用则如实记未验收。当前库只读，Host/worker/Provider/18181 不启动。
- 退出结论仅为“产品草稿入口接通且文案与权威一致”。下一波必须建设正式 active 来源的 Owner/审批/精确版本/Receipt 产品流程，再做安装绑定和自然首链，不能将本波称为配置已可用。
