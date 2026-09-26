# W5caq｜内容能力持久待执行交接（开码前方案）

## 上位方案复习与不可跳过的合同修订

231 A1、231-5、231-6 AR2-6/N7 要求已批准事实→预算/审批→唯一 Provider 请求→可读 Artifact；外呼必须发生在已提交的预算/命令意图之后，UNKNOWN 不重发。当前 `ContentGenerateHostService.execute` 在一个 HostTransaction 内 reserve→release_no_effect，包 `ContentCapabilityReceipt` 只接受 `COMPLETED/FAILED_NO_EFFECT/UNKNOWN` 三个**终态**；仓库已有隔离实现的 `ContentExecutionJournal`、`ContentExecutionWorker`、`ContentResultConsumer`、`ExactProviderInvoker`，但没有正式接到该 Host。若仍要求同步 terminal Receipt，会把网络调用压到事务内，或把 held 错报为 UNKNOWN/FAILED_NO_EFFECT，均违反上位安全规则。故需补一个显式的 **PENDING 非终态接收回执**，不计为 AR2-6 终态/业务成功；后续由持久 worker 独立消费并由正式状态查询/续跑取得终态。

本波只实现 Host reserve + Journal enqueue 的同事务原子交接及 PENDING 回读；**不启动 worker、不外呼 Provider、不生成 Artifact、不开真实部署**。方案本身不允许把孤立的 PENDING 视为首链已完成。先在 231-6 对非终态/终态口径作最窄修订，保留三种原终态定义。

## 文件级施工与验证

1. `docs/palantier/20_tech/电商平台接入/231-6-串行施工包与双目标联合验收实施方案.md` 明确 `PENDING` 只是已持久化的异步接收回执，Budget=`HELD`、零 Provider/Usage/Artifact；终态仍仅 `COMPLETED/FAILED_NO_EFFECT/UNKNOWN`，业务调用方必须等待/查询，不得用 PENDING 进入人工评审。
2. `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_receipt_first_no_effect.py` 与 `tests/extension_runtime/test_ecommerce_content_capability_budget_runtime.py` 先 RED：v1 no-effect 不变；v2 只有当前 Host 验证后才能产生 PENDING；同 key 相同命令回读、不同命令拒绝；Journal 写失败整个 reserve 回滚；PENDING 不允许任何产物/Provider 效果。隔离 PG `tests/aip/test_a0v_content_execution_journal_pg.py` 增原事务交接证明。
3. `services/aos-api/aos_api/ecommerce_growth_host_ports.py` 只增加受信任的 `HostTransaction` 窄方法，代原 Host 向既有 Journal 传底层连接，不开放任意 SQL/commit；`services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 对含方法的 v2 才 reserve→enqueue→返回 PENDING；现有 v1 保持释放 no-effect；`verify_receipt` 从原预算 Owner + Journal 读回 exact 请求，允许预算后续转态但不把 PENDING 改写成终态。需证明当前 Host 事务失败即无孤立预算/命令。

   施工中补充：预算一旦从 HELD 进入 SUBMITTED，当前 `BudgetReservationRevision` 的 revision/hash 会变化，若下游重算当前 ref 就会误判历史 PENDING。故在原 `services/aos-api/aos_api/aip_budget_reservation_store.py` Owner 内抽出创建初始 HELD/Invocation exact refs 的唯一函数，`reserve` 与 PENDING 回读共同复用；Host 不复制 hash 算法。`tests/aip/test_aip_budget_reservation_pg.py` 的默认 2026-09-08 审批已在 9 月 26 日过期，测试夹具改用当前 UTC；不更改生产审批语义。隔离 PG 必须证明提交后预算状态前进仍可回读原接收回执，且相同命令不再执行 reserve/外呼。
4. `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/content_capability_runtime.py` 接受严格 PENDING 非终态；不得改历史候选/已签名包。新增版本/安装迁移单列后波。运行专项+累计+隔离 PG，编译和 diff check；无 UI 改动，浏览器 N/A。
5. verification 落盘、m1 精确提交、AOS/Prime 上下文同步；下一波 W5car 设计正式 worker selector/prepare/定时驱动、提交后唯一外呼、结果消费和 UNKNOWN 只读对账，再谈当前批准下的真实调用。

停止门：若无法证明 PENDING 与现有 Receipt/Journal 原子同事务，或已签名包合同必须原地改写，则不执行第二调用、不释放成假失败；记录缺口并改方案。旧 12 Run 不重播，不读商城源，230 L0 挂起，dev-org 零 canary，m1 单写不 push。
