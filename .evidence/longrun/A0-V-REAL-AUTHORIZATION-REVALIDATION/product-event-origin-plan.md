# 事件任务原批次持久定位

基线34ec7f27。子Lease A0V-PRODUCT-EVENT-ORIGIN-20260914只允许新043迁移源码，主库不迁移。

新增 services/aos-api/alembic/versions/a0v_043_product_event_origin.py：ecommerce_product_event_origin按tenant+occurrence主键，同租户Occurrence外键、source_event_id、run_id、actor、content_hash，强制RLS，runtime仅SELECT/INSERT，禁止UPDATE/DELETE/TRUNCATE。定位是路由证据，不是当前来源授权；真实original parent/proof仍由Reader验证。

新增 services/aos-api/aos_api/ecommerce_product_event_origin.py：同Host事务读写元数据，验证hash和Occurrence sourceevent关系。新Occurrence写原run/actor；重放只读最初定位，不覆盖为后续批次；既有无定位任务拒绝自动补写。

修改consumer._write：Occurrence/outbox和origin同事务完成，异常统一回滚。新增PG测试证明三者原子、不可变、隔离和原run保留；既有consumer PG夹具是来源替身，此表只引用真实Occurrence，不把测试run当正式来源授权。

后继factory+discovery按origin.run_id选择既有当前原批次候选；分析仍当前claim/source/policy/approval前后复核。新043只在18432临时库验证；无主Host重启/push。
