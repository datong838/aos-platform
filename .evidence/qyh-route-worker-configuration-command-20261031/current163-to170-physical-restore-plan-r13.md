# 163→170 物理基础备份与独立恢复修正方案 r13

时间：2026-10-31（Asia/Shanghai）  
替代：r8/r11 中无法保持原 grantor 的逻辑角色恢复路径

## 1. 修正原因

逻辑备份本身完整且不含密码，但 PostgreSQL 16 的标准 `GRANT` 无法精确重建来源中“`aos_app` 作为 grantor 授予包含自身角色的成员关系”这一历史目录状态。r1 与 r2 都在隔离空集群明确失败，事务已回滚，业务数据库未恢复、迁移未开始、来源库未写。

不能为了得到一个“看起来能用”的恢复副本而改写 grantor。改用 PostgreSQL 原生物理基础备份，原样保留角色、成员、grantor、OID、ACL、RLS、策略、触发器和全部数据库历史。

## 2. 资源与边界

来源仍固定为：

- 容器 `qyh-restored-pg-20261011`；
- 命名卷 `aos-qyh-history159-prepared-data-20261011`；
- system identifier `7695302940039200809`；
- 数据库 `aos_meta_head`，迁移头 `a0v_163`；
- 来源没有非默认 tablespace，`aos_app` 具备 replication 属性。

新资源：

- 物理备份卷 `qyh-current163-to170-physical-backup-r1-20261031`；
- 物理恢复卷 `qyh-current163-to170-physical-restore-r1-20261031-data`；
- 物理恢复容器 `qyh-current163-to170-physical-restore-r1-20261031-pg`；
- 本机回环端口 `127.0.0.1:18459`。

r1/r2 逻辑恢复容器、卷、备份和日志全部保留；停止 r2 后不再修改。新资源执行前必须不存在且端口空闲。

## 3. 在线物理基础备份

1. 再次核来源 system identifier、迁移头、活动会话、prepared transaction 和当前 WAL；
2. 使用来源容器内 PostgreSQL 16.14 `pg_basebackup`，通过本地 socket 以 `aos_app` 连接，不读取密码；
3. 固定选项：tar format、WAL fetch、spread checkpoint、SHA-256 backup manifest、不创建 replication slot、不写 recovery 配置；
4. 单次流式写入新物理备份卷，不落工作树；
5. 记录 tar 字节数、SHA-256，使用 `pg_verifybackup` 校验 manifest 和文件；
6. 备份前后复核迁移头、业务连接、prepared transaction 和来源逻辑数据摘要。

`pg_basebackup` 会触发 PostgreSQL 正常 checkpoint/WAL 归档活动，但不修改任何业务行、角色、策略、回执或配置。该基础备份已由用户长期目标中的“第二份可校验一致备份与独立全库恢复”授权；仍不得执行业务写入。

## 4. 独立物理恢复

1. 把校验通过的 base tar 解压到全新恢复卷，保留文件 owner、group、mode；
2. 不创建 standby/recovery 配置，不连接正式 API；
3. 使用来源同一 PostgreSQL 16 镜像启动新容器，只发布本机回环 18459；
4. 预期物理克隆与来源拥有相同 system identifier 和数据库 OID；独立性由不同容器、不同命名卷、不同端口和来源仍在线共同证明；
5. 核对迁移头、数据库/表/行摘要、60 个角色、15 条成员关系及 grantor、ACL、RLS、策略、触发器和函数与来源完全一致。

任何 backup verify 或目录/数据摘要不一致即停止，不执行迁移。

## 5. 隔离迁移连接

迁移代码运行在宿主项目环境，物理克隆不复制或暴露来源密码。若来源 HBA 不允许隔离回环连接，则只在物理克隆内：

1. 备份克隆自己的 `pg_hba.conf`；
2. 根据克隆 bridge gateway 推导并固定一个 `/32` 来源地址；
3. 临时添加仅允许该地址、仅数据库 `aos_meta_head`、仅角色 `aos_app` 的 trust 规则；
4. reload 后证明宿主只能连接该克隆；
5. 使用提交 `6bb266200` 中的迁移代码执行一次 `alembic upgrade head`；
6. 完成迁移和核验后恢复克隆 HBA 原文件并 reload，证明无凭据宿主连接再次拒绝。

该规则只存在于隔离克隆，不进入来源卷、备份 tar 或正式运行环境。

## 6. 迁移与后续验证

继续按 r8 的 164–170 固定序列执行。成功后必须：

- 唯一迁移头为 `a0v_170`；
- 迁移前已有业务表行、角色成员、ACL、租户策略和不可变历史保持；
- 迁移新增对象与 164–170 代码定义一致；
- 来源权威库仍为 `a0v_163` 且业务数据摘要未变化；
- 配置保存 POST、Host、worker、Provider 继续关闭。

只有这些门全部通过，才在物理克隆内继续配置专用通道演练。该工作仍是迁移前置，不计为客户配置完成或业务验收。
