# SC4-5l6d 当前安装快照的SourceReadiness

基线42e2e4cc，AOS-000573，m1单写者；不push，230 L0挂起。方案服务于真实数据自然触发原经营分析，非新增一套状态机。原产品双侧增长方案为目标业务依据，其中历史Authority数字不当作当前授权或运行状态。

## 已核实差异

1. source_readiness.py的SourceReadinessService.read固定读取bundles/platforms/ecommerce-niushop文件，校验pipeline-live-v1与各表cron；当前完整组走已安装artifact和原受控执行器，两者不能冒名替代。
2. source-freshness.v1.json是逐表cron加120分钟宽限，不是本次需求的source最早观察时间加maxAge。新策略须独立版本，不篡改旧文档语义。
3. 旧_quality_observation只检查元数据。新链已有原QualityEvidence逐fact评估、原完整Store投影证明，但不能把其结果伪装成旧质量规则执行。
4. SourceReadinessEnvelope强制有序唯一P01-P12及相同tenant/checkedAt；保持不变。两对象PG fixture不能成为完整ready验收。
5. 原SourceReadinessReceiptStore只保存原合同快照，不是评估器。新入口继续调用该Store，禁止另存一份ready状态权威。
6. QueryResultRevision证明本次计算成功，不是CapabilityBinding健康。原查询能力引用须来自真实绑定及当前依赖，不能给Query ref改名。原_binding_id配置为ecommerce.data_advisor.strategy.plan.r2；新策略显式选择原治理绑定，缺失/过期时阻断，不偷偷创建激活。
7. 投影事件含基础和衍生事件，事件数不等于业务对象数；不能直接len(events)当projection_total。原read_batch_projection_evidence核完整Batch及全部Derived当前有效事件与Receipt，统计基础对象须从原保存BatchCommand.objects且校对完整输入及去重。

## 接线方案

新增受签名安装约束的SnapshotReadinessPolicy文档aos.snapshot-readiness-policy/v1。绑定同一安装的fieldPolicyHash、relationshipQualityPolicyHash，purposeCode=initial_store_analysis、完整有序P01-P12及objectType映射；声明freshnessMode=requirement-oldest-observation、reconciliationMode=current-original-base-and-derived、queryBindingId为非空原绑定选择。禁止调用者提交任意pass、宽限、阈值或时钟；年龄/阈值仍取原requirement。该政策只是适用规则，不能单独授予ready。

| 原合同字段 | 当前来源和必须检查的依据 |
| --- | --- |
| sourceConfig/mapping/schema/masking refs | 同一已安装完整组原PipelineSourceSelectionDraft；当前原Owner解析，保留resourceType/id/revision/hash，authority指向原真实存储或安装artifact，不用本地文件代替 |
| freshnessPolicyRef | 新SnapshotReadinessPolicy原安装artifact精确ref；期限为原QualityAssessment.freshness_expires_at并受控制/查询/绑定各自当前期限约束 |
| qualityPolicyRef及quality | 原安装field质量策略精确ref，逐factQualityEvidence判定；空分母/未知/低质量不能升级 |
| reconciliationPolicyRef及reconciliation | 新SnapshotReadinessPolicy原artifact精确ref，原完整输入/保存Batch及当前基础和衍生投影全部证明，缺对象或任一当前Receipt无效即阻断 |
| queryCapabilityRef | 原AipCapabilityBindingService/当前依赖权威；active、healthy、available、无reasons、版本/hash精确、未过期；本次Query仍独立当前校验 |
| latestRun | 原保存每表schedule run及完成证明；不把TaskRun或Query job充当源run |
| source/projection counts | 完整源输入观察数量、原已证明当前基础对象身份数量；deleted保留明示，排除历史业务窗口的数量不从源总数删除；不以投影事件总数充当对象数 |
| cutoff/checked/observed | cutoff原组read_completed，observed保守read_started；checked原数据库时钟；不将source_event_at补成观察时间 |

SourceReadinessService增加专用已安装快照计算入口，复用原_readiness_status及aggregate算法与原合同；旧read及旧文件路径保持。当前入口接收严格类型的完整12源事实，由专用Host Owner在原业务Evidence/原Source/投影当前守卫内构建，不接受浏览器自报ready。若基础计数无法证明，保留UNKNOWN/BLOCKED与缺口，不默认相等。过期/空数据/失败状态遵循原规则，任何一个源非ready时整体不得ready。

原SourceReadinessReceiptStore保存得到的envelope；读取不是历史快照直接放行，重新验证原安装epoch/generation、控制、原Query/Quality/business、原Binding当前依赖以及完整投影。checkedAt会随评估变化，不承诺不同时间的快照ID相同；同一canonical快照由原Store去重。实际snapshot resume仅接受当前会话重新核验的同一Requirement/来源/Bundle/Readiness组合。

原Store投影使用独立连接：沿用已完成Owner的前后复验，不声称与Host跨连接原子提交；投影或安装在消费中变化必须拒绝并回滚Host写入。正式Run转换交回原状态Owner，不能在现有只读pending守卫内盲目改状态。

## 分波文件和退出条件

- l6d2：新增services/aos-api/aos_api/pipeline_snapshot_readiness_policy.py与tests/test_pipeline_snapshot_readiness_policy.py。纯策略解析和完整12身份/原质量hash/purpose约束；不访问DB、不计算ready。非法字段/版本/hash/类型/重复缺失顺序/空binding拒绝。先Red后Green。
- l6d3：scripts/prepare_niushop_snapshot_readiness_candidate.py生成Niushop 1.22.0候选；源1.21冻结hash，旧文件逐字节不变，仅新增策略与版本/eval。绑定选择须核原已有配置，不把候选视为安装。真实binding检查在接线阶段另证。
- l6d4：新增ecommerce_analysis_snapshot_readiness_context.py与extension_runtime/test_analysis_snapshot_readiness_context_pg.py；原当前Owner中加载策略、12安装refs、实际源run和基础对象计数，读取原Binding/依赖健康。先实现当前事实输入，不先写ready。需要扩展原投影Owner时仅返回原保存的基础身份计数并保留全部当前核验；不得用事件数替代。
- l6d5：修改source_readiness.py增加专用严格类型计算入口，新增source_readiness_snapshot_contracts.py及tests/test_source_readiness_snapshot.py。保持原合同/状态优先级，完整12对象pure验证、失败/未知/过期/空/缺失/canary和旧source_readiness回归。纯fixture不是主验收。
- l6d6：新增ecommerce_analysis_snapshot_readiness.py及extension_runtime/test_analysis_snapshot_readiness_pg.py，原ReceiptStore保存/回读与当前复算；完整12隔离PG证明，包括撤销、过期、安装变化、写后变化回滚。不写主库迁移。
- 后续仍按总清单l6e原Run/TaskRun snapshot恢复、l6f原DataRequirement Outbox消费、l6g完整组大样/主升级安装/真实首链/八场景/连续观察及发布判断执行。

本方案不削减原质量阈值，不因费用或Provider速度抹掉失败；小样/零业务的产品事实版本另行方案处理。不创建第二个Run/Task，不发送经营消息，不执行商城修改。新增安装候选待真实构建签名和安装阶段处理。发现新接口缺口先补本表与清单，再编码。
