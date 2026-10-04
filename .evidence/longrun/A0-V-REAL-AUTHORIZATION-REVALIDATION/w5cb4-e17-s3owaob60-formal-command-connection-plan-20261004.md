# b60｜正式安装卸载命令专用连接预检文件级方案

## 上位与现状

- 231-3 的运行卸载要求 disable/排空/资源释放后同事务终结原 Installation 和 CommandReceipt；231-4 的跨身份边界禁止 Web/Runtime/Host 借权限。b58 isolated signed 两代次专用 NOINHERIT 命令登录能以显式 ACL 完成链，b59 `InstallationService` 已提供仅运行卸载使用的 `uninstall_command_store` 注入口。
- 当前生产 `control_wiring.build_runtime_control_plane` 仍只传普通 Store。当前真实库 `a0v_135`、`aos_app` 为超管/BYPASSRLS，不可当正式命令登录；正式凭证与唯一136角色/ACL尚无，当前库保持只读。
- 复用 `restricted_api_identity.read_identity` 的绝对路径、nofollow、0600、属主、重复 JSON key 和精确 schema/role/DSN 条件，但不能复用 `verify_identity` 的 logical-role SET ROLE 假设：命令登录必须不可继承/不可 SET `aos_app`，由自身显式 ACL 工作，不向运行角色借权。

## 本波最小文件

1. 新 `services/aos-api/aos_api/asset_registry/uninstall_command_connection.py`：受保护身份文件 `AOS_INSTALLATION_UNINSTALL_COMMAND_CREDENTIAL_FILE`，只在有明确引用时读取；建立连接前拒绝 DSN 与普通 Web 连接相同；在只读身份事务核对 session=current=文件 role、LOGIN/NOINHERIT/非 SUPERUSER/BYPASSRLS/CREATEROLE/CREATEDB/REPLICATION、`aos_app` MEMBER true/USAGE false/SET false、`aos_runtime` MEMBER false、无直接 Binding UPDATE、当前 DB 目标与普通连接一致；验证后才能交给安装 Store。失败码无凭证内容。
2. 只改 `asset_registry/control_wiring.py` 两处安装服务组装：显式设置文件引用时注入 `PostgresInstallationStore(connect_factory=...)`，在命令连接前逐次预检；其他命令/只读装配不变。正式凭证缺失时旧普通命令路径保持，当前运行卸载仍由 `ar2_018` 拒绝高权 session，保持失败关闭；RED 核对默认边界。
3. 测试在 `services/aos-api/tests/asset_registry/` 新增单元负门和 isolated PG 正门；复用 b58 signed 夹具验证独立连接与同事务 Receipt，不碰真实当前库。专项+相邻控制装配回归，复审计划一致性。

## RED 与完成标准

- 无文件、相对路径、符号链接/宽权限、重复字段、角色不匹配、高权、可 SET/继承 app、runtime 成员、Binding UPDATE、DB 目标漂移、Web DSN 复用均拒绝，不能回退普通身份。
- 正式低权 isolated 角色连接在同事务完成 terminal Receipt 与 CommandReceipt；旧操作仍用原 Store。当前实例只报告缺正式凭证/迁移，不宣称 active、首链或可卸载。
- 唯一136与 Capability/安装锁/evaluator 合并审查，当前卷迁移另波需新备份、全恢复演练、零执行窗口；本波不启 Host/worker/Provider、不读商城源、不重发旧 Run、不 push。
