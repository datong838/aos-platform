# SC4-5l6 完整快照进入经营分析的真实连接方案

2026-09-14；基线a89c1248；m1单写串行、不push、230 L0挂起。状态：实施方案，未实现自动续跑。继续原AR2/A0-V/231计划，非替代业务目标的新项目。

## 1. 目标与现状

目标仍是数据自然更新触发Case/Run，经营参谋根据真实商品、订单、人群和渠道事实形成带来源、缺口与假设的计划，进入exact评审、内容承接、受控能力、人工续跑、效果复盘/Wiki。双侧增长产品方案第4、12、13、16节要求解释推荐理由与不确定性、先重建事实/方法研究，再受控试运行，不能把一次体验激活当规模化销售组织。

已实现当前完整来源、业务cohort/字段质量、固定质量QueryResult、逐类QualityEvidence，均无自动Fulfillment。实际源观察曾有12类892行；实际30日订单只有5个非删除订单（不等于5笔成交），商品39上架/18下架/8删除。真实首链不能用两类PG fixture或这份历史观察替代；需要当前版本安装后的新完整来源组。

## 2. 代码实证指出的连接缺口

1. `ecommerce_growth_runtime_adapters.py:AnalysisAdvanceHostService._resume_authorities`与`aip_business_investigation_fulfillment_saga.py:BusinessInvestigationFulfillmentResumeSaga`的旧resume_data路径强制真实SemanticHydrationReceipt、SourceMappingRevision、SourceReadiness、EvidenceBundle/Checkpoint。原SemanticHydrationReceipt要求Ontology/DataProduct Owner写命令与回执、rollback/rebuild等真实权威；当前Dataset/Store回执不能换一个resourceType伪装成它。
2. `business_investigation_hydration.py`具备job/receipt合同与Store，当前aos_api中OwnerWriteReceiptRevision这两类名称只在该合同出现，未找到可直接复用的对应实际写执行器。不能只调用record制造“已水合”。
3. `aip_production_contract_store.py:_evidence_fact_ids`只从显式factIds/facts统计覆盖。当前source/quality Evidence刻意factIds=[]；把12个名称塞进去只能骗覆盖，不能生成经营参谋所需的实际事实内容。
4. 原EvidenceBundle评估将freshness_at<cutoff判stale。完整组保守观察时间是read_started_at，cutoff是read_completed_at，因此原通用规则不能直接表达“在要求年龄内的一次完整观察”。禁止把freshness_at改成query生成时刻或抹掉读取区间来通关。
5. `source_readiness.py:SourceReadinessService`仍按原固定映射/策略路径、12源与能力等检查；不能由质量Query宣称全部READY。当前1.20候选包mapping、关系/字段策略与旧目录P11均使用ProductReview（l6b1实际文件核对）；此前Review简称不构成类型差异证据。安装后仍核对精确版本，禁止临时别名。
6. `DataFulfillmentStore.bind`绑定完成回执；它本身不会生产有内容事实、完整bundle或当前就绪证明。原Outbox claim/ack/fail/unknown/reconcile是投递权威，不能用进程内“完成”替代。

## 3. 选定设计

保留旧hydration/resume_data路径及合同。新增显式、受完整来源约束的snapshot completion分支，由原分析dispatch/TaskRun/Run Owner执行预期状态变化；不制造旧水合回执、不取消其校验、不增加另一个任务状态机。

数据包的角色是读取/映射/事实配置；Host负责当前租户、安装/控制、固定来源与事务；原Query/Evidence/生产合同负责不可变产物；原Outbox/统一Receipt负责调度和重放；原Run/TaskRun负责恢复。每个快照完成请求须精确绑定原PREPARING receipt、Requirement、source/query/quality/business-fact Evidence、Readiness、EvidenceBundle、原checkpoint/plan/runtime；任何caller计数、qualityScore、allowed或“成功”标签不作为通过依据。

消费权限需分两个阶段：阶段A在原pending只读守卫内准备并重读全部依赖；阶段B由原状态Owner持有同事务当前安装/dispatch与Run锁、核阶段A精确依赖及当前版本后执行一次预期resume。阶段A不能把状态转换包在run_current consumer中；阶段B也不能只使用一个离开事务的布尔证明。状态转换后按原统一Receipt/reconcile读取最终Run/TaskRun，不再用要求WAITING_DATA的历史消费接口判成功。

未知提交结果只查原Receipt/Outbox reconcile，不能重读源或重发未知能力。取消/过期/权限撤销时失败关闭；所有外部动作仍属原Proposal/Approval/Budget/Attempt/Receipt，而非这条内部分析续跑授权。

## 4. 按顺序落地的子波次

| 波次 | 工作与预计代码目录 | 必须证明的退出条件 |
| --- | --- | --- |
| l6b | 原完整来源内生成有实际内容的业务事实Evidence；新`aos_api/ecommerce_analysis_snapshot_business_facts.py`与测试，策略先在原方案登记 | 内容来自原saved rows/cohort和明确语义规则，包含业务值/范围/来源/未知；PII不复制；不能仅用质量计数充当商品/订单事实；缺事实不发覆盖声明 |
| l6c | 原EvidenceBundle对显式快照事实的适用性与新鲜度接入；检查`aip_production_contract_store.py`/原EvidenceBuilder/依赖撤销 | 完整组实际来源和质量ref均当前验证，freshness按明确政策与read_started_at，旧bundle语义不变；坏内容/错租户/撤销/过期拒绝 |
| l6d | 安装映射与原SourceReadiness适配；复用原SourceReadinessReceiptStore | 12类实际current控制/映射/schema/masking/能力/调度及质量/对账满足；P11事实名称版本一致；缺一项不READY，不制造策略文件 |
| l6e | 原analysis dispatch显式snapshot完成/续跑合同及执行分支；原Fulfillment与Run/TaskRun/Receipt | 当前全依赖同事务核验，两个状态各只转换一次；旧hydration路径回归；exact失配/取消/unknown/reconcile与rollback覆盖 |
| l6f | 原DataRequirementOutbox消费者串接前述步骤、原调度入口调用 | 正常调度自然推进，无手动拼ref/改状态；重复投递0次重复效果，故障恢复不再读已完成源，unknown只对账 |
| l6g | 隔离完整12类型/大组组合、安装候选与主环境升级执行清单 | 两类fixture限制解除；跨租户/并发/卸载禁入/重装恢复验收；随后主环境039–048迁移与签名安装独立波次，新真实首链与八场景/连续观察 |

新增/修改文件在各子波次开始前精确确认、完善方案和Lease，再写Red测试与最小实现。表中不是已实现列表。若发现现有实际Owner接口可复用则缩减新增，避免平行权威。

## 5. 业务事实语义与空数据

质量证据回答“这些输入能否按要求使用”，业务事实证据回答“当前有什么、发生了什么、还不知道什么”。首次经营计划至少需要可引用的商品供给/上下架及库存约束、订单业务窗口与支付状态分布、会员关联覆盖、渠道可用资料与公开内容供给。金额/支付/退款必须有精确业务定义，不能将普通订单数冒充成交、将支付尝试数相加当收入。人员/客户信息遵守既有公开投影，系统配置不输出值，媒体/评价不得编造。缺少经营必要字段时明确DataNeed，不猜结论。

旧initial_store_analysis v1每类分母为0仍失败。若真实观察证明某类“窗口内没有业务事件”是正常经营事实，需单独版本化Profile/事实定义（例如已观察的零发货，而非空样本有效率），新的Case/Run/Requirement采用新版；不改旧需求hash、阈值或cutoff。该业务定义必须先补产品/技术方案和清册，再执行。真实小样只能支持研究假设，不证明可复制获客或销售组织建立。

## 6. 验收与回滚

每一阶段都要可读产物、精确引用、当前拒绝与原流程回归；无模型也可验证固定执行契约，真实经营分析仍须真实模型+可读产物+人工评审续跑。部署前接口默认不暴露、不切换主运行；候选失败保留旧路径。无数据删除/重置/强推。新安装版本退出条件包括禁用/卸载阻断、重装恢复和Tenant隔离，最终再以栖月汇真实任务覆盖八工作台并连续观察。

### l6b1 可配置事实内容计算

l6b分纯计算l6b1、领域包策略l6b2、原当前Owner事实Evidence l6b3。本波新增aos_api/pipeline_snapshot_business_facts.py和tests/test_pipeline_snapshot_business_facts.py。业务策略绑定原fieldPolicyHash/purpose，完整覆盖该策略全部objectTypes，每类显式records或group-counts模式，1..16字段，字段必须来自绑定的质量策略；无默认全字段导出。group-counts仅enum/boolean/非负整数，防自由文本泄漏；records仅策略显式选中的公开字段。正式策略需签名安装授权，不能由调用者即席提供。

纯函数复用原完整cohort与quality重算；未知cohort保留、字段不合格输出null而非原值，excluded只报告数量/原因。records按稳定source key排序并输出稳定sourceKeyHash作为定位线索（不声明匿名化）（不是伪造的领域ref）；所有范围内行完整输出，超过1000行/2MB拒绝，不截断。group-counts把已知/未知cohort分别分组，值严格类型、未知值独立计数，最多256组拒绝不截断。保留field/relationship issue计量，不输出原source_pk、external_id或未选字段。结果明确未验证成交/利润、未认证来源，无factIds授权；l6b3完成当前源绑定后才进入正式Evidence。

验证真实商品名等内容保留、历史/删除排除、unknown保留、不可选字段/自由文本分组/多余字段/篡改hash/超限拒绝，空事实明确零而非通过。原quality/cohort回归。无需模型、源读取或数据库写。

### l6b2 Niushop 1.21业务内容策略候选

新增scripts/prepare_niushop_business_facts_candidate.py和bundles/candidates/ecommerce/platform.ecommerce.niushop/1.21.0。源1.20固定tree hash sha256:0a5d0b369f701e5aee68d5b3692fc0b6a89b1d89d195ccd4b549f7388d5a423b；只新增content/policies/business-facts.v1.json、更新bundle版本与静态eval证据，原mapping/策略逐字节保持。目标已存在即拒绝，源hash不符即拒绝，无源读取/build/sign/install/publish。

records：Shop(name/status/currency/timezone)、Product(title/status/price/stock/currency/createdAt)、ProductSku(name/status/price/stock/currency)、Category(name/status/level)、OrderLine(goodsName/quantity/unitPrice/lineAmount/refundStatus/currency)、Weapp(name/status)、SystemConfig(key/status/isUse)。group-counts：Order(orderStatus/payStatus)、Shipment(status/deliveryType)、CustomerLite(memberLevel/status)、ProductReview(status/score/isAudit)、Payment(status/payStatus)。Product/SKU价格仅当前标价，OrderLine行金额非成交GMV，评分数字不解释量表，渠道配置记录不证明外部服务可用。

静态eval复用原12类字段fixture与cohort/关系约束，确认内容/12类型/敏感字段排除/未知与缺口/确定性、不修改旧候选、重复拒绝。新增脚本本身为确定性生成器，不将fixture报告作为真实经营验收。1.21尚未构建签名，继承OCI/SBOM元数据须正式构建阶段再生成。

### l6b3 当前业务事实Evidence

新增aos_api/ecommerce_analysis_snapshot_business_evidence.py与tests/extension_runtime/test_analysis_snapshot_business_evidence_pg.py。修改ecommerce_analysis_fact_quality_context.py抽共享私有_load_policies，原公开回调/body不变；业务Owner在原SourceEvidence._run_current内复用此加载器取得同一安装的关系/cohort/质量/field策略，避免复制校验逻辑。加载SnapshotBusinessFactPolicy精确ref，编译绑定当前field hash，原saved rows经已实现纯内容函数产生完整公开内容。

原SnapshotQuality Owner._value及QualityEvidenceStore精确回读必须相等且当前未过期；原Query/current source均有效。结果存原aip_evidence，稳定hash identity，来源/查询/质量/business policy全精确ref，内容+每类质量缺口。顶层factIds只列实际有范围内内容且通过原该fact阈值的类型，人口不足时不列任何类型；其他缺口保留，不把部分覆盖当Fulfillment。使用原评估reasons判每fact，不另写舍入评分。observed_at原cutoff/freshness_at原read_started_at，created_at为原query.created_at保持稳定重放，当前期限每次检查。

记录/读取均检查原tenant/hash/type/actor/subject/timestamps/撤销；消费后再核质量证据与business policy。原source/quality Evidence factIds=[]保持。历史业务Evidence不能独立授予新执行；当前read重入所有原Owner。无新源读、无模型、无主环境/安装/Run转换。纯内容中的sourceKeyHash只是定位哈希，不替代匿名化或精确领域ref。

PG测试复用原实际Query/Quality/Source/Store完成组与named pending/策略fixture：实际内容与逐fact覆盖、低fact仅部分覆盖、幂等、各类撤销、策略漂移/错误type、写后回滚/租户隔离、旧字段上下文回归。主环境12类真实业务链路仍l6g另验。

### l6c1 原分析Task冻结简报

l6c拆为c1原TaskBrief、c2显式观察新鲜度的原EvidenceBundle适配。新增aos_api/ecommerce_analysis_snapshot_brief.py与tests/extension_runtime/test_analysis_snapshot_brief_pg.py；原BusinessEvidence添加run_current回调（read_current作为其只读包装），保存内容/hash不变。

AnalysisPendingDataContext原当前守卫提供完整requirement/runtime；BusinessEvidence当前守卫内比较同requirement精确ref，任务简报绑定原runtime.task_ref，不新建Task。定义本模块可验证的AnalysisSnapshotBriefSchema v1（明确内部schema而非虚构registry），固定spec包含原requirement/业务Evidence/runtime精确血缘、窗口/所需fact/缺口和只读经营分析目标。原AipProductionContractStore.create_brief/freeze_brief完成同事务创建与冻结，scope+requirement+business evidence+schema产生幂等键并串行锁；原Brief/Receipt权威不复制。

读取校验原head当前revision、精确brief hash/type/schema/spec/task/actor/frozen，与实际当前pending/runtime/evidence一致；原freeze Receipt重放后若head已有新revision必须拒绝，不能覆盖用户编辑。源或策略/质量撤销、task取消/过期拒绝。写后前后守卫失败回滚，无Run/TaskRun状态变化。

PG测试使用原w2_001 DDL及现有aip_task行；分析/pending/runtime仍明确named fixtures，保存简报/冻结/Receipt为原实际Store。验证相同Task、幂等、错scope/回执/撤销/当前head变化/写后漂移回滚。c2才处理bundle freshness，不先改旧全局评估。无源读取、模型、安装或主环境动作。

补充验证边界：原冻结Brief禁止revise，测试必须验证原禁止规则；current head漂移另用明确数据库故障注入测试，不描述为允许的用户编辑。新增Host模块直接引用原runtime兼容模块，按既有AR2规则追加Host分类及初始hash；不放宽验证器或修改历史preHash。
