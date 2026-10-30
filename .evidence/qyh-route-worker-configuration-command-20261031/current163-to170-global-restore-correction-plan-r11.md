# 163→170 全局角色恢复授权者修正方案 r11

时间：2026-10-31（Asia/Shanghai）  
前序：`current163-to170-restore-rehearsal-plan-r8.md`

## 1. 已知失败

r1 恢复副本在执行第一条带 `GRANTED BY aos_app` 的角色成员授权时明确失败。角色定义已创建，只有 3 条系统初始成员关系，业务数据库尚未恢复，迁移未开始。来源权威库、备份卷和当前正式服务均未改变。

根因不是备份损坏：PostgreSQL 16 要求执行者对指定 grantor 角色拥有 ADMIN OPTION；临时恢复 superuser 不能直接伪装原授权者。来源的 15 条角色成员关系全部由 `aos_app` 授予，备份正确保留了这一事实。

## 2. r1 处理

- 停止 r1 恢复容器，释放 18457；
- 保留 r1 容器、恢复卷、日志和失败目录供审计；
- 不在 r1 上补跑、不删除半恢复角色、不继续恢复数据库。

## 3. r2 新资源

- 恢复卷：`qyh-current163-to170-restore-r2-20261031-data`；
- 恢复容器：`qyh-current163-to170-restore-r2-20261031-pg`；
- 本机回环端口：`127.0.0.1:18458`；
- 继续只读挂载已校验备份卷 `qyh-current163-to170-backup-r1-20261031`。

资源执行前必须不存在且端口空闲。

## 4. 修正恢复流程

1. 在全新 r2 集群中创建临时实验管理员 `restore_admin`；
2. 从全局备份只执行角色定义部分，在第一条 membership GRANT 前停止；
3. 核对源角色 60 个均已创建，另有且仅有实验管理员和 PostgreSQL 系统角色；
4. 临时执行 `GRANT aos_app TO restore_admin WITH ADMIN OPTION`；
5. 原样执行备份中的 15 条 `GRANT ... GRANTED BY aos_app`，不删除、不改写 grantor；
6. 立即 `REVOKE aos_app FROM restore_admin`；
7. 核对业务角色数、15 条成员关系、member/role/grantor/admin/inherit/set option 与来源完全一致，且没有任何指向 `restore_admin` 的残留业务成员关系；
8. 只有角色与成员摘要一致，才执行数据库 custom dump 恢复。

临时 ADMIN OPTION 只存在于隔离空集群的角色恢复窗口，不进入业务数据库，不写备份，不进入最终摘要。

## 5. 后续与停止规则

数据库恢复、来源一致性核验、163→170 迁移和配置专用通道演练继续服从 r8。任何角色数量、属性、成员关系或 grantor 不一致，都停止在 r2 角色阶段，不恢复数据库、不执行迁移。

该修正只修复可重复的恢复工具链缺口，不放宽当前业务库只读边界，不增加业务验收数字。
