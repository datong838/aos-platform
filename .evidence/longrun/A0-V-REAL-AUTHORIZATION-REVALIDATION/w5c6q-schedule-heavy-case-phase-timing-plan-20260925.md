# W5c6q 旧 Schedule 单项长时路径分段计时方案（2026-09-25）

上位 W5c6p 已将三模块 17 项缩到唯一 `test_claim_ack_and_input_ack_loss_recover_original_group_once` 未终态；其余 16 项通过。中断栈曾在 canonical JSON，但那只是单点样本，不能归因为 CPU 热点或死锁。本波只在隔离一次性 PG 为该测试取完整终态与分段证据，不读商城真实源、不触发真实 Schedule。

## 文件级九步

1. 复习 W5c5t/W5c6p、Runtime `execute`、旧测试的 ACK-loss 三段与 canonical JSON/Store 调用链。
2. 本方案先提交。候选最小文件仅 `services/aos-api/tests/extension_runtime/test_snapshot_schedule_runtime_pg.py` 的可选诊断计时（若需持久化）及 verification；生产代码暂不改。
3. 优先用 pytest 单项 `--durations=1`、隔离 PG 会话/进程采样，在 600 秒硬上限内取得终态；每 50 秒只读采样，超限中断保留未知，不重试真实操作。
4. 如需改测试，先证明计时不改变断言、数据库事务、模拟源次数、ACK-loss 次序；仅加单调时间分段观测，不改变通过条件或延长生产 deadline。
5. 专项单项与旧其余 16 项/安全累计 111 项回归；不能把不同进程的 16+1 机械宣称同一次三模块全绿，须说明证据组合边界。
6. 浏览器只读 A0-V rev4 disabled；不保存/运行/冲刷队列。
7. 复审性能证据和方案/代码一致性，区分“慢但终态通过”与真正卡滞；真实 closure 门仍独立拒绝。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回。
9. 下一波按计时证据决定是否最小优化 fixture/热路径，或转其他独立安全债；先方案后编码。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
