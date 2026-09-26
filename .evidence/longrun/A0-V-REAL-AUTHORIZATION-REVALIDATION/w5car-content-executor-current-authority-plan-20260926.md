# W5car｜内容持久命令的正式执行输入与结果回流（开码前方案）

## 上位、现场与目标

依 231 A1、231-5 第 1/5/6 节、231-6 AR2-6/N7、栖月汇双侧增长产品方案及 W5caq 核验。基线 m1 `6e6d86b7`：v2 `content.generate` 已在 Host 同事务留下 HELD Reservation、不可变 Journal Command、PENDING 非终态 Receipt；原 `ContentExecutionWorker` / `ContentResultConsumer` / `ExactProviderInvoker` 只在隔离测试经任意回调装配，生产没有可信 selector、prepare、结果查询及启动入口。不能用 PENDING 伪称完成，也不能让旧 v1 FAILED_NO_EFFECT 或旧 12 Run 被扫描重发。

目标是把现有 Owner 串成唯一、安全的文字内容执行链：当前租户及安装/Dispatch 权威选择 → 从不可变命令得到原 approved Plan、事实与有界 prompt → READY exact route/price/Provider → 预算提交外呼意图并 commit → 原 invoker 一次外呼 → Journal 结果 → 原 Consumer 原子 Usage/Artifact/Budget → 独立状态回读。真实调用只在当前 scoped Provider、预算、出境/分类、事实、审批均有效时开放；隔离测试不能代替真实授权。不得新增第二套预算、路由、产物或幂等 Owner。

## 串行文件级清单（第 1～6 步）

1. **当前身份与 selector**：在 `services/aos-api/aos_api/ecommerce_content_execution_journal.py` 增加租户限定、有限批量的 HELD 候选读；候选必须同时有 v2 PENDING runtime Receipt、同一命令 hash、同一 Reservation，且不存在结果。仅返回稳定 reservation id，不以时间阈值重新领取 SUBMITTED/UNKNOWN；读回与运行时再次复核。测试放 `services/aos-api/tests/aip/test_a0v_content_execution_worker_pg.py`，含 v1/no receipt、污染、并发、跨租户、未知状态。
2. **可信 prepare**：新增 `services/aos-api/aos_api/ecommerce_content_execution_composition.py`，复用 `ContentGenerateHostService.revalidate` 的批准 Plan/Brief/事实/预算/容量门及当前 Dispatch/Installation fence，复用原 `AipModelRuntimeResolver` exact READY，不从调用者收 prompt/Provider/tenant/Secret。只用 approved 方法及已验证事实正文组装有界文字 prompt；没有可读业务事实则该实例 HELD 且 blocked，不造商品名。`PreparedContentInvocation` 必须携带 exact resolution 与允许的数据分类。独立测试覆盖 drift/撤销/过期/缺事实/错误租户及无外呼。
   - 锁序补充：原 Host 先锁 Dispatch group、后锁预算；当前 Worker 却先锁 Reservation、后调用 `prepare`。正式 `prepare` 若复用 Dispatch 锁，必须先重排 Worker 为只读预检 → 锁当前 Dispatch/安装 → 锁预算并复核状态/命令 → submit；不能维持反向锁序。预检不可充当提交时授权。并发测试必须证明与 Host 入队并行时无反向锁、同一 Reservation 只提交一次。
   - 费用上界补充：现有 `ExactProviderInvoker` 文字请求未带 `max_tokens`，而命令含 `maxOutputTokens`。在正式 worker 接线前，先将已验证命令上限经 `PreparedContentInvocation` 传给原 invoker，并在文字请求中设置明确输出上限；不接受 caller 自报或靠 prompt 文案限额。旧隔离调用默认参数保持兼容，生产组合必须提供严格正整数。prompt UTF-8 字节数不得超过已批准 `maxInputTokens`，超限直接保持 HELD 并报 blocker，不截断来源。
3. **正式唯一外呼**：在原 `ContentExecutionWorker` 接入上述 prepare 与原 `ExactProviderInvoker`；提交 ProviderRequestReceipt 后 commit，再在事务外调用。多进程并发由原预算行锁与 submit 幂等控制；任何已 SUBMITTED/UNKNOWN、崩溃后重启、网络超时、结果存储不明都只读 reconcile，不自动重发。运行生命周期采用现有 API 进程明确开关和受管后台任务，不用临时脚本或第二 Runtime Host；启动前先只读核验单进程/配置/授权。
   - 受管启动的精确文件是 `services/aos-api/aos_api/main.py`、`ecommerce_content_execution_composition.py` 与 `tests/extension_runtime/test_ecommerce_content_execution_startup.py`。新增显式 `AOS_ECOM_CONTENT_WORKER_ENABLED`，默认 false；true 时必须同进程已有 ACTIVE Runtime Host 任务、独立 runtime DB 身份与固定 `org-org/dev-project` 试点 scope，任何缺失使启动 fail-closed。后台一次只跑有界 `run_once`，先消费旧结果→执行 HELD→消费新结果；异常不自动重发，任务失败须显式状态可见，不静默无限重试。正式开启仍需独立当前授权验收，代码合入不等于启用。
4. **结果回流与状态**：复用 `ContentResultConsumer`，从当前 TaskRun/Brief/Plan/商品事实生成 context，而非测试 lambda；消费后独立读 Journal+Budget+Usage+Artifact，只有真实可读 Artifact 与 exact Receipt 全部吻合才暴露 COMPLETED，费用未知为 COST_PENDING；UNKNOWN 只读对账，不把提交/结果记录当完成。
   - 独立状态读回还需核对 ProviderRequest/ProviderResult Receipt、Usage 两种 measured token 类别、Artifact 正文非空/内容 hash/TaskRun 归属；`RESULT_RECORDED_UNSETTLED` 不是完成。某条命令的已知当前权威冲突可记为该条 `BLOCKED_CURRENT_AUTHORITY`、不妨碍其他已授权命令；提交边界或外呼结果未知、非预期异常仍 fail closed，绝不因为继续批处理而重发。
   - 外呼已发生后，即使 Plan 头随后更迭或来源超出七天，也必须以当时提交前已验证的不可变 exact Plan/命令和 AgentRun→TaskRun lineage 记账/保存产物；不能再用“当前头”门把已发生费用永远卡在未消费状态。此历史 exact 读取**只用于结果消费**，不授予再次调用 Provider 或推进新业务动作。人工评审/续跑仍需各自当前门。
   - 崩溃恢复补充：Journal 有结果但 Artifact/Usage/Budget 尚未消费时，HELD selector 不再命中。原 Journal 需有独立的租户有界 `list_recorded`，仅选 SUBMITTED/UNKNOWN 且结果 hash 与 ProviderRequestRef exact 的待消费行；runner 先消费这些行，再处理新 HELD。消费失败保留原结果可重试消费，但绝不再次 Provider 外呼。状态仍需独立读回，不以消费函数返回值直接宣称 COMPLETED。
5. **RED→GREEN 和累计回归**：先写失败用例再最小实现；隔离空 PG 覆盖事务提交后外呼、双 worker、重启、rollback、错误 Provider、消费中断、RLS/canary、状态读回。累积运行 W5cap/W5caq、N7、预算、原 worker/consumer/invoker 及 migration tests；`compileall`、`git diff --check`。如有 UI/路由变化再浏览器逐页验收；本步若没有则 N/A，不能伪造。
   - 测试环境边界：旧 `test_a0v_content_result_consumer_pg.py` 与 `test_a0v_content_usage_pg.py` 夹具先 `LIKE public.aip_lineage_event`/`aip_artifact`，空 PG 容器缺公共基线时会在夹具失败；必须使用经原迁移建立该基线的**隔离** PG，或精确补全夹具前置，不能改代码逻辑来掩盖基础设施失败，也不能拿 71 项邻接通过冒充全部累计绿。
6. **证据和续波**：落 `w5car-...-verification-20260926.md`，只在真实做到的范围内写 GREEN，m1 精确提交；更新 D-waves、AOS 上下文、Prime 记忆。下一波 W5cas：新签名包版本与安全安装迁移、当前真实 scoped authority/Provider canary，随后自然内容产物→人工评审→反馈/Wiki 候选；若某实例授权不全，仅阻断该实例并继续其他首链研发。

## 停止、风险与回滚

`PENDING`、`HELD`、隔离测试、计划和提交均非业务成功。未能证明当前安装代次或 approved 方法、事实、审批、预算、数据分类、模型与 Provider 时，绝不提交新的外呼意图；如果提交边界未知或 Provider 结果未知，冻结原 reservation 并只读对账，不重发、不换 Provider、不手工 `run_definition`。旧 12 Run 退休和 230 L0 后置。只改上述精确文件与测试；现有已签名候选包不原地改；撤回未启用的新执行组合即可回滚本波代码，不删除已经提交的 Journal/预算/Receipt。
