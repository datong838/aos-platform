# SC4-5l 完整快照事实查询与质量存证方案

状态：IMPLEMENTATION_PLAN；2026-09-14；基线 d2476193；m1串行、不push、230 L0挂起。目标是原真实数据事件任务自然取得有来源的经营分析输入，并沿原审核/续跑链推进；本方案完成不代表真实首链或八工作台验收。

## 1. 已核事实与缺口

- 原initial_store_analysis v1请求12类事实、store粒度、实际30日窗口、qualityThreshold=1.0、minPopulation=1、无降级。不得通过改旧请求或空分母变绿。
- SC4-5k3已经在原pending Run/TaskRun/Checkpoint与completed source group当前权限内加载安装策略、选择样本、逐行计量。公开函数不能接任意rows/run/window。
- 真实一次完整源观察892行，12类型。QueryResultRevision.source_refs上限100，CanonicalQueryQualityMeasurement.source_refs上限200；不能逐行硬塞或截断，也不应全局放大旧合同来绕限制。
- 原aip_evidence已经支持带类型的不可变证据、内容hash、租户和撤销；SourceObservationEvidenceStore/ConfiguredObservationEvidenceStore只证明观察/配置血缘，不能重新解释成业务质量或连接健康授权。
- 原ecommerce_ingress_dataset_receipt绑定parentHash/derivedHash及完成计数，completed journal检查原调度succeeded/stopped和原回执。它不替代当前ecom_object精确一致性回读。
- EcomConsistencyStore.read_batch_projection_evidence通过原完整BatchCommand/DerivedCommand、原base/derived Receipt验证当前payload与唯一effective event及projected；BASE_RECORD_NOT_CURRENT可以拒绝已被新组覆盖的旧对象。read_saved_projection_completion已有全部saved输入路径，空源分支有原empty observation定义。
- 字段联合有效仅描述字段结构/引用覆盖；金额对账、成交或退款、物流签收、评价正文、渠道真实可用性均未由它证明。正式查询必须保留该边界。

## 2. 选定路径与保留边界

采用一个完整组来源Evidence聚合引用，内部绑定原manifest与全部成员的hash和实际完成证据；QueryResult引用该Evidence而非截取100行来源。使用现有aip_evidence/AipAnalystQueryStore/QualityEvidenceStore，不新建影子Run/SourceSnapshot权威表，不伪造SemanticHydrationReceipt/EcommerceObjectRevision/历史快照。

新增显式SnapshotQueryQualityMeasurement版本，与旧hydration和canonical query两个variant共存。它的source_refs只接受实际组来源Evidence精确ref，并有query_result_ref；现有type上限与旧序列化不变。该DTO仍只是数据合同，不具备授权；只有专用当前Owner验证Evidence、原完整组、QueryResult与当前requirement后，才能送原QualityEvidenceStore。任何caller自报计数/来源ref均不得成为Fulfillment路径。

Evidence聚合不是丢弃来源：要求组成员完整（1至12）、每成员原run/control/source selection/package/mapping/schema/masking引用、原parent/derived/Dataset回执hash、read interval和组manifest hash全部匹配。源行留在原不可变input，完整rows hash绑定；消费时按原Owner加载全部rows并重算事实，不能凭聚合Evidence单独授权。保存可读计数而不重复导出客户键或raw行。证据整体大小有上限，超限fail-closed，不截断。

## 3. 实施波次及退出条件

| 波次 | 实施范围 | 退出条件 |
| --- | --- | --- |
| SC4-5l2 | completed group当前规范投影只读Owner，复用原Claim/Input/Store全部saved证明，消费前后同组回读 | 原实际PG完成组正例、对象被覆盖/缺事件/未投影/缺derived或Dataset回执/撤权反例；无source读取、无写恢复 |
| SC4-5l3 | 组来源Evidence在原aip_evidence类型化持久化，精确内容与撤销回读；封装当前Owner存证入口 | 12成员/超过200行完整绑定、同key重放、篡改/跨租户/撤销拒绝；输出不含raw客户数据 |
| SC4-5l4 | 固定字段质量QueryResult，用原MetricQueryRequest和AipAnalystQueryStore；输入原requirement与组Evidence，输出12类计数和明确缺口 | 原查询request/result完整hash回读、来源不截断、失效/重放/过期拒绝，空事实保持零；不声称经营结果 |
| SC4-5l5 | 新SnapshotQueryQualityMeasurement合同与专用适用性Reader，store人口策略按真实Shop唯一范围，不跨类型求和；复用QualityEvidenceStore | 新旧合同回归、892行完整组测试、独立fact阈值/空分母/时间/人口/撤权校验；无客户端评分入口 |
| SC4-5l6 | 接原DataRequirementOutbox消费者与FulfillmentResumeSaga，保持exact Requirement/Readiness/Evidence/TaskRun/Checkpoint | 隔离组合完整成功与恢复/幂等/取消/unknown反例；真实环境正式首链另行执行，不能用mock代替 |

每波先补精确文件/测试清单并登记Lease，证据与提交后进入下一波。必要的新文件预计位于services/aos-api/aos_api及tests/extension_runtime；不提前新增迁移。若复核现有Store无法支持全部来源证明，先登记具体缺口，禁止绕开原Owner。

## 4. 当前一致性与来源语义

查询基于明确的一次read interval，业务窗口来自原需求，时间截止为原source observation；不声称重建该窗口内任意时刻的历史对象状态。当前安装/控制/预算/权限在读前后重检；原Store读取当前对象与有效投影事件。Store自有事务与Host事务不能虚称跨连接原子快照，证据表示受控观察期间核验结果，不是长期执行许可。消费需要当前authority，发布/能力执行仍走其原exact审批与预算门。

全量raw用于关系和身份证明，业务cohort决定窗口范围，unknown保留分母；每fact有效行=必需字段联合+该用途required关系+已知cohort。disclose问题仍可读。Shop粒度人口只能从受控唯一Shop范围取得，不能把所有OT行相加。最旧源观察应使用整组read_started_at作为保守freshness，不用查询生成时间冒充源新鲜度；cutoff仍保持需求/原组read_completed_at，二者职责不同。

## 5. 真实首链衔接

代码/候选通过后仍需按原清册升级主环境039至048、构建签名安装合格候选、更新当前配置/预算/权限并重载服务。由自然调度产生新完整组与原Case/Run，旧过期任务不能强改cutoff补绿。真实sourceReadiness、全12类质量和Fulfillment回读通过后才恢复原分析，产物必须引用事实来源与缺口，再走exact方案评审、内容承接、能力执行、人工评审续跑及Wiki候选。

若12类中业务窗口内某类确实无行，旧v1仍EMPTY_DENOMINATOR；不能为通链补假数据或修改历史要求。应先以真实事实解释缺口；如果业务需要承认“当前无发货/无支付”本身是一项可验证事实，必须另做版本化事实定义/新Profile计划和新任务，不改变旧v1。这是业务语义问题，不是放松测试。

随后按231路线/栖月汇双侧增长方案扩展八工作台真实经营计划，连续观察后才发布决策。主系统真实业务完成度与本方案开发进度分开报告。

## SC4-5l4 精确实施补充

新增services/aos-api/aos_api/ecommerce_analysis_snapshot_fact_query.py与tests/extension_runtime/test_analysis_snapshot_fact_query_pg.py。输入仅实际AnalysisSnapshotSourceEvidence与精确Evidence ref；execute_current/read_current都重入原当前来源Owner，不能接caller计数/窗口/actor。复用原fixed_metric和AipAnalystQueryStore；固定metric为snapshot结构与引用覆盖计数，逐fact行保留observed/eligible/valid/excluded/duplicate/unknown及字段、关系问题（确定性JSON文本）。status partial、confidence not_applicable、freshness unknown，不评分不授予Fulfillment。

request绑定Evidence精确ref和原requirement ref，窗口/cutoff/expiresAt全部来自原请求；租户、Evidence与固定版本形成自动幂等key，并沿原查询Store Receipt/CAS。读取重算预期request/result全部结构，核原raw JSON、request/result hash及deadline/actor；撤销、过期、策略/投影变化拒绝。消费写后原来源守卫失败须整体回滚，调用不触发新源读取。

隔离PG测试复用原Evidence/Store完成组；原analysis/pending仍named doubles。Query与Metric原DDL在ar1c隔离schema执行，测试专用连接适配只把原public表命名空间定位该schema，不mock SQL结果、不修改生产SQL或RLS。验证幂等/计数/来源/失效/撤销/故障回滚。真实12类892行运行仍单列欠项，不能由两类fixture替代。无主库迁移、无安装、无新增模型调用。

SC4-5l4实际最小权限PG发现原aip8事件表只GRANT SELECT,INSERT，而AipAnalystQueryStore._latest_for_update使用FOR UPDATE导致InsufficientPrivilege；不能给fixture临时UPDATE掩盖。补入原aip_analyst_query_store.py最小修复：使用scope+query_id命名的pg_advisory_xact_lock，后读最新事件，保留原CAS/唯一sequence/append-only/RLS。事件不可变行的旧更新锁不能锁住新尾事件，事务级查询锁也消除该尾部竞争。无DDL/新增权限。新增隔离PG验证原start/reconcile/cancel、过期sequence冲突与无UPDATE授权，旧查询测试适配到相同原DDL命名空间执行。

## SC4-5l5a 合同分段

SC4-5l5拆为l5a显式合同/旧评估与存证兼容、l5b原当前Owner适用性+Shop人口+QualityEvidence存证。l5a修改services/aos-api/aos_api/data_requirement_quality.py，新增tests/test_snapshot_query_quality_measurement.py。新schema aos.data-requirement-snapshot-query-quality-measurement/v1，queryResultRevision精确ref，sourceRefs严格且仅一个完整组Evidence精确ref，id/hash前缀与revision=1/无receipt_id匹配。沿用原计数、时间、租户、逐fact/过期/人口独立校验。旧hydration/canonical query DTO字段与hash不变，联合判别器显式加入第三variant。DTO不验证源真实性、不授予执行权限；源Owner和固定查询重验在l5b。测试覆盖合法序列化、错误/重复/截断来源、伪造query ref、旧合同回归、空分母/弱fact/过期保留，以及原QualityEvidenceInput完整回读兼容；不改默认threshold或旧请求。

## SC4-5l5b 当前质量适用性与存证

新增services/aos-api/aos_api/ecommerce_analysis_snapshot_quality_evidence.py和tests/extension_runtime/test_analysis_snapshot_quality_evidence_pg.py；原ecommerce_analysis_snapshot_source_evidence.py仅抽内部成对回调，原公开接口/证据body/hash不变，使质量Owner在同一源守卫内取得原编译mapping与saved Shop行。无客户端rows/counts/人口参数。

仅适用原grain=store、purpose=initial_store_analysis；Shop必须是原组唯一Shop成员且每个saved source_pk对应编译mapping.shop_id，最多一个源Shop行。有效人口是存在且未删除的该Shop数0或1；与Shop eligible计数一致且无unknown，否则适用性拒绝，不将其他事实行数相加。来源缺口不伪造人口，其他用途另行定义版本政策。原固定QueryResult当前精确验证、原完整requirement模型+hash与已有Source guards后，把实际逐fact counts转SnapshotQueryQualityMeasurement。query_version为固定metric hash；rule_version为绑定完整cohort/关系策略的fieldPolicyHash；人口固定执行规则版本hash。source_observed_at取原read_started_at，measured_at取query.created_at。

为固定query稳定存证，QualityEvidenceInput.evaluated_at取原query.created_at，表示该查询时的评估；每次put/read另用DB当前时间调用原evaluate_quality，过期拒绝，不把历史评估当当前许可。正常字段缺口可保存失败assessment，不强行变绿；所有引用需当前重验。原QualityEvidenceStore存精确body/撤销，run_id=NULL不把BI Run伪装为AIP TaskRun。写后质量撤销/字段或投影变化整体回滚；外层当前源守卫保留。已有source/query/Evidence公开接口保持不变；当前适用性不是source readiness/hydration/Fulfillment替代。

测试复用实际Query/Evidence/Store/schema，完整DataRequirement值为明确named pending fixture，Shop实际两类完成组；检查稳定重放、真实counts/freshness/population、错误grain/expired/低fact/来源与质量撤销/写后失效回滚。12类892行真实组合仍欠，l6原调度续跑与主环境真实首链不得据fixture完成。
