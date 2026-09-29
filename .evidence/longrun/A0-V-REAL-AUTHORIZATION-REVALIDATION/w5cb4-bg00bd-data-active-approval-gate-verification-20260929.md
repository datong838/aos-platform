# W5CB4 BG-00bd｜数据分类策略新 active 审批禁入验证

方案：`w5cb4-bg00bd-data-active-approval-gate-plan-20260929.md`。隔离临时 PG RED：仅 `approval:test` 的新 DataClassification active 原会被接受，退出 1，`Failed: DID NOT RAISE DataPolicyApprovalRequired`。

最小修复：`AipRuntimeGuardPolicyStore._publish` 对 data_classification 在同请求 Receipt 幂等回读后、新 revision/Receipt 写入前抛 `AIP_DATA_ACTIVE_APPROVAL_REQUIRED`；Router 以 422 中文解释。拒绝后同 ID 回读不存在。Egress 已有门、非 active 草稿及历史精确读取不变；既有 Data active 消费在隔离 PG 以既存行测试，不是假批准正向。

| 命令 | 结果 |
| --- | --- |
| `python -m pytest test_aip_runtime_guard_policy_store.py test_aip_runtime_guard_policy_api.py test_aip_network_policy_store.py test_aip7_model_runtime_store.py -q --tb=short --disable-warnings` | 退出 0，17 passed。 |
| 两个生产文件 `compileall -q`、五个改动文件 `git diff --check` | 退出 0。 |

当前库只读，未迁移/启 Host、worker、Provider。正式 Data maker/checker 审批权威、Quota/Budget Policy 同类路径、DB直写门、当前八候选和自然首链仍待证；browser-pilot 无可调用工具，本波无截图验收。下一波 BG-00be 审 Quota 新 active 路径及相邻依赖，先方案/RED/最小失败封闭；Budget Policy 和正式审批来源继续后置。
