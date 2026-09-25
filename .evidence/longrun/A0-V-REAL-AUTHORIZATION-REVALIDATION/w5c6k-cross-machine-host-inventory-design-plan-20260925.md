# W5c6k 跨机器 Host inventory 权威边界设计（2026-09-25）

上位 `ar1_003` 绑定 DB 登录角色→Host identity 与 workspace assignment，并保留不可变 revision；W5c5f/j 证明受管目录/本机 PID/已知 DB 会话均非全机活动证明。目录缺 Host 实例 heartbeat/进程启动 epoch/租约 TTL；`pg_stat_activity` 无法排除离线但仍持外部权限的非受管 Host。正式 closure 门因此仍 `topologyComplete=false`。

## 文件级九步

1. 复习 `ar1_003` 表/读函数、RuntimeHost materialize、`a0v_093/094` lease、W5c5f/j 发现器和正式 closure 门。
2. 本方案先提交。本波只新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6k_cross_machine_inventory_design.py` 无效应合同与 verification；不迁移真实库、不改 Host/worker/closure。
3. 合同固定现状：identity/assignment 有 revision/history 但没有实例 heartbeat、运行 epoch、DB-clock freshness/expire；目录只返回被分配 scope，非全机运行实例 inventory。`pg_stat_activity` 是当前连接快照，不是离线/非受管排除证明。
4. 候选权威须具备受管节点集合完整性来源、每实例不可变身份+启动 epoch、短 TTL 的 DB-clock heartbeat、失联后的 revoke/隔离、旧 generation/外部权限 fencing、与 closure 同事务重读/锁定；任缺一项不得宣布 topologyComplete。
5. 专项静态合同 + W5c5k–z/W5c6a–k 累计回归；无真实 side effect。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审：此波设计不能排除非受管 Host，不能让 `a0v_091` 因 24h 到线自动执行；到线后仍需新方案、唯一 key、Owner 门及独立读回。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6l：若可复用现有 lease 体系，先在隔离 PG 设计受管实例心跳/启动 epoch 与关闭门的同事务锁；否则保持 no-effect 并明确基础设施缺口。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
