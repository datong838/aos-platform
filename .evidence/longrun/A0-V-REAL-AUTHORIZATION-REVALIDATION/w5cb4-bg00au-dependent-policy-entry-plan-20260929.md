# W5CB4 BG-00au｜网络/预算策略缺口的合法前置入口

## Rules 与方案复习

按 231-3/9、BG-00at、网络/预算策略 API/Store 及现有页面，先 RED 再最小改动。`AipNetworkPolicyStore.publish` 即便 draft 也要求当前 active 精确 EgressPolicy；`AipModelGovernancePolicyStore.publish_budget` 即便 draft 也要求 active BudgetRevision。当前八候选0，Budget active API 仍422，直接做策略创建按钮会误导且无法合法提交。

## 文件级最小点

- 修改 `apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.tsx` 的两条 CANDIDATES 引导：网络策略链接已有 `/aip/model-runtime` 的出站草稿准备页，预算策略链接已有 `/aip/capacity` 的预算修订草稿页；文案明确是前置准备、尚不能生效/创建对应 active 策略。
- 修改 `apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.test.tsx`：RED 证明缺候选时两条目前没有合法准备链接；GREEN 校验准确目标与不生效文案。测试不触发 API、当前库或业务运行。
- 不改网络/预算策略 API、预算 active 422、配置 Stage/Host、其他六条候选。专项与相邻前端回归、diff check；浏览器验收依 browser-pilot 可用性如实记录。
