# W5CB4 D01 当前来源包确定性选择计划（2026-09-27，下一波编码前）

## 复习与目标

231 A1-02/03、231-9 BG-02/03 要求原自然 Occurrence/Case/Run、批准 Plan 与 D01 完整同截止面来源。W5cam/W5can 现有 `D01SourcePacket`、同事务校验与未注册 coordinator；`65e32a45` 已将发行 actor 绑到原链，`c4ddec84` 已让**新**分析 Task 保留原数据 `selectionRef`（旧 Task 不回填）。编译 Receipt 仍未包含 Method/Metric/Query/EvidenceBundle/DisclosureGrant 完整包。不能从当前库“最新一条”推断 D01 输入。

## 文件级施工顺序（以最小原 Owner 复用为前提）

1. 先沿 `ecommerce_analysis_task_preparation.py`、`aip_business_investigation_compile_saga.py`、`ecommerce_analyst_portrait_inputs.py`、`ecommerce_analyst_analysis_sources.py` 和正式 Evidence/Disclosure Owner 查是否已有**同 TaskRun、同截止面、已批准、可撤销**的选择 Receipt。若有，复用它；若没有，先冻结新增仅引用的 `D01SourceSelection` 权威合同及同租户不可变存储、CAS/幂等 Receipt 和撤权读回方案，不复制来源材料或新建第二事实真源。
   - 已查明的最早丢链：`AnalysisContextPreparation` 在原事务已读 `sourceSelectionRef` 并经 SourceSelection Owner 复核，但 `prepare_analysis_task` 创建 Task 未写已有 `selection_ref` 字段。本波先以 `services/aos-api/tests/extension_runtime/test_analysis_task_preparation_pg.py` 的 RED 证明新 Task 必须保留原 exact 选择身份、错类型/缺失在写前拒绝；最小修改 `ecommerce_analysis_context_preparation.py` 与 `ecommerce_analysis_task_preparation.py`。该引用仅是原数据选择谱系，不包含 Method/Metric/Query/DisclosureGrant，绝不冒充完整 D01 packet 或执行许可。
   - 接续 `c4ddec84`，在未注册 `NaturalD01AtomicCoordinator` 内将 Task `selectionRef` 与原 AnalysisContinuationOrigin `context.source.policy.sourceSelectionRef` 的身份/修订同事务核对；原 exact 哈希继续由原 SourceSelection Owner 验证。先为缺失、错 ID/修订写 RED，不改 Task/Owner 表或执行入口；只加 D01 原链源选择一致性门。
2. RED 先覆盖缺失、多义、跨租户、错原 TaskRun/Plan、错截止面、过期/撤销、Grant 缺失、重复 key 不同 payload、未知提交；正式正例只能由原批准来源 Owner 创建选择引用，不接受调用者任意 packet 或“最新”排序。
3. 最小实现文件预计 `services/aos-api/aos_api/ecommerce_analyst_d01_source_selection.py`、现有 `ecommerce_analyst_d01_atomic.py`，必要时一项窄迁移与原 Owner 接口；测试放 `services/aos-api/tests/extension_runtime/` 并有隔离 PG 原事务/回滚/同键证明。实际文件与 schema 须在第 1 步核清后修订本计划，不能隐性扩范围。
4. 仅在精确来源选择和当前预算/模型/安装/能力/健康均有权威、隔离 PG 全链通过后才考虑 Host 注册；本波默认 Host/Provider/18181 关闭，真实库无业务写。专项/累计、适用浏览器、方案/代码复审、verification、m1 精确提交、AOS/Prime 上下文更新。

## 停止门

没有合规来源选择 Owner 时只阻断 D01 真实实例，继续可独立完成的 BG-00 正式配置开发；不读商城源、不重放旧 12 Run、不手工 `run_definition`、未知结果不重发。`dev-org` 仅零 canary，230 L0 挂起，m1 单写不 push。计划不等于实现或准入。
