# 共享内存失败边界复审
原r3受低work_mem/并行off连接包装控制，SQLAlchemy DefaultDialect.connect调用loaded_dbapi.connect，即psycopg.connect；没有连接绕过证据。64MiB共享内存分配32MiB失败+backend signal11+WAL自动恢复已留原始日志。127库7条Source独立签名/hash/provenance/committedxid审计通过、136库inventory、failed库仅228assetintegration且Source关系不存在、其他client0；不等于完整386通过。
PG16.14上游pgstat_shmem.c指出共享统计采用in-place256KiB DSA并可扩展DSM，多个保留库/大量表的统计增长是候选解释；仍缺故障调用栈，不能定性为已证实pgstat缺陷。源码：https://raw.githubusercontent.com/postgres/postgres/REL_16_14/src/backend/utils/activity/pgstat_shmem.c 。资源文档：https://www.postgresql.org/docs/16/runtime-config-resource.html 。
新ownedlab只增加shm256MiB，原内存768MiB与耐久配置不变，旧资源不重启/不清统计/不删除库。原失败专项1PASS17.26s并独立1库0Source审计，原386fresh累计仍在执行。下一原finalCOMMITdeadline反例与自然首链均未解决。环境容量修复不等于PostgreSQL崩溃机制修复，不授业务执行。
