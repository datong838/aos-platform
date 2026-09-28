# W5CB4 E17-e｜未接正式审批的预算 active HTTP 发布失败封闭计划（2026-09-28）

## 依据与范围

- 231-9 BG-00 要求正式更新、影响预览和恢复；231-3 安装消费只认当前精确配置。E17-d 证明 `BudgetRevisionCreate` 可声明 active，但公开 POST 不核验独立批准权威。历史 R1 审批单只授权 R1 实现，不是当前运行批准。
- 仓库有 ActionApprovalEvent 的 exact 消费合同，但未发现预算修订发布对应的 ActionType/Proposal、当前审批事件与金额/窗口绑定。不能把该事件类型或 `approval:test` 字符串直接套到预算发布。
- 当前权威库八类 active 候选 0，真实库只读；本切片仅保护公开 HTTP 入口，暂不改内部 Store 及其隔离测试生成 active fixture 的能力。后续正式审批 Owner 确定后才开放正向发布。

## 文件级步骤

1. `services/aos-api/tests/aip/test_aip_budget_api.py`：新增 RED 断言，`active` 请求必须在调用 Store 前返回 422 `AIP_BUDGET_ACTIVE_APPROVAL_REQUIRED`；`draft` 仍经过原租户、幂等键、If-Match 发布；缺字段/跨租户继续原拒绝。
2. `services/aos-api/aos_api/routers/aip_budgets.py`：在公开 POST 验证 body 生命周期；active 时明确返回上述阻断，不允许伪造批准引用。draft 保持原逻辑；其他非 draft 生命周期亦不得借此入口形成当前 active。GET 不变。
3. 同目录 verification：记录 RED/GREEN、API 专项与相关累计、代码/方案复核；本波只证明公开 API 失败封闭，不声称 Store 内部所有调用路径已被授权或配置已恢复。浏览器 `browser-pilot` 可用时补页面，当前工具不可用如实登记。

## 风险与后续

- 这是有意收紧公开 API 的 active 发布。现有真实库没有有效 active 候选；若有尚未盘点的合法调用方，需通过正式 Approval Owner 接线后恢复，不能临时放宽。
- 下波盘点内部 Store 调用方并设计可复用的审批绑定：精确租户、预算 ID/revision/hash、金额、窗口、maker/checker、批准状态及撤销；再以新版本/Receipt/影响预览做正向恢复。
- 不写当前库，不启动 Host/worker/Provider，不使用假账号/审批，不读商城源，不碰旧 12 Run、dev-org 或 230 L0。
