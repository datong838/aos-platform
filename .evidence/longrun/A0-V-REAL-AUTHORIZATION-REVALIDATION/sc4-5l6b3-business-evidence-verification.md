# SC4-5l6b3 验证

基线2e3c110c；m1串行；不push；230 L0挂起。

### SC4-5l6b3 当前实际业务事实Evidence

新增AnalysisSnapshotBusinessEvidence，原SourceEvidence当前守卫内重新读取Query/Quality原权威并加载安装的SnapshotBusinessFactPolicy。原FactQualityContext抽共享私有_load_policies，公开body与回调不变。原完整rows/cohort生成实际内容，当前人口不足时无覆盖，逐fact仅实际eligible且原评估无该类失败原因才列factIds；质量与源Evidence的factIds仍为空。保留实际值、未知与质量原因，存原aip_evidence，完整selection/subject/tenant/actor/hash/时间与撤销回读；反复消费重入全部当前Owner。业务产物非水合/Fulfillment许可。

Red新增模块缺失；初始6 PG passed/29.85秒。补入Weapp缺字段保留内容但只覆盖Shop、写后quality revoke/输出内容变化回滚后，新9+原field8+quality7共24 PG passed/81.12秒，7既有warnings。证明实际fixture业务内容、幂等、三类撤销、跨租户、原策略与结果不变；source calls仍1。原Query/Evidence/Store实际隔离PG18432，分析/pending/安装artifact为named fixtures；非主环境12类真实经营验收。AR2扫描1940/188/93五类错误空；memory strong CURRENT/validate GREEN。无主库、安装、源读、模型或外部业务动作。

下一波l6c：原EvidenceBundle覆盖继续服务端计算，新增显式完整观察新鲜度适用性，不更改旧Evidence语义，也不把freshness_at改成query时间。业务Evidence当前Owner验证、原Requirement/TaskBrief/Checkpoint与真实内容绑定后走原AipProductionContractStore/BusinessInvestigationEvidenceBuilder；精确回读/撤销/过期/重放需在新入口同时核验。先补具体方案与测试目录，原水合路径保持；Readiness、snapshot resume/Outbox、主升级安装及真实首链八场景继续后续。
