# D01 描述性画像方法权威方案

2026-09-11；m1 5a22c175；AOS-000573。已复习产品07经营参谋、技术15、101-W3-13 ADR及231-5/231-6。用户允许单人持续开发，先补方案再编码；不push，230 L0挂起。

## 查明的实际缺口

InsightRevision要求Metric/Evidence/Method/Eval精确引用。MetricDefinitionRevision已有aip_metric_definition_revision及AipEvalAuthorityStore，EvalContract已有公共Production Owner，均应复用。MethodRevision目前仅出现在引用验证，未有Owner/表；不能将Skill或随意字符串改名当方法权威。

## 本波行为和范围

实现租户内版本化的描述性画像方法元数据，供后续D01读取，固定algorithm=descriptive_snapshot_v1、insight_kind=observation，记录名称、解释、最低来源条数、最大来源年龄和局限。只表示基于明确来源的描述，不提供因果/归因批准能力。方法不复制指标值、查询或Eval；这些实际依赖在下一波D01输入读取时分别核对原Owner。

方法为领域内部配置，当前修订通过head与完整hash解析；每次修订追加历史，priorRef必须真正存在且hash一致。后续方法漂移使旧分析在新执行时不可用，历史exact仍可回读。保存配置不等于触发任务或获得Provider权限。

## 具体文件

- `services/aos-api/aos_api/ecommerce_analyst_authority_contracts.py`：新增MethodRevision，复用原修订链约束，固定描述性算法/结论类型，明确正数界限及非空局限。
- `services/aos-api/aos_api/ecommerce_analyst_authority_store.py`：新增publish_method、get_method_exact；复用已有analyst receipt与_publish原子链，校验完整hash和真实prior；method身份与幂等键事务锁避免首次并发冲突。既有对象不改语义。
- `services/aos-api/aos_api/ecommerce_analyst_growth_plan_sources.py`：原allowlist当前读取增加MethodRevision，FOR SHARE锁head并重算payload。
- `services/aos-api/alembic/versions/a0v_013_analyst_method.py`：additive head/revision两表，复用已有receipt表，FORCE RLS、revision不可改删/截断、runtime最小权限；head/version线性；只向前。此次只在一次性隔离库执行，不迁移主库。
- `services/aos-api/tests/test_ecommerce_analyst_method_authority.py`：类型/界限、哈希/actor/scope/prior漂移、并发同一次幂等、旧exact及新current、回滚与RLS/不可变验证。

## 退出条件和剩余

真实一次性PG验证同key同结果、异key/版本冲突无部分记录、r2保留r1且旧current失败、负租户不可读、运行角色不可改历史；关联诊断/方案Owner和生成回归。记录pre/post hash、风险和提交。主库仍012/旧API，不能声称真实画像完成。

下一波复用MetricDefinition/EvalContract并读取当前Method+完整受控Bundle，D01固定请求和原文可信保存；之后D01工作者、正式三阶段宿主和运行配置、真实源与经营计划首链、八业务场景及观察。
