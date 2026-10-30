# 物理基础备份数据库定向连接修正方案 r15

时间：2026-10-31（Asia/Shanghai）

## 已知结果

r13 的第一次 `pg_basebackup` 使用默认 replication pseudo-database，本地 HBA 没有对应规则，会话建立前明确拒绝。r1 物理备份卷中只有 0 字节、0600 的 `base.tar`；来源迁移头、WAL 和 prepared transaction 未变化，未产生基础备份。

## 修正

不修改来源 HBA，不重发原连接。创建新物理备份卷：

`qyh-current163-to170-physical-backup-r2-20261031`

新的 `pg_basebackup` 使用 libpq database-specific replication 连接：

`host=/var/run/postgresql dbname=aos_meta_head user=aos_app`

这样仍通过来源容器本地 socket、仍不读取密码，但匹配现有 `local all all trust` 规则。备份参数、SHA-256 manifest、WAL fetch、spread checkpoint、no slot 和后续验证均与 r13 一致。

成功前 r1 空备份卷保留为失败证据；不得覆盖或删除。若新连接仍在会话建立前失败，停止物理备份并重新评估，不修改来源 HBA。
