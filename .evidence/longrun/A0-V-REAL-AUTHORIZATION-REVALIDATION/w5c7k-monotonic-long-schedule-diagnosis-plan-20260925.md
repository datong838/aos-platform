# W5c7k 单调有界旧 Schedule 长测诊断方案（2026-09-25）

W5c7i 旧 12-source ACK-loss 单项无终态且计时口径冲突；W5c7j runner 已用短项证明单调上限与进程组中断。W5c6u–z 已定位 `_bound_parent`/每成员重读为热点，但未授权删减。本波只在隔离 PG 诊断，不改生产或旧测试。

## 文件级九步

1. 复习 W5c6u–z、W5c7i/j、旧用例与 runner 合同。
2. 先提交本方案；仅新增 verification，不修改代码。任何生产优化另开方案。
3. 在隔离 PG 以 runner **900 秒单调上限 + 5 秒宽限**、`AOS_TEST_SCHEDULE_TIMING=1` 运行一次精确旧用例；只认 runner `A0V_BOUNDED_TEST` 摘要和 pytest 正式终态。超时退出 124 即未绿，不重跑本波。
4. 收集阶段计时/完整性读回；若未输出也如实记载，不能推断具体卡点。确认 `aos_test_%` 临时库清理为 0。
5. 跑 Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/j/JDBC 累计回归；临时 PG 用后停。
6. 浏览器只读 rev4 disabled，不保存/运行/冲刷队列。
7. 复审长测终态和计划/代码一致性；真实 closure 始终 no-effect。
8. verification 提交后 CAS 更新 docs/AOS 上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c7l：若长测通过，补全旧三模块回归；若超时，先方案研究每事务 12 成员数据库往返的等价批量化/索引，必须保留 callback 前后重读和每成员 running binding；若断言失败，先方案最小修复。

旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读，230 L0 挂起，dev-org 零 canary，m1 单写不 push。
