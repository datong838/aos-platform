# W5CB4 当前预算修订产品入口 verification（2026-09-27）

## 本波结论与边界

- 已按同目录 plan 增加 `/aip/capacity` 的 BudgetRevision 草稿入口；这只是用户填写与权威回读入口，不是预算批准、激活、Runtime 绑定或可支付能力。
- 当前新库未由本波创建任何预算行。预算金额、告警阈值、owner、overBudgetApprover、生效窗口由使用者明确填写；页面不会暗中代填。表单固定 `development/CNY/hardStop=true/unknownUsageBehavior=block/lifecycle=draft`，不提供 active 按钮。
- 写入调用带一次性幂等键、`If-Match: 0`，不进入离线写队列；首次尝试后本页只允许原命令只读对账，不换键重发。POST 结果、GET 当前版本、租户、字段与 contentHash 需一致；身份在 POST 后及 GET 后均复核。任何未知、漂移或不一致都不宣称完成。

## 验证

- `apps/web` 专项与相邻 Vitest：`BudgetRevisionSetupPanel.test.tsx` 3、`CapacityPage.test.ts` 36、`api/client.test.ts` 4，共 43/43 通过。
- `apps/web` TypeScript `tsc --noEmit` 通过；`git diff --check` 通过。
- 当前本地浏览器 `http://127.0.0.1:8434/aip/capacity` 实见新增表单、告警阈值和七项其他空字段；点击空白「创建 draft 并核对」只显示“预算 ID、负责人和超预算审批人均须明确填写”，没有进入 attempted，也没有提交预算。未填真实金额/审批人，因此未做真实 POST 验收。
- 后端 `/v1/aip/budgets` 为已有租户作用域 BudgetRevision POST/GET，响应含 tenant 与 contentHash，字段契约同前端对齐；本波未修改后端或现有容量逻辑。

## 剩余与下一波

- 实际创建 draft、激活 BudgetRevision、BudgetPolicy exact 引用与安装运行准备仍为零候选，不能将本波记作配置就绪。需要真实业务金额/责任人/审批人及相应权限，不能由开发者编造。
- 下一波优先检查 BudgetPolicy 的正式 Owner/API 与当前产品入口，做独立的方案与最小 UI 切片；不得因预算草稿入口存在而绕过安装八类配置或支付/审批门。
- 既有 P2g30b 正向生产者 RED 测试和 `w5c8i` 测试专用文件不属于本波，保持原状；原 12 Run、商城源与旧卷不触碰。
