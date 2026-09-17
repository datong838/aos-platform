# SC4-5L6Z-Q｜计划为空时经营参谋首次全店基线自动启动方案

日期：2026-09-17。基线：`5250e8d4`。本切片承接 Q Policy12 真实自然空窗，目标是让已安装并完成租户配置的电商包在没有活动经营计划时，自动启动一次来源化的全店基线分析。它不修改商城源数据，不伪造商品变化，不批准 GrowthPlan，不执行外部触达，也不扩大 230 L0 权限。

## 1. 产品与当前事实

- 产品方案规定：`StorePortfolio` 没有活动计划时，经营参谋仍须盘点当前业务、读取可信数据、形成问题/机会和候选计划；首次接入应运行 `FULL_STORE_BASELINE_ASSESSMENT`，首个内部场景为“商品尖刀验证”。
- 当前 Q 已完成安装、配置、切流、event-control 和一次真实只读 Cron；最新来源运行写入 65 行商品，但相对当前事件游标没有变化，所以自然窗口正确地产生零候选、零 Case/Run。
- 当前 Case `case-qyh-full-store-baseline-20260915@14` 已绑定 ProductEvent Policy12。Case 只允许一个 `schedulePolicyRef`，不能把一次性基线计划覆盖到同一 Case 上。
- 正式 D01/D02/D03、GrowthPlan 草稿 Owner、exact 评审、Handoff 已存在；当前缺的是“首次安装/计划为空”到一个正式 Run 的自动触发和当前真实来源上下文，而不是第二套分析或计划实现。

## 2. 选择的产品路径

建立一个独立的首次基线 Case，并使用现有 `initial_checkup / once` BusinessInvestigationSchedulePolicy。一次性策略属于租户安装配置；配置完成后由 Runtime Host 自然枚举到期 slot、生成唯一 `schedule` occurrence、消费 occurrence 并启动分析，开发者不参与每次 Case/Run 创建。

计划为空不是充分条件。自动启动必须在同一受控读取中同时满足：

1. 当前租户为 `org-org/dev-project`，当前安装精确为 Q installation/generation/epoch；
2. Case 为 ACTIVE、`initial_store_analysis`、独立 baseline Case，且 once policy 当前启用；
3. 当前业务实体唯一、来源 readiness 可用，存在一组已完成且可回读的真实 Pipeline Snapshot Group；
4. 当前没有同 Case/analysisType 的活动 Run；
5. 当前没有可用的 DRAFT/APPROVED GrowthPlan；若已有计划则 occurrence 记为 `not_applicable`，不重跑基线；
6. 当前路由、安装、配置、预算、能力和 reviewer 边界仍通过现有 bootstrap 守卫。

首次基线不伪装成 ProductEvent。它使用现有 `trigger_source=schedule` 和 once binding；来源上下文引用最新合格快照组、Case exact ref、SchedulePolicy exact ref 和 occurrence exact ref。分析启动后仍走现有 compilation、bootstrap、DataRequirement、D01/D02/D03、stage review、GrowthPlan approval 和 Handoff 权威。

## 3. 六步施工顺序

1. **入口与契约**：新增 baseline eligibility/discovery 纯读取服务，输出 exact Case、Policy、安装目标和最新合格 snapshot group；已有计划、活动 Run、来源不新鲜、canary 或代次漂移全部失败关闭。
2. **自然 once occurrence**：补齐 once slot 枚举与 watermark；每个 policy 只产生一个稳定 occurrence，重启重放不重复。未到 effectiveFrom 不产生；超过恢复窗标记 missed。
3. **schedule 分析上下文**：抽取 ProductEvent 分析启动中的公共 bootstrap 核心；新增 schedule 来源适配器，只接受 `trigger_source=schedule`，不要求 ProductEventOrigin，也不读取源库。
4. **宿主 worker**：Runtime Host 增加 baseline-schedule worker。它先枚举 once slot，再只 claim 当前 Q 的 schedule occurrence；执行结果未知时进入 reconcile/needs_attention，不重发模型或动作。
5. **真实租户配置与运行**：通过当前 Q canonical router 建立独立 baseline Case、once policy 和审批/绑定；不直接写表。等待 Host 自动生成 occurrence 和 Run，随后观察 DataNeed、画像、诊断和计划草稿。
6. **exact 评审和下一波**：对可读且逐项有来源的计划执行人工角色 exact 评审；批准后进入内部工作台任务，不执行外部发布。下一波补齐计划承接、可读产物、人工续跑、总控复盘和 WikiCandidate。

### 3.1 电脑重启后的前置恢复增补（2026-09-17）

电脑重启后的现场复核表明：Q installation 仍为 `active@5`，但运行租约已按设计回收，binding 已进入 `revision7 / epoch4 / enabled=false / fenced / observed=unknown`，三项运行资源均为 `released`；九项正式入口加 event-control 仍保留在旧 epoch3，当前无 running execution、无 unresolved occurrence。已释放资源不得由新 Host 原地复活，因此第 5 步前增加固定恢复子波次：

1. 停止无 live target 的 Host，冻结 Q 当前头、released resource、route group、Policy12 和零在途证据；
2. 通过 released event-control Owner 禁用 Policy12 binding，再以 exact approval 依次 fence、shrink 可选 event-control；
3. 通过正式 disable consumer 对 Q 的九项入口执行 fence/detach，禁止直接改路由或运行绑定；
4. 以 Q detach Receipt 为前驱，新建相同包版本的干净 R installation，执行 prepare、verify、stage、configure、enable；
5. 注册并 cutover 到 R，重新签发 Product source selection/control/binding 与 ProductEvent policy；随后才启动本方案的一次性 baseline Case/Policy；
6. 验证 Q 不再可执行、R 单一 live target、canary 为零、旧 epoch occurrence 不被重放，再回到第 5 步。

该增补只恢复运行所有权，不修改商城源数据，不补造 ProductEvent，不跳过审批，也不把历史 Q projection 当作 R 的当前授权。

## 4. 实现文件与最小边界

| 文件 | 动作 | preHash / 边界 |
|---|---|---|
| `services/aos-api/aos_api/ecommerce_baseline_assessment_discovery.py` | 新增 | 只读 eligibility；不创建 Case/Run/Plan |
| `services/aos-api/aos_api/ecommerce_baseline_assessment_worker.py` | 新增 | once slot + schedule claim；只处理当前 live target |
| `services/aos-api/aos_api/ecommerce_scheduled_analysis_service.py` | 新增 | schedule occurrence 到现有 bootstrap；不接受 event occurrence |
| `services/aos-api/aos_api/ecommerce_product_event_analysis_service.py` | 最小抽取 | `4e86e96b...`；ProductEvent 行为和守卫保持不变 |
| `services/aos-api/aos_api/automation_occurrence_store.py` | 最小补强 | `a5bfbcad...`；复用已有 schedule schema，不改数据库约束 |
| `services/aos-api/aos_api/aip_logic_automation_scheduler.py` | 最小补强 | once slot 计算；weekly 语义不变 |
| `services/aos-api/aos_api/pipeline_control_service.py` | 最小装配 | `cdbb8de5...`；仅构造当前安装的 schedule 分析服务 |
| `scripts/a0v_ecommerce_runtime_host.py` | 最小装配 | `85cae8db...`；新增 worker 生命周期与状态，不改变原两 worker |
| `services/aos-api/tests/test_ecommerce_baseline_assessment_*.py` | 新增 | 空计划/已有计划、重放、来源/租户/代次/活动 Run 反例 |
| `services/aos-api/tests/test_aip_logic_automation_scheduler.py` | 修改 | once/weekly 不回归 |
| `scripts/a0v_q_advisor_baseline.py` | 新增 | 当前 Q 配置、观察、恢复和证据；禁止直接 DML 业务对象 |

实际编码前逐文件重新校验 hash；若现有公共 bootstrap 无法安全抽取，则新增 schedule 专用适配层，不放宽 ProductEvent 类型检查。

## 5. 验收与停止条件

- 一个独立 baseline Case、一个 enabled once policy、一个 schedule occurrence、一个 BusinessInvestigationRun；同一配置和重启重放数量不增长。
- Run 的 Case/Policy/occurrence/snapshot group/installation/generation/epoch 均可 exact 对账；来源只来自受治理快照，不查询或修改商城 MySQL。
- 已有计划时不启动；活动 Run、来源失效、预算/能力/角色/配置漂移时不启动；`dev-org/dev-project` 产生零对象。
- 计划正文必须可读，建议逐项引用 Evidence/Insight/Decision；缺订单、支付、成本或内容事实时生成 DataNeed 或显式未知，不猜数字。
- 未经 exact 评审不批准 GrowthPlan；未经预算、能力和动作批准不生成外部副作用。任何未知写结果只读 reconcile，不盲重发。
- 专项测试、受影响原回归、PostgreSQL 隔离用例、AR2 `--phase ar2-7` 验证全部通过；真实结果另落 JSON/Markdown 并提交。

## 6. 风险说明

- 当前真实窗口只确认 Product 65 行，完整全店分析需要十二类事实。首个 Run 很可能先进入 `WAITING_DATA`；这是正确结果，后续由既有 DataRequirement worker 补齐，不能用商业材料或模型猜测替代。
- “计划为空”不能长期作为重复触发器；once watermark、Plan existence 和活动 Run 三道门必须共同阻止重启风暴。
- 商品尖刀方法来自产品方案和商业案例，仅作为候选分析方法。最终选品、价格、预算、内容声称和渠道动作必须由当前真实证据和后续评审决定。

## 7. 施工补充：调度控制凭据（2026-09-17）

编码复核发现，现有 `SchedulePutHostService` 会在写入时锁定并校验 exact `ActionApprovalEvent`，响应也返回 `approvalRef`；但底层 `ecommerce_investigation_schedule_policy_command_receipt` 只保存 Policy/Case authority，没有把该审批与成功写入永久绑定。首次基线 bootstrap 需要同时验证来源控制凭据和审批有效期，若运行时从历史 proposal 反查，无法证明“这个审批就是这次调度写入采用的审批”。

因此在 schedule 分析上下文之前增加一个最小、不可变的控制凭据切片：

1. 新增 `a0v_078_schedule_policy_control_receipt.py`，保存 tenant、SchedulePolicy exact ref、Case exact ref、ActionApprovalEvent exact ref、原 command receipt、Q installation/generation/epoch、内容哈希和创建时间；表启用强制 RLS、禁止普通 DML，并通过 security-definer 函数在同一 Host 事务中写入。
2. 写入函数必须锁定当前 Policy/Case、原 command receipt、当前 dispatch 和审批事件，逐字段验证 proposal action binding；重放只允许完全相同的请求哈希。
3. `SchedulePutHostService` 在成功写 Policy、绑定自然 schedule 后立即写控制凭据。任一步失败则整个事务回滚，不能出现“Policy 已启用但没有 bootstrap 权威”的半成品。
4. baseline discovery 只接受与当前 once Policy、Case 和 Q epoch 一致的 `SchedulePolicyControlReceipt`，并把它作为 `AnalysisBootstrapIntent.sourceControlReceiptRef`；商品事件仍只接受 `EventPolicyControlReceipt`。

该补充引入数据库对象但不修改 occurrence 约束，也不放宽已有 ProductEvent 类型检查。新增或修改文件限定为：

- `services/aos-api/alembic/versions/a0v_078_schedule_policy_control_receipt.py`
- `scripts/a0v_q_advisor_baseline_migration.py`（仅执行冻结过的 `a0v_077→a0v_078` 单步迁移与无业务变化审计）
- `services/aos-api/aos_api/ecommerce_schedule_policy_control.py`
- `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`
- `services/aos-api/aos_api/ecommerce_baseline_assessment_discovery.py`
- `services/aos-api/aos_api/ecommerce_analysis_bootstrap_contract.py`
- 对应专项测试与 migration 静态测试。

## 8. 重启恢复实况修订：R 中断后由 clean S 接管（2026-09-17）

Q 完成正式 fence/detach 后，R 已按计划创建并完成 `runtime-apply`。但 Q 在 R 的
`runtime-verify` 受理前已经正式卸载，验证器因此命中 `CurrentInstallationStaleError`；
Host 释放 R 的三项资源并停止，R 保持 `applied@4`，未形成 binding。该失败是当前性守卫
的正确拒绝，不能通过回写 Q、复活旧 owner 或重发未知 verify 绕过。

恢复沿用已验收的 preparation-reset 协议：等待 R 原 verify 租约自然过期，调用正式
`reset_preparation` 回到 `approved@5`；创建无 predecessor 的 clean S；确认 S
`approved@3` 后正式卸载 R；再让唯一 Host 完成 S 的 prepare、verify、stage、configure、
enable。当前 S 为 `77b8e5c2-db96-4d55-a808-1b62e00163d2`，generation
`e621100a-baea-440f-9075-ae8a5290845a`，binding `revision4 / epoch3 / ready / enabled`。

接续施工必须使用 Q disable operation 的最终 detach Receipt
`2bcb4ff2-9da1-4bc8-a3b3-7ed98e18eb4d@sha256:cc974be8...`，并只在九条路由仍为
`legacy / fenced / groupRevision59 / routeRevision32`、零在途、零 unresolved 时：

1. 新增 `scripts/a0v_s_successor_business.py`，固定 S identity、configuration、Q detach
   Receipt 和 expected group revision 59，生成并登记 successor Receipt；
2. 新增 `scripts/a0v_s_successor_cutover.py`，用新的 operation/idempotency namespace 完成
   approve、prepare、pause、commit、validate、resume，预期最终 group revision 60；
3. 新增只读终态验证，要求九条路由全部指向 S epoch3、无 fence、S 为唯一 live target、
   Q/R 均不可执行、canary 为零；
4. 将 `scripts/a0v_q_advisor_baseline.py` 的运行目标改为 S，之后才重签来源控制与创建
   baseline Case/once Policy。

这些文件不触碰商城源库，不修改业务表数据，不继承 Q 的旧安装审批作为 S 当前授权。

### 8.1 S 基线权威重绑的最小实现

切流终态确认 S binding 已由 cutover 从 revision4 推进到 revision6。因此新增
`scripts/a0v_s_product_preflight.py`：复用只读 Product 图和 source-selection 校验，但将
create Receipt 固定为 S、cutover resume 固定为 S 本轮 Receipt，并要求
`active@5 / binding revision6 / epoch3 / generation e621100a-… / current config`。

`scripts/a0v_q_advisor_baseline.py` 保留原文件名以维持已冻结任务入口，但内部 runtime plane、
preflight、输出 outcome 与所有新 idempotency key 改为 S namespace；它不得读取 Q 的
`currentInstallationRef` 或 generation。原 Product TaskBrief 仅作为内容需求 exact ref 使用，
不作为安装或来源授权。prepare 的成功条件增加 S identity、S resumed cutover 和当前时间窗内
的新 source-selection draft，随后 Case/Policy 写入形成的 control receipt 也必须绑定 S epoch3。

### 8.2 Schedule revalidation 的只读锁修复

首次真实 Policy 提交在事务写入前失败：`SchedulePutHostService.revalidate` 对 Case head 使用
`SELECT ... FOR SHARE`，而 `aos_runtime` 按最小权限只有这些权威表的 SELECT；PostgreSQL
行锁还要求 UPDATE，因此正确拒绝为 `InsufficientPrivilege`。相同方法还对 Policy head 和
dispatch route 使用 `FOR SHARE`，后两者也只有 SELECT 权限。

最小修复限定为 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：SchedulePut
的三处当前性读取及 ScheduleTrigger 对 Policy head 的同类读取
改为普通 SELECT。事务本身为 SERIALIZABLE；实际 SchedulePolicy 写函数会对 Case/Policy 执行
`FOR UPDATE` 并校验 expected revision；新增的 schedule-control SECURITY DEFINER 函数会再次
锁定 Policy、Case、审批和 route，并在同一事务绑定 Receipt。因此移除前置冗余行锁不放宽 CAS，
也不向 runtime 授予 UPDATE。补一项回归测试，要求只读头和 route 查询不带行锁，而审批事件和
proposal 的既有锁保持不变。

### 8.3 已部署 a0v_078 的 Case hash 修复迁移

移除冗余前置行锁后，真实事务推进到 control Receipt 函数并再次整体回滚：已部署的
`ecommerce_schedule_policy_control_put_a0v_078` 从
`ecommerce_investigation_case_head` 读取 `content_hash`，但该列只存在于 Case revision 表。
这是 a0v_078 函数定义缺陷；当前数据库已经到 a0v_078，不允许回改历史迁移或手工替换函数。

新增 `services/aos-api/alembic/versions/a0v_079_schedule_policy_control_case_hash.py`，只用
`CREATE OR REPLACE FUNCTION` 更新同一函数：锁定 Case head 后，按 head.current_revision 联接
`ecommerce_investigation_case_revision` 取得 content_hash；其余请求形状、审批、command Receipt、
route、幂等和插入校验逐字保持。`scripts/a0v_s_advisor_baseline_migration.py` 只执行冻结的
`a0v_078→a0v_079` 单步迁移，迁移前后所有业务表行数必须一致，control Receipt 仍为 0，
canary 为 0。然后才允许再次提交原 Policy intent。

### 8.4 Approval exact-ref 时间序列化修复

a0v_079 后原事务推进到审批哈希复核并再次回滚。逐字段只读诊断确认审批、proposal、payload、
过期时间均正确；差异只在哈希序列化：应用 `canonical_hash(..., default=str)` 将 Python
`datetime` 编码为 `2026-09-16 23:19:27.088899+00:00`，而 a0v_078 函数把 timestamptz 直接
放进 jsonb，编码成 `2026-09-16T23:19:27.088899+00:00`。两者语义相同但字节不同。

新增 `a0v_080_schedule_policy_control_approval_hash.py`，继续 CREATE OR REPLACE 同一函数，
仅把审批的 `expires_at/created_at` 规范为应用当前既有 Python datetime 字符串（UTC、空格分隔、
非零微秒六位、`+00:00`）后计算 exact-ref hash。迁移前先用只读 SQL 证明新算法得到冻结审批 ref
`sha256:1484b2...`；迁移仍要求业务行数、control Receipt、canary 均不变。后续应统一全局
canonical datetime profile，但本切片不改历史审批哈希合同。

### 8.5 审批 policyHash 与最终 authority hash 分层修复

a0v_080 后逐项复核确认时间哈希已一致，剩余拒绝来自 policyHash 语义混用：审批 proposal
批准的是 `PutBusinessInvestigationSchedulePolicyRequest` 的内容哈希；control 函数却把它与写入后
包含 tenant/revision/contentHash/createdAt 的 `SchedulePolicyRevision.contentHash` 比较。两者本应
不同。新增 a0v_081，仅将该条件改为：从 command Receipt 的 `policy_authority` 删除
`schemaVersion,tenant,revision,version,priorRef,contentHash,createdBy,createdAt`，得到原 Put request
投影，以 canonical JSON 计算并核对 proposal.policyHash；最终 Policy exact ref 仍独立核对
revision contentHash。其余条件不变。

### 8.6 首次自然 occurrence 的前置读模型修复与恢复边界

Policy v1 写入成功后，唯一 Runtime Host 自然枚举出 occurrence
`3c927751-b91a-53d0-8a42-7c5223ea109d`，随后在 baseline discovery 阶段以
`UndefinedTable` 进入 `needs_attention`。只读核验确认缺失对象是代码误写的
`ecommerce_investigation_run_revision`；数据库的既有权威模型从 biw4_002 起就是不可变
`ecommerce_investigation_run`，活动槽 `ecommerce_investigation_run_active_slot` 也明确外键到该表。
同一 occurrence 没有 `ecommerce_growth_runtime_command_receipt`、没有 target Receipt、没有新 Run，
因此失败位于目标命令前，但 dispatch attempt 仍按既有规则保留 `unknown`，禁止原 occurrence 盲重发。

最小代码修复限定为 `ecommerce_baseline_assessment_discovery.py`：活动槽直接联接
`ecommerce_investigation_run` 读取 `trigger_key`，并移除 analysis dispatch 的冗余 `FOR SHARE`；
这些表对 runtime 只有 SELECT，串行化事务、后续 dispatch 当前性校验和真正写路径的 CAS 不变。
补充查询形状测试，防止再次引用不存在的 revision 表或要求只读路由的 UPDATE 权限。

既有 v1 occurrence 只允许通过可审计的“已证明目标前失败”终结路径关闭；若当前产品没有该正式
接口，则保持 `needs_attention`，不得直接 DML。后续重试必须续签审批并写 Policy v2，使 once
绑定产生新的确定性 occurrence；新 occurrence 只能由加载修复后代码的唯一 Host 执行。

### 8.7 唯一 Host 的 crash-rehydrate 代码换代

当前唯一 Host 在 07:07 启动，进程内仍装载修复前的 discovery；优雅停止会主动释放 S 的三项
资源，不能为代码换代而制造一次无意义卸载。S 当前三项 lease 均为 `pending / observedRelease=false`，
容器 identity 完整且租约持续续期；`PostgresPendingPreparationDirectory` 与
`PreparationWorker.resume_current` 已提供正式 `rehydrate` 路径。

本轮采用真实 crash-recovery 验证：先确认零 running execution、零 unresolved attempt 和 closure
终态，再强制终止旧 Host 及仅负责 attach 的本地 docker client；不停止容器、不改数据库。旧进程
singleton 锁释放后，立刻以原固定参数启动唯一新 Host。新 Host 必须通过正式 rehydrate 重新接管
同一 S generation，保持三项 lease 未释放、binding/route/epoch 不变，并在状态文件公开新的 PID。
若 rehydrate 失败或任一 lease 过期/释放，则停止本次 Policy v2，不以第二执行器或手工 worker 绕过。

### 8.8 Policy v2 的自然重试

新 Host PID 38768 已经通过正式 rehydrate 接管同一 S generation；三项容器 identity 未变、lease
继续续期、binding revision6/epoch3 和九条 route revision33/group60 均未变化。旧 v1 occurrence
已有 closure Receipt，tenant unresolved attempt 为 0。

v2 不复用已过期审批，也不重发 v1：读取当前 Case rev3 与 Policy rev1，构造相同业务语义但绑定
当前 exact Case 的 Put request，以新的 proposal/idempotency namespace 获得独立审批；随后按
`expectedPolicyRevision=1 / expectedCaseVersion=3` 写入 Policy rev2。SchedulePut 必须在同一事务
生成新的 control Receipt，并把 Case 推进到绑定 Policy rev2 的下一 revision。新 once binding
必须自然产生一个新的确定性 occurrence，唯一新 Host 从 discovery 开始执行；v1 始终保持
`cancelled/closed_unaccepted`，不得复活或复用其 target idempotency key。

### 8.9 第二次 discovery 拒绝后的停线穷尽检查

Policy v2 自然生成 occurrence `34733f17-f1ce-582d-b1b6-585a96aee2ff`，修复后 Host 已越过
缺表位置，但活动 Run 查询的 `analysis_type` 同时存在于 slot 与 Run 表，PostgreSQL 以
`AmbiguousColumn` 在目标调用前拒绝。该 occurrence 同样没有 RuntimeCommandReceipt、Run 或目标
Receipt。由于同一 discovery 阶段连续两次失败，本轮停止继续写 Policy revision。

最小修复把谓词限定为 `s.analysis_type`，并在测试中固定完整查询形状。随后必须使用真实
`aos_runtime` 租户连接，对 discovery 的活动 Run、当前 Plan、analysis route、ScheduleControl 和
Product snapshot 五段只读 SQL 逐段执行并校验列形状、权限与唯一性；同时检查当前 Case/Policy
exact refs。只有该离线穷尽检查全绿、v2 occurrence 经 a0v_082 正式 closure、唯一 Host 再次
rehydrate 新代码后，才允许新审批与 Policy v3。任何新 SQL/权限错误都回到方案与测试，不再消耗
新的真实 occurrence。

### 8.10 S 自有十二源 governed snapshot group

真实 runtime 只读角色执行五段 discovery SQL 后，前四段已经通过，但 Product snapshot group 为
空。现有最近成功 65 行属于已卸载 Q generation；S 没有自己的
`pipeline_source_selection_revision / pipeline_runtime_control_revision /
pipeline_schedule_control_binding`，因此不能借用 Q 的 claim 或 snapshot 作为 S 来源权威。

首次按 P02 正式链路执行后，S 已生成 Product selection/control/binding，并通过受控 API
真实读取 65 行，形成一个绑定 S installation/generation 的
`pipeline_controlled_source_claim`。但该单源 schedule run 不负责组装
`pipeline_snapshot_group_input/member`；组表为空是既有职责分离的正确结果，不能把单源 claim
描述成完整 snapshot group，也不能手工补表。

在允许 Policy v3 前，改为按现有十二源 snapshot schedule 正式链路为 S 生成一致性组：

1. 从当前 S 签名包一次性编译 P01-P12 的 graph、mapping/schema/masking exact refs；逐管线读取
   current selection/control/binding，以 exact previousRef 做 CAS，用 S 专属且每管线唯一的
   idempotency key 写入；已完成的 P02 只允许 exact readback，不重复提交；
2. 十二个既有 schedule 必须全部保持 disabled，且 `ingest.kind=pipeline-live-v1`、pipelineId 与
   schedule 一一对应；将每个 schedule 绑定到同一 S installation/generation/epoch 的 current
   control，禁止跨安装继承 Q/J 的 control 或 claim；
3. 调用 `PipelineSnapshotScheduleService.options` 反向验证十二成员和签名包导出的
   SnapshotRelationshipPolicy；以新 definition id 配置 disabled definition，再用 exact predecessor
   transition enable。配置与 enable 只授权组调度，不直接写商城源库；
4. 启动既有 independent snapshot worker。worker 必须从 enabled definition 自然 claim 同一 group，
   经十二个 current schedule 读取真实商城，并在正式 completion 路径写入唯一
   group/input/12 members；每个 member 的 run/claim/control/selection 均绑定 S，组的
   readCompletedAt 在 24 小时内；
5. 任一源失败时由既有 recovery/Receipt 路径处理，不手工插入 snapshot 表、不复制或回写旧代
   claim、不把部分组供经营参谋使用。执行结束将 definition disable，十二个源 schedule 继续保持
   disabled；要求 canary 组为 0，随后再让真实 runtime 角色重跑 discovery 五段 SQL；
6. discovery 只在恰好一个当前 S 完整组时才允许 Policy v3。若 Host/worker 没有装配该正式能力，
   先补运行时接线及生命周期测试并完成 crash-rehydrate，不能用一次性脚本冒充自然链路。

### 8.11 首个十二源 group 的预算前拒绝与正式关闭

S definition rev5 以一分钟验收节奏自然产生 group `f8d6b5af-f7a3-5f15-88ee-6432012f9537`，
并原子预留 12 个 schedule run。随后 group claim 在任何源调用前命中
`SourceCallBudgetExhausted`：P02 control rev1 的 `maxSourceCalls=1` 已被之前的单源 65 行验证消费。
只读核验和回滚复演共同证明：该 group 没有 `pipeline_snapshot_group_claim`、没有本组
`pipeline_controlled_source_claim`、没有 ingress journal、没有 snapshot input/member；12 个 run
仍为未受理的 `running / executor_stopped=false`。因此不能提高旧 control 的预算、复用旧 claim，
也不能让 worker 把未知源结果当作可重试。

新增 `a0v_083_snapshot_unaccepted_group_closure.py`，提供受限 maintainer 函数和不可变 Receipt：

1. 只接受 exact group、current definition ref、12 个原始 run，要求 definition 先 disabled；
2. 在同一 SERIALIZABLE 事务锁定 schedule claim、definition、12 个 run，并再次证明 group claim、
   source claim、ingress journal、snapshot input/member 全部为零；
3. 写 `pipeline_snapshot_unaccepted_group_closure_receipt` 后，将 12 个 run 终结为
   `failed / ec-live-v1 / executor_stopped=true`，错误码固定为
   `SOURCE_BUDGET_REJECTED_BEFORE_GROUP_CLAIM`；该 Receipt 明确 `businessAccepted=false`；
4. 关闭后为 P02 写新的 selection/control revision 和 binding，获得新的单次源调用预算；其余 11
   个 current S control 不变。definition 在 disabled 状态以 12 个 current binding CAS 重配并重新
   enable，新 minute slot 由 worker 自然产生；
5. 若任一“零副作用”断言不成立，closure 必须拒绝并转人工 receipt reconciliation，不得覆盖 run。

### 8.12 已关闭未受理组退出 dispatch pending 集合

a0v_083 已证明原 rev5 group 在任何 group/source/ingress 接受前因 P02 单次预算耗尽而失败，
并以不可变 Receipt 将 12 个悬挂 schedule run 终结。rev8 启用后未产生新 group；只读诊断确认
`PipelineSnapshotScheduleDispatch.inspect` 仍把所有非 12/12 succeeded 的历史 group 放入
`original_group_pending`，没有识别正式 closure Receipt，因此新 definition revision 被旧失败历史永久阻塞。

最小修复限定为 `pipeline_snapshot_schedule_dispatch.py`：候选历史查询左联
`pipeline_snapshot_unaccepted_group_closure_receipt`，仅无 closure Receipt 的未完成组继续进入 pending；
已关闭组仍保留完整 claim/member/run/Receipt，不删除、不改成成功，也不进入 saved-input recovery。新增回归测试固定
“有 Receipt 排除、无 Receipt 仍阻塞”的 SQL 形状。由于唯一 Host 已加载旧模块，测试通过后按 8.7 的
crash-rehydrate 路径换代，保持 S installation/generation/epoch、route 和 lease 不变；新 Host 自然枚举 rev8。
若重启后仍无自然 group，则禁用定义并回到只读诊断，不直接调用 `run_definition`。

### 8.13 独立 worker 的无敏感信息失败分类

rev8 在加载 8.12 修复后已由正式 runtime 只读状态确认处于 `due`，独立 worker 也持续按 15 秒节奏
建立数据库连接，但没有生成新 group。现有 `PipelineSnapshotScheduleWorker.tick` 会把单个 definition 的
所有异常统一收敛为 `SNAPSHOT_EXECUTION_UNCONFIRMED`，同时不写任何安全分类日志；这保持了未知结果不重发，
却使“claim 前整体回滚”无法与源调用后的未知结果区分，不能据此安全修复。

最小诊断改动限定为 worker：捕获异常时继续返回原有 unknown 合同、继续禁止自动补写 failed/stopped，
只用既有结构化 logger 写入固定事件名、definition id 与 Python 异常类名。禁止写异常消息、traceback、
SQL、连接信息、源数据或 actor。回归测试必须证明外部 outcome 不变、日志不含异常消息且仅包含安全分类。
加载补丁后只重启独立 API/worker，不重启唯一 Runtime Host；等待自然 tick 暴露分类，再针对真实根因另起
方案切片。不得为了诊断直接调用 `run_definition`，也不得在 unknown 结果下重复提交任何源副作用。

### 8.14 PermissionError 的安全来源定位

8.13 自然 tick 已稳定确认异常类为 `PermissionError`；十二个 current binding 的 actor 又经 runtime
只读角色逐项核验，均与 definition executor 一致。为避免读取或输出异常消息，诊断继续只在 worker
边界增加末端 traceback 函数名分类：函数名必须匹配受限 ASCII identifier，超界一律归为 `unknown`。
日志仍只含固定事件、definition id、异常类名和该安全函数名；不输出文件路径、行号、异常消息或调用栈。
测试固定安全函数名，并证明命名不合法时降级。重启独立 worker 后，以自然 tick 的来源函数决定下一项
修复；正式 claim、unknown 合同、重试和业务表均保持不变。

### 8.15 S 租约释放后的禁入与 clean successor

安全来源定位得到 `PermissionError / run_guarded`。随后以 runtime 只读身份复核权威状态：S binding 已为
`observed_state=unknown / enabled=false / operation_fence=true / execution_epoch=4`，三项资源租约均在
`2026-09-17T00:30:35.436590Z` 后由正式恢复器记录为 `released / observed_release=true`；唯一 Host 的
liveTargets 为空。该终态解释了门禁拒绝，也证明 SSH、商城源表和 cron 不是阻点。

rev8 definition 仍 enabled 但已无可执行安装权威，先通过原 SnapshotScheduleService 的 exact rev8
transition 正式 disable，停止无意义 unknown tick；不得直接更新 definition。S generation 不允许原地
复活、续租或改回 ready。下一波复用已评审的 clean-successor 生命周期建立新 installation/generation，
完成 prepare/verify/configure/enable 与九路 successor cutover；随后为新代重新签发十二源 selection、
control、binding 和 definition，旧 S 的 closure、rev8 与资源释放历史全部保持不可变。只有新代
ready/unfenced、唯一 Host liveTarget 和 canary=0 后，才恢复自然 snapshot group。
