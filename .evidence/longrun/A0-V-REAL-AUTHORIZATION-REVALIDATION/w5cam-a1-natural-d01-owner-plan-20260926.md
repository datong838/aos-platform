# W5cam｜A1 自然 D01 正式 Owner 接线计划

## 上位目标与 W5cal 交接

依 231 A1、231-9 BG-02/03、经营参谋 D01-D03 与栖月汇产品方案，商品更新自然 Case/Run 之后须在当前来源、exact 方案、权限/预算约束下产生有来源建议。W5cal m1 `950b9958` 只做 Host 内原分析 Receipt/代际/Task 状态的**只读发现**；它不是执行授权。当前真实 PG 无 running TaskRun/MethodRevision/Insight，旧 12 Run 不重播、不作业务输入。

## 本波 1–6 步

1. 复习 `AipAgentRunService.create/transition`、D01 Worker、`PostgresAipProductionCompositionSource`、Metric/MethodRevision 与方案审批/预算合同；确定单个当前自然 TaskRun→原 Occurrence/Receipt→批准 Plan→D01 绑定/输入的精确闭包。发现缺 authority，只阻断该实例，继续可隔离实现。
2. 文件级 RED：优先复用现有 Owner，不新增平行 AgentRun 表；在 `services/aos-api/aos_api/ecommerce_analyst_stage_runtime.py` 旁新增最小 D01 issuer/coordinator，测试覆盖同租户、旧代、暂停/终态、重复领取/未知提交、当前 Method/指标/模型路由/预算缺失、唯一正例。若现有事务/Receipt API 不足，先更新本方案再改码。
3. 最小实现：Host 仅在所有当前门为真时调用正式 `AipAgentRunService.create` 并读回原 Receipt；稳定 idempotency key，unknown 不换 ID。D01 Worker 使用原稳定 attempt，不人工 `run_definition`，不读商城源。真实 Provider 默认不开。
4. 专项、累计、隔离 PG 重启/重复事件/撤权测试；区分 mock GREEN 与真实运行。
5. 有运行 UI 才做浏览器只读验收；没有当前真实安装/新鲜截面/审批/预算时，不起真实 Host 或收费 Provider，不伪称自然结果。
6. verification 落盘、提交、AOS/Prime 上下文同步，自动进入 D02/D03 或最早未闭合核心波。旧 12 Run 正式退休及历史逐行来源列后置待办。

停止条件：原链不唯一、当前 authority/方法/来源/预算/模型不可证或提交未知，冻结该动作并只读对账；绝不重发、造来源、绕 Owner、拿旧数据当今天新鲜。m1 单写者、不 push、230 L0 挂起、dev-org 仅零 canary。

## 第 1 步后文件级细化（编码前）

`AipAgentRunService.create` 只核 exact Task/TaskRun/Plan 版本、当前实例/Skill/Logic/Capability，不核 TaskRun running/Task executing/Plan approved；D01 Worker 才核运行态。W5cam 第 2 步先新增 `services/aos-api/tests/extension_runtime/test_ecommerce_analyst_d01_issuer.py` 的 RED：错误 scope、paused/terminal、未批准 Plan、缺完整 inputRefs、已有 AgentRun/未知结果、单一合法正例。实现仅在 `services/aos-api/aos_api/ecommerce_analyst_d01_issuer.py`，用原 `AipTaskStore.timeline`、原 D01 来源 reader 与 `AipAgentRunService.create`，稳定 ID/key；不改泛型 AIP Owner。Host 尚不能无来源包自动发 D01，因真实 MethodRevision=0；本波后续须做自然 packet selector 的隔离 PG 证据后才注册发行路径。任何 mock 正例都只证明代码，不是现实业务执行。

## 第 2 步复审纠偏（下一代码改动前）

m1 `4423c87c` 的布尔 `require_current_sources` 只有注入式测试，没有把 exact Method/Eval/Metric/Query/EvidenceBundle 包传入 reader；不能作为生产来源门。先在 `services/aos-api/tests/extension_runtime/test_ecommerce_analyst_d01_issuer.py` 写缺包/错包 RED，再改 `services/aos-api/aos_api/ecommerce_analyst_d01_issuer.py` 接收严格来源包；在 `services/aos-api/aos_api/ecommerce_analyst_portrait_inputs.py` 抽取共用的“拟签发请求输入”只读核验，保持既有 D01 Worker 行为不变。生产来源 reader 必须实际走同租户当前 Method/Eval/Metric/Query、EvidenceBundle 与 DisclosureGrant 既有 Owner，不直接读取商城源。此门通过前不接 Host；隔离测试只证明代码，真实 MethodRevision/running TaskRun 仍缺。
