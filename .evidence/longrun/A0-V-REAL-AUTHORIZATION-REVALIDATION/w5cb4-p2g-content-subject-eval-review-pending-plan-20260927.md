# W5CB4 P2g｜已结算内容→主体 Eval→人类待办的离线接线（施工前）

## 上位目标与边界

- 依据 231-5 §1/4/5/7、231-9 BG-04、栖月汇产品方案及 W5CB4 总方案：内容必须是同一安装代次、原 TaskRun/Plan/Brief、真实商品和来源下的可读 Artifact；经正式结构/来源 Eval 后进入人工 exact 评审。机器不替人判断事实/合规，不自动发布或触达。
- P2d 已有受控内容结果的正式生成 StepRun；P2e 有内容主体 Eval 输入与策略 ref；P2f-a 令原 Plan gate 必须 exact；P2f-b `b771dc66` 在新 Plan 创建前读唯一当前内容权威。当前实例 `a0v_092`，预审包未安装，运行时链仍默认关闭。P2f-b 安装 executor 的多提交/未知结果对账暂列恢复队列，不阻断本波隔离、无副作用的核心编码。

## 文件级顺序与失败关闭

1. 只读审 `ecommerce_content_result_consumer.py`、`ecommerce_content_step_owner.py`、`aip_eval_runner.py`、`aip_production_contract_store.py` 的 Artifact、最新生成 StepRun、EvalReport、ReviewIssue 字段和当前安装权威；选一个由原生产链持久对象组成的 exact 候选键。先不要从测试夹具的任意报告生成待办。
   - 先行安全断点：公共 `create_review_issue` 目前对内容报告只核存在、同主体/attempt/原 Plan，不核 `gate_passed`；`ContentReviewHostService._issue_eval_authority` 的 ACCEPT 也未核结构预审通过。P2g 第一小改动先 RED→GREEN 封住 ACCEPT：失败报告可保留人工 RETURN 处置，但不能作为通过结构门的 ACCEPT；不改媒体/文本旧路径，也不把结构通过写成事实/合规通过。
   - 第二安全断点：`AipEvalRunner._assert_media_subject` 对内容只验 StepRun 身份/最新 attempt，未要求 `content_generate` 已正式 `succeeded`；现有正向测试甚至在刚 claim 的 StepRun 上跑内容 Eval。先把该隔离测试修成真正四相 TAOR 完成，再加未完成 attempt 的 RED；仅内容主体新增 succeeded 门，媒体/文本旧语义不动。主体 Eval 不可抢在已结算生成步骤前。
   - 纵深防线：内容 `create_review_issue` 和 Host 读取历史报告时也必须核最新生成 StepRun 的 `succeeded`，防止绕过新版 Runner 的旧报告/直写报告进入人工路径；先改邻近测试 RED，再仅在内容分支核状态，不改其他领域的 StepRun 规则。
2. 第一段先加 RED，再做 `services/aos-api/aos_api/ecommerce_content_review_pending.py` 只读候选投影。只有**已结算** Artifact、原 TaskRun 的 `content_generate` 最新 succeeded StepRun、原批准 Plan exact EvalContract gate、同一当前安装/Task/Brief、同一 Artifact/attempt/合同的通过报告才返回一个待办候选；缺失、跨租户、旧 attempt、错合同/hash、旧安装、失败报告、已有决定均为零或明确 blocked。GET 不创建 EvalRun/ReviewIssue，不写库。
3. 第二段在单独方案/测试下接正式主体 `AipEvalRunner`，按持久 intent／唯一候选键先只读对账再调用；EvalRunner 内多提交发生未知时冻结，不自动重跑。正式报告独立读回后才走公共 `create_review_issue`，不能拿治理报告或空壳 Artifact 代替。人类 resolve/return 沿既有公共 API 和 Host exact Receipt；worker 无代批权限。
4. 后续 ACCEPT 完成 `content_review` StepRun/TaskRun 正式终态，RETURN 形成新内部生成目标；反馈读回总控/Wiki 候选。每段都先专项、累计、隔离 PG、方案/代码复审、verification、m1 commit、AOS/Prime 上下文。若涉及页面做真实浏览器验收；纯后端段标不适用。

## 本轮首段停线

- 在当前实例无正式内容预审包、无合法真实 Artifact/报告时，只能给出默认关闭的代码与隔离验证，不开放生产 GET 的虚假待办。任何未知提交/当前安装不明、Report/Plan/attempt 不一致都失败关闭。
- 不读商城源，不回放原 12 Run，不推进 230 L0；`dev-org/dev-project` 仅零 canary；m1 单写、不 push。

## P2g 待办候选第一子步文件级细化（2026-09-27）

- `services/aos-api/aos_api/ecommerce_content_review_pending.py` 先只提供内部 `read_one(scope,reservation_id)`，不加 GET 路由、不创建 Issue。复用 `ContentGenerationStepSource.read` 的已结算 Result/Provider/Usage/Artifact/Task/Brief 来源读回和 `ContentGenerationStepOwner._readback` 的 TAOR/checkpoint；另核原内容操作 Receipt 与当前 dispatch/runtime binding exact 相等。后续 Host 仍需完整安装锁，不把 GET 的只读快照当写授权。
- 同一只读事务读取唯一内容报告、EvalRun、最新生成 StepRun、原 Plan gate 和当前内容合同；要求 report canonical hash、gate_passed、同 Artifact/attempt/合同、EvalRun succeeded。无报告返回 `None`；任一多义/漂移/撤销/旧安装抛出 `ContentReviewPendingBlocked`，不能自动造报告或审批。候选身份用 `(scope,reservationId,runId,artifactId,stepRunId,reportId@revision)`；重复只读返回相同值。
- 测试先在 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending.py` 用无写连接验证无报告、错租户、旧 attempt、错合同/失败报告、重复读稳定；再用隔离 PG 组合真正 settled Artifact/StepRun/EvalReport 的正向证明。若本子步做不到同库正向，verification 必须标为部分代码门，不得暴露生产 GET。
