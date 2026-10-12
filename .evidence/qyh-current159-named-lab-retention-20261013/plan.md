# 历史159完成实验库的保留与内存释放

Rules：231 原恢复保留、Task/Lease归属及零外部执行门；同一m1写者。先方案后本目录retain.py；不改产品代码、当前库/服务或旧Task归属，不删卷/备份，不启Host。候选A已登记的其他命名卷实验资源归属保留，依赖已完成Task Delivery/无重叠Lease/原证据CID卷及native无clients；候选B原Source权限/锁兼容，仍独立但当前避开大内存执行。选择A。

已回读 qyh-current159-fresh-backup-restore-20261012 的完成Delivery FRESH_TRUE159_FULL_NATIVE_RESTORE_DATA_SCHEMA_ACL_SEQUENCES_AND_ROLES_EQUAL。其历史owner为codex-thread-01a107a2-e9e4-7670-bc44-1144fa9b27e2，前缀不同但thread UUID与当前唯一写者一致；以该精确旧owner和Delivery核验，保留旧记录，不改归属。新合法Task接续同维护scope qyh-current159-owned-restore，不凭TTL取锁。

精确资源：3fb59cb46c8daeb402caee95bf9f2d9aefbb3aa42d87988811afe29418790687 / qyh-current159-exact-restore-20261012 / aos-qyh-current159-exact-restore-20261012，以及原lab-created.json绑定的 qyh-current159-restore-lab-20261012 / aos-qyh-current159-restore-lab-20261012。当前inspect确认两者均命名卷；第二个旧失败库不当完成库或成功证明，保留其现有状态及数据。

复用上一已交付 named-lab 保留脚本中的docker/catalog/record原函数，不复用其硬编码主流程或重复旧stop。每个新子目录中先exact原创建证据CID、native无连接、network-none/noports、命名卷核验；native当前cluster登记为归档身份，不猜历史cluster。全部非模板DB新完整dump和无口令globals、private700/600、第二份同SHA和pg_restore --list，再核目录和clients无变化，才新O_EXCL stop intent及精确CID stop。原volume native存在、所有备份再次同SHA、别的容器不动。已有子阶段intent仅只读对账，不重跑；资源不足或某个归属/连接门拒绝仅限制该资源。

完整原卷保留和新备份不代表Host/八台/自然首链或新的完整恢复演练完成。测量剩余内存后再规划有界全库恢复；不会因为停止历史实验实例而重启当前系统。
