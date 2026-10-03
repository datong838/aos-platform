# E17-s3o-w-ai：预算 exact 就绪门验证

## 现时只读来源

- `docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -U aos_app -d aos_current_preview_20260927 -Atqc "BEGIN READ ONLY; ...; COMMIT;"` 退出 0，返回 `aos_current_preview_20260927|a0v_135|on`，`org-org/dev-project` 的 `meta_membership` 为 `owner|1`。成员 Owner 存在不等于正式 Provider/预算签发者、OIDC 或 Host Owner 已就绪。
- 本波前的同范围只读统计：`aip_provider_instance_revision`、`aip_model_route_revision`、`aip_runtime_policy_revision`、`aip_release_gate_decision`、`aip_eval_contract_revision`、`aip_evidence_bundle_revision`、`aip_tool_binding`、`aip_budget_revision`、`aip_capability_binding` 均为 0；首个 `strategy.plan` 空依赖预检七个缺失原因，未创建任何绑定或新来源。

## RED 与修复

先写 `test_matching_runtime_policy_cannot_make_missing_budget_policy_available`。原 `AipBindingReadinessService` 返回 `AVAILABLE`、`reasons=[]`，目标测试 1 failed、退出码 1。根因是它只比较 RuntimePolicy 携带的 budget ref，没有读同租户预算权威。

最小修复在原只读依赖 Authority 中查 `aip_model_governance_policy_head` 联接当前 revision：必须同租户、kind=`budget`、同 revision/hash、lifecycle=`active`、评估时处于有效窗口。仍复用 `BUDGET_POLICY_MISSING` 原原因码；未改表、迁移、DTO、写路、Host/worker/Provider。

| 验证 | 新鲜结果 |
| --- | --- |
| 原 Binding readiness 与受限 PG Reader 专项 | 19 passed，退出 0；含缺行的真实隔离 PG 只读身份、合法与五类失效单元负例。 |
| Binding API 与 Skill readiness 相邻回归 | 9 passed，退出 0。 |
| `py_compile`、`git diff --check` | 均退出 0。 |
| `ruff` | 环境没有 `.venv/bin/ruff`，退出 127，未计验证通过。 |

## 复审与限制

对照 `231-9` 与 BIND-1 §5 第 6 项：本波只使 Budget exact 证据缺失/失效时失败关闭。隔离测试的合法预算行是单元替身，未证明当前正式预算生产、正式 Owner/签发身份、Provider/Route/Eval/License、六绑定或自然首链正向。当前库只读且 `a0v_135`，此波无迁移，不需重启 PG；API 新代码需在下一次最新栈质量门加载后才能称 live。Goal 保持 active。
