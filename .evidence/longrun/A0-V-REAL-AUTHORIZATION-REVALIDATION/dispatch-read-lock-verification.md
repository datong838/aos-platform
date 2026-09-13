# 受限路由组行锁与ACL收敛迁移

2026-09-13，基线f6916250。新增a0v_028_dispatch_read_lock.py，主库未部署。

固定public.extension_dispatch_lock_group_a0v_028(uuid)仅接受已绑定scope、采用aos_runtime、serializable、非super/bypass session；固定public表、固定排序、最多锁10行并要求恰好九个已知经营操作。返回既有Host的九字段，同事务持有FOR UPDATE行锁，不写路由或业务产物。可读fenced/legacy组并不意味着可执行，Host exact/runtime/fence/权限检查仍必需。

对dispatch表撤PUBLIC/runtime/maintainer的表级和所有列级直接权限，恢复两角色SELECT；新函数仅runtime EXEC。未改全schema默认ACL、runtime binding权限、历史迁移、已有受限登记/切换函数。

RED：迁移文件不存在时新隔离测试失败。GREEN：新锁/ACL、027原子登记、026回执存储三组49 passed（8.52s），7项既有警告。隔离PG先模拟遗留DML及列级UPDATE，再迁移；两普通角色INSERT/UPDATE/DELETE/TRUNCATE/直接FOR UPDATE拒绝，列级UPDATE不可用；027仍原子登记九项并幂等重放。canary/错组/空scope/非serializable/超管/maintainer调用拒绝，部分/额外/未知操作组拒绝。另一连接UPDATE在锁事务内超时，提交或回滚后可更新，验证真实行锁保留和释放。

AR2 ar2-7：1817扫描/158分类/93迁移，五类错误为空；diff检查通过。主库依旧025，026/027/028均未部署；未真实登记、未改主库权限、API/Host均未重启。

下一波必须修改ecommerce_growth_host_ports.py使用固定锁函数，并检查生产connect_factory：目前默认connect_serializable路径需要确认使用非特权runtime session；新函数明确拒绝super/bypass，因此不能把原aos_app高权限连接作为新路径。旧Host PG测试只种两路由且另授UPDATE、以postgres SET ROLE模拟；须升级为真实非特权登录与完整九项，保留旧exact/authority/receipt/原子事务测试，不以测试专用宽权限掩盖产品缺口。完成Host接入/权限回归后才决定部署新迁移；首次fenced审批、未激活撤销/卸载和自然事件首链仍待后续。
