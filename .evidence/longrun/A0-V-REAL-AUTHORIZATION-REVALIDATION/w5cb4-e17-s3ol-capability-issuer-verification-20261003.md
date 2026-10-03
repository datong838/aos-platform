# W5CB4 E17-s3o-l｜原 CapabilityBinding create 独立发行验证

日期 2026-10-03。依同名 plan、231-4/231-9、583 与 D-waves。当前真实库只读；只用自动销毁隔离 PG。

| 步骤 | 命令/结果 |
|---|---|
| RED | `.venv/bin/pytest -q tests/aip/test_e17_s3ol_capability_issuer_pg.py --tb=short` → exit1，两个测试因原连接门不识别 `capability` 命令族而 `REGISTRY_ISSUER_EXACT_CONNECTION_REQUIRED`；原 create 没写出 Binding 半行。 |
| 最小实现 | 原 Registry 发行连接增精确第三登录 `aos_aip_capability_issuer`，不复用 Agent/Skill 身份；CapabilityRevision SELECT、CapabilityBinding SELECT/INSERT+FORCE RLS、Registry Receipt SELECT/INSERT+FORCE RLS、租户 GUC/私有 passfile/超时/非 owner 无 runtime membership 逐项验真。禁止 CapabilityBinding U/D、Agent/Skill/Tool/Assignee/源 Revision/PublicationEvent 写。原 Capability Store、Agent/Skill 命令不改。 |
| 原路径与负例 | test-only published Capability 夹具下原 `create`→同键 replay 只一条 Binding/Receipt；同 key 异载荷冲突、dev-org 只读 canary 看不到、普通 runtime 直插 Registry Receipt 不足权。撤 CapabilityBinding INSERT 时原命令失败且无绑定行，返宽 UPDATE 被预检拒绝。夹具不代表正式签名来源或 secretRef 真有效。 |
| 回归 | `.venv/bin/pytest -q tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_e17_s3oj_skill_issuer_pg.py tests/aip/test_e17_s3oi_registry_issuer_pg.py tests/aip/test_aip6_capability_run_handoff.py tests/aip/test_aip_agent_registry_store.py tests/aip/test_aip_skill_publication_service.py --tb=short` → exit0，38 passed/1既有 xfailed/7 warnings。新增三发行身份专项14 passed；`py_compile` 两目标、`git diff --check` exit0。试验库三 issuer 残留角色0。 |
| 当前实例 | 原卷 `aos-a0v-recovery-pg-data` running、库 `aos_current_preview_20260927@a0v_135` 只读，独立全备 SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0` 一致。签名启动器预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、installation approved、publishedVersions4/runtimeBindings0。仅 API launchd bootout/bootstrap exit0 后 PID45566；health/ready/OpenAPI/Web200，日志 `migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`，18181 `HOST_CLOSED`。这不是新一次 PG/Web 全栈重启，浏览器业务门仍按本日既有证据禁入。 |

复审：此波仅证原 create/replay 同事务发行，默认未接当前 API/Host。`AipCapabilityBindingService` 的 readiness 默认通过另一连接工厂读取多种原权威；因此 evaluate/update、当前角色/来源与正式 active 均未证明，不能借本 test-only 夹具开 Host。当前库普通 runtime Registry/Assignee 直写、正式 OIDC/issuer/ACL/六 Binding/八配置/首链仍 pending。

下一波 E17-s3o-m：先盘点 CapabilityBinding evaluate/update readiness 读取身份、原表/角色与 CAS；隔离 RED/最小接线，检查可选引用 NULL、同键/跨租户/失效，不让独立发行写者借 preview owner 读取。正式当前库切换仍需新全备、ACL-faithful 克隆、零执行窗口与正式凭证。
