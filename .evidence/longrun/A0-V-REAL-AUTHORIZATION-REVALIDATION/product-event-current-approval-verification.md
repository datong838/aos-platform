# BG-02 当前批准资格验证

2026-09-14，基线c50ef275。调度保存风险floor由默认R1草稿明确为内部状态变更R2，提示只能升不能降，R4保持禁止执行。AIP批准角色集合提取共用常量。新增当前事件批准检查并在事件Host保存前后调用：当前Action快照与风险策略/hash重算、原精确批准hash、Proposal版本/有效期、有效独立人数、maker/checker分离、批准人不得执行、当前持久化membership及markings。

所有查询在Host原事务；041持锁原批准，其他批准逐个按原Case/策略锁后重新读取，集合变化拒绝；退出前再查数据库时间。无角色授予、无远程权限fallback、无runtime角色切换。未用请求roles替代当前表。

风险RED4项失败后修复；PG测试先因meta_membership的真实工作区外键失败，补完整测试租户目录，未放松约束。累计56 passed无skip，包含11项当前批准PG、风险分类、原cutover/provider及事件保存服务。已验证实际批准/Proposal/成员表及事件保存接入，来源Owner/Profile目录仍具名替身，不算真实自然链验收。旧存储边界测试显式替代当前review gate，独立当前PG测试恢复真实gate。

日志/tmp/product-event-approval-policy-{red,green}.log、/tmp/product-event-current-approval-{red,green,green2,final,closure}.log。AR2扫描1869模块，166分类/93迁出，全部错误数组为空；diff和memory-validate通过。主库038/代码041，Host/API未重启，新服务未注册。

下一波正式身份装配：HTTP已有require_principal提供真实subject；复用PipelineControlServiceFactory按当前tenant构造SourceOwner。事件schema专用资格与旧九操作证明分开，旧定时路径保持；未具备正式资格时不让默认registry接受事件新语义。随后事件绑定/消费、产品入口及真实自然链、八场景与连续观察。
