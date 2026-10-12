# 临时实验库容量恢复

原容量维护将data盘扩60GiB，但原tmpfs512MiB边界保留，累计原生测试将其写满；PG现确认terminal stopped/PID0，不能在线remount、不直接start空临时盘。当前真实栖月汇卷独立保持159，API仍只读；本恢复仅实验18431。

当前Task已登记，同线程单写；保护原失败容器/原备份。复用已验证physical loader思想新增recover.py，精确原镜像/Env/CMD/network/127.0.0.1:18431，新增容量1GiB（只增tmpfs上限，不重启VM）；原pg_basebackup档案SHA/manifest/WAL已验证、启动前再次原生验证，再原cluster/五数据库集合校验。原HBA未在该备份临时改动，无权限放宽。物理备份只读流式装载到新容器PGDATA，不复制或删除正式卷。

原失败tests仅isolated新DB/无业务模型执行，fixture清理不能证明完成，保留失败日志与原container。新容器恢复的是维护前已验收备份，不虚称保存故障时新fixture数据；之前所有真实开发实验数据库5个均在备份清单中，独立full159/最新160演练在不同磁盘实验卷未受影响。本轮恢复后记录新Name/ID/1GiB/原systemid/原数据库集合与健康，未知stage只读对账不重放；然后新UUID测试session再跑专项与相邻，9skip不得当通过。
