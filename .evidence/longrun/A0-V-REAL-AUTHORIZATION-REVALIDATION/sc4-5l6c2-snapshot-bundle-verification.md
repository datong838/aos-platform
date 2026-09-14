### SC4-5l6c2 原EvidenceBundle当前完整观察适配

基线aa2a884f。新增AnalysisSnapshotBundle，只在原Brief及业务Evidence当前守卫内，以私有snapshot-current-observation/v1适配原Store覆盖计算；事实覆盖/缺失/冲突与撤销仍原权威。非零读取区间保留最早freshness_at，当前源年龄由原质量评估前后校验；原uncertainties披露观察不等于源交易时间并参与原hash。原BuildJob/Receipt、license pending-policy-review不变，重放重新精确核原bundle/hash/缺口/撤销和当前依赖，无新Task/Run。

Red新增模块缺失。首轮3失败为markings字段误写，已修正；第二轮7通过1失败是旧来源fixture start=end，非旧规则失效。新fixture在原输入保存之前加入非零读取区间，不修改历史权威；最终10新Bundle加8Brief共18 PG passed/108.26秒，7既有warnings。包括完整/部分/阻断覆盖、旧默认Store仍stale、原时间保持、幂等、原撤销、hash错误、政策写后漂移回滚、实际SQL推进评估时钟的过期/途中到期回滚。原PG18432隔离schema/Store/Receipt真实，源和pending/runtime/安装仍named fixtures，不是主环境真实首链。AR2扫描1942/分类190/迁移93五类错误空；memory CURRENT/validate GREEN。

下一波SC4-5l6d1：完善当前安装的SourceReadiness技术方案。旧服务固定文件与pipeline-live-v1调度不能直接证明新领域包就绪；保留原P01-P12合同、状态算法与Receipt，明确安装映射/schema/masking/freshness/质量/对账/查询能力各项精确来源和失效边界后分步实现。l6e恢复、l6f Outbox、主升级与真实首链八场景仍待执行。无新源读/模型/主库/安装/外部业务写，不push，230 L0挂起。
