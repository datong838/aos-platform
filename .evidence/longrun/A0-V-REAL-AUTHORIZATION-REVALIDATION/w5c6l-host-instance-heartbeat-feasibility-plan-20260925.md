# W5c6l 受管 Host 实例心跳/启动 epoch 隔离可行性方案（2026-09-25）

上位 W5c6k：`ar1_003` identity/assignment 有版本历史但没有实例存活权威。`a0v_093` 已有每 scope token/epoch/DB-clock TTL/event，`a0v_094` 在 worker 原事务取同一 advisory lock 和行 share lock；这可作为受管实例 heartbeat 候选，却不能证明非受管 Host 不存在。真实库仍只有 `a0v_092`，不能启用。

## 文件级九步

1. 复习 `ar1_003` 目录、`a0v_093/094` 受管 lease/acquire/renew/worker fence、W5c6k 完整性要求与正式 closure `a0v_091`。
2. 本方案先提交。本波仅新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6l_host_instance_lease_feasibility_pg.py` 隔离 PG 合同与 verification；不改生产 migration/Host/closure/真实 DB。
3. 隔离 PG 验证受管 Host lease 的 token/epoch/DB-clock expiry 可表示一个 scope 的受管实例活性；current holder + worker guard 同事务可阻止 concurrent release/renew，过期旧 epoch 被拒绝。
4. 用无效应分类明确：此证明只覆盖目录内已分配/已登录的受管实例，无法排除非受管进程、其他物理机或外部 source effect；不能直接替换 `FULL_MACHINE_HOST_TOPOLOGY` 门。启动 epoch 与 lease epoch 也不能盲目等同。
5. 专项隔离 PG + W5c5k–z/W5c6a–l 累计回归；不写 Store/商城源行。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审：真实 closure 需要同事务 Owner 门、新方案/唯一 key、严格 24h 与完整拓扑；此波任何 PG GREEN 不授权 closure。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6m：先设计可审计 Host 节点集合完整性来源与非受管排除；若不存在可信来源则明确外部基础设施阻断，继续处理独立研发债而不循环制造放行幻觉。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
