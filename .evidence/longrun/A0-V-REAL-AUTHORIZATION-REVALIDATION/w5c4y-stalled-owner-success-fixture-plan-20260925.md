# W5c4y stalled Owner 隔离成功/重放 fixture 方案（2026-09-25）

上位 231 A0-V、231-9 BG-00，W5c4x 已证拒绝侧 189 passed；真实原组尚未满 DB 严格 24h。本波仅在自动销毁的隔离 PostgreSQL，用原定义/claim Owner 构造 12 Run，验证正式 stalled Owner 的成功、同 key 重放与失配拒绝。**绝不针对真实 group 调用关闭**。

## 文件级九步

1. 复习 `a0v_091`、`pipeline_snapshot_stalled_group_closure.py`、`test_pipeline_snapshot_schedule_definition_pg.py` 的 fixture 与 claim Owner、W5c4t 时间门。
2. 文件清单：本方案；新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c4y_stalled_owner_success_pg.py`；本波 verification。生产 Owner/迁移不变。
3. 最小 fixture：使用原配置 Owner configure→enable→原 claim Owner v2 产生唯一 12 Run→disable，隔离库内把 12 fixture `started_at` 置于 DB clock-25h，保持 executor_id 空/无终态；使用独立非 superuser maintainer 会话调用原 Service。测试只看 receipt、12 failed Run、业务未接受、同 key replay 无新增 Receipt、失配 key 失败回滚。
4. 专项：先验证 fixture/角色环境，RED 或明确环境修复；若隔离 DB 合同拒绝或 fixture 不能忠实构造，不修改 Owner 抢过测试，记录真缺口。
5. 累计：合并 W5c3/W5c4、request/拒绝合同与本成功 fixture；慢集有界且按完成结果计数。
6. 浏览器只读核 12 单路计划与整组页，绝不触发运行。
7. 一致性：fixture 成功不能授权真实关闭；effects 计数如 fixture 为零，只证明无副作用场景，真实 effect 非零仍由原 SQL 只读证据和后续真实全门禁复核。
8. verification 提交后 CAS 同步 AOS 上下文及 Prime 独立受管记忆、读回。
9. 下一波 W5c4z：继续非零 effects/事务回滚测试；若严格 24h 已到且全门禁新鲜，独立真实关闭方案与唯一原 Owner 动作，随后定义退休。

任何未知提交边界或真实组漂移冻结；不补跑旧代、不读取商城源行、不 push。
