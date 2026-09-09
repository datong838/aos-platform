# AR2-7D D5B 整组切换 commit 权威施工方案

日期：2026-09-09
状态：施工前冻结；仅在隔离 PostgreSQL 验证，不执行真实租户 cutover

## 1. 现场事实与设计纠偏

- `AutomationOccurrenceStore.claim_next` 只有在 dispatch 已为 `extension`、目标 runtime ready/enabled/unfenced 时才领取；prepare 时固定九项仍为 legacy，因此 pause 提交之前不存在新 extension claim 的竞态。
- 单靠 prepare 请求里的 watermark/pending refs 不能证明当前运行事实。D5B 必须从 `automation_occurrence`、`automation_occurrence_dispatch_attempt` 与 `extension_runtime_execution_attempt` 重新枚举；claimed/running 阻断，UNKNOWN 仅保留对账身份且绝不重放。SERIALIZABLE 事务不能靠等待后重读刷新快照，因此 pause 还必须锁住并 fence target runtime，使 pause 前已开始的 attempt 先落库，pause 后的新 attempt 由既有数据库 guard 阻断。
- 切换提交后若没有持久 gate，pending occurrence 会立即被领取，无法形成可验证的切后窗口。因此新增 tenant/group claim gate：先单独提交 paused，再做最终 CAS；CAS 成功后仍保持 paused，由 D5C 在 9/9 读回和新入口验证通过后显式恢复。
- 不用普通角色直接 UPDATE dispatch。`aos_extension_maintainer` 只调用固定 SECURITY DEFINER 函数；函数自行核对非特权 maintainer、租户、operation 状态、exact 旧快照、目标 runtime 与 drain 门，并一次更新精确九行。

## 2. D5B 合同

1. 线性迁移 `ar2_014_ecommerce_growth_cutover_commit.py` 新增 `extension_dispatch_claim_gate`，每租户/cutover group 唯一，保存 paused 状态、所属 cutover operation、revision 和数据库时间；RLS/FORCE RLS，普通 runtime 只读，maintainer 只能经有界函数写。
2. 扩展 cutover event/receipt 合同，允许 `CUTOVER_CLAIMS_PAUSED` 和 `phase=pause`。pause 函数按 tenant/group/runtime 锁序读取 prepare operation，先把 exact target runtime 从 enabled/unfenced revision N 推进为 disabled/fenced revision N+1，再创建 gate 并推进 `draining`；同 operation 精确重放，其他 operation 占用同组冲突。既有 attempt insert guard 对 runtime 行持共享锁并核对 enabled/fence，因此 pause 与 attempt 启动形成数据库线性化点。
3. 修改 `AutomationOccurrenceStore.claim_next`：候选 occurrence 对应 dispatch group 存在 `claim_paused=true` 时不得领取。单条 SQL 的一致快照只能看到“legacy 且无 gate”或“extension 且 paused gate”，不会跨提交点漏领。
4. `begin_activation_commit` 接受严格 `CutoverCommitRequest`，必须 exact 引用 prepare Receipt。它重新锁定 group/runtime/approval，回读 prepare 权威，调用 pause 函数，并保存实际 occurrence watermark、claimed/unknown occurrence attempt、running runtime attempt 与未决 prepare refs 的不可变 pause Receipt。pause 可在有在途时成功，以便后续排空；不会自行结算或改写 attempt。
5. `commit_activation` 复用同一请求并再次锁定和重验上述权威，要求 target runtime 保持 disabled/fenced revision N+1。任何 claimed occurrence/attempt、running runtime attempt 或非空 prepare pending target Receipt refs 均阻断；UNKNOWN 只写入 commit Receipt 的 reconcile-only 列表，原 occurrence/attempt 保持不变。
6. commit 函数对排序后的九行逐字段核对 D5A old snapshot 和 prepared revision，核对 target installation/generation/epoch/runtime revision、ready/enabled/unfenced，再一次 UPDATE 为 D5A new snapshot；更新行数不等于九立即异常并整事务回滚。Python 随后 9/9 读回，写 `CUTOVER_COMMITTED`、commit Receipt 和 operation `committed`，同事务提交。
7. commit 成功后 claim gate 继续 paused，target runtime 继续 fenced。D5B 不实现恢复 claim/runtime、失败 rollback 或 lifecycle 联动；这些属于 D5C/D6，不能以 `committed` Receipt 冒充整波可用。

## 3. 文件与最小变更

- 新增 `services/aos-api/alembic/versions/ar2_014_ecommerce_growth_cutover_commit.py`。
- 修改 `services/aos-api/aos_api/ecommerce_growth_cutover.py`，增加 pause/commit DTO、读回与状态方法。
- 修改 `services/aos-api/aos_api/automation_occurrence_store.py`，仅在 claim 候选 SQL 增加持久 gate 条件。
- 修改 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`，在同一切换 fixture 接续 commit 反例；最小维护旧 occurrence PG fixture 以包含 gate schema，并增加 paused/open 行为回归。
- 更新 closure manifest 的接续登记与本计划；完成后新增 verification 文档。

## 4. 验证与停止规则

- Red 先证明：paused gate 仍可领取、缺 drain 门仍可切换、九行中一行漂移可造成错误提交；随后最小实现转绿。
- PostgreSQL 专项覆盖 pause 首次/重放/并发占用、claim gate、实际水位、active claimed/running 阻断、UNKNOWN 保留、pending target Receipt 阻断、审批/runtime/dispatch 漂移、9/9 同 revision、0/9 回滚、跨租户、TEMP shadow、非特权角色、Receipt 篡改和非空 downgrade。
- 运行 occurrence 邻接、canonical router/host port/runtime store、完整 extension_runtime、closure、memory validate、compile 与 diff check；验证文档与代码分开可追踪提交。
- 相同阶段失败两次先停下定位，不改用共享库或旧 18432；不调用真实源/Provider，不执行真实租户、生产迁移、发布或 push，230 L0 挂起。
