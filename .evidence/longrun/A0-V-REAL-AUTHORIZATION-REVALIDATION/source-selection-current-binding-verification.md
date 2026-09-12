# 当前管道与源绑定校验复用

2026-09-12，基线59193273。IngressJournal.verify_pipeline_source_binding提取原有graph/source FOR SHARE、双租户、图摘要、唯一Source节点、源类型/status/配置版本检查，并增加可选严格graph_revision。verify_running_schedule仍先要求running run及正确enabled schedule，再调用同一检查，没有放宽正式运行准入。

RED：12 failed/1 passed，新方法尚不存在。第一轮关联34 passed，5项独立PG因开关未设置而跳过；显式开启AOS_EXTENSION_PG_TEST后3 passed/2 failed，原因是旧恢复fixture依赖postgres公共目录遗留meta_dataset表。按正式228ti4d1建表常量和228ti4d7主键常量，在测试临时schema内自建Dataset表，保留全部恢复断言，不写public。补一个无调度表的真实PG当前绑定测试，验证正scope可读、负scope和错误修订拒绝。最终独立PG 6 passed，5.81秒；与34项合计40项通过，7项既有警告。

真实库08:31:21Z只读读取P01-shop-qyh@revision1，Ingress payload摘要d06f4bee366cd6d9061d69a7964378ce5ad3a5020c9a762ca2dd5415de3134ec，见source-selection-p01-authoritative-graph-hash.json。先前页面整体摘要de39916f...包含展示字段，是页面稳定性证据，不能用作Ingress graphHash；本波未改变图或读业务源行。

AR2 ar2-7闭包1792/158/93及五类错误空，diff检查通过。此方法只校验图/源，不授予执行权限，不代替安装、当前配置、数据权限和预算。下一波继续来源选择Owner的当前权限组合及CAS/幂等记录，之后接正式控制与ScheduleRun。P01仍禁用，未完成业务首链。不push，230 L0挂起。
