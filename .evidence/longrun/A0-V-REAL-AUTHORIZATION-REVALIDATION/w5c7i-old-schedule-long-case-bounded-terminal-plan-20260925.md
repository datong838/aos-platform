# W5c7i 旧 Schedule 长时用例有界终态核验方案（2026-09-25）

## 上位与问题

W5c6t–z 的 12-source ACK-loss 旧 Schedule 用例多次在 180/300/600 秒观察窗未有正式终态；InputOwner `_load` 的 `_bound_parent` 读回是已测热点（1357 次/172 秒），但 callback 前后及每成员 running binding 不可凭性能印象删除。此波在隔离 PG 上给长时用例一个明确上限，优先取得**正式 pass/fail**，不改安全读回。

## 文件级九步

1. 复习上位 231/231-9、W5c6t–z 与旧测试 `test_claim_ack_and_input_ack_loss_recover_original_group_once`，确认 source 是 fixture、只用隔离数据库。
2. 本方案先提交；仅新增 verification，不改生产或测试代码。若发现真实最小缺陷，再另开 plan 波次，不在本波即兴改。
3. 在隔离 PG 单独运行该用例，记录开始/结束时间、PID/退出码、正式 pytest 终态；900 秒硬上限，超时只中断测试进程并核临时库清理，不标 GREEN、不重发真实 attempt。
4. 专项结果若 pass 才计 GREEN；若 fail 分析断言/堆栈；若超时记未终态及资源路径。不会以阶段日志、计数或 17 个短项通过代替正式结果。
5. 运行既有 Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/JDBC 累计回归；测试 PG 用后停。
6. 浏览器只读 rev4 disabled，不保存/运行/冲刷队列。
7. 复审有界长测结果与方案/代码一致性；真实 closure 保持 no-effect。
8. verification 提交后 CAS 更新 docs/AOS 上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c7j：依据正式长测结果，若失败先方案最小修复；若通过补全三模块旧 Schedule 回归，若仍超时则做不减安全读回的查询层优化可行性方案。

m1 单写不 push；不读商城源行、230 L0 挂起、dev-org 零 canary；旧 attempt 不重发、不手工 `run_definition`。测试未知结果先冻结边界。
