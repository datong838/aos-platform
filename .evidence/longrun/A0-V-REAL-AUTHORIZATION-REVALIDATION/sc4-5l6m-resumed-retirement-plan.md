# SC4-5l6m 扩缩后正式退役组合验证

Rules：m1、先方案、最小测试改动，隔离 PG；不 push、不迁移主库，230 L0 挂起。

基线 9927349f。使用既有 _resumed_activation 走真实 prepare/commit/validate/resume SQL 流，再在同安装代次上执行 a0v_054 expand/fence/shrink。请求中的 runtime/installation/group revision 从该 fixture 的实际行读取，不硬编码之前的小型测试版本。

随后执行既有 _begin_runtime_disable、_complete_runtime_disable 和 EcommerceGrowthDisableDependent.after_runtime_disabled，验证九项恢复 legacy、组版本继续推进、claim gate 释放、重复 detach 回放同一 Receipt。只修改 test_event_control_dispatch_lifecycle_pg.py；如失败，先定位方案与 SQL 断点，不放宽原退役约束。

该测试是隔离 PG 组合证据，不涉及 OCI 真实卸载，不能替代真实租户或完整 Service 签名审批验证。
