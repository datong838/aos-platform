# W5c5k worker 同事务 fencing 原语方案（2026-09-25）

上位 W5c5h 排他设计、W5c5i `a0v_093` 隔离 PG、W5c5j 默认关闭的 Host opt-in。真实库仍未迁移，生产 Host/worker 不启用。当前生产 worker 有 Runtime Host 核心、product-event、analysis-data-requirement、baseline-assessment 三条业务路径；其中一次 tick 可进入多个独立 DB transaction，且外部 effect 与 Receipt 是独立机制。只在 tick 前检查 `host_ready()` 不构成 fencing。

## 文件级九步

1. 复习 `a0v_093` 租约头及 acquire/renew/release、Runtime Host 和三类业务 worker 的全部写事务，列出独立 side-effect 边界；确认真实迁移头和角色权限。
2. 本波只加 additive `services/aos-api/alembic/versions/a0v_094_host_lease_worker_fence.py` 与 `services/aos-api/tests/extension_runtime/test_a0v_w5c5k_worker_fence_pg.py`；不改已有 worker 或真实 DB。这个范围提供后续逐事务接线所需的受限 guard 原语，不将任何 worker 标为已围栏。
3. 原语要求显式租户、随机 token、epoch，受限 runtime 登录角色在其已有事务内调用；校验当前 Host 租约未过期且 token 哈希/epoch、当前 assignment/Host/OID 与真实登录角色均匹配。锁定同一租约行直到事务终止，防止在此事务未结束时发生新 Host take-over。错误/缺表/角色漂移 fail closed。不得返回 token 或授予直表权限。
4. 隔离 PG 覆盖有效当前 holder、缺租约/错误 token/旧 epoch/过期、assignment/OID 漂移、非 runtime 角色与直表拒绝、并发 take-over 等待写事务完成。需审计事务跨 TTL 边界的剩余风险，不能夸大为外部 side-effect fence。
5. 专项通过后跑 W5c3–W5c5k + Host/目录/definition 累计回归；隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 仍停用；页面不证明 DB 新迁移或 worker 权限。
7. 本波的 guard 是**未接线原语**：真正逐 worker 同事务调用、旧角色停机撤权、全机清单/第二 Host=0 尚未完成。真实库仍 a0v_092，禁止启用 W5c5j flag、禁止真实旧组关闭。任何未知边界冻结不重发。
8. verification 落盘/提交后 CAS 同步 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5l：从最窄的单事务 owner/worker 写路径开始 opt-in 接线与失权故障注入，逐路径推进；未全覆盖前不启用真实 Host。

m1 单写不 push；230 L0 挂起；商城源行不读；dev-org 零 canary；旧 attempt 不重发。
