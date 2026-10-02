# E17-s3o-b｜Provider Binding 当前撤销门 verification

基线 `m1@0a76e7e2` / `AOS-001186`；仅 `org-org/dev-project` 的 disposable PG，当前真实库只读。上位方案与文件级计划见同前缀 plan。

| 复核项 | 新鲜命令或输出 |
|---|---|
| 电脑重启影响 | `colima list`：aos-extension 与 aos-a0v-test-only Running；容器 `aos-a0v-recovery-pg` Running 且 `/var/lib/postgresql/data` 挂载 `aos-a0v-recovery-pg-data`；`psql -U "$POSTGRES_USER" -d aos_current_preview_20260927 -Atc 'select version_num from alembic_version'` → `a0v_135`，exit0。`lsof`：18435/8080/8434 LISTEN、18181 无监听；health/ready/Web 三项 200。原完整备份 SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`。此前本日完整重启验收见续接564；本次检查无新一轮全栈重启。 |
| RED | `.venv/bin/python -m pytest -q tests/test_ecommerce_analyst_stage_review_authority.py -k revoked_provider_binding --tb=short` → exit1；Provider Binding 合法改为 `suspended` 后旧 Plan 仍 `ready`。第一次试验误用了表约束不接受的 `disabled`，修正测试设置后才得到有效 RED。 |
| GREEN | 同一 Provider 专项 `-k provider` → exit0，7 passed/10 deselected；状态、健康、版本、就绪有效期与网络策略漂移均使 GET/freeze 失败封闭，冻结 Receipt 仍 0。两连接 250ms 锁超时测试证实写准入到提交间不能并发撤销；提交后可撤销并使只读 GET BLOCKED。 |
| 相邻回归 | `pytest -q tests/test_ecommerce_analyst_stage_review_authority.py tests/aip/test_w6_01_exact_assignee_resolution.py tests/aip/test_w_l20_assignee_resolution.py tests/test_w2b_production_contract_store.py tests/extension_runtime/test_ecommerce_content_repair_action_binding.py --tb=short` → exit0，54 passed/7 warnings。`py_compile` 与目标 `git diff --check` → exit0。 |

复审：原 `_require_exact_assignee_resolution` 在 Receipt 校验后调用已有 Resolver 候选判定，使用原租户、精确 Binding ID/version 和 Receipt 的 exact Capability refs；再比较当前 Binding snapshot refs，避免跨租户或同名租户全局绑定代替。GET 保持读路径，Plan create/revise/freeze 写准入先给本 Binding 行 `FOR SHARE`，不改 Resolver Receipt 或数据库迁移。此波只覆盖 Provider；AgentInstance、ToolBinding、正式六绑定/八配置、发行身份/ACL、Host 与自然首链仍待独立证据。旧 RETURN 正向冲突仍待对账，不宣称全量回归 GREEN。
