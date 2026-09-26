# W5CB4 P2g26 · RETURN 生成命令权威门验证（2026-09-27）

## 基线与范围

- 方案先行：`m1@c372e6c7`，复习 231-5 §4/5、231-3 和 P2g24/25 的正式 ReturnDecision/queued attempt 证据。
- 修改仅限 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 与 `tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py`。原十字段首次生成命令和 requestHash 不变；不改 DB、worker flag、当前安装或商城来源。
- RED：两项新测试先分别因缺 `returnRef` 和缺 `_return_authority` 失败；修复后专项与累计均通过。

## 核验结果

- 返工命令只认额外唯一 `returnDecisionRef`，精确 `ReturnDecision` revision=1/hash；Host 在同租户事务内核最新正式决定、原 Task/Run、returned Issue 与原 Artifact、queued 最新 StepRun/input refs、attempt 幂等键，并核所选批准事件创建时间晚于退回决定。省略决定、错 hash/Task/step、旧批准均拒绝。
- 安全收口：即使上述必要条件成立，当前 Host `revalidate` 仍明确拒绝返工执行，`execute` 也单独拒绝。原因是新版本返工准备、批准绑定、全新容量/预算和第二次 settled-result StepRun Owner 尚未组成；本波不能给 Provider 执行许可。原始首次生成入口仍可走原完整校验。
- `uv run pytest -q` 对生成交接、RETURN target、预算命令、同库 review、下游启动、评审权威及 Provider 启动七组累计回归：**90 passed**。新专项+RETURN target：**41 passed**。`compileall`、`git diff --check` 通过；Alembic 唯一 head `a0v_106`。初次辅助测试命令引用不存在的测试文件，未执行；改用仓库真实文件后 29 passed。所有测试只用受控测试库/fixture，未触真实商城或当前恢复库写入。
- 8080/18181 无 LISTEN；当前恢复库仍保留 P2g23 的 `STOP_MIGRATION / STOP_CURRENT_API_AND_WORKERS`。纯后端且当前 API 不可安全开启，本波浏览器验收不适用，不能称自然返工或业务闭环。

## 方案/代码一致性与剩余风险

- 符合计划的“必要不充分”门：不复用旧批准、不重投旧预算、不手动 run_definition、不触 Provider。未知结果保持冻结；两份用户自有 `w5c8i-test-only-*` 未动。
- 本波没有返工 command producer、新版 Brief/产物准备、精确批准提案、预算/容量 reservation 或 attempt=2 结果 Owner。同库真实正向仍缺，不能由新单元测试推定。后续波按 231-5 先实现版本化返工准备与新批准/预算闭环，验证同库之后才能有界解除 `revalidate/execute` 双重禁入；当前实例继续 off。
