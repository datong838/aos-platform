# W5c6w Journal 内部分段计时方案（2026-09-25）

上位 W5c6v：长时隔离测试 300 秒被中断，Object journal `read_current` 13 次/55.338 秒、`run_current` 1 次/12.053 秒，Link command 6 次/73.614 秒，Retirement 2 次/45.909 秒。跨独立 Store 提交与逐成员 current 重读均是安全边界；这些总耗时为嵌套 inclusive 时间，不能直接归咎哈希或数据库。

## 文件级九步

1. 复习 W5c6u/v、Relationship/Link/Retirement journal、Current materializer 的原调用链、事务与 no-effect 边界。
2. 本方案先提交。仅修改 `services/aos-api/tests/extension_runtime/test_snapshot_schedule_runtime_pg.py` 测试专属探针及合同，另增 verification；生产/DB/部署零改。
3. 在原聚合之外，以相同 opt-in 透明包装 Relationship 的 `_run_current`/`_load`/`_restore`，Assessment 的 `materialize_current`，Link/Retirement 的 `_operate`；计数与 inclusive 单调耗时，标签/次数/秒数而已。嵌套子段不能相加作为总耗时，且不得输出引用、行、参数。默认零包装，返回/异常原样。
4. Completion `finally` 一次性输出，隔离 PG 单项外部 300 秒硬上限、20 秒清理，核实临时测试库。若静态方法包装的 descriptor 语义不透明，则放弃该子项并在 verification 说明，不扩张生产改动。
5. 探针专项、旧 Schedule 非长时、W5c5k–W5c6w/JDBC 累计回归；超限单项不计 GREEN。
6. 浏览器只读 rev4 停用与真实 closure 拒绝，不保存/运行/冲刷队列。
7. 复审子段归因与方案/代码一致性；下一波只针对有证据的热函数审计，不删跨提交 current。
8. verification 后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c6x：根据子段数据先方案，细查最热内层函数或隔离 PG 等待；真实门仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
