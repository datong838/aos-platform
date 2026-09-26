# W5CB4 P2g28 · RETURN 批准 exact 绑定门验证（2026-09-27）

## 方案与实现

- 方案先行 `m1@9b7d2a00`；复习 231-5 §5/6、公共 `AipActionStore` 和 `AipBudgetReservationStore._approval_authority`。后者对内容生成只核 Task、operation、金额与通用 proposal hash，并不核 RETURN 新版输入或安装代次；“批准晚于退回”只是必要非充分条件。
- 新增 `ecommerce_content_repair_approval_authority.py`，在同租户只读快照中核正式 Action approval event／proposal／draft：事件 exact hash、maker/checker、approved 状态、未过期、proposal/draft hash 与 binding、Task/Run/operation，以及 payload 必须精确等于 ReturnDecision、新版 Brief、原 Artifact、当前安装/代次/dispatch、Capability 与上限金额。Host RETURN 门在 P2g27 新版 Brief 证明后调用该门。原首次生成路径及公共 Action/预算模型未改。
- RED：新增测试先因模块缺失不能 collection；Host 调用断言先因无接线失败。最小实现后专项与累计转 GREEN。

## 新鲜验证

- 构造的正式形状单元契约对每个 payload 缺项、非 approved 状态、错 Run/安装/哈希拒绝；这是合同单测，**不是**公共 Action API 产生的真人批准证明。
- 原 `a0v_106` 一次性同库 RETURN 链虽已有新版 Brief，用旧 ActionApprovalEvent 仍被 Host 拒绝；没有为过测直接 INSERT 返工批准。正式新批准的公共 API 正向尚未组成，不能据此称返工可执行。
- 九组相邻累计 **92 passed**；`compileall`、`git diff --check` 通过，Alembic 唯一 head `a0v_106`。当前 8080/18181 没有可安全启用的 API；纯后端门浏览器验收不适用。

## 退出边界与下一波

- P2g26 的 `revalidate/execute` 双重返工禁入继续有效；本波无 Provider、无费用预留、无新 Action 决策、无当前实例变更。批准人必须经正式公共 API 看见并批准 exact 新版输入；当前单元绿色不可替代真人事件。
- 下一波优先正式 Action draft/proposal 生产者与 exact 审批 UI/权限路径的同库证明，再建全新容量/预算 reservation，继而验证版本化 prompt、结果及 attempt=2 Owner。任何未知提交只读对账，不重发。
- 当前真实恢复 PG 仍 `a0v_092`、无当前一致备份，继续 `STOP_MIGRATION / STOP_CURRENT_API_AND_WORKERS`。不读商城源、不重放旧十二 Run、不手工 `run_definition`；用户两份 `w5c8i-test-only-*` 未触碰。
