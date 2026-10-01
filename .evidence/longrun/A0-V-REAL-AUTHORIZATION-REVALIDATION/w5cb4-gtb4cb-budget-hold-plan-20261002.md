# GT-b4c-b｜Model 首评共桶预留事务方案

基线：2026-10-02 03:52 CST，m1 `8319189b`，AOS-001089。当前真实库 `aos_current_preview_20260927@a0v_118` 只读，代码头 `a0v_133`；本波仅在 disposable PG 做迁移及写测试，Host/worker/Provider 禁入。本方案复习 231-5 §6、228 AIP 模型容量与成本治理、GT-b4a 与 GT-b4c-a，以及原 `AipBudgetReservationStore`、`ModelEvalRequestStore`、`ModelEvalActionGuard`、`require_cost_risk` 后先于代码落盘。

## 现有缺口与事务边界

普通预算 Store 必须引用真 Task、原批准和三桶；其 `reserve` 自开事务，Model 首评不能构造假 Task/AgentRun 或先后调用它。首评申请已有不可变 `aip_model_eval_request` 和独立 checker 的原 `aip_action_approval_event`，但没有 Eval 预算预留账本。`derive_model_eval_bucket_authorities` 已保证日/月账户与普通 `BudgetRevision` 相同，首评第三桶为 `model-eval/<request_id>`。正式费用风险门目前只统计 `aip_budget_reservation`，直接增加 Eval hold 会漏算 `max_requests/total_risk_minor`，必须在同一正式 fence 与三桶锁下合并统计。

新增事务绑定 `reserve_model_eval_budget(conn, scope, request_id, approval_event_id)`；调用者负责 SERIALIZABLE 事务且可在同事务继续接物理容量与一次性 Intent，函数不自行 commit、不调用 Provider。锁顺序固定为持久申请/Model current head → 原 proposal 和审批事件/current maker-checker → current BudgetPolicy 和 BudgetRevision、Price → 正式费用风险 fence → 三桶。审批必须是未过期、未撤回的原批准，提案为当前 approved 状态，版本/hash/binding 和申请 request_hash 均 exact；Model/Provider/Price/政策在锁后复验。价格与申请费用上界不匹配时拒绝，不以未知价格为零。

`a0v_134` 新增独立 append-only `aip_model_eval_budget_reservation` 与三桶链接表；唯一键 `(tenant,request_id)` 和 `(tenant,approval_event_id)`，只给受限运行角色必要权限，RLS 强制租户；不改变普通 reservation 的 Task 门。预留内容含 immutable request/proposal/approval、BudgetRevision/Price exact refs、currency/upper bound、held 状态与 hash。重入仅返回相同 hold，不重复占额；输入漂移冲突。三桶 INSERT/锁/余额核验、风险额度合并、hold 与链接、桶 held 增量都在同一事务；任何一步失败全回滚。后续提交/unknown/release 必须基于独立状态事件与证据实现，未实现前本 hold 禁止发送且不得通过 TTL 自动释放。

## 文件级施工与 RED

施工拆为连续两段，不能以第一段代替本节出口。**b1 账本基础**先为第 2/4 项建立表、租户与 append-only 约束，并让正式费用风险门合并普通/Eval 计数；RED 是 disposable PG 上缺两表，专项与原申请/费用门相邻回归。**b2 真正预留**再执行第 1/3 项、并发及风险上限正向/拒绝测试，只有 b2 GREEN 才能称 GT-b4c-b 完成。拆分是因为当前无可执行 Provider 物理额度，b1 单独部署也不会产生首评预留或发送许可；本波不改变目标完成定义。

b2 继续按证据拆为 **b2a 原申请/批准与 Eval 共桶事务**、**b2b 普通 Task 与 Eval 的同账本并发及正式开发风险额度正反证明**。b2a 的 helper 只从既有 PG 测试提取原造数，必须保持原断言；writer 在调用者的 SERIALIZABLE 事务中运行，不自行 commit。b2a 仍未满足 b2 出口；b2b 须以真普通 Task/审批及正式费用消费 fixture 证明，不用手写桶数冒充普通业务路径。

1. `services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py`：disposable PG 复用真实持久申请及原 maker/checker 审批 fixture；为避免复制约 150 行造数，`test_model_eval_request_pg.py` 的既有测试仅提取一个返回原审批前状态的测试 helper，原全部断言由 wrapper 保留。先 RED：当前无 Eval hold store/table；验证无批准、maker 自批、过期/撤回、预算政策或 Model head 漂移均零桶增量；相同申请幂等；不同申请 Eval/普通共享日/月余额并发只准一方；三桶失败全回滚；跨租户零行；未知状态不释放。
2. `services/aos-api/alembic/versions/a0v_134_model_eval_budget_reservation.py`：仅追加独立表、索引、RLS/最小 GRANT 与防改触发器。正式迁移只在独立恢复波处理。
3. `services/aos-api/aos_api/aip_model_eval_budget_reservation.py`：受调用者事务约束的持久读取、原 Action 和预算权威复验、同桶占额；复用原三桶锁函数，不复制普通 Task 接口。
4. `services/aos-api/aos_api/aip_budget_cost_runtime.py`：正式费用风险门在 fence 锁后合并普通及 Eval exposure，新增表不存在时 fail closed；专项证实超限及并发。历史非正式成本预算沿原路径；正式记录不能漏算。
5. 专项、相邻回归、迁移升级及 RLS/并发、方案/代码复审、verification；m1 精确提交，AOS/Prime/D-wave 同步。浏览器无页面变化，本波不适用。

## 出口与剩余门

本波完成标准是隔离 PG 下真实持久申请+原批准的同事务三桶共用、幂等、并发、回滚与正式风险额度均有新鲜 GREEN。它仍不构成可执行 Eval：GT-b4b 正式 Provider 物理额度和共享容量、一次性 Intent、受限 transport、Usage/Report/Gate、真实当前实例授权及迁移未齐备，必须保持零发送。当前真实库不得迁移、启动新代码或制造正向首链证据。
