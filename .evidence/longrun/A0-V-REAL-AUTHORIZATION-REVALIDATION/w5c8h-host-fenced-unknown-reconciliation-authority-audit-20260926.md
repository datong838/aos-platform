# W5c8h｜Host-fenced 原 unknown 对账授权审计

## 结论

**当前代码不能安全自动对账。** W5c8g 的诊断证据为只读快照；`DataRequirementOutboxStore._execute_transition` 另开连接/事务调用 `a0v_050`。即使在外层先调用 `a0v_094`，随后调用旧 Store，也不是同一写事务。`a0v_050` 的 `reconcile_completed` 函数仍授予 `aos_runtime`，单独新增 Python guard 或新函数若不同时撤去旧 EXECUTE，仍留可绕过的旧入口。

## 精确调用与锁序

| 层 | 当前事实 | 受控入口必须做到 |
| --- | --- | --- |
| W5c8g 诊断 | 一个 `REPEATABLE READ READ ONLY` 快照核原 attempt、双 Receipt、PREPARING、Occurrence、Origin、组成员/manifest；类型不是可执行 route | 仅作路由线索，不把快照对象或布尔值直接当作写授权 |
| `DataRequirementOutboxStore` | `_execute_transition` 自己开连接/提交；`reconcile_completed` 调 `a0v_050` | 新显式 API 必须独占**同一个** `aos_runtime` 写事务，原 claim/refs 与 Host token/epoch 一次提交；未知提交结果只能只读对账 |
| `a0v_094` | 先租户 advisory xact lock，再 Host lease、identity、assignment `FOR SHARE`，核 DB 时钟/token/epoch | 新 SQL 入口在任何 Delivery 写之前调用同事务 Host fence；锁序固定 Host → Delivery，禁止别处反向持锁再进 Host |
| `a0v_050` | Delivery `FOR UPDATE` 后核 `unknown`、原 attempt/token、双 Receipt 并写 `acked`；**不核** Host/source group | 新入口需在同写事务重读并核原 Requirement、原 PREPARING Receipt、accepted Occurrence/原 dispatch Receipt、Origin source Run、唯一组成员及完整 binding/manifest hash，再复用旧双 Receipt/Delivery 原子谓词 |
| `a0v_045` 保存组 | claim/member/input 有 RLS、UPDATE/DELETE/TRUNCATE 不可变触发器；run_id 租户内唯一，Locator 对成员顺序/manifest/actor/cutoff 逐项复核 | 不信 caller 提供的 group id/hash；写事务用精确租户/原 source Run/原 cutoff 从权威表复核，不靠旧只读快照替代。DB canonical hash 与 Python `_digest` 的等价及并发插入边界须隔离 PG 证明 |
| 当前 Worker | `run_scope_once` 对 ambiguous 返回 `unknown`；遗留 `_run_claim(reconcile=True)` 会运行 Coordinator/source 组合 | 不复用该分支做对账；未来单独零 source/零 coordinator 的 bounded reconciler，默认关闭，且需完整 Host/Store/fleet authority 后才可上线 |

## 必须先封的旁路与分波条件

1. 新安全函数不能与旧 `data_requirement_outbox_reconcile_completed_a0v_050` 对运行角色同时开放而宣称全局安全。迁移/发布需设计原 EXECUTE 撤权、受控新入口授予、旧 Worker 兼容拒绝和回滚行为；正常 `complete_a0v_050` 不能误伤。
2. `a0v_094` 的 Host token/epoch 不是 W5c8g 证据字段，也不能从历史 Attempt 推导。只能来自当前正式 Holder，且全机拓扑/真实 `a0v_093/094` 部署仍为独立门。单事务 SQL/隔离 PG GREEN 不等于真实 Host 排他。
3. `a0v_050` 缺原 PREPARING、Occurrence、Origin、源组谓词；只在 Python 预读再调用旧函数仍有时序/绕过缺口。须在同一事务内按确切源校验，不能“先读后写”跨连接拼装。
4. 过期 `claimed` 不符合 `unknown` 谓词，仍单独设计审计状态迁移；不能因双 Receipt 存在就直接转 `acked` 或换 token 重领。
5. 上游 Store/外部 effect 提交属于其他事务，Outbox 短事务 Host fence 不能倒推所有上游 effect 曾被围栏；真实恢复需分别查原 Receipt 与上游全链 authority。源组历史不可变性不证明当前安装/批准有效。

## W5c8i 最小施工合同（尚未实施）

- 先在隔离 PG 实现**默认不接生产 Worker**的受控原型：迁移候选 `services/aos-api/alembic/versions/a0v_096_*`，新函数入参只收精确原 claim/双 Receipt、当前 Host token/epoch、必要原源组 exact refs；函数自己重读所有权威关系，在一条写事务内按 Host→Delivery 锁序判定，成功才 `acked`。避免复制哈希算法：优先复用现有 canonical SQL 或把已保存 hash 与原始体一致性通过有证据的同算法比较。
- `services/aos-api/aos_api/data_requirement_outbox_store.py` 新增显式 opt-in 方法，**不复用**另开连接的 `_execute_transition`；旧自动 Worker 路径保持冻结。迁移若无法安全撤旧函数 EXECUTE，则原型只算拒绝设计、不算可授权实现。
- 隔离 PG 必须覆盖正例/重放、错租户/attempt/token/Host epoch、过期/失权、缺/错双 Receipt、PREPARING/Occurrence/Origin/组成员/manifest/actor/cutoff 漂移、多组、旧入口撤权、并发/锁序、未知提交结果；`dev-org` 只负例。任何一项不可构造或无正式验证则留 STOP，不进入真实库。

## 重启后环境观察

真实 gate 2026-09-26 00:06–00:08 CST 返回 `FROZEN_REAL_CLOSURE_GATE_COMPOSITION / OBSERVATION_FirstInstallBlocked`；异常码下钻为 `DATABASE_CONTAINER_UNAVAILABLE`。`colima list` 显示 default、aos-extension 均 stopped；专用 Docker context socket 不存在。没有启动容器/Host、没有读取真实 Run 新计数、没有读商城源或调用对账。昨夜的 12 Run running/closure Receipt 0 **不能当作本次当前值**。本审计不提供真实恢复授权。

本地 8080 `/v1/health` 为 HTTP 200，但不代表租户目录可读。内置浏览器经临时 Vite 只读查看 `/data/schedules`：显示“工作台目录读取失败”“tenant directory is unavailable”，整组采集页提示“请先确认当前登录身份”。待同步写操作仍显示 1，未冲刷；临时浏览器页和 Vite 已关闭。故不能从本次 UI 读回 rev4 当前状态，更不能继承昨夜的页面作为新证据。

尝试运行 `test_analysis_data_requirement_worker.py`，其 session 级隔离 PG 夹具在用例开始前连接 127.0.0.1:5433 失败，10 项均 setup ERROR；本波**无测试 GREEN**。未设置共享库绕过隔离，未创建/清理任何测试数据库。只完成受审 Python 文件 `py_compile` 和 `git diff --check` 静态检查。
