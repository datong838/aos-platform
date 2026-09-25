# W5c7w PipelineControlServices Owner 可选同事务 fence 计划

## 复习与边界

W5c7v 确认 selection/control/bind 三类 Owner 写入经 `consumer_connection` 独立事务；该 context 已有 `fence(conn, scope)` 钩子，执行于设置租户/角色/超时后、Owner 写入前。W5c7u 的 Snapshot worker 参数不覆盖这些 Owner。真实 `a0v_093/094` 未部署，Host flag 默认 off，全机 universe 缺失。

## 文件级清单与九步

1. 复习 W5c7b/v、`pipeline_control_service.py`、`consumer_connection.py`、现有工厂测试和 `main.py` 不注入路径。
2. 本方案先提交。仅修改 `services/aos-api/aos_api/pipeline_control_service.py` 与 `services/aos-api/tests/test_pipeline_control_service.py`；审计/verification 增于本证据目录。
3. 红测：`PipelineControlServiceFactory.build(scope, host_lease=...)` 仅接受 exact 同 scope `OptInHostLease`；默认 None；三个 Owner 写入口将同一 `fence_in_transaction` 交给 `consumer_connection`，并在 Owner 写前执行。最小实现仅复用原 transaction hook，不新增连接/commit。
4. 专项覆盖默认、错误类型/跨租户、三路径 fence 传递和无提前连接；隔离 PG 守卫由既有专项证明，不碰真实 DB。
5. 跑近期 A0-V 累计回归与工厂/Owner 邻接测试；测试临时 DB 归零。
6. 浏览器只读核 rev4/组停用，不冲刷队列。
7. 复审 `main.py`、Host/业务 worker 未注入，不把接口等于全路径权威；真实 closure gate 不变。
8. verification 落盘提交 m1，CAS 更新 docs 与 Prime 三投影。
9. 自动进入 W5c7x：独立分析这三种 Owner 的连接事务与 Host epoch 失租并发，之后处理业务 worker 多提交边界。

未知结果冻结，不重发旧 attempt、不手工 run_definition；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。
