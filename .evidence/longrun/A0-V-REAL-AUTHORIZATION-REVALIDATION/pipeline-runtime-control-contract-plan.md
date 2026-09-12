# 持久运行控制：严格草稿合同子步骤

2026-09-12，基线9d8ceacf，承接pipeline-runtime-control-plan.md。本子步骤只完成DTO/纯校验，不能授予或开启live，不注册生产入口、不读源。

## 具体文件和字段

新增services/aos-api/aos_api/pipeline_runtime_control_contracts.py及tests/test_pipeline_runtime_control_contracts.py。

PipelineRuntimeControlDraft绑定双租户、pipelineId、graphRevision/graphHash、CurrentInstallationRef、generation、executionEpoch、ConfigurationRef、选中的package publisher/id/version/contentHash、实际DataSourceConfigurationRevision、SourceSelectionRevision、Mapping/SchemaFingerprint/MaskingPolicy引用、rowLimit/timeoutSeconds/maxSourceCalls、notBefore/expiresAt。只接受state=prepared/readOnly=true；不接受SQL、连接配置、enable、execution_mode、密码或额外字段。SourceSelection在后续独立Owner绑定平台/店铺/对象/方法版本和读授权，本合同本身不产生该Owner。

复用已有CurrentInstallationRef、ConfigurationRef、InvestigationExactRef，增加不可变及重验实例约束；不接受组合SourceConfig代替真实连接版本、不接受bool当revision、不接受UUID非规范形式/空scope、引用类型错配/前后空白。Package版本复用现有semver验证。

预算上限为单批1000行、单调用30秒、最多32次源调用；控制有效期必须有时区、正序且不超过24小时。当前权限Owner仍必须将这些预算压到实际批准范围，合同上限不是费用授权。graphHash沿Ingress的raw64格式，lockHash/packageHash/Configuration及Investigation refs沿既有sha256:格式；不混用摘要语义。

## 验证和后续

先红后绿：合法内存/JSON往返、输入拷贝不可变、嵌套引用不可变、字段/类型/范围/时间/引用purpose逐项拒绝；相同内容hash稳定且任何约束变化改变hash。错误消息不回显fixture敏感值。DTO导入零数据库/源调用。

验证通过后再接持久Store：当前安装及权限锁→唯一SourceSelection/SourceConfig及图/包资产核对→提交控制修订→调度执行时重新核对当前状态。不先加公开live字段、不创建假SourceSelection或Approval、不绕过九项dispatch既有访问限制。不push，230 L0挂起。

## 关联检查修正

SourceConfigurationRevision空库回退测试原先从head开始，现被后续a0v_021仅前进保护正确拒绝。仅修改services/aos-api/tests/test_source_configuration_revision.py，将独立测试库初始版本钉到本测试负责的ar2_010，仍实际执行ar2_010→ar2_009→ar2_010；不删除断言、不修改任何生产迁移或真实库。
