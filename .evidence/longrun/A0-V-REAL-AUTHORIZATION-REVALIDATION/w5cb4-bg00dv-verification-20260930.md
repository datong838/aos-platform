# W5CB4 BG00dv｜签名 BI 配置 UI 只读接线验证

## 范围与结果

按本波文件级方案，只改运行实例候选和上线审批职责计划的只读引导。`/apollo/assets` 的职责计划链接带当前 installationId 到 `/aip/production-contracts`；目标页显示来源安装和返回安装列表，明确查询参数不是权威。页面没有调用 `bi-preparation` POST，也没有开放提交按钮。候选仍需与当前 installation revision/ETag 对齐；过期时不展示八候选数量。运行准备按钮的原 Host/Owner 禁入条件未改。

| 验证 | 命令与证据 |
| --- | --- |
| RED | `apps/web` 下 `./node_modules/.bin/vitest run src/pages/s2/assetBundles/RuntimeInstallationPanel.test.tsx src/pages/s2/ProductionContractsPage.test.tsx --reporter=dot`，带工作区 Node PATH；文案和安装路由两组新增断言各先失败，随后通过。 |
| 专项 | 同命令，exit 0，2 files / 29 tests passed。 |
| 前端累计 | `./node_modules/.bin/vitest run --reporter=dot`，exit 0，314 files / 2733 tests passed，日志 `/tmp/aos-bg00dv-full-final.log`。 |
| 构建 | `pnpm --filter @aos/web build`，exit 0，TypeScript 与 Vite 构建通过；仅有既存大 chunk 提示，日志 `/tmp/aos-bg00dv-build-final.log`。 |
| 范围复审 | `git diff --check` exit 0；只读链接和文案没有新 API mutation、权限判定或运行开关。未触碰当前/clone DB、Host、worker、Provider。 |

## 验收边界与下波

当前没有可调用的 browser-pilot，未作真实浏览器截图/交互验收；单测与构建不能代替此项。正式 OIDC actor、六 active AgentInstance、当前 signed-approved 安装和 Host/Owner 仍缺正向证据，故本波只关闭 UI 误导风险，不关闭 E17 首链。下波 BG00dw 应先实现服务端只读的精确 BI 准入投影，再决定何时开放受限产品提交；继续只读核验正式身份与来源。
