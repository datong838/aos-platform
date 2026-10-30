# 163→170 干净停机快照与独立恢复方案 r17

时间：2026-10-31（Asia/Shanghai）  
替代：因来源 HBA 正确拒绝 replication 连接而不可执行的在线 physical basebackup

## 1. 目的与授权边界

在不修改来源 HBA、不读取密码、不写业务行的前提下，建立当前权威命名卷的第二份可校验一致备份，并恢复成独立迁移副本。用户长期目标已授权最新权威卷的第二备份、独立恢复、迁移演练和每日 PG→API→Web 重启；本窗口不开放业务执行、不启动 Host/worker/Provider。

## 2. 固定资源

- 来源容器：`qyh-restored-pg-20261011`；
- 来源卷：`aos-qyh-history159-prepared-data-20261011`；
- 正式只读 API：当前 PID 38160，端口 18080；
- 正式 Web：PID 4054，端口 18434；
- 新备份卷：`qyh-current163-to170-offline-backup-r1-20261031`；
- 新恢复卷：`qyh-current163-to170-offline-restore-r1-20261031-data`；
- 新恢复容器：`qyh-current163-to170-offline-restore-r1-20261031-pg`；
- 新恢复端口：`127.0.0.1:18459`。

所有新资源执行前必须不存在，18459 必须空闲。

## 3. 零执行窗口

1. 复核配置 POST=405、Host/worker/Provider OFF、来源迁移头 163、无其他 active connection、无 prepared transaction；
2. 记录来源全局角色、schema/ACL 和业务数据三个只读 SHA-256；
3. 对正式 API PID 38160 发送 TERM 并确认 18080 关闭；Web 保持运行但不执行写入；
4. clean stop 来源 PostgreSQL 容器并确认 stopped；
5. 以来源卷只读挂载检查 `postmaster.pid` 不存在；存在则停止，不复制；
6. 来源卷只读挂载，使用同 PostgreSQL 16 镜像把完整数据目录 tar 到新备份卷，保留 owner、group、mode、symlink 和时间；
7. 记录 tar 字节数和 SHA-256，并验证 tar 可完整列出；
8. 立即启动来源 PostgreSQL，等待本地数据库 ready；
9. 使用既有冻结正式启动器恢复只读 API，配置 POST、命令身份和全部执行开关继续 OFF；
10. 验证 PG、API、Web、卷身份、迁移头、三个只读 SHA 与窗口前一致。

来源停止后只允许读取数据卷和启动原容器，禁止对来源卷解包、删除、改名或写入任何文件。

## 4. 独立恢复

1. 把校验通过的 tar 解压到全新恢复卷；
2. 再次打包恢复卷并比对 SHA，或用完整目录摘要证明文件内容和元数据一致；
3. 使用同 PostgreSQL 16 镜像启动恢复容器，只发布本机回环 18459；
4. 核对 system identifier、数据库 OID、迁移头、60 个角色、15 条成员关系及 grantor、schema/ACL/数据 SHA 与来源一致；
5. 来源与恢复副本同时在线，但容器、卷和端口不同；正式 API 只连接来源 18446。

## 5. 后续迁移

恢复一致后，迁移与配置通道演练继续服从 r13：只在恢复副本临时建立精确 `/32` HBA 入口，执行一次 163→170，恢复 HBA，再验证全部旧数据/权限保持。当前权威库仍停在 163，除正常 clean shutdown/checkpoint 和重启外无业务写入。

## 6. 停止规则

- API 无法在窗口前停净、PG 无法 clean stop、`postmaster.pid` 仍存在：停止；
- tar 结果 unknown、SHA/大小缺失、恢复目录不一致：保留资源只读诊断，不重做；
- 来源重启后任一身份、迁移头或三类 SHA 漂移：停止，不启动恢复迁移；
- 正式 API/Web 未恢复健康：优先恢复正式只读服务，不继续演练。

该窗口是备份恢复前置，不增加客户配置或业务验收数字。
