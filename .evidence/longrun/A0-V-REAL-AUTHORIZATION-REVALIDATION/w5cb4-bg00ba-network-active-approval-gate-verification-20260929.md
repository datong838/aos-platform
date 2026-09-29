# W5CB4 BG-00ba｜网络 active 发布审批禁入验证

方案：`w5cb4-bg00ba-network-active-approval-gate-plan-20260929.md`。本波只改网络策略发布 Store、HTTP 错误映射及 test-only PG 测试；未写当前权威库，未改 schema，未启 Host/worker/Provider。

## RED → GREEN

- RED：新增 `test_new_active_network_policy_rejects_string_only_approval` 后，隔离临时 PG 明确 `Failed: DID NOT RAISE NetworkPolicyApprovalRequired`，原路径接受 `approval:test` 新 active。
- GREEN：Store 对同请求已持久化 Receipt 先按原幂等语义回读；**新** active 在写 revision/Receipt 前抛 `AIP_NETWORK_ACTIVE_APPROVAL_REQUIRED`。HTTP 映射 422 中文解释。拒绝用例再回读同 policy ID 为不存在。
- 草稿 CAS/幂等及跨租户读取仍按原测试；历史 active 只读和漂移/有效期门在 test-only PG 以隔离的既存记录核验，不借假 approval 走新 active 发布。模型运行相邻依赖测试同样改用隔离既存记录，不宣称它是正式权威。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_aip_network_policy_store.py services/aos-api/tests/aip/test_aip_runtime_guard_policy_api.py services/aos-api/tests/aip/test_aip_network_policy_contracts.py services/aos-api/tests/aip/test_aip7_model_runtime_store.py -q --tb=short` | 退出码 0，22 passed。 |
| 新 active 拒绝与无残行专项复验 | 退出码 0，1 passed。 |
| `python -m compileall -q` 两个生产文件；`git diff --check` 精确五文件 | 均退出码 0。 |

## 方案一致性与风险

阻断位置在 Store 而非仅前端/Router，因此当前所有 Store 新 active 调用都失败封闭；草稿和历史读取保持。唯一合法正向须以后续正式 maker/checker 审批权威在同事务精确消费后再设计，不能用环境开关或字符串绕行。当前出站策略本身仍有 `approvalRef` 字符串边界，且直接数据库写入防线未纳入本波；这些分别作为后置安全工作登记，不能据此启动 Host。当前安装 approved、binding0、八候选0、正式首链 pending；本波测试不等于业务完成。浏览器 pilot 无可调用工具，本波无截图验收。

下一波 BG-00bb：先审 Egress/data/quota/budget 策略中同类 active 字符串审批路径，选最小共性安全缺口；保持已有历史读取和当前库只读，按方案/RED/最小修复，不作架构重写。
