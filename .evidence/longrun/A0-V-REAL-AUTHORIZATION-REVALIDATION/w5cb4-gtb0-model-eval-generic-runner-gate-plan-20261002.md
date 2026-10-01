# GT-b0 Model/Route 通用 Eval Runner 禁入文件级方案

基线 AOS-001083 / m1 `83de66c4`，Task `W5CB4-GTB0-MODEL-EVAL-GENERIC-RUNNER-GATE-20261002`。复习 231-5、BG00GT 清单、GT-a 预检及原 EvalRunner、预算/容量 Owner。用户只批准评测用途设计、代码和隔离验证；当前真实库仍只读，Provider/Host 无执行授权。

## 已定位缺口

`AipEvalRunner.run_by_contract` 和 `run` 对 Skill target 拒绝任意 callback，但 `registered_model` 和 `model_route` 可进入 caller 传入的 `execute_target`。GT-a 永远 `executionAllowed=false`；通用 Runner 无 maker/checker、费用 hold、容量预留、发送意图或当前候选同事务重验。现有 `AipBudgetReservationStore.reserve` 强制 `Task` 和 ActionApprovalEvent，`AipModelCapacityReservationGate.reserve` 强制 AgentRun；它们不能用假 Task/AgentRun 代替 Model EvalRun。直接将 Model/Route 交给通用 callback 可产生未经 GT-b 授权的外部效果。

## 本子波文件与判据

- `services/aos-api/tests/aip/test_aip_eval_runner.py`：先 RED，Model 和 Route 两种 target 分别覆盖 `run` 及 `run_by_contract`，断言在 artifact/target/judge callback 前拒绝，EvalRun/Report/Gate 表 0 行。保留 Logic 既有正向测试与 Skill 拒绝测试。
- `services/aos-api/aos_api/aip_eval_runner.py`：在现有 Skill guard 相同位置最小扩充为三种目标的 fail-closed；不改普通 Logic 等 Eval、Report/Gate、普通 Model resolver，不调用 Provider。
- 只在隔离 PG schema 跑专项及相邻回归，当前权威卷不迁移、不写；`py_compile`、diffcheck。无 UI 变更，浏览器不适用。

## 完整 GT-b 后继

单独设计 Model EvalRun 的一等持久 request/approval/预算容量/发送意图 Owner：精确 source/target/head/Price/Policy、独立 maker/checker、固定费用上界与截止、同事务重读、幂等键；不能借用 Task/AgentRun。随后受限 transport 和 Report/Gate/页面逐波施工。GT-b0 是必要的禁入修复，不声称首评可执行或自然首链达成。
