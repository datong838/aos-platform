# W5CB4 E17-s3o-j｜原 SkillBinding create 独立发行验证

日期：2026-10-03。依据同名 plan、231-4/231-9、581 与 D-waves；仅隔离库测试、当前库只读。此前电脑重启后的完整 PG/API/Web 验收见续接564，本波只重载 API。

| 步骤 | 实际命令/结果 |
|---|---|
| RED | 新测试在隔离 `aos_test_*_ti4_test` 中给 issuer SkillBinding SI，原连接门仍拒绝：`pytest -q tests/aip/test_e17_s3oj_skill_issuer_pg.py --tb=short` → exit1，1 failed/1 passed，错误 `REGISTRY_ISSUER_DATABASE_IDENTITY_REQUIRED`，绑定行0。夹具起初 FK/JSON 约束错误均已修正，未计为产品 RED。 |
| 最小修复 | `aip_registry_issuer_connection.py` 按命令族选精确独立登录：Agent 保留 `aos_aip_registry_issuer`，Skill 使用 `aos_aip_skill_issuer`。Skill 要求 AgentInstance 与其 Template、SkillTemplate、CapabilityBinding 读权、SkillBinding SI、Registry Receipt SI、FORCE RLS、租户 GUC/私有 passfile/非 owner；拒绝 AgentInstance I/U、SkillBinding U/D 和其他 Binding/Assignee 写权。两个身份默认均未接当前 API/Host。 |
| 专项和相邻 | `.venv/bin/pytest -q tests/aip/test_e17_s3oj_skill_issuer_pg.py tests/aip/test_e17_s3oi_registry_issuer_pg.py tests/aip/test_aip_agent_registry_store.py tests/aip/test_aip_skill_publication_service.py --tb=short` → exit0，25 passed/1 既有 xfailed/7 warnings。原 create/replay 同一 applied Receipt、同键异内容拒绝、跨租户不可见、runtime 直插 Receipt 拒绝；缺 Skill INSERT 与额外 UPDATE 均失败关闭且无半行。曾试去掉 AgentTemplate SELECT，原 `_instance_row` JOIN 实际返回权限错误，按最小读取依赖恢复并复测通过。 |
| 静态与试验库 | `py_compile` 两目标文件、`git diff --check` → exit0。试验库 `SELECT count(*) FROM pg_roles WHERE rolname IN ('aos_aip_registry_issuer','aos_aip_skill_issuer')` → 0，退出0。测试只生成/删除隔离角色和库；不写当前卷。 |
| 当前事实 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg` → running，挂载 `aos-a0v-recovery-pg-data`；只读 SQL `alembic_version=a0v_135`。签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，安装 approved、4 published、runtimeBindings0。独立备份 SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0` 不变。健康实际路由 `/v1/health`、`/v1/ready`、`/openapi.json`、Web `/aip/skill-publish` 均200；误用 `/health` 得404，已按路由纠正。 |
| 服务加载 | 原 launchd API `bootout` exit0、`bootstrap` exit0，PID43867 的8080已监听；PG18435/Web8434持续。启动日志 `migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`；18181无监听。无 UI 改动，沿用本日浏览器禁入证据，不把页面200算业务完成。 |

复审：Skill 原 Store 的 published/latest/publication_tenant/能力覆盖、幂等键、同事务 Receipt 与 CAS 逻辑未修改。新身份不能借 Agent 命令族通过，旧 Agent 原身份不受 Skill 的表权要求影响。测试 published Skill 是显式 test-only 夹具，不是正式签名发布证据。当前库仍有 runtime 直写 Registry/Assignee 权、未建正式 Skill issuer、无外部 OIDC 与六正式 Binding/八配置/Host Owner；这些阻断当前实例的正向首链，Goal 继续 active。

下一波 E17-s3o-k：按原 D-waves 继续 SkillBinding evaluate/update 的确切权限与 CAS/新鲜度；CapabilityBinding create/evaluate/update 单独最小身份与 ACL；ToolBinding/Assignee 归属只读对账。当前库切换仍需新全备、ACL-faithful 克隆、零执行窗口和正式凭证，不能把本隔离结果直升当前实例。
