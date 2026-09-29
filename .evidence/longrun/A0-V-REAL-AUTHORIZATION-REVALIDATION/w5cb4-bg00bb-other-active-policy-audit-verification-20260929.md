# W5CB4 BG-00bb｜其他 active 策略审批路径审查

方案：`w5cb4-bg00bb-other-active-policy-audit-plan-20260929.md`。本波只读审查代码及 test-only fixture 依赖，没有修改代码或当前数据库。

1. `aip_runtime_guard_policy_contracts.py`、`aip_model_governance_policy_contracts.py` 的 `approval_ref` 均为非空字符串门；本身不提供当前 maker/checker、撤销、期限或一次性消费。
2. `aip_runtime_guard_policy_store.py::_publish` 对 Egress/data classification 新 active 在幂等检查后直接 CAS 写 revision/Receipt；无正式审批 reader。当前 Egress 是网络策略和 Provider 出站的上游，优先安全门。
3. `aip_model_governance_policy_store.py::_publish` 对 quota active 也仅凭字符串；budget policy 额外要求 active BudgetRevision，但当前 BudgetRevision active API 已禁、激活外部用量权威未接线，不能称已有正式正向。
4. 测试目录中 `publish_egress` 出现在 4 个文件，data 2、quota 3、budget policy 2。若四类一次性改动将广泛改变隔离测试依赖；按最小波次先在 BG-00bc 处理 Egress 新 active，保持历史读取/幂等/草稿和下游测试的既存行语义，再逐一处理 data/quota。当前 signed install approved1/binding0、八候选0，Host/worker/Provider仍禁入。

下一波 BG-00bc：文件级方案 → test-only RED `approval:test` 新 Egress active 误受理 → Store 最小失败封闭 → 现有历史读取/依赖测试隔离 fixture 调整 → 专项/相邻回归及审查。无正式批准消费前不开放正向。浏览器 pilot 不可调用，本波无截图验收。
