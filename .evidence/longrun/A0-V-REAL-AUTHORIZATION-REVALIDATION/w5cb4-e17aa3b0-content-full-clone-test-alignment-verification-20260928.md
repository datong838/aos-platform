# W5CB4 E17-aa3b0｜完整克隆测试基线对齐与 RETURN 正式缺口定位

## 事实与变更

- 原 `test_ecommerce_content_review_pending_pg.py` 已有独立未提交 +45 行，意图在人工 RETURN 后通过 ActionProposal/Approval 发起返工；本波保留这段 RED，不将其误当正式能力。
- 先把可销毁完整克隆的旧固定版本 `a0v_106` 对齐当前 `a0v_111`。单项测试随即从旧版本断言失败推进到 `BUDGET_ACTIVATION_CONSUMPTION_REQUIRED`（退出 1），证明当前 DB 禁入真实生效。
- 仅在名称精确匹配 `a0v_growth_graph_test_*`、版本为 `a0v_111` 且存在门禁 trigger 的测试克隆中，使用 owner 事务临时暂停 trigger 种历史 active 预算，再恢复 trigger 并提交；异常使事务回滚。测试之外的运行角色、迁移与真实库没有旁路。原预算 held 测试 `1 passed`。

## 回归与真实剩余缺口

- 本文件全量 `AOS_DOTENV_DISABLED=1 ... pytest -q .../test_ecommerce_content_review_pending_pg.py --tb=short`：退出 1，`7 passed, 1 failed`。唯一失败在新增 RETURN 正向测试的 `AipActionStore.create_proposal`，错误 `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED`；`ecommerce_content_repair_action_binding.py` 明文 fail-closed，尚无可复核的当前 ReturnDecision/排队尝试/冻结 Brief/安装/预算同事务 producer。这是已知正式能力缺口，不改成假成功。
- `compileall -q` 与 `git diff --check` 退出 0。此前预算 DB 门的运行角色 active 直写负例仍保持；当前真实库在本波仅只读，无 active 预算或运行绑定写入。
- 精确提交只纳入版本断言与测试克隆预算种子两个本波 hunk；原 +45 行 Action RED 继续留在工作树，待正式当前 Agent/Skill/Capability 健康绑定与 RETURN producer 实现后再闭合。不得把 7/8 宣称为累计 GREEN，也不把受控测试 Provider 当真实首链。

## 下一波

先盘点当前正式 AgentInstance/SkillBinding/CapabilityBinding/ResponsibilityPlan 和八类配置，确定 RETURN producer 可用的 exact 上游；缺身份时完成独立的验证合同与负例，但不可开放 Action 正向。预算批准单次消费 E17-aa3b 与正式费用上界/外部账单继续并行串行推进；Host/worker 保持禁入。
