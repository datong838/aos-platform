# 管道图重启发现与详情恢复：验证

2026-09-12。只读目录投影补齐已保存图，冷详情复用既有图Owner恢复disabled管道；目录不泄露节点config，不给无来源图指定niushop。已退役catalog同ID不会被热内存/冷图重带回列表。普通内存管道来源由其source节点唯一source_id投影。

测试：最初2 failed，修复后42 passed（新重启发现、既有Phase5图/节点/并发/持久化及配置登记真实性）。跨未知工作区由现有认证返回403；Store双租户查询为空。退役测试先加载持久目录再设置已退役缓存，避免测试前置被正常hydrate覆盖；热/冷均不可见。AR2闭包五类错误空，git diff --check通过。

真实只配置验收：org-org/dev-project P01-shop-qyh，以已有p01-shop.yaml登记3节点/2边图，site_id=1，PII排除site_tel。写前graph404，单次PUT200，revision1；没有创建schedule或启用executor。后端真实重启后07:12:17Z正式列表唯一命中、detail/graph200、revision1和完整graph哈希不变，execution_mode=disabled、executor_id为空、builds0/schedules0。证据p01-disabled-graph-registration.json和p01-disabled-graph-after-restart.json。IAB tab12管道构建页实际1条栖月汇-店铺，草稿，成功0，画布入口可见。

边界：持久图恢复不恢复执行授权，不等于P01同步，不等于首链或八工作台通过。真实记录未删除；本波未读取源业务行、未启用旧DDL/bootstrap、未写源库。仍缺正式运行控制、读取治理绑定以及自动消费。

下一波：审核现有Pipeline内控启用/执行授权、真实executor注册以及SourceReadiness/Mapping/Schema/Masking入口，补齐P01正式执行所需持久控制合同；不得向公开graph字段暴露execution_mode开关或借旧seed自动启用。SSH已恢复，不再阻塞。m1串行、不push、230 L0挂起。
