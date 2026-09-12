# P01 首次同步的持久运行控制合同

2026-09-12，基线e4e586a3。已恢复Source及禁用P01图；既有SourceReadiness只认meta_pipeline正式登记，不能把内存图或YAML当执行授权。

## 本波配置对账

通过既有POST /v1/pipelines登记P01-shop-qyh：sourceId=niushop-qyh、target=dataset、datasetRid=ri.aos.main.dataset.P01-shop-qyh、objectTypeHint=Shop。写前用SourceReadiness确认pipeline_missing，用API确认同IDgraph的Source为niushop-qyh/site_id=1、target_ot=Shop，禁用且revision1；不得改图。登记不添加build/history，不创建schedule或启用executor。登记后回读SourceReadiness缺口及正式列表/graph/builds/schedules；不得把其blocked改成ready。

## 后续生产控制的最小边界

1. 持久PipelineRuntimeControl只记录当前tenant、pipelineId、graph revision/hash、source configuration exact ref、mapping/schema/masking refs、installationId/generation/configRef、固定执行器及明确读取预算。记录必须由现有安装/权限Owner确认当前有效配置后产生；HTTP字段或纯hash校验不能自授live。
2. 引用恢复前必须读取当前安装绑定enabled/ready/unfenced和同generation、当前有效四源授权；禁用/卸载/重装使旧控制失效。不能把旧bootstrap整组seed当控制Owner，也不能只因为用户看到连接在线就自动全库读取。
3. Graph/Source修改使旧控制失效，重试不能漂移到新版本。Schema/Mapping/Masking需明确绑定批准的列与源表/店铺，源库只读、限制查询时间和返回数量。分类策略并不自动提供每张表的读取授权；新权限不得从其他数据库身份借入。
4. 首次同步门禁检查读取资格和映射完整性，不要求已经有成功同步。SourceReadiness中observedAt/latestRun/counts用于完成后的事实检查，缺同步历史不能形成首次同步死循环；缺配置/权限仍必须拒绝。
5. 执行统一进入meta_schedule_run与ec_durable_executor/IngressJournal，不新增第二套业务游标/对象写入。运行最先冻结graphHash/sourceRevision/输入批次，失败恢复只用原批次，结果不明只核对原run。手动入口不得生成第二次source读来掩盖第一次未知状态。
6. 先P01 shop，后Category/Product/ProductSku依赖组，再订单/会员等；每段检查真实行、规范对象、projection、Dataset、SourceReadiness一致，再接源事件消费者。成本不限不会解除预算/审批/幂等隔离约束。

## 预期实现与退出条件

后续新增控制合同/Owner及必要线性迁移，具体编号须检查当前HEAD；挂接既有RuntimeConfiguration/CurrentPermission及ScheduleRun，不向graph公开execution_mode；必须覆盖当前绑定/过期/跨scope/generation变化/graph和source漂移/重复与未知恢复。部署前用独立真实PG验证，真实P01执行要落唯一ScheduleRun+Ingress+Receipt。此文件不是新的权限grant，也不表示已实现控制或已完成源读取。

## 07:30 实证补充：避免混用两个不同权威

- SourceReadiness._source_config_ref当前是postgres:meta_pipeline+meta_schedule组合hash，不是DataSourceConfigurationRevision；新运行控制必须使用SourceConfigurationRevisionStore给出的实际连接revision，不能拿组合投影替代。
- 旧_QUERY_BINDING_ID固定ecommerce.data_advisor.strategy.plan.r2；当前真实库读取存在8个active首链绑定，其中D03为a0v-firstchain-d03-strategy.plan@version6；A02/G06也有strategy.plan。因此不得按capabilityId随便选一个，必须从当前责任计划/角色/技能绑定解析唯一当前引用，重新评估依赖有效期，不能仅凭active宣布就绪。
- 此旧查询能力引用只影响后续分析可用性评估，不应成为P01初次合法数据摄入的循环前提。首次读取资格与同步后的SourceReadiness结果分开判断。
