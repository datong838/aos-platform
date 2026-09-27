# W5CB4 E06：数据源登记安全入口验收（2026-09-28）

## 完成范围

承接 E05 审计和 E06 方案 `3634cd3c`，只改 `apps/web/src/pages/DataPage.tsx` 与其交互测试。正式 `/v1/sources` Owner、数据库及连接器后端未变；不存在本波新建的真实数据源或源读取。新建入口改为 `apiPostUnqueued`，先权威读现有 ID/配置修订，写前保存仅含 tenant 作用域、ID、运行时和预期修订的 pending 标记。本次 POST 明确响应且权威读回同一配置修订后才清除；未知/漂移在页面重开与租户切换后保持冻结，只允许只读对账。同 ID 元数据不等于原请求 Receipt，不能据此重发。保存不再隐式调用 `/v1/sources/{id}/test`。

## 验证

- `DataPage.source.interaction.test.tsx`、`Wave3bW4Truth.test.ts`、`sourceSetup.test.ts`：21 passed。覆盖成功、不排队写调用、无隐式 probe、漂移冻结、marker 不含密码、跨刷新与租户切换保留 pending。`tsc --noEmit -p tsconfig.json` 通过，Vite production build 通过，`git diff --check` 通过。
- 今日最新代码 + 当前命名卷 `aos-a0v-recovery-pg-data` 的完整重启已在 E04 验证时执行；E06 检查时容器 `/aos-a0v-recovery-pg` 为 running 且挂载仍为该卷，当前 API 8080 OpenAPI=200、前端 8434 `/data`=200。E06 前端修改由运行中的 Vite 服务呈现，尚无 E06 改动后的第二次数据库容器重启；下一次每日全栈重启仍必须使用最新代码与此当前卷，不得把前端热更新冒充再次完整重启。
- 内置浏览器实际 `/data` 显示数据源总数 0、近 24 小时同步 0；打开“新建数据源”并走到运行时选择，未填写凭证、未创建、未调用 `/test`、未同步。页面显示的 12 数据集不是已验证的商品对象。

## 一致性与剩余门

本波只保证未来数据源登记的客户端失败关闭，不证明后端已拥有幂等 Receipt，也不证明源可连、真实商品已更新、SourceSelection/Automation/TaskRun 已获准。跨标签页同毫秒并发登记仍无服务端单写 Receipt；正式重试需要 Owner 层 Receipt/未受理证明，而不是手工清 pending。商城源数据继续不读；旧 12 Run 不重放；Host/worker/Provider 均不因本波打开。下一波应优先按 231-9 首链补安全的正式来源配置和 SourceSelection 准入生产者，在真实源读授权前保持纯配置/只读验收。
