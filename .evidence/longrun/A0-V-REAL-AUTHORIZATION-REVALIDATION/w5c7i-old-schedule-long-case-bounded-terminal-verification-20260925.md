# W5c7i 旧 Schedule 长时用例有界终态核验（2026-09-25）

## 九步结果

1. 复习 W5c6t–z、231/231-9 与旧 `test_claim_ack_and_input_ack_loss_recover_original_group_once`；source 是测试 fixture，使用 `aos_test_%` 隔离库。
2. 方案 `91198ef6` 先提交；本波无生产/测试代码修改。
3. 单独启动旧 12-source ACK-loss 长测。启动时 UTC 读回 `2026-09-25 06:47:06`；随后进程 `ps etime` 读回 `26:44`，超过计划的 900 秒表观上限，立即 Ctrl-C。pytest 正式退出码 **2**、`KeyboardInterrupt`，其自身报告 `7 warnings in 697.36s (0:11:37)`，与 `ps etime` 和外部时钟读数不一致。不能确认单调运行时长达到 900 秒，也不能声称有正式 pass/fail；保守冻结，不在本波重跑。
4. 临时 `aos_test_%` 数据库读回 **0**。未对真实库迁移；测试中断不是断言失败，也不是 GREEN。只读 DB 等待诊断因容器无通用 `postgres` 角色未获得，未尝试扩大权限。
5. Host/closure + W5c7c/e/f/h + W5c5k–z/W5c6a–z/JDBC 累计 **211 passed**；旧长时单项不在这 211 内。真实 gate 仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled closure Receipt=0。
6. 浏览器只读核对时间 `2026/9/25 15:32:17` CST：A0-V Canonical “已配置 · 已停用 · 版本 4”，运行状态“数据组已停用”；1 条待同步写操作未冲刷。临时 Vite/测试 PG 均已停。
7. 方案/代码一致性：未删除 callback 前后、12 成员 parent/running schedule 重读；计时口径冲突和超长非终态属于未解决测试债，不能靠更长等待标绿。真实 Host/closure 边界未改变。
8. 本文件提交后 CAS 更新 docs/AOS 上下文与 Prime 独立长记忆并读回，docs 提交另记。
9. 下一波 W5c7j：先方案，使用单调计时和隔离 PG 只读诊断明确长测的等待/查询热点，并审查不削弱授权读回的最小查询层优化；未证明前不改生产，不重发旧测试作为授权。

旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读；230 L0 挂起；dev-org 零 canary；m1 单写不 push。
