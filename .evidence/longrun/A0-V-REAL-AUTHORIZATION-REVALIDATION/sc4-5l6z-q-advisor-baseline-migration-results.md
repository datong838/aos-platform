# SC4-5L6Z-Q｜经营参谋基线授权表迁移结果

日期：2026-09-17。执行分支：`m1`。迁移：`a0v_077 -> a0v_078`。

## 结果

- 迁移前单一 head 为 `a0v_077`；迁移后单一 head 为 `a0v_078`。
- 新增 `ecommerce_schedule_policy_control_receipt` 及其不可变触发器、租户 RLS 和受控写函数。
- 迁移前后八张既有权威表行数完全一致：Case revision 14、Run 1、SchedulePolicy revision 12、Schedule command receipt 12、occurrence 390、GrowthPlan revision 0、ActionProposal 73、ActionApprovalEvent 84。
- 新表初始回执数为 0，`dev-org/dev-project` canary 回执数为 0。
- 审计结论：`A0V_078_SCHEDULE_CONTROL_MIGRATION_GREEN`，外部副作用为 0。

## 证据

- 私有 prepare/apply/audit JSON 位于 `.aos-recovery-20260917/state/q-advisor-baseline/migration/`，权限为 `0600`。
- 迁移文件 SHA-256：`sha256:88d16b489cec9bb9dc7aa516d14c874a61bbb2e6745113868baf088dcc1d8918`。
- 迁移不授予任何业务执行权限；每个真实 SchedulePolicy 写入仍必须生成绑定当前安装 generation/epoch 与 exact ActionApprovalEvent 的独立控制回执。
