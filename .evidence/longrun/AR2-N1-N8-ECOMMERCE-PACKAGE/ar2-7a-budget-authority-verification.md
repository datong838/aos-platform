# AR2-7A 费用与调用权威验收证据

- 验收时间：2026-09-08T08:35:26+08:00
- 分支：`m1`
- 源提交：`5135abc68acc9020db60db1b53ed60fc69639652`
- 结果：`AR2_7A_RECEIPT_FIRST_BUDGET_AUTHORITY_GREEN`

## 闭合范围

1. 三桶 CNY 预算按任务、上海自然日、上海自然月稳定排序并在同一事务内锁定。
2. 调用、Provider 请求、Provider 结果、Usage 与结算形成不可变精确引用。
3. ApprovalEvent 回读 Proposal，精确绑定任务、操作、动作绑定和预算上界；价格只接受当前 CNY 快照。
4. Usage 精确绑定 invocation、Provider 与结果 hash，只接受整数 token，并以 Decimal 推导费用。
5. `HELD → SUBMITTED → SETTLED | RELEASED | UNKNOWN` 状态机 fail-closed；UNKNOWN 不超时释放、不换 Provider、不重放。
6. 提交前与提交后的 `FAILED_NO_EFFECT` 形状分离；所有终态重放逐项核对原始凭据。
7. 历史迁移测试固定到各自真实目标，避免新 head 的非空降级门污染旧版本测试。

## 验证结果

- 本地整组专项与受影响累计回归：`135 passed`。
- 独立 Prime：合同与 N7 `22 passed`；PostgreSQL `6 passed`；历史迁移 `107 passed`；结论 `PASS`。
- Python 编译、`git diff --check`：通过。
- Alembic：唯一 head `ar2_003`。

## 安全边界

- 正向租户仅为 `org-org/dev-project`，`dev-org/dev-project` 只作为隔离 canary。
- 未解析 Secret，未调用真实 Provider，未写真实经营数据，未产生外部发布或费用。
- 本证据只封板 AR2-7A；宿主接线、切换、回流、物理装卸与浏览器业务闭环继续由 AR2-7B～E 验收。
