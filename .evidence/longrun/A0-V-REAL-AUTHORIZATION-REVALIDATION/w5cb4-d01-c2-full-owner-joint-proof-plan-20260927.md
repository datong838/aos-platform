# W5CB4 D01 C2：完整原链与 AgentRun Owner 隔离 PG 联合证明方案（2026-09-27）

## 上位、现场与目标

沿用 231 A1-02/03、231-9 BG-02/03、`w5cb4-d01-complete-packet-selection-plan-20260927.md`。A/B/C1 的提交依次为 `088fe0eb`、`ce18aa32`、`a615c552`；C1 已在单个隔离 PG 正式两阶段决定后读回、撤销后拒绝，但尚未把真实原 AnalysisContinuationOrigin、当前 Method/Query/Bundle/Grant 与 AIP AgentRun Owner Receipt 合并为同一次 PG 联合正向。当前实例最近独立库版本 a0v_106；本波只用隔离库，不能把夹具写到当前业务库。

目标是证实唯一获批 D01 packet 经原链、同事务选择、当前来源读门后，AIP Owner 只写一条同租户 AgentRun 与一份原 key Receipt；撤销、缺 Grant、错来源、旧 Plan、错 actor、未知提交均不触发第二写。正式 Host 仍不注册，不制造可执行预算/Provider。

本计划分两个可独立提交的子切片：**C2a** 先修复正式 Plan Schema 与后置 packet 的错误等价假设，并做专项/累计/隔离 PG/浏览器禁入证据；**C2b** 再做下述同库完整原链联合正向。C2a GREEN 不算 C2 退出，C2b 没有真实 PG Owner Receipt 前不得进入 D 的运行准入。

## 文件级清单与执行顺序

### C2 方案修订：正式 Plan 与后置来源包不是同一审批对象

本波源码审计发现真实硬冲突：`aip_production_contract_store.py::compile_stage_template` 将每个正式 PlanStep 的 `input_refs` 固定为 `[stage.input_schema_ref]`；Method/Query/EvidenceBundle/Grant 由后续分析才形成。因此原先要求 portrait `PlanStep.inputRefs == D01SourcePacket/AgentRun.inputRefs` 会使**正常编译的 Plan 永远不能进入 D01**。不能靠测试夹具给 Plan 塞运行后引用，或在已批准 Plan 上补写。正确的双门是：Plan 审批批准任务阶段/Schema/责任人；后置 `D01SourceSelectionApproval` 由同一原 Plan checker 对完整 exact packet 独立批准，绑定不可变 Plan hash、TaskRun 和原 SourceSelection。`NaturalD01Issuer` 必须强制消费当前选择回调（缺失即拒绝），并保留 AgentRun inputRefs 与 packet exact 相等及原 Method/Query/Bundle/Grant 当前校验。C1 Atomic 的同事务选择读门不得因为移除错误的 Plan 包集合比较而失效。

修复文件：`ecommerce_analyst_d01_issuer.py` 构造器强制选择回调、把 Plan 输入验证改为编译器的 Schema 身份；`ecommerce_analyst_d01_source_selection_store.py` 的 propose/read_current 同步使用 Schema 门；`ecommerce_analyst_d01_atomic.py` 将同事务选择读回供 issuer 强制回调复核；对应三组单元/隔离 PG 测试以真实 compiler 样式 Plan 先 RED。不得放宽 Plan 批准状态、hash、checker 与 packet/AgentRun exact 集合。

1. 复习 `test_ecommerce_analyst_d01_atomic.py`、`test_analysis_continuation_origin_pg.py`、`test_ecommerce_analyst_portrait_inputs_pg.py`、`test_aip_agent_run_execution_service.py` 的隔离 fixture 和 Owner 建立合同，明确哪些可复用，禁止用 fake 代替联合正向。
2. 在 `services/aos-api/tests/extension_runtime/test_ecommerce_analyst_d01_atomic_pg.py` 先 RED：构造**仅隔离 PG** 的合法原 Context/Run/Plan/选择 proposal→checker approval、Method/Eval/Metric/QueryResult/EvidenceBundle/Grant 与 AIP Actor/Agent/Skill/Policy 最小必要行；调用未注册 Atomic coordinator，读回唯一 AgentRun/Receipt。基于同一 fixture 做撤销/缺 Grant/跨租户/漂移拒绝与 Owner 零写。
3. 若 RED 暴露生产代码缺口，只在 `services/aos-api/aos_api/ecommerce_analyst_d01_atomic.py`、`ecommerce_analyst_d01_source_selection_store.py`、`ecommerce_analyst_d01_issuer.py` 所需精确位置修，不放宽现有门；先修方案记录再最小编码。
4. 专项、C1+B+A/原链/Task/AgentRun 累计；安全浏览器 8080/8434 状态只作“不适用真实运行”的边界读回；方案/代码一致性、verification、m1 精确 commit。通过后才进入 D 当前库迁移/产品入口的独立备份和权限前置。

## 有界停止与旁路主线

不读商城源数据，不人工 `run_definition`，不重放原 12 Run，不开放 18181/Host/Provider，不删除当前库或备份。若现有 Owner fixture 无法在合理范围合法拼接，记录具体缺的权威/契约与可复用准备结果，保持 C2 RED，不把 mock/隔离单项标绿；及时转 BG-00 最小合法绑定/配置主线，避免只为测试夹具无界消耗。未知提交只按原 key/Receipt 只读对账。
