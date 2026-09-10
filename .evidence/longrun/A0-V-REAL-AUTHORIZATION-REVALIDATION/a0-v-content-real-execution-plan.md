# 内容真实生成与费用待核算承接

基线 07b14348；用户已授权开发期承担模型费用，媒体慢请求可延长等待。当前代码证据表明 ContentGenerateHostService.execute 仅 reserve→release_no_effect，返回 FAILED_NO_EFFECT。HostCommitter 将 revalidate/execute/verify_receipt 包在一笔锁定事务中，因此不能在现方法内直接等待 Provider。

## 真实执行必须形成的链路

1. 原 Host 事务按当前 installation/dispatch、任务、责任、能力、路由、来源和批准权威核验后，持久化 invocation/outbox 及预算预留；提交后由进程拥有的 worker 领取。不得更改 AR2 no-effect 回执语义或将未知结果说成失败。
2. worker 在事务外调用 ExactProviderInvoker；调用前必须先提交 ProviderRequestReceipt。并发领取和崩溃重启不能再发同一已提交请求。已知异步 job 查询原 ID，响应未知进入 reconciliation，不能因观测超时重发。
3. 成功结果先可靠记录，再在租户事务内生成 measured UsageReceipt 和 ArtifactRevision，写 CapabilityProviderReceipt；商业已知价 settle，明确开发授权用 complete_cost_pending。产物保留任务/Brief/方案/来源 lineage。
4. 领域包读回 COMPLETED，费用为 SETTLED 或 COST_PENDING，后者金额 null；进入人工评审后自动续跑。费用核算不得触发第二次 Provider 调用。
5. 进程重载、隔离 PostgreSQL 故障恢复、多次回放及真实文本首链验证后，才启用实际开发模型/路由。图片/视频按各自 capability 和可用模型接入，不能用文本冒充。

## 本施工切片：消费成功产物

现领域包 ContentCapabilityReceipt 将 COMPLETED 绑定 SETTLED+整数金额，故实际费用待核算的成功结果会被丢弃。本步修改 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/content_capability_runtime.py`：允许 COMPLETED+COST_PENDING+actualFen=null，同时严格保留 Provider 请求/结果/用量、可读产物 lineage、retry NONE、历史一次调用；不能允许未知执行、缺结果、缺产物或把金额0称作未知。

测试文件 `services/aos-api/tests/extension_runtime/test_ecommerce_content_capability_budget_runtime.py`，覆盖接入/回放不重复调用、缺证据、错误金额、错误预算状态；继续原有成功、失败、UNKNOWN和评审合同测试。先红后绿。只改可开发源码，不回写已经封存/安装的 candidates 或 releases；后续需要新候选包 digest 和安装升级核验，旧 AR2 fixture 清册不冒充此新代码的验收。

该合同消费的是受信 Host Receipt，不允许调用者靠填写 COST_PENDING 激活 Provider；真实授权依然由价格/预算 Owner 校验。当前 no-effect Host 不会产生新状态，本步不激活、不接外部 Provider。回滚源码，不改既存 Receipt。完成后继续 outbox/worker 实现，不以此合同测试视为真实首链完成。
