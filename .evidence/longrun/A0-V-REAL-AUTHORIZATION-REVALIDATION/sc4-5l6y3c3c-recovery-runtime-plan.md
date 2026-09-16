# Y3c-3c 原Completion保存输入恢复运行

## 实施与验证结果（2026-09-16）

Red缺恢复Runtime模块；完整实际隔离Store主例1 passed，773.65秒：原普通Completion先提交1对象/1原Store Receipt后模拟确认丢失，再正式续期，新的固定恢复Runtime/新连接完成原组；十二对象、十二DatasetReceipt、十三StoreReceipt、一Link、十二原Run成功停止，源总调用一次。再次新实例completed重放数量、projectionHash及preparationHash不变。日志`/tmp/aos-recovery-runtime-green.log`。

6项运行前负例54.98秒通过（`/tmp/aos-recovery-runtime-negatives.log`）：已disable、错actor、旧ref、全failed当前分支、负租户、取消/截止全部在Store写入前拒绝。未重新跑已通过的长主例；两次验证期间生产实现未变化，仅追加负例。diff检查通过。

主例耗时较长，不能据此宣称性能或真实商城验收通过。仅源与安装资产为具名夹具，Store/Owner/PG约束/原Completion实际运行；主库061、主服务、真实经营首链未改变。下一波C4全停止失败的原Run原子重领，随后C5完整失败恢复。绝不把此隔离成功当产品发布结论。

前置3142b4da及C3双窗口方案。新增aos_api/pipeline_snapshot_group_recovery_runtime.py、tests/extension_runtime/test_snapshot_group_recovery_runtime_pg.py；不改主库，不加HTTP执行入口，不自动审批，不调用任何prepare/源读取。C4失败Run重新领取单独后续。

RecoveryRuntime以原普通SourceClaim Owner、原Store、独立连接工厂、原PipelineEngine构造；执行参数scope/actor/exact RecoveryRef及deadline/cancel。服务端从回执定位原group/原Run和当前definition bindings，构造C3a固定Authority与C3b固定保存SourceClaim。独立事务前置重验当前权限和完整原input，确认COMMIT后用同一原Completion进入。所有Store动作继续原current guards、独立事务、原命令/idempotency key/后续Link/retirement；不创建新ScheduleClaim/SourceClaim。仅全running与全completed原路由，混合/failed当前仍拒绝，由C4另管。

结果明确saved-input-only及原/当前definitionRef、RecoveryRef、inputReplayed=true；源读取入口不在该类中。每次新连接仍完整重验，原Completion持有相同组锁，禁用/过期/换回执会在原步骤阻止后续效果。未知效果只读原回执恢复，不换key或重发源。

验收主例：原普通Completion先产生一个真实Store对象/Receipt后模拟确认丢失，运行保持原十二Run；再正式审批新窗口，新的恢复Runtime实例续跑真实隔离Store。完成需十二Object、十二DatasetReceipt、十三StoreReceipt（一条批准Link批）、一条Link、原十二Run成功停止、源总调用一次。另一个新实例completed重放所有数量与projection/preparation hash不变。明示模拟源与签名资产夹具，不能作为真实商城经营闭环完成。

负例：禁用或错固定ref/actor/不完整原input不能写Store；取消/截止不进入效果；已有failed或混合Run拒绝且不自行改状态。完整恢复可能耗时较长，应持续查看业务阶段和计数，不因耗时长盲目重发或放松准入。
