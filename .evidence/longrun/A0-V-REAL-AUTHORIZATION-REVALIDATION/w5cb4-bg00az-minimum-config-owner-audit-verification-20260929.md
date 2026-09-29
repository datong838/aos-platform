# W5CB4 BG-00az｜首链最小配置与激活 Owner 审查

方案：`w5cb4-bg00az-minimum-config-owner-audit-plan-20260929.md`。本波只读审查方案和代码，未写当前库或运行任何真实配置激活。

1. 231-9 BG-00 要求从“过期原因→正式更新→影响预览→恢复”完成产品入口；首链仍是安装、选择已授权店铺/数据、配置数字同事及策略，再自然形成业务证据。当前签名预检（BG-00ay，本日 21:24，退出 0）仍 approved 1、binding 0、八候选之前当前读回均 0；不能视为可配置。
2. `runtime_configuration_candidates.py` 只统计八类当前 head/revision；`configuration_source_catalog.py` 在有精确 binding 后仅提供 frozen 职责计划与 active、kill switch 关闭的运行策略。`ConfigurationStagePanel.tsx` 在没有 binding 时不呈现登记表单。六类依赖不能手工塞假 ref，Stage 不能代替正式激活 Owner。
3. `aip_budgets.py:153-167` 对 active 预算直接返回 422；`aip_budget_activation_store.py:218-221` 外部用量证明缺/未接线时拒绝消费。当前没有合法预算 active 正向来源。
4. `aip_runtime_guard_policies.py:149-162` 对网络策略直接调用 `AipNetworkPolicyStore.publish`；`aip_network_policy_contracts.py` 只要求 `approval_ref` 为非空字符串；`aip_network_policy_store.py:75-130` 在当前出站策略通过后即可写 revision/Receipt，没有精确 maker/checker 审批消费。既有测试 `test_aip_network_policy_store.py` 用 `approval:test` active 正向。这是独立的正式 active 审批缺口，测试证明功能路径，不构成正式批准。

结论：首链必要配置与 Host/Owner 仍缺，当前实例禁入正确。网络 active 审批门值得独立 BG-00ba RED/最小失败封闭；先复核上位授权合同与已有 active 历史兼容，再仅阻断新 active 发布，保留草稿/历史读取。需要正式审批权威才可恢复正向。此项不补当前配置数、不启 Host、不改变当前库。浏览器 pilot 未提供可调用工具，本波没有截图验收。
