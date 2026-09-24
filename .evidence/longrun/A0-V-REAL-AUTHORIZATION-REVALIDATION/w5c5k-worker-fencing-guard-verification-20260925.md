# W5c5k worker 事务内租约 guard 原语核验（2026-09-25）

上位 W5c5h/W5c5i/W5c5j，方案 `1d2bc55c` 先行，实现 `99bdc62d`；仅隔离 PG，真实库/Host/worker 零接线、零迁移。

## 九步证据

1. 复习 `a0v_093` 租约行/目录授权、Runtime Host 及 product-event、analysis-data-requirement、baseline-assessment 的多独立事务写路径。tick 前 `host_ready()` 不构成同事务 fencing。
2. 仅新增 `services/aos-api/alembic/versions/a0v_094_host_lease_worker_fence.py` 与 `services/aos-api/tests/extension_runtime/test_a0v_w5c5k_worker_fence_pg.py`。没有修改旧 worker、Owner、真实库或前端。
3. `a0v_094` 在调用者已有事务中校验租户 scope、受限 runtime 登录角色、当前租约 token 哈希/epoch/DB 到期时刻、受管目录 identity OID/Host 与 assignment revision，并持有同一租约 advisory/行锁到事务结束。仅授予 `aos_runtime` EXECUTE；不给任何直表权限。缺失/漂移拒绝，默认无人调用。
4. 隔离 PG 专项 **5 passed**：精确当前 holder/权限、缺失/错 token/旧 epoch/过期、scope/assignment/OID 漂移、guard 事务阻挡并发 release。初版测试把不存在租户误当参数/事务 scope 不匹配，修正测试后通过；生产授权未放宽。
5. 累计稳定排序主组 **318 passed、11 skipped**，定义合同独立 **24 passed**，本专项独立 **5 passed**，合计 **347 passed、11 skipped、7 warnings**。合并进程存在旧测试环境变量夹具顺序污染（`AOS_DATABASE_URL` 被清空），故三组分别执行；红灯及原因保留为测试隔离债。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V 整组“已配置 · 已停用 · 版本 4 · 十二类来源”；`BROWSER_PARTIAL`。未保存、运行、冲刷队列；临时页/Vite 已关闭。
7. 实时只读门禁仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格线 `2026-09-25T20:00:04.800482Z`。原语未接线，真实 `aos_meta_head` 仍未应用 `a0v_093/a0v_094`。guard 的行锁防止新 holder 在事务未结束前接管，但长事务可能跨 TTL，外部副作用/未知结果仍靠独立幂等、Receipt 与冻结规则；不能宣称全链路围栏或旧组关闭权。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5l：先把最窄单事务 worker/Owner 写路径 opt-in 接入 guard，隔离注入失权/过期与旧路径回归；逐路径扩展，未全覆盖前真实 Host 不启用。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
