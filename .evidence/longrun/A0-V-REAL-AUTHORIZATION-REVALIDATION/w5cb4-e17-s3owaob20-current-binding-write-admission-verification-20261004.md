# E17-s3o-w-ao-b20｜当前 Capability Binding 写身份门验证

## 方案、RED、最小修复

- 文件级方案：同目录 `w5cb4-e17-s3owaob20-current-binding-write-admission-plan-20261004.md`，先读 231-4/AIP-7/BIND-1 及 b17-b19 结论；当前签名预览私有 Binding 双身份配置0，工厂会退回普通 owner DB连接。
- `AOS_DOTENV_DISABLED=1 uv run pytest -q tests/aip/test_e17_s3owaob20_current_binding_private_admission.py`：RED `5 failed, 2 passed`，5类写命令均到达服务，exit1。
- `m1@01d83069` 仅改 `scripts/a0v_current_preview_http.py` 的当前预览标志，以及 `routers/aip_bindings.py` 对 create/evaluate/activate/suspend/revoke 的服务调用前检查；无私有双身份时稳定503 `AIP_BINDING_PRIVATE_CONFIGURATION_REQUIRED`。列表/详情与普通开发模式不改；已配置双身份仍进入原工厂及服务验证。
- `AOS_DOTENV_DISABLED=1 uv run pytest -q --disable-warnings tests/aip/test_e17_s3owaob20_current_binding_private_admission.py tests/aip/test_aip_binding_api.py tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py -k 'not full_schema'`：16 passed/1 deselected/exit0；`py_compile`、精确 `git diff --check` exit0。测试 spy 仅证明调用前拒绝，不作业务通过证明。

## 原卷与最新代码完整重启

- 重启前 `m1@01d83069`、原容器 `colima-aos-extension/aos-a0v-recovery-pg` 挂载唯一权威命名卷 `aos-a0v-recovery-pg-data`；`BEGIN READ ONLY` 读库 `aos_current_preview_20260927@a0v_135`。当日独立全备 `aos-recovery/.aos-current-backup-20261004-s3owaob15/current-full.dump` SHA256 `e9038a51cee401e280d9dcfe4422f533cdb2fb407b00bd37bb21b6b5879bf498`，先前 b17 已完整恢复并验证数据/ACL。签名预检 `scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` exit0：approved、4 published、0 runtime binding、代码/库135。
- 旧 API/Web PID58016/58037 是 launchd KeepAlive 服务；直接 TERM 后它们立即重生，故不把初次操作冒充严格顺序重启。随后 `launchctl bootout` 两个精确 LaunchAgent，确认8080/8434均无监听；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` 后立即 `pg_isready` exit2，重试 exit0，库版本仍135；再 `launchctl bootstrap` API 后 health200、bootstrap Web 后页面200。新 API/Web PID64808/64842，18435/8080/8434监听、18181无监听；Host/worker/Provider未启用。
- 新 API `/v1/health`、`/v1/ready` 200；八个 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 各200，脚本 exit0。`org-org/dev-project` 授权 GET CapabilityBinding list 200/items0；合法 DTO 的 `POST /v1/aip/capability-bindings/b20-nonexistent/revoke` 得503及精确错误码，未进入 Store。`dev-org/dev-project` GET 受 `AUTH_TENANT_UNKNOWN` 拒绝，仅零副作用只读 canary。
- 原库 `BEGIN READ ONLY` 后读 RegistryReceipt6、CapabilityBinding0、ReleaseGate0，正式 Reader/Capability issuer角色0。CUA 重载 `/aip/skill-publish`，org-org/dev-project 页面 37仅评测/已发布0、三阻断、发布按钮 disabled、无可见电商工作台入口；截图显示于本轮浏览器工具输出，未另存本地PNG，故不虚称有文件截图。

## 复审与边界

- 本波只关闭当前预览 Capability 命令的 owner 回退写入口；普通开发模式、SkillBinding、既有只读列表详情不改。私有配置出现时仍由 Reader/issuer 连接工厂核 DB身份与权限；不能以 env key 或本次503称正式身份通过。
- 当前真实库未做 DDL/业务写；正式 OIDC/API非owner身份、Reader/issuer DB CONNECT、共享 Receipt operation scoped 配对、八配置/六 Binding/Host Owner/自然首链均 pending。`org-org/dev-project` 唯一正向，`dev-org` 零副作用；不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
