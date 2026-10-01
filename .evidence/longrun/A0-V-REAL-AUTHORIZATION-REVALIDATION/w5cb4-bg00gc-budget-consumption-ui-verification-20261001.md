# BG00GC 已批准预算启用UI验证

基线AOS-001043/b8d1dc01。复习231-5、436，采用现有BudgetCostReviewPanel及共享身份epoch/attempted guard，未复制状态机。

## 结果
- CostRef新增consume，POST/GET精确映射consumption-request，body仅proposalHash/decisionId；无调用者幂等key/actor/tenant。无队列重发。
- 启用仅原maker、同身份读取的approved未撤销未过期提议、原请求not_attempted且未尝试、明确确认时可点。点击前标attempted并保存原ref；unknown/刷新仅查询，身份切换丢弃迟到结果。
- Receipt严格字段/type/正整数revision/hash格式/proposal引用，并在有source时比对原hash/decision/budget/revision；查询同样传source校验。Receipt只称历史启用记录，不宣称当前执行权。URL仅保存ref/operation/attempted，无凭证/批准正文。
- 原decide/revoke路径保持，新增操作不启动Host/Provider/worker/业务Run。

## RED/回归/类型
- 首次pnpm测试因shell缺node失败，属于环境错误，不算RED。使用现有运行时PATH=/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH后，RED为6failed/7passed，缺consume控件/解析（/tmp/aos-gc-red.log，exit1）。没有安装依赖或修改锁文件。
- 实现后专项13passed/exit0。
- 最终 `pnpm test src/pages/s2/BudgetCostReviewPanel.test.tsx src/pages/s2/BudgetActivationReviewPanel.test.tsx src/pages/s2/BudgetRevisionSetupPanel.test.tsx`：23passed，exit0，/tmp/aos-gc-final-tests.log。
- `pnpm exec tsc -p tsconfig.json --noEmit`：exit0，/tmp/aos-gc-final-tsc.log空。git diff --check exit0。
- UI测试fixture是交互逻辑验证，绝非正式批准/启用预算证据。

## Browser-pilot实测
使用仓库Kitewright Skill和engine_adapter BrowserPilot，独立8097临时会话访问当前8434/aip/capacity，org-org/dev-project。没有手写CDP、注入账号/fixture或点击写按钮。
首次select被视口边界遮挡，保留失败截图；只用SDK点击可见审批select后Escape/Tab将费用操作滚入视口，select consume成功，再Tab至确认框。目标button.btn-primary:disabled matches=1。
截图 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-bg00gc-browser-verified-20261001.png`（197142bytes）已view_image核看，配套txt记录真实提取及禁用button。所有本次SDK会话已关闭。界面可切换、明确确认可见、无来源按钮禁用；下方数据源读取中/缺少凭证不算容量权威数据通过。

## 复审与边界
方案/实现/测试一致；服务端BG00GB仍是最终权威门，前端条件不授予权限。未连接/写入/迁移/重启当前真实库，正式API未reload；代码a0v127不代表当前库版本。E16禁入/E17首链pending，正式不同UID及价格/政策producer/真实Task风险证明未完成。Watchdog仍仅方案，Goal状态未修改；旧dirty保护，不push。
下一BG00GD核验合法development价格/政策producer及部署配置必要缺口，形成首链必要集；正式恢复波需备份可恢复、克隆全链和零执行窗口。
