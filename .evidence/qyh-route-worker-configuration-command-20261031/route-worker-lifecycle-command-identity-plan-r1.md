# 后台处理配置命令专用身份方案 r1

时间：2026-10-31（Asia/Shanghai）
范围：`org-org/dev-project` 的“确认后台处理配置”命令持久化通道
状态：方案先行；本轮仅实现代码侧拒绝式接线，不开通当前业务库写入

## 1. 业务目的

运营人员确认“后台处理配置”时，系统需要保存两类内部回执和一份受保护配置文件。该动作只表示“配置已保存”，不表示开始处理业务，也不启动 Host、worker 或 Provider。

当前正式 API 使用只读业务库身份和只读 HTTP 外壳。不得为了一个配置动作把整套 API 改成可写，也不得复用拥有大量业务表权限的 `aos_runtime`。因此新增一个只服务于后台处理配置回执的专用数据库登录通道。

## 2. 本轮实施边界

本轮实施：

1. 新增受保护身份文件读取和数据库连接校验；
2. 将后台处理配置服务的默认命令回执连接切换为该专用通道；
3. 缺少身份文件、目标库不一致、权限过宽、租户策略不准确时全部拒绝；
4. 保持状态查询继续使用原只读连接；
5. 增加单元测试和相邻接线回归。

本轮明确不实施：

1. 不在当前业务库创建登录角色、授权或 RLS 策略；
2. 不创建真实受保护身份文件；
3. 不解除正式 API 的只读 HTTP 外壳；
4. 不执行配置 POST，不写当前业务库或配置文件；
5. 不启动 Host、worker、Provider，不处理任何真实业务任务。

## 3. 专用身份合同

受保护文件环境变量：`AOS_ROUTE_WORKER_LIFECYCLE_COMMAND_CREDENTIAL_FILE`
文件 schema：`aos.route-worker-lifecycle-command-identity/v1`

文件必须是当前进程所有、权限 `0600`、非符号链接的绝对路径，只含：

- `schemaVersion`
- `role`
- `dsn`

DSN 必须与正式 API 指向相同 host、port、dbname，但登录名和完整 DSN 必须不同；禁止 `hostaddr`、service 文件和 session options。

## 4. 数据库最小权限合同

将来由独立受控步骤准备的专用登录必须：

- `LOGIN`、`NOINHERIT`；
- 非 superuser、非 bypass RLS、非 create role/database、非 replication；
- 不属于 `aos_runtime`、`aos_app` 或任何其他角色；
- 仅拥有目标 schema 的 `USAGE`；
- 仅对 `bundle_installation_command` 拥有 `SELECT`、`INSERT`；
- 不拥有该表的 `UPDATE`、`DELETE`、`TRUNCATE`、`REFERENCES`、`TRIGGER`；
- 不拥有当前 schema 其他表的任何写权限；
- 目标表必须启用并强制 RLS；
- 必须存在只授权给该登录的命名策略 `route_worker_lifecycle_command_scope`；
- 策略必须把可见和可写数据硬限制为 `org-org/dev-project`，不能仅信任客户端可修改的 session 变量。

连接建立后先以只读事务验证上述身份、权限和策略；验证成功并提交后，才把该连接切换为读写，供一次命令回执事务使用。

## 5. 接线与兼容性

`RouteWorkerBusinessEntryFactory` 的默认 `connect_factory` 改为专用连接函数。测试和其他调用方显式注入连接时行为不变；配置预览不打开该连接；状态读取仍走 `connect_read_only`。

由于当前正式运行环境没有专用身份文件，即使未来误穿透只读 HTTP 外壳，配置命令也会在数据库连接前拒绝，不会回退到通用业务库身份。

## 6. 验证标准

1. 缺失或不可信身份文件在数据库连接前失败；
2. 相同 Web DSN、错误目标、登录漂移均失败；
3. 权限过宽、角色继承、RLS 缺失或租户策略漂移均失败；
4. 合格身份验证期间连接保持只读，验证完成后才切换读写；
5. 默认工厂使用专用通道，显式注入仍兼容；
6. 专项测试、生命周期接线测试和相关回归全部通过。

## 7. 风险与后续开通门

- 本轮不会带来运行时写入风险，因为不准备真实数据库身份，也不开放 POST。
- 后续若要让用户真正点击“确认配置”，必须另行评审并执行：数据库角色与硬租户 RLS 准备、受保护身份文件落盘、真实只读核验、一次明确用户确认、受控 POST 开通与结果对账。
- 任一步结果为 unknown 时只读对账，不重发配置命令。
