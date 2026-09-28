# W5CB4 E17-c｜预算草稿来源入口验证（2026-09-28）

## 范围与方案对账

- 对照同目录 `w5cb4-e17c-budget-source-entry-plan-20260928.md`，仅改 `RuntimeInstallationPanel.tsx` 的八候选静态入口映射和对应组件测试。`/aip/capacity` 在 `App.tsx:264` 已注册，`CapacityPage.tsx:432` 已挂 `BudgetRevisionSetupPanel`。
- 预算行现能到达已有表单，明确显示“创建预算草稿（不生效）”；数据分类/出站入口也明确仅建草稿。候选读回、安装 ETag、运行准入和写动作均未改；草稿不计入当前有效候选。
- 当前真实库只读；没有填写预算金额、Owner、批准引用，没有创建 active 配置、安装绑定、Host assignment 或业务 Run。Host/worker/Provider 继续关闭。

## 新鲜验证

| 检查 | 命令/观察 | 结果 |
| --- | --- | --- |
| RED | `pnpm --filter @aos/web exec vitest run src/pages/s2/assetBundles/RuntimeInstallationPanel.test.tsx`，补断言后、实现前 | 退出 1；预算行 href 实际为 `undefined`，预期 `/aip/capacity`。首次因系统 PATH 无 `node` 的调用属环境错误，随后改用捆绑 Node 复现有效 RED。 |
| 专项 GREEN | `PATH=/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH pnpm --filter @aos/web exec vitest run src/pages/s2/assetBundles/RuntimeInstallationPanel.test.tsx` | 退出 0；9 passed。 |
| 相关累计 | `PATH=/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH pnpm --filter @aos/web exec vitest run src/pages/s2/assetBundles src/pages/s2/BudgetRevisionSetupPanel.test.tsx` | 退出 0；23 files、119 tests passed。 |
| 类型与生产构建 | `PATH=/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH pnpm --filter @aos/web build` | 退出 0；`tsc -p tsconfig.json && vite build` 完成。只有既有大 chunk 警告。 |
| 差异检查 | `git diff --check`；`git diff -- RuntimeInstallationPanel.tsx RuntimeInstallationPanel.test.tsx` | 退出 0；仅候选入口及其断言，未改运行门。 |

## 未通过的门与风险

- 本次环境没有可调用的 `browser-pilot`，故没有新鲜浏览器截图；页面验收仍待补，不以组件测试或构建替代。
- 本波只解决草稿入口可发现性。当前八类 active 候选仍为 0，正式 Owner、批准、版本、Receipt、安装绑定与当前三身份/OCI 均未齐；不得据此启 Host 或称首链完成。
- 工作树中浏览器插件、`pnpm-lock.yaml`、P2g 测试和两份 test-only 文件属其他现场改动，精确提交排除它们。
