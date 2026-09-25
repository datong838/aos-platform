# W5c6y Input `_load` Parent 子段计时方案（2026-09-25）

上位 W5c6x：隔离长时测试仍未终态；Input `_load` 三链合计约 61–78 秒，Policy `_load` 仅毫秒。Input `_load` 每次重读 group claim、原输入 SQL 和 12 个 `_bound_parent` 并验证哈希；这些 current 检验不可凭慢测删除。内联 SQL 不适合仅为诊断改生产代码。

## 文件级九步

1. 复习 W5c6u–x、InputOwner `_load`、GroupClaimOwner 和 `_bound_parent` 原实现、A0-V no-effect 边界。
2. 本方案先提交。仅修改 `services/aos-api/tests/extension_runtime/test_snapshot_schedule_runtime_pg.py` 现有 opt-in 探针及合同，另增 verification；生产/DB/部署零改。
3. 透明聚合三条 Input Owner 各自 GroupClaim `read_current` 与 `read_completed_current` 次数/inclusive 耗时，并对 InputOwner 模块导入的 `_bound_parent`、`_digest` 记录合计次数/耗时；只标签/次数/秒，不输出参数、行或引用。未启用零包装、返回/异常原样。全局函数合计不可归因特定 Owner，使用计数交叉检验。
4. Completion `finally` 一次性输出；隔离 PG 长时单项外部 300 秒硬上限、20 秒清理、核实临时库。若共享模块包装污染其他测试，收窄到单项运行，不允许改生产。
5. 专项、旧 Schedule 非长时、W5c5k–W5c6y/JDBC 累计回归；超限单项不计 GREEN。
6. 浏览器只读 rev4 停用及真实 closure 拒绝，不保存/运行/冲刷队列。
7. 复审 Input `_load` 未覆盖的内联 SQL、验证与时钟成本；不能用剩余时间推出单个数据库调用慢，下一波再选择可证明透明的测量。
8. verification 后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立记忆并读回。
9. 下一波 W5c6z：依据 claim/parent/hash 结果，先方案再审最热路径或转向 Host 拓扑缺口；真实门仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
