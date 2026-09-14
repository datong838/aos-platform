## SC4-5l6d6 原就绪回执当前保存与消费（2026-09-15）

Rules：方案先行、m1单写者、不push、230 L0挂起；同租户PG测试串行。新增ecommerce_analysis_snapshot_readiness.py及test_analysis_snapshot_readiness_pg.py。只从exact当前ReadinessContext消费，原SourceReadinessService计算，原InvestigationReadinessProjection绑定完整Requirement、实际覆盖/阻断，原SourceReadinessReceiptStore保存/精确回读；无新表、迁移或状态权威。读旧回执重新核验当前来源/安装/策略/Binding，禁止未来checkedAt与过期，旧expiry不得超过当前允许期限，归一旧时间后全字段比较，不刷新旧回执；消费结束再用DBclock核旧期限，防消费中到期。

Red：新增模块缺失收集错误（/tmp/sc4-d6-red.log）。6个完整12隔离PG场景通过/199.39s（/tmp/sc4-d6-green.log）：保存/当前读/同body幂等、policy/binding/source撤销、canary和写后依赖变化回滚。最终针对性10passed/43.10s（/tmp/sc4-d6-final.log）：正常PG消费含最终期限检查+9个纯比对/到期/Requirement与部分覆盖测试。原不可变触发器追加实证1passed/42.49s（/tmp/sc4-d6-immutable.log）：RESET ROLE后尝试UPDATE仍被immutable拒绝，回执保持原值。共15个唯一用例全部有通过记录，重复复验不重复计数。7项已有框架警告。原DDL仅在ar1c测试schema重定位，原canonical JSON函数及pgcrypto算法不改；无主库变更。

AR2 ar2-7 1947/190/93全部错误列表为空（/tmp/sc4-d6-final-closure.log）；memoryctl validate GREEN。质量不足保留FAILED、11/12与unmet Weapp，不虚构满覆盖。历史回执不能替代当前安装/来源授权；此回执仍不允许Run自行转换。完整12测试仍明确使用named源样本/签名安装/分析起点/Provider依赖，不等于真实经营首链验收。原用户进度文档与Playwright依赖改动保留。

下一波l6e先完善原Fulfillment和snapshot续跑技术分解：以真实原EvidenceBundle/SourceReadiness作为数据承接，不伪造SemanticHydrationReceipt；检查原requestedOutputs、当前Requirement/Run/TaskRun/checkpoint及单次CAS，保留旧hydration路径。随后原Outbox自动消费、主升级安装、真实首链/八场景/观察与发布决定。整体目标未完成，自动接续。
