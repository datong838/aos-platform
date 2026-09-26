# W5CB0｜内容 AgentRun／容量／自然命令接线（施工前）

## 上位方案和现场复核

- 231-5 §1/§4/§6 与 231-9 §2/§5：内容 Run 之后应自然进入数字同事实执行，独立核当前 ModelRoute、能力、预算、审批、容量；生成的真实文字与来源供人工评审，不发布/发送。产品方案的内容官武器包仍以已批准方法为事实边界。
- W5CAZ `7c93cf24` 已把 exact Review→内部 Plan/TaskRun 启动写为单次持久意图，真实开关默认关；仅 `accepted` 且 Run 当前 running 才可进入本波。原 Review Receipt 仍表示创建时 0 Run，不可篡改。W5CAR/AS 已有正式内容 Worker/Consumer，入口依赖 `content.generate` 的 12 个 exact authority、事实来源、预算与容量引用；目前没有自然 Owner 填这些引用。
- 公共 `AipAgentRunService._create_in_transaction` 能借原串行事务创建 queued AgentRun；其 `transition` 到 running 才会解析 READY Route 并通过 `AipModelCapacityReservationGate` 预留容量。D01 的 `NaturalD01AtomicCoordinator` 是可复用的单事务模式，但未注册真实 Host。不能复制 AgentRun 表或直接插容量行。

## 文件级最小切片

1. RED：新增 `services/aos-api/tests/extension_runtime/test_ecommerce_content_agentrun_owner.py` 与隔离 PG 门，覆盖 accepted Review/Run 唯一出队、同租户当前 full group、exact Task/Plan/Run 与 Approved GrowthPlan/Brief/四来源、撤销/旧 epoch、已有 AgentRun Receipt、未知提交和 dev-org 零 canary。
2. 先核现有公共 AgentRun、容量及 `content.generate` 请求合同是否有可借用的同事务执行入口；不得绕过 `AipAgentRunService`、`AipModelCapacityReservationGate`、预算 Owner。必要的 `a0v_102` 持久 intent/claim/ack 在 Review/Run accepted 后独立写入，先 claim 唯一 attempt，再创建 queued AgentRun。若创建与容量/命令无法原子化，拆为两个持久阶段，绝不对 claimed 重新发。

   施工修订（RED 后、编码前）：`a0v_102` 的下一阶段 pending 意图必须由 W5CAZ 的 Run ack 所在事务同步写入；ack/put 任一失败时 Plan/Run 启动整体回滚，已持久 claim 仍不重发。此前未上线的 W5CAZ Worker 默认关闭，故不回填既有 accepted 结果；若未来发现迁移前 accepted 行，冻结并走正式对账，而非扫描补发。下一阶段 claim 与 AgentRun 创建则分离事务，提交未知一律不自动重试。
3. 新增 `services/aos-api/aos_api/ecommerce_content_agentrun_owner.py` 的 tenant-bounded 默认关闭自然消费者，及 `main.py` 同进程 ACTIVE Host/runtime-only 身份门。先让 exact 当前 AgentInstance/Skill/Logic/Route/Policy/TaskRun 形成唯一 queued AgentRun，并独立读回 Receipt；容量和 `content.generate` 命令在另一个明确的 claim 门，不得把 queued 当可生成内容。

   实码复审补充：W5CAZ 内部 PlanStep 当前尚无 `assigneeRefs`/`responsibilitySlotIds`，故单靠 AgentRun Owner 查一个“当前内容官”会发生未获批准的动态指派。先在 W5CAZ 创建内部 Plan 的事务里，从当前且唯一的 frozen/READY/COMPLETE `content.generate` 责任槽解析 AgentInstance 与 Capability，写入生成步骤的责任槽、assignee 与 exact 责任计划依赖；若无唯一当前槽，必须在 claim 前拒绝而非花费 attempt。W5CB0 之后以该不可变 Plan 绑定再重验当前责任、Skill/Logic/Route/Policy，任何漂移不创建 AgentRun。隔离 PG 与负例应证明此绑定。
4. 复用 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/content_capability_runtime.py` 的严格请求，所有 12 个 authority、价格、审批、预算上界、factSourceRefs、容量需由当前 Owner 读取并精确编译，禁止页面或工程师补引用。预算 held/PENDING 同原 Host 事务提交；Provider 提交和调用仍归原 W5CAR/AS Worker，开关不自行开启。
5. 若上位方案所需的 AgentInstance/Skill/Route/审批/价格/容量当前权威无法证明，本波只交付不产生副作用的持久下一阶段门和证明测试，verification 明列阻断；不得捏造 Ref、硬编码角色或以 mock 绿当真实产物。

## 验证与停止

- 施工分段裁决：公共 AgentRun `create` 只留下 queued Receipt，`transition` 才有容量预留；`content.generate` Host 才有预算 HELD/PENDING，Provider Worker 又有单次外呼提交边界。三者不能由 W5CB0 的 queued 事务伪装为同一效果。W5CB0 退出门限为“不可变 Plan 责任绑定→唯一 queued AgentRun/Receipt 的安全代码门”；容量、预算与自然命令是紧接的 W5CB1 实施目标，不把 queued 当内容完成。W5CB0 verification 必须逐项列出尚未达成的原计划第 4 项，不能改写成完成。

- 先 RED→最小实现→专项/累计/隔离 PG→浏览器（无活体明确记未验）→方案/代码一致性→verification→m1 commit→D-waves/AOS/Prime 更新→下一波。只读业务实例状态，不读商城源。旧 12 Run 不重放、230 L0 挂起；dev-org 仅零 canary。
- 任何 commit/Provider 结果不明：停止该 intent，独立 Receipt 对账；不手工 `run_definition`、不重发。无当前 Provider 出境、预算、审批和安装权威时真实外呼保持关闭。
