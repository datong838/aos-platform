# W5CB4 BG-00bc｜Egress 新 active 审批禁入验证

方案：`w5cb4-bg00bc-egress-active-approval-gate-plan-20260929.md`。本波只改 Egress 新发布 Store/HTTP 错误映射和隔离临时 PG 测试；当前权威库只读，未改 schema、未启 Host/worker/Provider。

| 证据 | 命令/结果 |
| --- | --- |
| RED | `test_new_active_egress_rejects_string_only_approval` 在修复前退出 1，明确 `Failed: DID NOT RAISE EgressPolicyApprovalRequired`；原路径接受 `approval:test`。 |
| GREEN | Store 同请求 Receipt 先回读；新的 Egress `active` 在任何新 revision/Receipt 写入前抛 `AIP_EGRESS_ACTIVE_APPROVAL_REQUIRED`；HTTP 422 中文提示。拒绝后按 ID 回读不存在。 |
| 专项/相邻 | `python -m pytest test_aip_runtime_guard_policy_store.py test_aip_runtime_guard_policy_api.py test_aip_network_policy_store.py test_aip7_model_runtime_store.py -q --tb=short --disable-warnings` 退出 0，15 passed。 |
| 静态 | 两个生产文件与 test-only fixture `compileall -q`、精确改动文件 `git diff --check`，均退出 0。 |

草稿 CAS/幂等、Data 策略路径不变。旧 active Egress 精确读取及 Network/Model 下游门通过隔离临时 PG 的既存行测试，未用假审批走新 active 发布；该夹具不是正式授权。当前生产没有 Egress active 正向来源，首链依然禁入。Data/Quota/Budget Policy 的同类字符串审批、正式审批消费和数据库直写门仍待处理；浏览器 pilot 无可调用工具，本波无截图验收。

下一波 BG-00bd：审 DataClassification 新 active 审批字符串路径及隔离 PG 依赖，方案/RED/最小失败封闭；保留旧读取、草稿、幂等。当前签名安装、Host/Owner 和自然首链仍分门核验。
