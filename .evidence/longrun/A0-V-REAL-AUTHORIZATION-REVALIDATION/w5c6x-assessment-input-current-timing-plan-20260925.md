# W5c6x Assessment/Input Current 实际分支计时方案（2026-09-25）

上位 W5c6w：Relationship `_load`/`_restore` 仅毫秒级，`materialize_current`=0；旧长时测试走 Assessment `_run`→Input `run_current`，其中包含完整 12 成员当前控制、原始 claim/parent、Policy 与哈希复核。嵌套 inclusive 耗时不能相加，不能凭测量删除安全校验。

## 文件级九步

1. 复习 W5c6u–w、AssessmentOwner/InputOwner/PolicyOwner/GroupOwner 原代码与 A0-V no-effect 边界。
2. 本方案先提交。仅改 `services/aos-api/tests/extension_runtime/test_snapshot_schedule_runtime_pg.py` 现有 opt-in 探针及合同，另增 verification；生产/DB/部署零改。
3. 对 Object/Link/Retire 三个 Assessment Owner 的 `_run`、其 Input Owner 的 `_run`/`_load`、Policy Owner 的 `_load`、Group Owner 的 `run_current` 聚合调用次数与 inclusive 单调耗时；只打印标签、次数、秒，默认零包装，返回/异常透明，不输出业务内容。
4. Completion `finally` 一次性输出；隔离 PG 长时单项外部 300 秒硬上限、20 秒清理并核实临时库。若探针影响运行路径或合同失败，回退测试侧更窄方案，不碰生产。
5. 专项、旧 Schedule 非长时、W5c5k–W5c6x/JDBC 累计回归；长时超限不计 GREEN。
6. 浏览器只读 rev4 停用及真实 closure 拒绝，不保存/运行/冲刷队列。
7. 复审 inclusive 归因和最热子段；不删跨提交 current，下一波只针对有证据的热点作等价性/锁等待审计。
8. verification 后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立记忆并读回。
9. 下一波 W5c6y：按实际 Input/Policy/Group 分段结果先方案，细查最热子段；真实门仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
