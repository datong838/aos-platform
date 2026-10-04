# b61｜正式卸载命令凭证来源与唯一136依赖核验

## 上位规则与范围

- 231-3/231-4 要求运行安装卸载先合法停用、排空、释放，原 Installation 与 CommandReceipt 同事务；Host/worker/Web/命令身份分离。b58～b60 仅在隔离 PG/OCI 证明低权调用与受保护文件预检，不能生成当前正式凭证。
- 当前权威卷 `aos_current_preview_20260927@a0v_135` 只读，本波仅查当前迁移头、角色/EXECUTE/安装状态和已知仓外身份文件的文件名/字段形状，不读取 secret 内容、不运行迁移或 Host。

## 文件级核验与结论门

1. `services/aos-api/alembic/versions/a0v_135_extension_schema_acl.py` 和 `ar2_018_runtime_uninstall_authority.py`：只读对照迁移头、现有函数 EXECUTE、正式 command-role 最小 grant 差额；不创建第二个 136。
2. `services/aos-api/aos_api/asset_registry/uninstall_command_connection.py`、`control_wiring.py` 与既有受限 API/Host 身份方案：核实专用凭证文件 schema/权限/DB 身份要求、当前服务配置是否引用、是否存在非 test-only 正式来源。若只有 test-only 文件，实例失败关闭。
3. D-waves b25/b41/b44/b45/b46/b49/b50 与 231-3/231-4：将 Capability operation/Receipt、安装锁、可信 evaluator、专用命令角色/ACL 的唯一136前置条件列成矩阵。每项要有 disposable 正反证；正式卷切换必须新全备、全恢复、零执行窗口。

## 本波只读现场（待验证后落结果）

- Alembic 文件只见 134/135，无 136；当前库版本135。
- 当前 `aos_app` LOGIN/SUPERUSER/BYPASSRLS，`aos_runtime` NOLOGIN 且无卸载函数 EXECUTE；查询中没有 `aos_installation%` 正式命令角色。已发现的 `.aos-testonly-bg00cf-3r_lw6yp/api-service-identity.json` 是 test-only 且字段为 `dbname/host/pgpassFile/port/user`，不是 b60 专用 schema。`.env` 中无专用文件引用。

## 下一可执行项

- 正式凭证签发和当前卷角色/ACL缺失仅阻断当前实例；继续在 disposable PG 设计唯一136权限矩阵和独立可验证的代码/测试。不得为了凑版本提前提交部分迁移，也不能以 test-only 文件替代正式身份。
