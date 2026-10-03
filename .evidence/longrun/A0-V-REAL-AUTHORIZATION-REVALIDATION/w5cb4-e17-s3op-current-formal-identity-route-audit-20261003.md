# W5CB4 E17-s3o-p｜当前正式身份与启动路由只读审计

日期 2026-10-03。先复习 231/231-4/231-9、栖月汇首链方案、E17 正式启动 Owner 方案、a2b selector、s3o-o 受限读者与 D-wave。范围只读：当前 `aos-a0v-recovery-pg-data` / `aos_current_preview_20260927@a0v_135`，不改库、进程、签名根、凭据或迁移。Goal 保持 active；当前实例准入缺口不妨碍其他独立波。

## 当前事实与退出码

| 检查 | 结果 |
|---|---|
| 启动身份 | `launchctl` 的 API 参数仍是 `a0v_current_preview_http.py --signed-receipt ... --serve`；plist 环境键仅 `PATH,PYTHONUNBUFFERED`，无 `AOS_OIDC_*`。`.env` 仅有 bundle root/trust root 键而无 OIDC 键；本审计只输出键名，不输出值。当前 API PID48728 是预览，不是 `--serve-limited`。 |
| 当前数据库登录 | 以原签名 Receipt `preflight` 取精确连接参数，在 `conn.read_only=True` 下查询 `pg_roles`：仅 `aos_app`（LOGIN/SUPERUSER/BYPASSRLS）与 `aos_runtime`（不可 LOGIN）；不存在 E17 专用 issuer/reader 登录。`extension_runtime_host_assignment` 对 org-org/dev-project 为0，Host identity全表0。命令 exit0。 |
| 正式受限 API | `--serve-limited --api-identity-file /nonexistent/identity.json` 预检 exit2 `EXTERNAL_OIDC_CONFIG_REQUIRED`，在读取该占位身份文件前拒绝；不启动第二 API。当前已知唯一 `api-service-identity.json` 文件名位于 `.aos-testonly-*`，不得接当前实例。 |
| Host | 不给 credential file 的签名预检 exit2 `CREDENTIAL_FILE_REQUIRED`，没有启动 Host。`a0v_ecommerce_runtime_host.py` 仍固定 `FORMAL_OWNER_AUTHORITY_UNPROVEN`；Host assignment/identity也为0。 |
| 路由兼容 | `select_formal_current_release` 已是只读形式的同代签名 selector；现行 `--serve-limited`/Host 仍复用 pinned preview 四旧版本/binding0 预检。Growth1.13 正式发布或 binding 后旧谓词将 `PREVIEW_DATABASE_DRIFT`，故不能简单切启动开关。 |

## 下一实施门的顺序与文件级落点

1. 正式来源输入合同：在 `scripts/a0v_current_preview_http.py` 的受限启动选择和 `scripts/a0v_current_runtime_host_preflight.py` 核签名 Receipt、trust roots、OCI、Growth1.13 同代 selector、当前安装及确切租户；禁止任意本地 test-only trust/root。保留 pinned preview `--serve` 质量栈。先隔离 PG/OCI 做原入口 RED，再最小接线与负例；当前正式制品未齐时只能失败关闭。
2. API 与三平面身份：外部 HTTPS OIDC JWKS/issuer/audience、独立可核 API identity file 与只读/发行/Directory/Runtime/Web 各自私有凭据。`services/aos-api/aos_api/aip_binding_readiness_reader_connection.py` 和 `aip_registry_issuer_connection.py` 现仅给隔离可验证连接合同；当前库角色不存在。不得复用 `aos_app` 或给 `aos_runtime` issuer membership。先在 disposable PG135 用精确角色/ACL/原命令验证，正式当前库切换另立安全波。
3. 正式当前库迁移门：先独立新全备且可验证、ACL-faithful 克隆全链演练、只允许零执行窗口；确认代码/库迁移头、同代签名安装、Receipt、回滚与监控。对当前 `aos_runtime` 五表宽 SIUD 收窄时须保护所有原合法命令的替代 issuer，不能只 REVOKE 造成业务失败。不得在 HTTP 启动或普通请求里跑 DDL。
4. 当前产品来源：正式 Growth1.13 发布与安装 Owner、八类配置、六 Binding、Host assignment/identity/Owner 与有界自然首链须逐项回读。当前值0不能靠 test-only 夹具或手工 Run 填正。

本波只有只读审计和下一文件级方案，没有代码、当前库迁移或正式启动。下一安全代码波可先做与外部 OIDC 无关的 ToolBinding 原事务独立发行/ACL 正反链；身份来源到位后再执行本卡正式切换。
