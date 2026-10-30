# 正式迁移连接门修正 r24

时间：2026-10-31（Asia/Shanghai）

## 已知结果

第一次正式迁移命令在建立数据库连接前被 HBA 明确拒绝：来源仍为 `a0v_163`，新增表为 0，无 prepared transaction、无其他连接。Alembic 迁移逻辑没有启动，因此结果不是 unknown，也没有部分数据库效果。

## 原因

正式 PostgreSQL 使用独立 `/etc/qyh_pg_hba.conf`。它只允许既有正式 API 登录走 SCRAM，其他 host 连接全部拒绝；宿主机 Alembic 以 `aos_app` 从 Docker 网桥网关 `172.17.0.1` 连接，因此被正确拒绝。隔离副本使用实验 trust HBA，不能把它的连接方式直接假定为正式环境可用。

## 最小修正

维护窗口内正式 API 已停止。为同一次迁移建立精确临时入口：

1. 冻结原 HBA 内容与 SHA-256；
2. 仅在最终 reject 之前增加一行：`host aos_meta_head aos_app 172.17.0.1/32 trust`；
3. 临时规则同时固定数据库、角色和单一来源地址，不开放其他数据库、角色、地址或 IPv6；
4. reload 后只执行一次已冻结源文件的 Alembic 迁移；
5. 无论成功或明确失败，立即恢复原 HBA 并 reload；
6. 恢复后用同一宿主连接证明再次被 HBA 拒绝，再进行数据库后验和正式 API 恢复。

临时 trust 只承担本机维护通道，不生成或读取密码；正式 API 停止期间配置 POST 不存在。若 reload、迁移或恢复原 HBA 的结果 unknown，禁止重试迁移，先通过本地 socket 只读核对 HBA 与迁移头。

## 与 r22 的关系

本修正只补充正式迁移的连接实现，不改变 r22 的迁移范围、物理备份、失败保全、后验和非验收边界。
