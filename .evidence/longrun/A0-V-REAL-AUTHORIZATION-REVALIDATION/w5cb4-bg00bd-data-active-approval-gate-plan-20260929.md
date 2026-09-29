# W5CB4 BG-00bd｜数据分类策略新 active 审批禁入

沿 231/231-9 的正式批准要求及 BG-00bc 最小 Store 门，现有 `GuardPolicyCreate.approval_ref` 仅非空，`AipRuntimeGuardPolicyStore._publish` 对 data_classification 新 active 尚可直接写 revision/Receipt。当前无精确 maker/checker reader。本波只封该新发布路径，保留 Data 旧记录读取、草稿和幂等 Receipt 回读；不触碰 Egress、Network、Quota/Budget 的既有改动，不写当前库、不启 Host/worker/Provider。

文件级：在 `tests/aip/test_aip_runtime_guard_policy_store.py` 先加隔离 PG RED，断言 `approval:test` 新 active 被拒且无行；在 `aip_runtime_guard_policy_store.py` 同请求 replay 后阻断；`routers/aip_runtime_guard_policies.py` 映射 422；用已建立的 `_runtime_guard_history_fixture.py` 调整旧 active Data 消费测试，覆盖模型依赖；专项/相邻回归、编译/diff、方案自洽复核，再 verification、精确 m1 提交与 AOS 上下文更新。
