# 142→150恢复门第一阶段编码检查点

Task w5cb4-current150-restore-gate-20261005-154201 ACTIVE。原142执行器精确版本/authority写死，不直接修改；新脚本第一阶段仅当前142库REPEATABLE READ READ ONLY exported snapshot全备、无密码globals、独立none网络/无端口/新卷完整恢复与全snapshot比对，再回读源未变。不是143..150迁移演练、维护sequencer或真实重启完成。

新模块缺失RED9failed0.09秒；新边界与原恢复相邻26passed0.25秒，简化目标mount严格bool门后最终26项通过；两文件AST/精确diff通过。mock结构反例只证明边界代码，不证明完整恢复。真实backup/restore另记录实际终端及私有路径/摘要。

新目标全部保留，禁止删除备份/卷；失败保存原stage/error type、同Task固定private目录O_EXCL拒重复。原Task/livelease/Owner/authorityrun内不变、m1/head/原源容器卷及固定PG/库门在动作前回读。实际source Docker命令仅pg_dump/pg_dumpall/pg_restore--list；连接事务READ ONLY，没有源DDL/服务控制/LOGIN/Provider。未编码逐步迁移、精确ACL增量或源维护，下一继续这些门，不将当前代码准备与unit结果替代完整提醒验收。
