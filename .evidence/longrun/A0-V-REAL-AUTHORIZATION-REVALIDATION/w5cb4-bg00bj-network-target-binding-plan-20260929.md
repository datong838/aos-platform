# W5CB4 BG-00bj｜NetworkPolicy 激活精确目标纯合同方案

复习规则：AGENTS.md、aos-engineering-delivery、231/231-5/231-9、BG-00bi 审批消费审查。NetworkPolicy 是五类中新 active 坚持 422 的一类；本波只做可复核的目标摘要，不接审批或 Store，保持当前库只读。

文件级改动：新增 `services/aos-api/aos_api/aip_network_policy_activation_target.py`，只接收确切 `TenantScope` 与 `NetworkPolicyRevisionCreate`、expected head revision/version，要求生命周期 active 和下一个 revision，按现有 Network Store canonical hash 计算完整目标内容 hash，并计算带 tenant、固定 `aip_activate_network_policy` ActionType、policy id、revision、head、内容 hash 的绑定 hash；返回不可变结果。新增 `services/aos-api/tests/aip/test_aip_network_policy_activation_target.py`，先 RED 再 GREEN 覆盖确定性、跨租户、错 revision/head、draft、内容漂移与相似 ActionType 无法注入。测试只构造纯合同，不当业务批准。

不修改 Network Store、HTTP、ActionType 注册、审批生产/消费、数据库或当前实例；此 hash 不能单独开启 active。专项及相邻回归、编译/diff 复审、verification、精确 m1 提交。下一波 BG-00bk 再将精确目标与正式 Approval Producer/产品预览设计相接，实际消费需同事务和迁移安全门。
