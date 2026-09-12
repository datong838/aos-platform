# 配置登记与构建事实分离：验证

2026-09-12。计划pipeline-registration-truth-plan.md。新登记不产生lastBuild、READY或DatasetHistory；重登记保留已有状态/历史；启动先加载当前租户缓存，缺失才登记PENDING配置，已有跨租户同名管道拒绝；种子构建无正式运行时不进入builds列表，已有持久运行仍显示。

验证：新增测试先3 failed；完整专项及R41/Wave3-5相邻17 passed；补充启动租户保护后专项3 passed。第一轮邻接失败来自测试创建两个数据源污染共享测试组织的固定计数，改用独立测试租户后17项通过。均使用18432专用测试实例创建的临时数据库，非真实恢复数据库。首次测试基建缺少aos_app角色，仅在专用测试实例补NOLOGIN角色，未改真实实例权限。

AR2闭包1790模块/158分类/93迁移，五类错误空。git diff --check通过。后端实际重启后07:03:17Z：5173/ontology 200、前后端health ok、数据源1、正式pipelines/schedules/builds各0。IAB tab11数据源页面显示1源、上次同步为空、近24小时0；页面12数据集不代表全量同步。

运行连续性07:03:18Z：4786秒/78次续租、3容器running、binding ready/enabled且无fence、canary安装0。没有源数据读取/源库写入/自动业务动作；主机未重启、只重启API。历史非seed构建未做推断式清洗。未完成真实首链与八工作台验收。

下一波：解决生产迁移模式禁用旧bootstrap后，管道图持久配置及真实executor注册的恢复入口；先只恢复禁用状态配置和重启可见性，再做P01正式同步。禁止重启时启用legacy DDL/自动seed来绕过缺口。SSH已恢复，不再作为阻碍；九项dispatch访问范围仍独立；230 L0挂起、不push。
