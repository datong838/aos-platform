# a0v056 在线继任登记结构部署核验

Rules：m1单写、保留历史、不push、230 L0挂起。代码c49f321a。

专项10passed（含真实隔离PostgreSQL/Alembic并发提交保留及迁移DML回滚）；首轮发现字典row_factory不兼容Alembic，已限定迁移阶段使用默认行格式，复验通过。全量产品迁移在恢复库执行成功。

状态目录：/Users/ddt/work/projects/ai_agent/.aos-recovery-20260916/state/successor-registration-deployment。
备份6046375字节；同一导出快照的541张旧表指纹与恢复库一致。恢复库aos_successor_registration_20260916_test升级055→056后旧数据不变。

主库aos_meta_head同一REPEATABLE READ事务内迁移前后541张旧表指纹一致，版本056独立读回成功；新继任登记表0行，强制RLS、不可变触发器、角色权限验证通过。备份至迁移的正常变化仅extension_runtime_event、extension_runtime_operation、extension_runtime_outbox、extension_runtime_resource_lease，未排除这些表参与事务内零写验证。

API单独重启84100→86172，受控身份预检GREEN，带租户OpenAPI HTTP200。Host83243未重启。F仍revision4/epoch3、enabled=true、fence=false、ready；E仍disabled/fenced，隔离canary安装0。

限制：本波仅部署继任注册结构及服务，不代表F已接管经营入口。下一波按真实E detach来源登记F，再精确审批、prepare/commit/validate/resume，随后事件控制与真实经营首链；不能以登记收据代替经营闭环完成。
