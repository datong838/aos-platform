# W5CB4 BG-00au｜网络/预算策略合法前置入口验证

方案：`w5cb4-bg00au-dependent-policy-entry-plan-20260929.md`。复习 231-3/9、BG-00at、网络/预算策略 Store/API 及 `/aip/model-runtime`、`/aip/capacity` 页面后，确认网络策略 publish（含 draft）要求当前 active 精确 EgressPolicy；预算策略 publish（含 draft）要求当前 active 精确 BudgetRevision。当前八候选0，不能直接显示“创建可生效策略”。

先改 `RuntimeInstallationPanel.test.tsx`：要求缺网络/预算策略时分别能到合法前置草稿页。运行 `PATH=.../dependencies/node/bin:$PATH pnpm --dir apps/web exec vitest run src/pages/s2/assetBundles/RuntimeInstallationPanel.test.tsx --reporter=dot`，RED 退出1，9项中1失败：网络行链接 `undefined`，期望 `/aip/model-runtime`。

最小修改 `RuntimeInstallationPanel.tsx` 两条候选：网络→已有出站策略草稿页，预算策略→已有预算修订草稿页；链接文字明确“先准备”“不生效”，并保留策略仍需当前批准/正式预算的限制。未新增提交 API、active 权限或修改其他六条候选。GREEN 同命令9 passed；相邻安装动作/运行页/容量页共57 passed；`pnpm --dir apps/web exec tsc --noEmit --pretty false`、`git diff --check` 均退出0。

复审：改动只在当前八候选只读引导可见时提供导航，不触发 API 写；过期候选测试仍隐藏列表。现有预算 active 422、网络策略 active 前置、Stage/Host禁入均未改。当前正式候选仍0，不能称配置已创建或绑定。`browser-pilot` 工具检索为空，未做浏览器交互截图；前端自动测试与类型检查是本波的验证范围。下波 BG-00av 继续审网络/预算策略真正产品提交入口的前置权威和最小合法只读/草稿路径，不虚构 active。
