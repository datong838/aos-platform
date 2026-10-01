# GT-b1 Model 首评一等 Owner 施工方案（进行中）

基线 AOS-001084 / m1 `ad6d3477`，Task `W5CB4-GTB1-MODEL-EVAL-FORMAL-OWNER-20261002`。已复习 231-5、BG00GT/GT-a/GT-b0、原 `AipEvalRunner`、`AipActionStore`、预算与容量预留。用户批准设计/代码/隔离验证；当前权威库只读，真实 Secret/Provider/Host 调用未获本任务授权。

## 1. 源码判定

- ModelRuntimeStore 只读候选包含 `sourceRef`、next-active `targetRef` 与 `expectedHeadVersion`；GT-a 预检跨事务，固定 `executionAllowed=false`。
- 原 `AipEvalRunner` 立即创建随机 EvalRun 并由 queued 转 running，调用 caller 的 target/judge callback；GT-b0 已对 Model/Route fail-closed。它不能作为首评持久请求或发送意图。
- 原 `AipActionStore` 的 maker/checker 可产生 ActionApprovalEvent，但普通提案没有 Model Eval 专属候选、用途、费用和执行代次校验；必须加专用请求/批准 guard，不能只填 `purpose` 文本。
- `ReserveBudgetRequest.task_ref` 必须是 `Task`，`_task_authority` 回读 Task；`_approval_authority` 还要求提案 `task_id` 等于 Task。容量 `reserve` 唯一键是 `agent_run_id`。当前 Model EvalRun 不具备两者身份；严禁伪造 Task/AgentRun 复用通用表。
- 原容量池发布还要求 Route、Model、Provider 均为 active；首评候选的 Model 必为 draft/validated。因此不能给它指向普通 active 池，也不能另建不共享锁的评测池造成容量超售。GT-b1 容量段需明确 provider/物理容量共用锁和旧 reservation 的迁移兼容，未解决前始终阻断 intent。

## 2. 目标持久链与不变量

1. 使用一等 `ModelEvalRequest` 身份，固定 tenant、source/target/head、suite/contract/dataset/judge、Price/Provider/Quota/Budget、费用上界、有效截止、稳定 idempotency key 与申请 hash。Source 必须是当前 draft/validated，target 是唯一 next-active；创建和批准时在串行事务锁 head 后重读，跨租户、hash/head 漂移拒绝。
2. 经原 Action maker/checker 身份与成员资格产生精确批准事件；批准必须绑定同一申请 hash、用途 `quality-eval`、费用上界/截止和当前实例代次。申请人与批准人不同，撤销/过期在发送前再读。专用 ActionType 不能被通用 executor 直接执行。
3. 给 `EvalRun` 增设独立预算与容量 reservation Owner，费用按任务等价的**评测账户**、日、试点三个稳定桶计入同一账本，不复用虚构 Task；容量必须与普通 AgentRun 共享物理上界及同一事务锁，不能只另建 Eval 池。先在单事务内拿到费用与容量，再插入有界发送 intent；任何失败全部回滚。多次同键返回相同 intent，payload drift 拒绝；未知外部结果只读对账。
4. GT-b1 的最终产物只能是持久 `prepared` intent；GT-c 的独立签名执行者在再次核 current approval/candidate/lease 后才可发 Provider。GT-b1 本身不产生 Provider 调用、Usage、Report、Gate 或 active Model。

## 3. 文件级施工与 RED

- `services/aos-api/alembic/versions/a0v_133_model_eval_intent.py`：在独立克隆演练新增申请、审批绑定、费用/容量 reservation、发送 intent/事件及租户 FORCE RLS、幂等/外键/禁截断；不迁移当前 118 库。正式 SQL 先确认旧预算桶和容量池可共享锁，不能造第二套容量配额。
- `services/aos-api/aos_api/aip_model_eval_authorization.py`：补严格申请/批准/intent 契约；绝不暴露可由调用方伪造的 `executionAllowed=true`。
- 专用 Store/Action guard 文件待读完原 Action 细节后确定，避免把专用 maker/checker 放在通用 action 分支的错误位置；`aip_model_runtime_store.py` 只补同事务 head/candidate reader，不改普通 READY resolver。
- `services/aos-api/tests/aip/test_model_eval_authorization.py` 与新增 PG 测试：先 RED，覆盖跨租户、错 head/hash、maker=checker、批准过期/撤销、预算/容量不足、同键重放与漂移、失败零 reservation/intent、并发竞争；再最小实现。相邻原 Action、预算、容量、普通 Model resolver/EvalRunner 需保持通过。

第一施工切片：在 `aip_model_runtime_store.py` 增加接收**调用方事务连接**的 Model-only `require_current_model_eval_candidate_for_update`；锁定当前 head 并同连接读取 revision/payload，严格比对租户、source/target/head、full content hash 与 lifecycle。它只返回候选，不产生 approval/intent/Provider 权限。先在 `test_model_eval_authorization.py` 做 RED：正确候选锁定、错租户/head/source/target/payload hash 均拒绝，SQL 包含 head 行锁。此 reader 是后续批准和 intent 原子事务的必要依赖；不得把它单独当 GT-b1 完成。

## 4. 当前执行边界与下一步

本文件只冻结源码确认的契约和 RED 列表。下一步先读 `AipActionStore` 专用 guard 和原预算桶/容量锁协议，确定复用同一锁的 SQL 与精确文件清单，再写第一组 RED。未通过正式授权/真实费用预算门前，不给 GT-b1 正向执行许可；不得为了测试通过扩大 GT-a 或解除 GT-b0 禁入。
