# W5c6k 跨机器 Host inventory 权威边界核验（2026-09-25）

方案 `47defcd4` 先行、无效应合同 `bb11be71`。未改 Host/worker/closure/真实 DB。

## 九步证据

1. 复习 `ar1_003` identity/assignment/history、RuntimeTenantDirectory、`a0v_093/094` 与 W5c5f/j 只读发现。
2. 文件级仅新增 `test_a0v_w5c6k_cross_machine_inventory_design.py` 与本 verification。
3. 现状合同确认：受管 identity/assignment 有 revision/updated_at/不可变历史，目录返回 scope+assignment revision；没有运行实例 heartbeat、启动 epoch、DB-clock expiry。`pg_stat_activity` 只给当前连接快照，无法排除离线/非受管 Host。
4. 后续权威方案须具完整节点来源、实例身份+启动 epoch、DB-clock 短 TTL、失联隔离、旧 generation/外部权限 fencing、closure 同事务锁定重读；任缺一项不能宣称 topologyComplete。本波只设计，不新增真实 authority。
5. 专项 **3 passed**，W5c5k–z 加 W5c6a–k 累计 **74 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。到线也不自动 closure，仍需完整拓扑、新方案/唯一 key、Owner 门和独立读回。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6l：隔离 PG 设计受管实例 heartbeat/启动 epoch 与关闭门同事务锁；无法排除非受管 Host 则保持 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
