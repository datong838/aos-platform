# W5CB4 E17-s3o-t｜职责计划原冻结到八配置候选验证

日期：2026-10-03，北京时间。代码基线 `m1@51d31e3c`、Authority `AOS-001205`。上位方案和文件级范围见同前缀 plan。测试仅用既有可销毁隔离 PG 克隆；当前权威卷没有写入，Host/worker/Provider 没有启动。

| 步骤 | 精确命令/位置 | 结果 |
| --- | --- | --- |
| 原链基线 | `services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py -k 'original_settled_artifact_runs_current_content_subject_eval and ACCEPT' --tb=short` | exit 0，1 passed/9 deselected |
| 新断言聚焦 | 同上 | exit 0，1 passed/9 deselected；原 `create_responsibility_plan`、`freeze_responsibility_plan` 后冻结 Receipt 唯一，职责候选 +1，其余七类、异租户不变 |
| 相邻回归 | `services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py services/aos-api/tests/extension_runtime/test_runtime_configuration_candidates.py -k 'not RETURN' --tb=short` | exit 0，13 passed/1 deselected；RETURN 是已登记的 `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED`，本波没有修改或称其 GREEN |
| 静态/差异 | `services/aos-api/.venv/bin/python -m py_compile services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`、`git diff --check` | 均 exit 0 |

## 方案/代码复审

- 仅在现有原服务创建草稿后读基线、冻结后读结果和原 `responsibility_plan.freeze` Receipt；没有直接 INSERT 职责计划/Receipt，也没有修改生产查询、API、数据库迁移或配置提交逻辑。
- `read_candidates` 只给同租户当前候选计数；即使八类都非零也不证明同一安装相容或 Host 可执行。此隔离正例含测试模板 resolver，不是当前正式签名 bundle 或当前库候选。
- RETURN 测试原正向仍失败关闭；原生成命令合成 Agent/Capability 来源没有被本波提升为正式授权。当前实例正式 OIDC/三身份、Tool issuer/ACL、六 Binding、八配置、Owner、Host 与自然首链仍未闭合。

下一波：先查原 ConfigurationStage 将冻结角色与当前 active 运行策略绑定到**同一签名安装**的精确读者/提交路径，找可独立完成的 RED 与最小修复；当前实例缺身份时只禁入实例。RETURN 正向需先补原 Agent/Capability/责任来源，不能放开桩。
