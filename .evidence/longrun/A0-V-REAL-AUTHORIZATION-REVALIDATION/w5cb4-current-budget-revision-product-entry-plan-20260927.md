# W5CB4 当前预算修订产品入口波（2026-09-27，编码前）

## 上位与现状

- 231 BG-00/A0-V 要求在产品内配置预算、金额/审批明确，安装 approved 不能靠开发者填库启用。`aos_current_preview_20260927` 当前八项配置全 0，安装页已显示缺口。BudgetRevision 是预算策略的先行正式引用，当前后端 `/v1/aip/budgets` 有 publish/get、乐观版本与幂等 Receipt，但 Web 无创建/精确回读入口。
- 本波仅增加 UI 入口，不自动创建预算、不选择金额/审批人或告警阈值、不启用 Runtime、不触发模型或商城源。`BudgetRevisionCreate` 固定 development/CNY/hardStop/unknown=block；日/月金额以分为单位且月≥日，有用户填写的告警阈值、生效起止、owner、overBudgetApprover、lifecycle。当前生产预算是否可用仍需用户/真实审批选择，不能因表单存在计为 ready。

## 文件级

1. `apps/web/src/pages/s2/BudgetRevisionSetupPanel.tsx` 新增独立受控表单，仅允许先创建 draft；active 激活须独立确认并保持原版本/If-Match/幂等规则。为避免本波误授权，首切片只做 draft 创建与 GET exact 回读，不自动激活；已有预算按 ID 只读查询，不做覆盖。
2. `apps/web/src/pages/s2/CapacityPage.tsx` 嵌入面板，安装页既有 `/aip/capacity` 导航可到。新增 `BudgetRevisionSetupPanel.test.tsx`，覆盖金额单位、告警阈值、时间窗、租户/金额/哈希精确回读；`client.test.ts` 覆盖离线不排队和原幂等/版本头不丢。组件实现中在 POST 和 GET 后均重核身份、单次 attempted 锁阻止未知结果换键重发；浏览器验收空表单不发命令。`apps/web/src/api/client.ts` 增加带 headers 的明确不排队 POST helper，配合 `apiGetAuthoritative`；不可用普通 `apiPost` 的离线排队语义，不影响配额现有逻辑。
3. 专项与相邻累计、TypeScript、浏览器验收、方案/代码复审、verification→m1 精确提交。真实金额/owner/approver 未经用户输入不提交任何 Budget 行。下一波再做 BudgetPolicy 正式表单、active 生效与安装 exact 引用；不能将 draft 计为当前候选。

## 停止条件

- 如公共 POST 的幂等/回读不可证明或响应来源未知，页面只显示“提交状态待对账”，不换 key 重发。
- 如缺产品身份/权限，不引入管理员代填或数据库直写；只读阻断并登记。
