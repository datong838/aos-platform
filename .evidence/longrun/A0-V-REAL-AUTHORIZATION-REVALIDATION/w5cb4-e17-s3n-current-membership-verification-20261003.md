# E17-s3n 成员撤销后的 AssigneeResolution 当前性验证

基线 `aos-platform/m1@14d0fc12`、Authority `AOS-001184`；只在 `disposable_database()` 的 org-org/dev-project 隔离克隆执行 DML。当前真库 `aos_current_preview_20260927@a0v_135` 未改，Host/worker/Provider 关闭。

## RED 与最小修复

原 `AipAssigneeResolutionStore.resolve` 对 human 先查 `meta_membership`，然后发行可在数分钟内有效的 immutable Receipt。Plan 消费只核 Receipt 的 subject、状态、期限与 assignee 等，不再读成员资格。新测试先用原 Store 创建有效 Receipt 和 READY draft，再删除该成员，旧码 `get_responsibility_plan` 仍为 READY（RED，pytest exit1）；说明 Receipt 未到期不等于当前成员资格。

在原 `AipProductionContractStore._require_exact_assignee_resolution` 中只对 `human_principal` 同事务、同租户重读 `meta_membership`，缺失报 `ASSIGNEE_RESOLUTION_MEMBERSHIP_REVOKED`；draft 读模型转 BLOCKED、freeze 前置门拒绝，plan head不进位、freeze Receipt0。原 Analyst Stage Review 的既有测试原先在更后层报 `tenant member`；现在共用 Plan 门更早以“plan stale”拒绝，测试加 Plan blocker 明确断言后修正期望。原 Stage 执行门仍独立持成员行锁。

没有在此共用查询加 `FOR SHARE`，因为它也用于只读 Plan GET；并发撤销与 Plan freeze 之间的竞争仍需读写路径分层的独立设计。执行门仍复核成员。本波没有改变三种机器 assignee、Resolver、schema 或 Receipt 历史。

## 本次命令和结果

| 命令（在 `services/aos-api`） | 结果 |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/test_ecommerce_analyst_stage_review_authority.py -k revoked_human_membership --tb=short`，修复前 | exit1；`ready != blocked`，RED 成立 |
| `.venv/bin/python -m pytest -q tests/test_ecommerce_analyst_stage_review_authority.py --tb=short`，修复后首次 | exit1；新负例通过，原 Stage 测试只因拒绝文案提前而失败；按方案核 blocker 后修正断言 |
| `.venv/bin/python -m pytest -q tests/test_ecommerce_analyst_stage_review_authority.py tests/aip/test_w6_01_exact_assignee_resolution.py tests/aip/test_w_l20_assignee_resolution.py tests/test_w2b_production_contract_store.py tests/extension_runtime/test_ecommerce_content_repair_action_binding.py --tb=short` | exit0；47 passed、7 warnings |
| `.venv/bin/python -m pytest -q tests/extension_runtime/test_ecommerce_content_review_pending_pg.py tests/extension_runtime/test_ecommerce_content_review_authority_feedback.py -k 'not test_original_settled_artifact_runs_current_content_subject_eval' --tb=short` | exit0；21 passed、2 deselected；旧 RETURN 正向与正式返工来源禁入的冲突承接 s3m 待办 |
| `py_compile` 本波两 Python 文件；`git diff --check` | 均 exit0 |

## 剩余

这证明隔离代码路径上的成员撤销禁入，不证明当前实例六正式 Binding/frozen Plan、八有效配置、Host assignment/Owner 或自然经营首链。人类角色/ABAC、值班/容量、机器 Binding 当前撤销、独立 Receipt issuer/DB ACL 和上述并发窗口仍需独立核验；不得以本波 GREEN 启用 Host。
