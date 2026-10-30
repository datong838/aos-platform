# 正式配置保存专用通道准备方案 r26

时间：2026-10-31（Asia/Shanghai）
状态：方案先行；只准备通道，配置 POST 继续关闭

## 1. 当前事实

- 权威数据库已受控迁移到 `a0v_170`；
- `bundle_installation_command` 已启用并强制 RLS；
- 正式库不存在专用角色、专用策略或隔离测试回执；
- 正式 API 只读运行，配置 POST 为 405；
- 现有受保护 pgpass 仅包含正式 API 登录，文件 owner 为当前进程用户、权限 0600；
- 隔离副本已证明专用角色的正向与越权矩阵。

## 2. 固定对象

- 角色：`aos_route_worker_lifecycle_command`；
- 策略：`route_worker_lifecycle_command_scope`；
- 表：`public.bundle_installation_command`；
- 租户：`org-org/dev-project`；
- 身份文件：`.evidence/qyh-route-worker-configuration-preview-runtime-20261031/private/route-worker-lifecycle-command-formal-r26.json`；
- pgpass：`.evidence/qyh-full-system-restoration-20261011/private/restored.pgpass`；
- HBA：`/etc/qyh_pg_hba.conf`；
- 正式 API 新启动器：`launch_route_worker_submission_readiness_formal_r7.py`。

## 3. 最小权限准备

1. 生成一次高熵随机密码，不回显、不进入 Git、证据、命令参数或日志；
2. 在一个数据库事务中创建 `LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION` 角色并设置 SCRAM 密码；
3. 只授 public schema USAGE、目标表 SELECT/INSERT；
4. 创建只面向该角色、硬编码 `org-org/dev-project` 的 permissive `FOR ALL` 策略；
5. 在受保护 pgpass 中原子增加该角色精确的 host/port/database/user 行，保持 0600 和原 owner；
6. 在 HBA 的最终 reject 前增加精确 SCRAM 行：`host aos_meta_head aos_route_worker_lifecycle_command 172.17.0.1/32 scram-sha-256`；
7. 创建不含密码的 0600 身份描述，只保存角色和同数据库 DSN；密码由既有 pgpass 保护；
8. 用产品只读探针核对角色、权限、RLS、策略、无其他表写权和无序列权限。

任一步结果 unknown 时不重做角色或密码，只读核对角色、策略、HBA、pgpass 非敏感坐标和身份文件元数据。

## 4. 正式 API 切换

新启动器只在 r6 的全部 OFF 环境上增加身份文件坐标，不开放 POST、不改变 Host/worker/Provider。步骤：

1. 先独立运行产品探针；
2. 停止 r6 API，启动 r7；
3. 核 API、Web、配置预览及精确配置 POST；
4. 预览第五项应从“通道未开通”变为“通道已准备”，但配置 POST 仍为 405，不能保存配置；
5. 页面只允许展示准备状态，不显示 DSN、HBA、pgpass 或秘密。

## 5. 回滚

因 POST 始终关闭且正式库无配置回执，若探针或服务切换失败：

1. 恢复 r6 API；
2. 删除身份文件；
3. 原子移除 pgpass 中该专用角色行；
4. 恢复原 HBA 并 reload；
5. 撤销目标表权限和 schema USAGE，删除专用策略与角色；
6. 核对正式库无配置回执、原 API 200、配置 POST 405。

禁止删除任何既有回执或修改其他角色/策略。

## 6. 完成口径

成功只表示“保存通道已安全准备”，不代表客户配置已保存，不启动业务，也不增加 `runner 9/22、工程 2/8、业务 0/8`。首次保存必须由用户针对具体配置另行确认。
