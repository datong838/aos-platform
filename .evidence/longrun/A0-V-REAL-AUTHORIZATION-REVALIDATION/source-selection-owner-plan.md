# 来源选择 Owner 与首次读取接线方案

2026-09-12，基线765a06be。沿运行控制总方案推进；本波先将已验证包资产转换为可审阅、不可变的读取规格，随后才可由持久Owner批准。已安装Niushop 1.3.0的三份P01资产逐字节摘要及大小通过ManifestLoader核验，见source-selection-installed-assets-preflight.json。当前安装active@5；P01为ns_site/site_id=1/Shop，11列，排除site_tel。冻结指纹只校验表、对象与主键身份，不声称包含当前列类型或实时行数。

## 第一子步骤：把资产约束变成实际读取规格

新增services/aos-api/aos_api/pipeline_source_selection.py与tests/test_pipeline_source_selection.py。提供纯函数derive_mapping_read_spec(mapping, schema, masking)：来源表、目标对象、主键、选列和等值过滤只从三份已核验资产导出；不接受SQL或连接配置。表/列必须为规范SQL标识符，列1..100且唯一、包含主键；映射与Schema必须唯一匹配表、P编号、目标对象和主键。仅接受明确site_filter中的简单等值AND条件，复用既有解析器，并要求至少一个条件；缺过滤不能默认全表。

PII_DIRECT、PII_QUASI、sensitive_mask、全局drop和映射pii_exclusion合并为禁止出库列。映射若仍要求禁止列，明确拒绝而不静默删列造成语义残缺。当前先支持snapshot映射；增量读取必须另行绑定游标版本、重放边界与字段，不悄悄用快照代替。返回冻结dataclass、tuple列/过滤，不带active/approved状态，不生成权限或SourceSelectionRevision。只解析内存对象，不自行读库/加载未验证路径。用真实P01资产检查规格，不以此冒充真实源数据。

## 后续持久与执行，不得省略

1. SourceSelectionRevision绑定双租户、sourceId与实际DataSourceConfigurationRevision、installation/generation/configRef、已解析的包/三份资产exact refs、固定方法及规格、actor、时间窗/读取预算；服务器生成identity/revision/hash。当前安装和配置权限Owner在同事务锁内批准；客户端列清单、摘要或当前诊断连接均不能替代批准。复用CurrentConfigurationPermission和当前四源配置校验，不通过SET ROLE/GRANT绕过诊断身份拒绝。
2. Owner持久化前比较当前active lock、binding/configuration、source配置与graph版本；CAS和幂等键同请求重放、异请求冲突；不可变历史与当前选择分离。新的迁移编号在实施前查HEAD，单独补完整迁移/数据保护/测试方案。
3. 持久PipelineRuntimeControl引用该Selection。每次执行由当前运行身份在run_guarded范围内重新检查批准、有效期、预算、当前版本与安装状态；禁用/重装/漂移必须失效。不能先给graph加live字段。
4. SourceAdapter调用read_rows显式columns并使用有效批次上限，PII在源端排除；正式ScheduleRun/Ingress冻结输入并复用单写者，未知结果不重读。首次读取不依赖已有成功同步，完成后才检查SourceReadiness和真实对象。

## 验证

先红后绿覆盖实际P01规格、空/重复/非法列、禁止列、缺策略、Schema多重或错配、缺过滤/危险过滤、输入后续修改不影响冻结结果、增量模式拒绝。运行既有源适配器及选列测试、AR2闭包。纯资产结果不等于权限、不等于302表已同步。下一步继续持久Owner与正式执行接线；不push，230 L0挂起。

复核补充：MySQL列名按大小写等价处理重复列和禁止列，防止SITE_TEL绕过site_tel策略；保留原列名用于查询。此处采用更保守的等价判定，不新增可读取字段。
