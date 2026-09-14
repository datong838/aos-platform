# SC4-5d2 事件Worker原子准备数据

2026-09-14；基线e5b3f225；Lease A0-V-SC4-EVENT-AUTOMATIC-DATA；m1不push。

生产ProductEventConsumptionWorker固定调用ProductEventAnalysisService.handle_with_data：共用原初始化流程，在同一个原来源_phase提交回调中先封闭Host写START，再自动准备真实DataRequirement，然后一次commit返回原Receipt。未增加调用者授权参数。旧handle兼容保留。dispatcher只在该完整入口返回后确认事件，原未知结果/取消策略不变。

本次40 passed/7既有警告/28.25s：实际隔离PG从无Run完整初始化+需求、同claim重放不重复、原START已存在后补接、数据预算读取失败全部回滚，以及原正式初始化、Worker路由和编排回归。首轮4个失败均为缺少新入口/Worker仍调用旧入口，后实现通过。来源、安装计算、配置预算仍明确测试fixture；Run/Task/Plan/Receipt/需求Store与分派锁实际执行。不计主租户经营完成。

AR2 1908/187/93五数组空；memory GREEN1103/1086/2705；diff-check通过。主库版本/主服务未改，未执行数据采集或模型调用。

下一：12类数据映射与受控采集准备。现有主租户只有Shop/Product；需逐一处理剩余10类的店铺过滤、脱敏、软删、源时间、分页完整性。先核对现有包映射/实际schema形成新候选计划，再按独立Lease开发，随后连接原Outbox生产真实Fulfillment并完成统一恢复/数字同事链。
