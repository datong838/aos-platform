# 经营参谋真实业务计划接续核查

2026-09-11，基线3afa2303，用户明确计划为空可让经营参谋形成业务计划。依据231-5真实业务自动链和231-6串行清单；不是只补八页可点击。

## 当前代码事实

- apps/web/src/components/workshop/AnalystPage.tsx：增长计划消费已有exact引用；只读展示，不能创建计划或任务。
- 同目录BusinessInvestigationTab.tsx：读取已有Case/Run并支持已有运行控制、评审及handoff；当前client类型没有createCase。businessInvestigationFeatureFlags.ts开发默认仅read，commands关闭。打开flag不能补齐空Case启动。
- services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py：Describe能解析当前数据就绪、唯一门店及分析范围；CasePut还校验任务简报，SchedulePut校验exact Case/审批。前端不应手填这些引用或直写存储，须沿Canonical dispatch和受信Host解析。
- ec_ingress_dataset.py提交不可变结果及Dataset后只发布缓存，没有自然经营事件投递。
- automation_occurrence_store.py有record_event及稳定tenant/policy/sourceEventId去重；全仓生产Python搜索未找到调用该原语的位置。不能把原语存在当实际自然触发完成。
- ecommerce_business_investigation_schedule.py领域cadence仅once/weekly/on_demand；ScheduleTriggerHostService仅once/weekly。事件模式需要领域合同和受信来源接线，不仅是UI开关。

## 串行实施清单

1. 完成恢复库完整升级/运行服务基线切换准备，保持cron/外部运行关闭直到当前安装、真实源与作用域复验完成。已有隔离升级及新备份恢复证据full-upgrade-verification.md；原服务尚未切换。
2. 首次分析入口：复用AnalystPage/BusinessInvestigationTab与api/ecommerceInvestigation；服务端复用Describe和CasePut，核查任务简报当前权威的生成/选择来源，不能临时伪造TaskBrief。门店/渠道/范围由服务端当前数据解析；可读不足提示引导真实数据接入。创建只是Case草稿，不冒充已执行计划。具体DTO及幂等请求需编码前补细化设计。
3. 自然数据事件：围绕ec_ingress_dataset.py不可变完成回执与automation_occurrence_store.py设计持久投递；完整tenant、source/config版本、run/receipt哈希和安装代次；不能用接收时间当事件ID，不在数据写事务内调用模型。消费前检查当前策略和禁入，重复/重启不重复Case/Run；未配置不能默默丢失事件。领域event策略和既有once/weekly保持兼容。具体表/接口须先完善方案再编码。
4. 经营参谋生成可读、带来源的分析和业务计划，经exact评审承接内部内容任务。继续补已有内容异步执行与评审续跑缺口；未知外部结果仅对账。
5. 栖月汇真实首链至少两个自然周期，再扩八工作台、连续观察和最终发布评估。无真实数据不生成伪业务结论，不把测试通过算业务完成。

## 验证要求

首次分析：角色拒绝、tenant隔离、资料缺失/漂移、未知请求同身份、双击去重、刷新回读、不手填技术引用。自然事件：完成事务回滚零事件、重复消费一个运行、安装换代/禁用阻断、不同tenant同run不能串链、空观察不虚构经营变化、无变化/过旧批次不得重触发。实际源未恢复时仅报告局部实现证据。

本波仅核查/方案，不改变feature flag、业务数据、审批、安装状态或执行模型；不push，230 L0挂起。
