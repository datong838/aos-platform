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
