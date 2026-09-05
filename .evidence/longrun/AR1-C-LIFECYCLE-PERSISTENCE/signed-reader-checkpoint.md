# AR1-c 签名受控读取内部检查点

2026-09-06，m1。整波仍进行中，业务场景新增0。

已实现并实测：签名注册定义接纳→逐 SQL 制品摘要校验→严格参数→专用低权限事务→租户RLS→SELECT ONLY→有界结果。测试使用独立18432临时库和测试签名，不访问真实业务数据，不开启容器业务端口。

Prime 增量复核发现并已修复：谓词列未携带；关系在角色检查后才加锁；游标逐FETCH重置超时。现已带谓词信息、先锁表再验RLS、全部元数据语句和FETCH共用剩余预算。双连接 ALTER RLS 锁冲突和时钟耗尽回滚实测通过。签名接纳独立复核未发现新增缺口。

专项：查询39项；签名与隔离PG联合15项。累计305 passed、6已有warnings、35.99秒、exit0。累计命令沿用query-checkpoint.md的精确清单。既有JDBC退出日志closed stream仍存在，未宣称零告警。

新增文件：tests/extension_runtime/test_storage_reader_pg.py。修改admission.py、query_registry.py、storage_ports.py及其测试。未改页面，浏览器不适用；AR1-d未开始。

尚未完成：broker安装epoch/权限/审计接线，受控命令，schema安装与卸载审计，运行工作器和最终Installation CAS。无AR1-c Delivery，不晋级AR1-d；继续同波后续切片。
