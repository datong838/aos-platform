# 当前真实恢复卷159新鲜备份与独立完整恢复

依231-4和用户已授权当前库安全迁移/全系统恢复，1945旧clone160演练不能替代当前卷备份。真实目标qyh-restored-pg-20261011/命名卷aos-qyh-history159-prepared-data-20261011/cluster7695302940039200809/database aos_meta_head/schema159。只读查询当前Client/active数量、enabled绑定/旧Schedule disabled计数及运行保持；计数不是持续zeroexecution窗口，不先Stop或迁移真实库。备份pg_dump consistent snapshot readonly，数据仅private0700/custom archive0600；第二独立文件副本校验SHA256并用pg_restore list验证结构。

当前全部普通表server-side SHA256/rowcount readonly baseline，导出前后再比对。独立现有授权tmpfs clone381ac0/image7e7/cluster7695416748450308141/18431仅新数据库qyh_current159_restore_20261012接收全custom dump恢复；资源O_EXCL intent后CREATE DB，未知状态只读对账不重发。restore --exit-on-error --single-transaction，PGOPTIONS session_replication_role=replica仅本restore subprocess，阻止复制数据触发业务触发器，操作仅新ownedDB；角色已按原647全恢复存在，保留owner/ACL/序列原定义。严禁改全局或真实session设置。恢复后全部647表SHA/rowcount与当前baseline全同，Source当前fingerprint仍全同；原159保留，旧12Run不执行，新DB无应用/worker/Host连接。完整schema对象/序列/ACL需独立同当前源目录再对账后才能称全部restore gate过。

没有真实PG/API/Web重启或159→160迁移；不授OIDC/独立发布/Owner/预算/Start。候选2正式身份来源仍待既有配置路径，继续独立备份候选。新证据files本目录backup_restore.py/private/current.dump/private/copy/current.dump及public metadata hashes/intent/result/review。不提交dump/业务payload/身份或密码，m1只精确公有证据提交/Delivery/7strong同步。

失败与安全接续：原tmpfs SourceClone完整恢复COPY因No space left on device终止，native只读确认新库public tables0，整事务已回滚；不重发原restore/backup。磁盘实验vol aos-qyh-current159-restore-lab-20261012/container qyh-current159-restore-lab-20261012采用相同7e7镜像、network none/无端口，不替换/删除真实卷或原Clone。单独O_EXCL lab-intent后create同owner标签volume/container，bootstrap仅实验管理身份；当前源roles-only/no-role-passwords副本private0600导入新lab，再将已校验second dump单事务replica restore到lab内独立DB。所有数据/ACL/sequence对账只在lab，不启动应用/worker/Provider，保留失败状态与资源，不凭TTL夺锁。

磁盘lab角色恢复诊断：39源role flags均已准确创建，失败为PG16显式GRANTED BY要求grantor具ADMIN option，lab不同bootstrap导致系统bootstrap OID语义不匹配；12源用户membership尚未恢复，两个失败均已只读对账，不重放整个role脚本。使用另一个精确bootstrap=aos_app的独立network-none lab qyh-current159-exact-restore-20261012及volume aos-qyh-current159-exact-restore-20261012，原失败lab保留。源码roles.sql仅删除已存在且匹配的CREATE ROLE aos_app，其他原ALTER/GRANT保留；从全新DB恢复，避免改源或虚构grantor。
