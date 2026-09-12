# 运行控制历史表与当前来源选择消费

2026-09-12，基线6d486091，m1单写者。

SourceSelectionOwner.run_current在同事务检查运行身份/双租户，读取并严格解码指定引用，锁安装并核对同目标最新选择，然后重新运行已有当前安装/配置/角色数据预算策略/图源/资产检查。当前派生规格必须与已批准规格一致，可信后续操作同步完成，不返回独立权限令牌。旧修订、错误hash、跨scope、当前权限拒绝、规格漂移均不能调用后续操作。

a0v_023新增pipeline_runtime_control_revision；固定scope/installation/generation/pipeline、control修订、selection修订/hash、payload/hash、幂等请求hash和前序hash链。外键包含完整目标及selection hash，RLS强制租户，UPDATE/DELETE/TRUNCATE不可变，只向aos_runtime授予SELECT/INSERT。无live/启用快捷字段，记录仍须由下一步当前Owner产生。

验证：消费入口先5项RED（缺方法），后34通过；DDL先14项RED（缺迁移文件），实现后DDL/当前消费/组合检查/合同共 **91 passed**，7.96秒。完整测试数据库迁移成功；AR2 ar2-7 1795/158/93、五类错误数组为空；git diff --check通过。

隔离PG真实执行FK/RLS/事务约束；消费入口的named_fake_current_check仍只证明控制流/数据库，不是实租户权限证明。没有部署真实18435库、没有创建真实控制、P01仍未启用、没有源读取或业务写入。下一波实现控制记录codec/当前Owner，要求控制与来源选择共享合同完全一致，再接ScheduleRun及原输入恢复。未push，230 L0挂起。
