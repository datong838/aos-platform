# W5c6l 受管 Host 实例 lease 活性隔离核验（2026-09-25）

方案 `d7bc4989` 先行、隔离合同 `d7ea3b7a`。未改生产迁移/Host/closure/真实 DB。

## 九步证据

1. 复习 `ar1_003` 目录、`a0v_093/094` acquire/renew/worker fence、W5c6k 完整性条件与正式 closure。
2. 文件级仅新增 `test_a0v_w5c6l_host_instance_lease_feasibility_pg.py` 与本 verification。
3. 隔离 PG 证实受管 scope lease 的 token/epoch/DB-clock 到期和 renew：旧 epoch 在新 acquire 后被拒，当前 epoch 的 worker guard 成功；guard 原事务持锁时 concurrent release 超时，事务退出后可 release。
4. 这仅证明已受管的单 scope holder 活性；lease epoch 不是未经证明的进程启动 epoch，也不能排除非受管进程、其他物理机或外部 source effect。无效应分类持续 `topologyComplete=false`、`closureAuthorized=false`。
5. 专项 **3 passed**，W5c5k–z 加 W5c6a–l 累计 **77 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。隔离 PG GREEN 不授权真实 closure 或 Store effect；真实库仍缺 `a0v_093/094`。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6m：定义可审计 Host 节点集合完整性来源与非受管排除；若无可信来源则明确基础设施阻断，并转向其他独立研发债，保持真实 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
