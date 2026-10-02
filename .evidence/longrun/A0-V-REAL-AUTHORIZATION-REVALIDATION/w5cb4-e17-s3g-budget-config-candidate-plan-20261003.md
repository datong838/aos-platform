# E17-s3g 原签名预算到候选读者隔离联测方案

## 上位方案与边界

- 231 首链及栖月汇真实动作要求预算、额度、有效期、审批人和停止条件精确冻结；E17-f 不允许历史脚本/纸面批准发 active。BG00ga 已有私有低权预算消费者，但私有消费成功不等于当前实例合法配置。
- 原 `AipBudgetAuthorityStore.publish`、`AipModelGovernancePolicyStore._publish` 拒绝一般 active；已存在独立签名 BudgetCostIssuer→低权 Budget consume→`aip_configure_budget_cost_a0v_128` 派生 BudgetPolicy/Price 的隔离正反链。`runtime_configuration_candidates.read_candidates` 只计当前租户 head/active/窗口，不证明安装绑定或执行就绪。
- 本波只在现有全迁移一次性测试库证明原预算和派生策略对候选读者的正向贡献及错租户/其他六类不变；不碰当前库、无真实费用/Provider/Run/Host。Quota 正式来源独立，不能用旧 fixture 假批准补齐。

## 文件级最小计划

1. `services/aos-api/tests/aip/test_budget_cost_configuration_pg.py` 新增一个原签名 maker/checker/消费/派生→候选读者测试，先 RED 证缺桥接断言；断言 Budget、BudgetPolicy 各+1，其他六项不变、dev-org 零副作用，且 `activationEligible=false`。
2. 仅测试所需修改，不改产品 Store、SQL、安全策略；若现有链无法达成，记录准确阻断并转下个独立安全项，禁止造假 fixture。
3. 专项与相邻回归，py_compile、diff check；方案/代码复审、verification、m1 精确提交，AOS/Prime/D-wave更新并接续 Quota 合法生产者。
