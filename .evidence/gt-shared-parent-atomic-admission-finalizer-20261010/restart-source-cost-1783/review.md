# 原环境恢复与观测缺口复核

原容器 start 一次返回 0；重启后原集群7694680278363095064、PG16.14、原失败库可只读连接，九张准入表全0、其他会话0。未新建替代卷或库，未重放1782终态试验。

八次顶层调用累计119.238443秒；终态Receipt Source过期仍为RED，collector尚未执行。实际数据库track_functions=none，所以上波pg_stat_xact_user_functions空数组不是底层无耗时证明。静态body调用点只作后续profile路由，不当实际次数或修复依据。

方案一致：本轮仅原隔离容器恢复、只读对账、保存安装定义hash和静态路由；产品未改，未触碰正式库/Host/worker/Provider，完整Task不交付。新鲜完整Source统计试验为下一已登记步骤，需原Main/Judge/Source相关Task范围核对及数据库级临时统计设置计划；不对全局配置或旧已知失败数据库做计数刷新。
