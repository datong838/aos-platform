# BG00EL 消费者只读Receipt对账

基线AOS-001000/m1@f2baac28；复习231-1/3、BG00EJ/EK与issuer只读对账。消费函数FOR UPDATE不能作为只读查询，未知效果不能再次消费。当前真实库118只读，新增迁移仅隔离PG。

## 文件级计划

- `services/aos-api/alembic/versions/a0v_121_network_receipt_reconcile.py`：固定org/project/Proposal/Event四参数STABLE SECURITY DEFINER函数，owner沿用consumer_owner、EXECUTE仅caller、pg_catalog search_path、无新增表权限。要求transaction_read_only=on、精确身份/GUC、非特权无membership。无锁/写入，仅对当前租户activation Receipt精确查询，校验原Proposal binding/requestHash、resultRef与不可变revision一致。返回unresolved/observed/conflict；不存在/跨租户不泄漏目标。observed只表示历史提交，不代表当前active或可再执行；不依赖head仍等于旧revision，不因批准到期抹除已提交事实。
- `services/aos-api/aos_api/aip_network_consumer_reconcile.py`：入口要求read_only连接、当前身份预检、严格四参数，检查新函数固定属性/权限；调用SQL并验证结果形状。无重试、无消费调用、无自动重发授权。
- `services/aos-api/tests/aip/test_network_consumer_reconcile_pg.py`：复用标准一次性PG与真实连接工厂；无Receipt、提交后、事务回滚后、错误Event、跨租户、读写事务和普通runtime拒绝；持有Proposal行锁时只读查询不等待、不改变head/revision/Receipt。先RED缺模块/函数，随后实现和相邻累计。

精确Task/Lease、verification、D-waves、上下文/Prime与m1收口。正式HTTP/OS凭据/HBA/迁移与首链仍需后续安全波；不触当前库、不读商城源、不重发旧Run、不启Host/worker/Provider、不push、230 L0挂起。
