# W5CB4 E17-s3o-k｜原 SkillBinding evaluate/update 独立发行验证

日期：2026-10-03。依据同名 plan、231-4/231-9、582 和 D-waves。只用 disposable PG；当前卷只读。

| 步骤 | 命令与新鲜结果 |
|---|---|
| 原命令 RED | `.venv/bin/pytest -q tests/aip/test_e17_s3oj_skill_issuer_pg.py -k original_skill_evaluate_blocked_and_revoke_cas --tb=short` → exit1，原真实 readiness 在 Skill issuer 缺 `aip_publication_event` SELECT 时 `InsufficientPrivilege`。补精确 SELECT/SkillBinding UPDATE 后，第二次 RED 为 `aip_skill_binding_eval_gate_ref_chk`：原 `_json(None)` 写 JSONB null，未将 blocked 结果持久化。此缺陷与正式来源是否齐备无关。 |
| 最小实现 | Skill 发行预检要求 SkillBinding SELECT/INSERT/UPDATE 且无 DELETE、CapabilityBinding/PublicationEvent SELECT 且 FORCE RLS、PublicationEvent 无 I/U/D；Agent 发行身份与 ACL 保持独立。原 `aip_skill_registry.py` 三个可选 route/policy/gate 引用为 None 时绑定 SQL NULL，非空仍原序列化。未改业务 ready 算法、CAS、幂等键或 Receipt 结构。 |
| 专项/相邻 | `.venv/bin/pytest -q tests/aip/test_e17_s3oj_skill_issuer_pg.py tests/aip/test_e17_s3oi_registry_issuer_pg.py tests/aip/test_aip_agent_registry_store.py tests/aip/test_aip_skill_publication_service.py --tb=short` → exit0，28 passed/1既有 xfailed/7 warnings。原 create→evaluate(真实 readiness blocked，缺正式 PublicationEvent)→replay→revoked 的 Receipt/version 正向；过期 version、PublicationEvent 缺 SELECT、FORCE RLS 关闭、额外 DELETE、跨租户与普通 runtime 直写拒绝。缺权时无 evaluate Receipt，绑定 version 保持1。 |
| 静态/清理 | 三目标 `py_compile`、`git diff --check` → exit0。试验 PG `SELECT count(*) FROM pg_roles WHERE rolname IN ('aos_aip_registry_issuer','aos_aip_skill_issuer')` →0。夹具是 test-only，不代表正式签名 Skill 或 active readiness。 |
| 当前身份/服务 | 当前权威容器 running，挂载 `aos-a0v-recovery-pg-data`，只读库 `aos_current_preview_20260927@a0v_135`。签名启动预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，installation approved、publishedVersions4/runtimeBindings0；独立全备 SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0` 未变。API launchd bootout/bootstrap exit0，PID44856；`/v1/health`、`/v1/ready`、`/openapi.json`、Web页均 HTTP200，18181无监听。启动器仍 `migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`；本波未做 PG/Web 全栈重启或浏览器业务动作。 |

复审：SQL NULL 修复只影响缺可选依赖的 blocked 评测，使其能留下可审计结果；不能因此宣称 active/可执行。当前库 ACL/外部 OIDC/专用 issuer 未切换，Registry/Assignee runtime 直写旧 xfail 仍在。正式来源、六 Binding、八配置、Host assignment/Owner、自然首链继续 pending。CapabilityBinding evaluate 可选引用的类似 SQL 路径下波需独立核对，不能从本波推断其正确。

下一波 E17-s3o-l：先按 D-waves 盘点原 CapabilityBinding create/evaluate/update 的数据表、正式来源和发行身份；独立隔离 RED/最小权限与 SQL NULL 对账。ToolBinding/Assignee 归属与当前库切换另波；当前实例迁移先全备、ACL-faithful 克隆、零执行窗口与正式凭证。
