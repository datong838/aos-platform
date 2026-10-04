# b59 文件级方案｜卸载命令独立连接注入

## 上位与已验证事实

- 231-3：原 Installation 不可变历史、CommandReceipt、terminal Runtime Receipt 同事务；运行 worker 不得调用应用终结函数。b58 在本地真实签名两代次隔离 PG/OCI 以专用 NOINHERIT/SET FALSE 登录跑通合法 disable/释放/卸载/重装，但测试只替换了单独构造的 `InstallationService` Store；生产组合根仍用默认 `PostgresInstallationStore(connect)`，TI6 当前连接会切 aos_runtime。
- 当前 preview `aos_app` 是超管，`ar2_018` 拒绝高权 session_user；正式角色/私有凭证/唯一136迁移未齐。当前真实库135只读，不能把 test-only 登录或 preview DSN 接生产。

## 最小文件级方案

1. `asset_registry/installation_service.py`：增加可选、只供原 `UNINSTALL_INSTALLATION_OPERATION` 使用的可信 `uninstall_command_store` 依赖；默认同既有 `_store` 保持所有旧调用。`_execute` 仅在 operation 精确等于 uninstall 时选择它，handler 内所有原 Store 方法继续使用同一 `conn`，不能跨连接写 terminal 与 CommandReceipt，也不接受 HTTP 请求传工厂。
2. `test_ecommerce_growth_signed_lifecycle_pg.py`：保持普通 Store/服务装配在原身份，仅将独立专用低权 Store 注入原 InstallationService；先 RED 证未注入时 current runtime 身份卸载被 ACL 拒绝或 signed fixture 保留原路径，再以注入 GREEN 证两代次现有全部断言、两 Receipt、OCI 清理与角色负门。相邻原 app 路径、纯内容路径复跑。
3. 本波**不**新增正式数据库登录、迁移或 .env 开关；那是 b60 的独立凭证/连接预检波，需要明确角色合同与可恢复演练。当前组合根未启正式身份时维持失败关闭，Host/worker/Provider关。

## 验收

- 本地 signed 隔离专项及相邻测试 exit0；审查无同事务拆分、无新高权默认、无租户/幂等行为变化。`git diff --check`；浏览器当前发布页仍失败关闭。真实库只读，不读商城源/旧Run，不手工 run_definition，不碰230 L0，不 push。
