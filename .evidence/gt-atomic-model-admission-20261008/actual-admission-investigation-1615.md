# 实际准入前置调查 AOS-001615

核对 HEAD 4b08bf2b 的产品实现。原 physical account guard 以原 Source 身份插入/更新 account_guard，等待后用数据库时间检查 Source有效期。ModelEvalExecutionOwner 的 _prepare_dual_purpose_bucket_fences 要求 joint caller 先取得 Source 和 physical guard；合并两种 purpose 的 buckets，单次原 Store 加锁，等待后再次 derive，末尾以原 xid/pid 与数据库时间检查批准、请求和 bucket 有效期。该方法明确不建立物理准入或 Intent。

全模块实际检索 counts_as_inflight/actual_admitted/call_occupation_event：当前产品只存在新 prepared_only 根/首事件，counts_as_inflight CHECK false，没有 actual_admitted producer。原新表无任何允许真实状态的合法转换，且两表有无条件提交拒绝。故不能直接把首事件当实际持久占用，也不能松开这些提交门实现准入。

下一原生 RED 应针对：在原 Source+物理 guard+完整四腿计划/真实 Target Intent 准备链上，缺失受信 actual admission接口；并验证 unknown 的物理占用持续与费用释放分离。编码前先补全状态证据与精确锁顺序设计，明确何时落真实占用和哪项独立 finalizer 允许 COMMIT。null价格保留，不能用准备 debit 的测试金额当 fee authority。

本次为代码与锁顺序调查，没有发模型/Provider请求，没有库写入或新安装，没有扩大实际权限。原五个父任务保持 ACTIVE，未宣称完整锁图、全局竞态或业务首链完成。
