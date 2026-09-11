# 包内回答合同实施方案

基线f763a5a4，2026-09-11。依据231-1与闭包第9节。保持m1串行、不push、不改主库或运行注册。

## 归属和兼容

D01/D02/D03回答是无权威的领域DTO，放growth包，不放通用SDK。包不得导入aos_api；平台不得import bundle。现有宿主接口暂保持，用同一JSON schema与正负样本兼容测试约束双侧序列化合同，属于显式过渡DTO，不复制Owner/执行/审批状态机。最终宿主接收序列化包结果后仍独立核验权限和来源；本波不开放入口。

## 文件

- bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_growth_plan_draft.py：仅严格GrowthPlanProposal DTO与JSON解析，不带prompt/权威生成/DB。
- bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_analysis_proposal.py：D01/D02 DTO及索引约束，仅相对包内JSON帮助函数。
- services/aos-api/tests/extension_runtime/test_analyst_package_proposals.py：先红再绿，独立子进程禁止aos_api导入，schema/输出与既有平台合同一致，恶意字段/重复键/错误索引/NaN/大小边界拒绝。
- closure-manifest.md追加当前切片状态与摘要，原29项整体迁移仍PENDING；验证与文件哈希证据。

## 门禁

这只完成纯解析切片，不创建Insight/Decision/GrowthPlan，也不代表模型质量、当前来源真实性、人工批准或包安装执行完成。模型不能生成tenant/permission/approval字段；索引只对受信宿主给定的库存计数做结构校验。

先执行新增测试确认缺文件失败；实现后新旧解析和生成测试通过、AST闭包零私有跨层依赖。兼容测试确保无现有行为变化。下一波包内固定阶段结构评分及真实来源输入协议，再接受控宿主编排；不可用结构评分代替人的经营判断。回滚只撤本波新增包文件与测试，平台现有功能不变。
