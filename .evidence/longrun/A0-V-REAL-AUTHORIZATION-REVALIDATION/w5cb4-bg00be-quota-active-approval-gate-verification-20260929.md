# W5CB4 BG-00be｜Quota 新 active 审批禁入验证

方案：`w5cb4-bg00be-quota-active-approval-gate-plan-20260929.md`。隔离临时 PG RED：仅 `approval:test` 的新 Quota active 原会被接受，退出 1，`Failed: DID NOT RAISE QuotaPolicyApprovalRequired`。

最小修复：`AipModelGovernancePolicyStore._publish` 同请求 Receipt 幂等回读后，对新的 quota active 在 Revision/Receipt 写入前抛 `AIP_QUOTA_ACTIVE_APPROVAL_REQUIRED`；HTTP 映射 422 中文提示。拒绝后同 ID 不存在。草稿 CAS/多修订/幂等、已有 active 读取、Budget Policy 旧路径与模型下游用隔离临时 PG 复核；夹具既存行不是正式审批。

| 命令 | 结果 |
| --- | --- |
| `python -m pytest test_aip_model_governance_policy_store.py test_aip_model_governance_policy_api.py test_aip7_model_runtime_store.py -q --tb=short --disable-warnings` | 退出 0，11 passed。 |
| 两生产文件与 test-only fixture `compileall -q`、精确改动文件 `git diff --check` | 退出 0。 |

当前权威库只读，无迁移/Host/worker/Provider。正式 Quota 审批消费、BudgetPolicy 同类新 active 字符串路径、DB直写门、八候选/Owner/自然首链待证；browser-pilot 无可调用工具，本波无截图验收。下一波 BG-00bf 审 BudgetPolicy 新 active 审批与 active BudgetRevision 依赖的精确边界，先方案/RED/最小失败封闭；随后转正式审批来源接线。
