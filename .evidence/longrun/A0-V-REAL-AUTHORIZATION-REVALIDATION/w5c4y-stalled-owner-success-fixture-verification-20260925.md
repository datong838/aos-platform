# W5c4y stalled Owner 隔离成功/重放核验（2026-09-25）

上位 231 A0-V、231-9 BG-00。方案先行 `6e10ad97`，测试与方案细化 `68321376`。本波只在自动销毁的隔离 PostgreSQL 调用原 `a0v_091`，真实 group 未关闭。

## 九步执行与证据

1. 复习原 SQL/Owner、定义与 claim fixture、严格 DB clock 24h 门。
2. 文件仅本方案、新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c4y_stalled_owner_success_pg.py` 与本 verification；生产 Owner/迁移零改动。
3. fixture 原 Owner configure→enable→v2 claim 12 Run→disable；同一可回滚事务以非 superuser maintainer 身份调用原 SQL。先设 -23h：SQLSTATE 55000，12 running、closure Receipt 0；再设 -25h：12 failed、`businessAccepted=false`、Receipt 1；同 key 重放 `replayed=true` 且同 receiptId；漂移 ref 拒绝 SQLSTATE 40001。测试连接不 commit，teardown rollback。
4. 定向 **1 passed，7 warnings**。初版因 fixture 显式 commit 污染同一隔离测试库，累计出现 16 个重复键错误；已改为同事务会话身份切换、无 commit，并重测。该中间 RED 不计作通过。
5. 有界累计 W5c3/W5c4、定义、attempt、lease、preparation 等 **190 passed，7 warnings，23.37s**。隔离测试数据库已停止；此前更宽恢复 PG 集合中止事实不被覆盖。
6. 临时 5174 浏览器只读：单路页可见 12 条已注册计划；整组页可见入口及“尚无数据组配置”，不能独立证明后台 rev4，故 `BROWSER_PARTIAL`。无保存、运行或队列冲刷；临时页/前端已关闭。
7. 方案与代码一致：正式成功、重放、早关拒绝、漂移拒绝在零 effects fixture 获证；真实 group effects 非零，不能以此授权真实关闭。实时只读结果 `STALLED_WAIT_24H`、`automaticAction=false`，严格最早时间 `2026-09-25T20:00:04.800482+00:00` 后。原 12 Run/定义 rev4 禁用保持，Store Receipt 无新增。
8. 本 verification 提交后 CAS 同步 docs/AOS 项目开发上下文及 Prime 独立受管记忆并读回。
9. 下一波 W5c4z：隔离库补非零 effectEvidence/事务回滚门；若真实组严格 24h 到线，另起独立真实关闭方案并重新全门禁复核，唯一调用原 Owner，随后正式退休。

不读取商城源行、不补跑旧代、不重启 Host、不 push；230 L0 继续挂起。
