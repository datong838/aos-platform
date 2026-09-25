# W5c7p Claim Loop 身份与历史行不可变对抗方案（2026-09-25）

## 上位边界

231/231-5 要求当前授权、原代次/截面与失败恢复不可弱化。W5c7n 实测 claim Owner 为热点；W5c7o 的 15+2+1 项只锁定现有重复读的 fail-closed 行为，尚未证明可复用。`pipeline_snapshot_claim_context` 将原组 source claim loop 绑定同连接、线程、事务、scope、actor、成员；`a0v_024` claim 行 RLS、历史不可变触发器和 runtime SELECT/INSERT grant 只是历史边界，不代表当前控制不会改变。

## 文件级九步

1. 复习 231/231-5、W5c7o、ClaimLoop 源码、a0v_024 与现有隔离 PG fixtures；核对 m1 和隔离容器。
2. 本方案先提交。新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c7p_claim_loop_identity_and_immutability_pg.py`、审计和 verification；不改 `aos_api/`、迁移、真实 DB 或部署。
3. 纯合同负例：同连接/线程/事务/tenant/actor/member 通过；错连接、线程、事务、tenant、actor、member 全部 fail closed，不可将一次校验当跨边界缓存。
4. 专用 18432 PG：原始 claim 已存在后，以 runtime 角色尝试 UPDATE/DELETE 需被权限拒绝；以管理员角色尝试 UPDATE/DELETE 需被 immutable trigger 拒绝；租户 RLS 读另租户为零。每个失败事务回滚，不改变 fixture 数据。
5. 跑新专项和相关 SourceClaim/InputOwner/原组负例，以及既有短累计；检查临时 schema/库 0，用后停 PG。旧长例不重跑。
6. 浏览器只读 rev4 disabled，不保存/运行/冲刷队列。
7. 复审：这些测试不能替代当前安装/控制/Run 的并发可见性证明；若未测精确锁序，结论仍不授权生产 claim 复用。
8. verification 提交后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立长记忆，读回。
9. 下一波 W5c7q：方案先行，针对当前控制与 Run 的并发可见性和锁序做有界隔离 PG 对抗；仍不触真实 closure。

旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。
