# 八步迁移旧目录保持审计

Rules：231/AOS工程交付、原restore Task、m1单写、未知不重放。
候选1：八步13类完整catalog原记录精确保持；候选2：publication签名边界方案。选择已执行迁移的离线证据审计，不重新DDL。

逐步before/after规范JSON集合比较，同时拒绝重复记录、要求前步after==后步before、terminal0，固定代码原迁移中a150七函数PUBLIC EXECUTE撤销完整名字。其它步骤所有13类旧记录不得删除/变更；a150仅七指定function_acl授权可移除。输出每步前后文件SHA、原/后count、增加/删除count、全added/removed私有清单。共享结果包含清单hash和固定七撤权，不能声称新增目录逻辑/授权已全验收、运行门全绿或源迁移通过。

文件：本目录catalog-preservation-plan.md、catalog-preservation-verification.json；私有目录aos-recovery/current150-.../catalog-preservation-20261006-0745.json。无新增业务代码、无库或服务改变。原restore Task不Delivery。
