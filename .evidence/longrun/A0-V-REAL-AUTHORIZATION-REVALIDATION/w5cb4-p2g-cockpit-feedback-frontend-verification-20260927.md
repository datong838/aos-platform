# W5CB4 P2g18：Task Cockpit 反馈页面接线验证

日期：2026-09-27。方案先行提交 `af989d30`，上游只读 API `e7e65f0f`。本波只做前端只读展示，不开启自然 worker、不改变任务或 Wiki 写路径。

## 文件级实现

- `apps/web/src/api/ecommerceWorkshop/contracts.ts`、`parser.ts`、`client.ts`：新增严格三段 DTO/解析/有界 GET；校验租户、固定顺序、目标 Receipt、正式评估与候选状态，拒绝伪造 `executionAuthorized=true`、错 hash/多字段/跨租户。客户端只发 `limit=1..20` 的 GET，不含命令。
- `apps/web/src/components/workshop/TaskCockpitPage.tsx`：在原三个通用复盘/改进/Wiki 面板之外追加独立“内容评审后的经营反馈”只读区；中文标题/摘要与 `证据不足`/`待治理` 分开；审计 exact refs 默认折叠，空/读取失败不回退旧卡或演示值。原通用面板与 TaskRun 命令未改。
- 邻近三个测试文件覆盖合同拒绝、客户端租户/limit、页面三段及失败态。

## 验证和浏览器边界

- 前端专项：87 passed；全量前端回归：**301 files、2664 passed**；TypeScript `tsc --noEmit` 和 Vite production build 通过。`git diff --check` 通过。
- 浏览器：只读确认 8080/18181/5173 均无原服务；临时在 127.0.0.1:5173 起 Vite，真实浏览器打开 `/workshop/task-cockpit`。页面显示“工作台目录读取失败”“当前离线”；Vite 代理 `/v1/ecommerce-workshop/modules` 等到 127.0.0.1:8080 得 `ECONNREFUSED`。路由在安装目录门前停止，未能在真实当前实例验收新反馈卡。临时 Vite 已停止，5173 无监听。
- 因此浏览器门结论是 **BLOCKED_BY_API_OFFLINE**，不是页面或业务 GREEN。测试夹具的三段渲染只证明代码逻辑；不能当作当前栖月汇已安装、已自然反馈或 Wiki 入库。下次 8080 可安全运行并有当前签名安装时，补同租户有权/空/失败态浏览器验收。

## 方案一致性与下一步

- 方案要求的业务/审计分层、pending 与正式入库区分、默认 no-effect 均保持；没有读取商城源数据、回放旧十二 Run、手工 `run_definition`、Provider 或外发。静态卡测试不是生产结果。
- 下一波优先只读核当前签名安装、来源、审批、Runtime Host 与后半段自然消费者的启用条件；补第二段提交后独立读回。若实例仍未安全上线，继续独立后端安全门工作，不为了页面 GREEN 强启生产或跨越未知提交边界。
